"""위키 건강검진 — 사람이 읽는 리포트를 만든다.

여기서는 무엇도 자동으로 고치지 않는다. '봐야 할 것'만 모아준다.
중복 후보는 기계적 유사도로 거르고, 실제 판단은 AI(또는 사람)가 한다.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from . import config, extract, scan
from . import topics as topics_mod
from .build import load_taxonomy
from .models import Entry


def _shingles(text: str, n: int = 5) -> set[str]:
    """한국어에 단어 분리가 잘 듣지 않아 문자 n-gram 으로 비교한다."""
    normalized = re.sub(r"\s+", "", text)[:20000]
    if len(normalized) < n:
        return set()
    return {normalized[i : i + n] for i in range(0, len(normalized) - n, 3)}


def similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b))  # 포함 관계(부분집합)도 잡아내기 위해 min 사용


def find_duplicate_candidates(entries: list[Entry], threshold: float = 0.28) -> list[dict[str, Any]]:
    cache: dict[str, set[str]] = {}
    for e in entries:
        data = extract.load_extracted(e.slug)
        cache[e.slug] = _shingles(data["text"]) if data else set()

    pairs: list[dict[str, Any]] = []
    slugs = [e.slug for e in entries]
    for i, a in enumerate(slugs):
        for b in slugs[i + 1 :]:
            score = similarity(cache[a], cache[b])
            if score >= threshold:
                pairs.append({"a": a, "b": b, "similarity": round(score, 3)})
    return sorted(pairs, key=lambda p: -p["similarity"])


def _months_since(iso: str) -> int:
    if not iso:
        return 0
    try:
        then = date.fromisoformat(iso)
    except ValueError:
        return 0
    today = date.today()
    return (today.year - then.year) * 12 + (today.month - then.month)


def run() -> dict[str, Any]:
    taxonomy = load_taxonomy()
    rules = taxonomy.get("rules", {}) or {}
    stale_months = int(rules.get("stale_after_months", 12))
    split_threshold = int(rules.get("split_threshold", 12))
    misc_threshold = int(rules.get("misc_promote_threshold", 3))
    defined = {c["id"] for c in taxonomy.get("categories", [])}

    entries = scan.load_entries()
    unclassified = [e for e in entries if e.needs_classification]
    undefined_cat = [e for e in entries if e.category and e.category not in defined]
    stale = [e for e in entries if _months_since(e.doc_date) >= stale_months and e.status == "active"]
    flagged = [e for e in entries if e.status in ("outdated", "superseded")]
    duplicates = find_duplicate_candidates(entries)

    counts: dict[str, int] = {}
    for e in entries:
        counts[e.category or "misc"] = counts.get(e.category or "misc", 0) + 1
    oversized = [c for c, n in counts.items() if n >= split_threshold]
    misc_full = counts.get("misc", 0) >= misc_threshold

    # 고아: entries 는 남아있는데 docs/ 에서 원본이 사라진 경우
    orphans = [
        p.stem for p in config.ENTRIES_DIR.glob("*.json")
        if not (config.ROOT / Entry.load(p).source).exists()
    ]

    # 토픽 층 (PRD 8절)
    by_slug = {e.slug: e for e in entries}
    all_topics = topics_mod.load_topics()
    topics_mod.sync_modes(all_topics, by_slug)
    topic_ids = {t.id for t in all_topics}
    topics_pending = [t.id for t in all_topics if topics_mod.needs_synthesis(t, by_slug)]
    topics_locked_stale = [t.id for t in all_topics if topics_mod.is_stale_locked(t, by_slug)]
    topics_oversized = [
        (t.id, len(t.sources)) for t in all_topics if len(t.sources) >= topics_mod.SPLIT_SOURCES
    ]
    topic_orphans = [
        (t.id, [s for s in t.sources if s not in by_slug])
        for t in all_topics if any(s not in by_slug for s in t.sources)
    ]
    unassigned = [e.slug for e in entries if not e.topic or e.topic not in topic_ids]
    topic_problems = {
        t.id: probs for t in all_topics
        if t.mode == "synthesized" and not topics_mod.needs_synthesis(t, by_slug)
        for probs in [topics_mod.check_topic(t, by_slug)] if probs
    }

    report = {
        "topics_total": len(all_topics),
        "topics_pending": topics_pending,
        "topics_locked_stale": topics_locked_stale,
        "topics_oversized": topics_oversized,
        "topic_orphans": topic_orphans,
        "unassigned": unassigned,
        "topic_problems": topic_problems,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(entries),
        "unclassified": [e.slug for e in unclassified],
        "undefined_category": [(e.slug, e.category) for e in undefined_cat],
        "stale": [(e.slug, e.doc_date) for e in stale],
        "flagged": [(e.slug, e.status) for e in flagged],
        "duplicate_candidates": duplicates,
        "category_counts": counts,
        "oversized_categories": oversized,
        "misc_needs_promotion": misc_full,
        "orphans": orphans,
    }
    _write_markdown(report, entries)
    return report


def _write_markdown(r: dict[str, Any], entries: list[Entry]) -> None:
    by_slug = {e.slug: e for e in entries}
    title = lambda s: by_slug[s].title if s in by_slug else s  # noqa: E731

    lines = [
        "# 위키 건강검진 리포트",
        "",
        f"생성 시각: {r['generated_at']} · 문서 {r['total']}개",
        "",
        "> 이 파일은 `uv run wiki audit` 가 자동 생성한다. 직접 고치지 말 것.",
        "> 조치는 `wiki/entries/<slug>.json` 또는 `wiki/taxonomy.yaml` 을 수정해서 한다.",
        "",
        "## 1. 분류가 필요한 문서",
        "",
    ]
    if r["unclassified"]:
        lines += [f"- [ ] `{s}` — {title(s)}" for s in r["unclassified"]]
        lines += ["", "→ `/wiki-sync` 를 실행하거나 `uv run wiki classify` 로 처리."]
    else:
        lines.append("없음. 모든 문서가 분류되어 있다.")

    def verdict(a: str, b: str) -> str:
        """이미 관계가 기록된 쌍은 다시 검토하지 않도록 표시한다."""
        ea, eb = by_slug.get(a), by_slug.get(b)
        if not ea or not eb:
            return "⬜ 미검토"
        if ea.superseded_by == b or eb.superseded_by == a:
            return "✅ 대체 관계 기록됨"
        if b in ea.related or a in eb.related:
            return "✅ 관련 문서로 연결됨"
        if any(o.get("slug") == b for o in ea.overlaps) or any(
            o.get("slug") == a for o in eb.overlaps
        ):
            return "✅ 겹침 기록됨"
        return "⬜ 미검토"

    lines += ["", "## 2. 중복 의심 쌍", ""]
    if r["duplicate_candidates"]:
        lines.append("| 유사도 | 문서 A | 문서 B | 판단 |")
        lines.append("|---|---|---|---|")
        for p in r["duplicate_candidates"]:
            lines.append(
                f"| {p['similarity']:.2f} | `{p['a']}` {title(p['a'])} "
                f"| `{p['b']}` {title(p['b'])} | {verdict(p['a'], p['b'])} |"
            )
        lines += [
            "",
            "판단 기준: 한쪽이 다른 쪽의 상위 호환이면 구버전 entry 의 `status` 를 `superseded`,",
            "`superseded_by` 를 신버전 slug 로 설정한다. 서로 보완 관계면 `related` 로 연결한다.",
        ]
    else:
        lines.append("없음.")

    lines += ["", "## 3. 오래된 문서 (점검 권장)", ""]
    lines += [f"- `{s}` — {title(s)} (최종 {d})" for s, d in r["stale"]] or ["없음."]

    lines += ["", "## 4. outdated / superseded 표시된 문서", ""]
    lines += [f"- `{s}` — {title(s)} (`{st}`)" for s, st in r["flagged"]] or ["없음."]

    lines += ["", "## 5. 카테고리 현황", ""]
    for cat, n in sorted(r["category_counts"].items(), key=lambda kv: -kv[1]):
        mark = " ⚠ 분할 검토" if cat in r["oversized_categories"] else ""
        lines.append(f"- `{cat}`: {n}개{mark}")
    if r["misc_needs_promotion"]:
        lines += ["", "⚠ `misc` 에 문서가 쌓였다. 새 카테고리 신설을 검토할 것."]
    if r["undefined_category"]:
        lines += ["", "⚠ taxonomy.yaml 에 없는 카테고리를 쓰는 문서:"]
        lines += [f"- `{s}` → `{c}`" for s, c in r["undefined_category"]]

    if r["orphans"]:
        lines += ["", "## 6. 고아 entry (원본 HTML 이 사라짐)", ""]
        lines += [f"- `{s}`" for s in r["orphans"]]
        lines += ["", "→ 의도한 삭제라면 해당 entry json 을 지운다."]

    lines += ["", f"## 7. 토픽 층 (토픽 {r['topics_total']}개)", ""]
    if r["topics_pending"]:
        lines += ["### 다시 정리해야 할 토픽 (근거가 바뀌었거나 본문이 아직 없음)", ""]
        lines += [f"- [ ] `{t}`" for t in r["topics_pending"]]
        lines += ["", "→ `/wiki-sync` 3단계 또는 `uv run wiki synthesize` 로 처리.", ""]
    if r["topics_locked_stale"]:
        lines += ["### 잠긴 토픽인데 근거가 바뀜 (AI 는 손대지 않는다)", ""]
        lines += [f"- `{t}` — 사람이 직접 고치거나 `locked` 를 풀 것" for t in r["topics_locked_stale"]]
        lines.append("")
    if r["unassigned"]:
        lines += ["### 토픽에 배정되지 않은 문서", ""]
        lines += [f"- `{s}` — {title(s)}" for s in r["unassigned"]]
        lines += ["", "→ `/wiki-sync` 2단계에서 기존 토픽에 넣거나 새 토픽을 만든다.", ""]
    if r["topics_oversized"]:
        lines += ["### 근거가 너무 많은 토픽 (분할 검토)", ""]
        lines += [f"- `{t}` — 근거 {n}개" for t, n in r["topics_oversized"]]
        lines.append("")
    if r["topic_orphans"]:
        lines += ["### 근거 문서가 사라진 토픽", ""]
        lines += [f"- `{t}` — 없는 근거: {', '.join(f'`{s}`' for s in missing)}" for t, missing in r["topic_orphans"]]
        lines.append("")
    if r["topic_problems"]:
        lines += ["### 정돈본 신뢰 검사에 걸린 토픽", ""]
        for t, probs in r["topic_problems"].items():
            lines.append(f"- `{t}`")
            lines += [f"  - {p}" for p in probs]
        lines.append("")
    if not any([r["topics_pending"], r["topics_locked_stale"], r["unassigned"],
                r["topics_oversized"], r["topic_orphans"], r["topic_problems"]]):
        lines.append("문제 없음. 모든 토픽이 최신이고 검사를 통과했다.")

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "health.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
