"""토픽 — 원본 여러 개를 근거로 AI 가 정돈해 쓴 위키 본문 (PRD 8절).

원본 층(entries/extracted) 위에 얹히는 층이다. 원본은 건드리지 않는다.

  wiki/topics/<id>.json   메타데이터 (AI + 사람)
  wiki/topics/<id>.md     정돈된 본문. mode=synthesized 일 때만 존재.

여기서는 '판단'을 하지 않는다. 판단(무엇을 어떤 토픽에 넣을지, 본문을 어떻게 쓸지)은
AI 단계(/wiki-sync 또는 API)의 몫이고, 이 모듈은 해시·모드·렌더링·검사만 맡는다.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

from . import config, extract
from .models import Entry, Topic

PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesize.md"

# 근거가 이만큼 넘으면 audit 이 분할을 제안한다
SPLIT_SOURCES = 6

# 사람이 남긴 메모 블록. 재합성 때 그대로 옮겨 붙인다.
MEMO_RE = re.compile(r"<!--\s*memo\s*-->.*?<!--\s*/memo\s*-->", re.S)

# 본문 절 끝의 출처 표기: "출처: git-guide §최초 세팅, git-methods-comparison"
# 줄 안의 공백만 허용한다(\s 금지). \s* 를 쓰면 앞뒤 빈 줄까지 삼켜서
# 치환된 HTML 블록이 다음 제목 줄에 붙어 버리고, 제목이 날것으로 렌더링된다.
CITE_LINE_RE = re.compile(r"^[ \t]*(?:_|\*)?출처:[ \t]*(.+?)(?:_|\*)?[ \t]*$", re.M)
CITE_ITEM_RE = re.compile(r"^\s*([\w가-힣\-]+)(?:\s*§\s*(.+?))?\s*$")

# 코드 검사에서 무시할 짧은 블록 (프롬프트 한 줄 등)
MIN_CODE_CHARS = 20


# ── 로드/저장 ─────────────────────────────────────────────────────────────

def topic_path(topic_id: str) -> Path:
    return config.TOPICS_DIR / f"{topic_id}.json"


def md_path(topic_id: str) -> Path:
    return config.TOPICS_DIR / f"{topic_id}.md"


def load_topics() -> list[Topic]:
    if not config.TOPICS_DIR.exists():
        return []
    return [Topic.load(p) for p in sorted(config.TOPICS_DIR.glob("*.json"))]


def load_md(topic_id: str) -> str | None:
    p = md_path(topic_id)
    return p.read_text(encoding="utf-8") if p.exists() else None


# ── 해시와 모드 ───────────────────────────────────────────────────────────

def prompt_hash() -> str:
    if not PROMPT_PATH.exists():
        return "no-prompt"
    return hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()[:16]


def valid_sources(topic: Topic, by_slug: dict[str, Entry]) -> list[Entry]:
    return [by_slug[s] for s in topic.sources if s in by_slug]


def compute_synth_hash(topic: Topic, by_slug: dict[str, Entry]) -> str:
    """근거 문서가 하나라도 바뀌거나 합성 지침이 바뀌면 값이 달라진다."""
    hashes = sorted(e.source_hash for e in valid_sources(topic, by_slug))
    raw = "|".join(hashes) + "+" + prompt_hash()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def resolve_mode(topic: Topic, by_slug: dict[str, Entry]) -> str:
    """근거 2개 이상이거나 outdated 가 섞여 있으면 AI 가 써야 한다. 아니면 원본 그대로."""
    srcs = valid_sources(topic, by_slug)
    if len(srcs) >= 2 or any(e.status == "outdated" for e in srcs):
        return "synthesized"
    return "mirror"


def needs_synthesis(topic: Topic, by_slug: dict[str, Entry]) -> bool:
    if resolve_mode(topic, by_slug) != "synthesized" or topic.locked:
        return False
    if load_md(topic.id) is None:
        return True
    return topic.synth_hash != compute_synth_hash(topic, by_slug)


def is_stale_locked(topic: Topic, by_slug: dict[str, Entry]) -> bool:
    """잠긴 토픽인데 근거가 바뀌었다 — AI 는 손대지 않고 리포트만 한다."""
    return (
        topic.locked
        and resolve_mode(topic, by_slug) == "synthesized"
        and topic.synth_hash != compute_synth_hash(topic, by_slug)
    )


def sync_modes(topics: list[Topic], by_slug: dict[str, Entry]) -> list[str]:
    """entry 상태에 맞춰 mode 를 갱신하고 저장한다. 바뀐 토픽 id 를 돌려준다."""
    changed = []
    for t in topics:
        mode = resolve_mode(t, by_slug)
        if mode != t.mode:
            t.mode = mode
            t.save(topic_path(t.id))
            changed.append(t.id)
    return changed


def mark_synthesized(topic: Topic, by_slug: dict[str, Entry], by: str = "claude-code") -> Topic:
    topic.mode = "synthesized"
    topic.synth_hash = compute_synth_hash(topic, by_slug)
    topic.synthesized_at = date.today().isoformat()
    topic.synthesized_by = by
    topic.save(topic_path(topic.id))
    return topic


def preserve_memo(old_md: str | None, new_md: str) -> str:
    """이전 본문의 <!-- memo --> 블록을 새 본문에 옮겨 붙인다 (새 본문에 없을 때만)."""
    if not old_md:
        return new_md
    old_memos = MEMO_RE.findall(old_md)
    if not old_memos or MEMO_RE.search(new_md):
        return new_md
    return new_md.rstrip() + "\n\n" + "\n\n".join(old_memos) + "\n"


def updated_on(topic: Topic, by_slug: dict[str, Entry]) -> str:
    """목록 정렬용 날짜: 합성일과 근거 문서 날짜 중 가장 늦은 것."""
    dates = [e.doc_date for e in valid_sources(topic, by_slug) if e.doc_date]
    if topic.synthesized_at:
        dates.append(topic.synthesized_at)
    return max(dates) if dates else ""


# ── 출처 표기 → 원본 페이지 링크 ─────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^\w가-힣]+", "", s).lower()


def _find_anchor(entry: Entry, section: str | None) -> str:
    if not section:
        return ""
    want = _norm(section)
    if not want:
        return ""
    for h in entry.headings:
        have = _norm(h.get("text", ""))
        if want == have or want in have or have in want:
            return h.get("id", "")
    return ""


def link_citations(md: str, by_slug: dict[str, Entry], root: str) -> str:
    """'출처: slug §절' 줄을 원본 페이지 앵커 링크(HTML 블록)로 바꾼다."""

    def repl(m: re.Match[str]) -> str:
        parts = re.split(r"\s*[,;]\s*", m.group(1).strip())
        links = []
        for part in parts:
            item = CITE_ITEM_RE.match(part)
            if not item:
                links.append(part)
                continue
            slug, section = item.group(1), item.group(2)
            entry = by_slug.get(slug)
            if entry is None:
                links.append(f"<span class=\"cite-missing\">{part}</span>")
                continue
            anchor = _find_anchor(entry, section)
            href = f"{root}d/{slug}.html" + (f"#{anchor}" if anchor else "")
            label = entry.title + (f" §{section}" if section else "")
            links.append(f"<a href=\"{href}\">{label}</a>")
        return "<p class=\"cite\">출처: " + ", ".join(links) + "</p>"

    return CITE_LINE_RE.sub(repl, md)


def cited_slugs(md: str) -> set[str]:
    found: set[str] = set()
    for m in CITE_LINE_RE.finditer(md):
        for part in re.split(r"\s*[,;]\s*", m.group(1).strip()):
            item = CITE_ITEM_RE.match(part)
            if item:
                found.add(item.group(1))
    return found


# ── 렌더링 ────────────────────────────────────────────────────────────────

_md = MarkdownIt("commonmark").enable(["table", "strikethrough"])


def render_markdown(md: str, by_slug: dict[str, Entry], root: str) -> tuple[str, list[dict[str, Any]]]:
    """Markdown → (본문 HTML, 목차). 출처 표기는 링크로, h2/h3 에는 앵커 id 를 단다."""
    text = MEMO_RE.sub("", md)
    text = link_citations(text, by_slug, root)
    html = _md.render(text)
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    # 토픽 제목은 템플릿이 그리므로 본문 첫 h1 은 뺀다
    h1 = body.find("h1")
    if h1:
        h1.decompose()
    headings = extract._build_headings(body)
    return body.decode_contents(), headings


# ── 신뢰 검사 (audit 이 부른다) ───────────────────────────────────────────

def _code_blocks(md: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", MEMO_RE.sub("", md), re.S)


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def check_topic(topic: Topic, by_slug: dict[str, Entry]) -> list[str]:
    """정돈된 본문이 근거를 배신하지 않았는지 기계적으로 확인한다.

    - 인용: 모든 근거 문서가 최소 한 번 '출처:' 로 인용됐는가
    - 코드: 본문 코드블록이 근거 어딘가에 실제로 있는가 (공백 무시)
    - 분량: 본문이 근거 합계보다 길지 않은가 (정돈은 짧아져야 한다)
    """
    problems: list[str] = []
    if topic.mode != "synthesized":
        return problems
    md = load_md(topic.id)
    if md is None:
        return ["본문(.md)이 없다"]

    srcs = valid_sources(topic, by_slug)
    cited = cited_slugs(md)
    for e in srcs:
        if e.slug not in cited:
            problems.append(f"근거 `{e.slug}` 가 본문에서 한 번도 인용되지 않았다")

    corpus = _squash("".join((extract.load_extracted(e.slug) or {}).get("text", "") for e in srcs))
    for block in _code_blocks(md):
        key = _squash(block)
        if len(key) < MIN_CODE_CHARS:
            continue
        if key in corpus:
            continue
        # 여러 줄 블록은 줄 단위로 80% 이상 근거에 있으면 통과 (원본이 주석/줄바꿈만 다른 경우)
        lines = [_squash(l) for l in block.splitlines() if _squash(l)]
        hit = sum(1 for l in lines if l in corpus)
        if lines and hit / len(lines) >= 0.8:
            continue
        head = block.strip().splitlines()[0][:50] if block.strip() else ""
        problems.append(f"출처 불명 코드블록: `{head}` — 근거에 없다면 '원문과 다른 점'에 적어야 한다")

    body_len = len(_squash(MEMO_RE.sub("", md)))
    src_len = sum((extract.load_extracted(e.slug) or {}).get("char_count", 0) for e in srcs)
    if src_len and body_len > src_len:
        problems.append(f"본문({body_len}자)이 근거 합계({src_len}자)보다 길다 — 정돈이 아니라 부풀림")

    return problems
