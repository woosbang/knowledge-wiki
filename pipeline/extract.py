"""원본 HTML → 통일 템플릿에 꽂을 수 있는 '깨끗한 의미 HTML' 로 변환.

원칙
  1. docs/ 의 원본 파일은 절대 수정하지 않는다. 읽기만 한다.
  2. 스타일·스크립트·사이드바 같은 '껍데기'는 버리고 내용만 남긴다.
  3. 확신이 없으면 버리지 말고 남긴다. 잃는 것보다 지저분한 편이 낫다.
  4. SVG 다이어그램은 통째로 보존한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from . import config

# 이 태그 안에서는 남은 태그를 무조건 unwrap 한다 (새 블록을 만들면 안 되는 자리)
INLINE_CONTEXT = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "a", "strong", "b", "em", "i",
    "code", "pre", "li", "td", "th", "dt", "dd", "caption", "summary",
    "figcaption", "small", "mark", "sup", "sub", "kbd", "samp", "u",
}

# 블록으로 취급하는 태그 — 이것들을 품고 있으면 레이아웃 컨테이너로 보고 껍데기를 벗긴다
BLOCK_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "dl",
    "table", "pre", "blockquote", "figure", "details", "hr", "svg",
}

# 블록 사이에 맨몸으로 떠 있으면 <p> 로 묶어줘야 하는 인라인 요소
INLINE_ELEMENTS = {
    "a", "strong", "b", "em", "i", "code", "kbd", "samp",
    "small", "mark", "sup", "sub", "u", "br", "img", "span",
}

# 인라인 런을 묶어줄 대상 컨테이너
WRAP_CONTAINERS = ("blockquote", "details", "figure", "li", "td", "th")

_SYMBOL_ONLY = re.compile(r"^[^\w가-힣]{1,3}$")

# 원본에서 콜아웃/노트 박스로 쓰이던 컨테이너 — blockquote 로 살려낸다
_CALLOUT_CLASS = re.compile(
    r"callout|warn|caution|alert|note|tip|info|hint|danger|highlight",
    re.IGNORECASE,
)

# 라벨(kicker)로 승격할 조건: 짧고, 문장으로 끝나지 않는 것
_SENTENCE_END = re.compile(r"[.!?。]$|다$|요$|까$")


def _is_label(text: str) -> bool:
    return len(text) <= 30 and not _SENTENCE_END.search(text)


def _class_of(tag) -> str:
    value = tag.attrs.get("class") or []
    return " ".join(value) if isinstance(value, list) else str(value)

# lxml 의 HTML 파서는 태그/속성 이름을 소문자로 만든다.
# SVG 는 대소문자를 구분하므로(viewBox 등) 직렬화 후 원래 표기로 되돌린다.
# 이걸 안 하면 다이어그램의 크기·비율이 통째로 깨진다.
_SVG_CASE = {
    "viewbox": "viewBox",
    "preserveaspectratio": "preserveAspectRatio",
    "gradientunits": "gradientUnits",
    "gradienttransform": "gradientTransform",
    "patternunits": "patternUnits",
    "patterncontentunits": "patternContentUnits",
    "patterntransform": "patternTransform",
    "clippathunits": "clipPathUnits",
    "maskunits": "maskUnits",
    "maskcontentunits": "maskContentUnits",
    "markerwidth": "markerWidth",
    "markerheight": "markerHeight",
    "markerunits": "markerUnits",
    "refx": "refX",
    "refy": "refY",
    "spreadmethod": "spreadMethod",
    "textlength": "textLength",
    "lengthadjust": "lengthAdjust",
    "startoffset": "startOffset",
    "baseprofile": "baseProfile",
    "attributename": "attributeName",
    "repeatcount": "repeatCount",
    "keytimes": "keyTimes",
    "keysplines": "keySplines",
    "calcmode": "calcMode",
    "stddeviation": "stdDeviation",
    "lineargradient": "linearGradient",
    "radialgradient": "radialGradient",
    "clippath": "clipPath",
    "textpath": "textPath",
    "foreignobject": "foreignObject",
    "animatetransform": "animateTransform",
    "animatemotion": "animateMotion",
    "fegaussianblur": "feGaussianBlur",
    "fedropshadow": "feDropShadow",
    "feoffset": "feOffset",
    "femerge": "feMerge",
    "femergenode": "feMergeNode",
    "fecolormatrix": "feColorMatrix",
    "feblend": "feBlend",
    "feflood": "feFlood",
    "fecomposite": "feComposite",
}
_SVG_CASE_RE = re.compile(
    r"\b(" + "|".join(sorted(_SVG_CASE, key=len, reverse=True)) + r")\b"
)
_TAG_RE = re.compile(r"<[^>]+>")


def _fix_svg_case(html: str) -> str:
    """태그 안쪽에서만 SVG 이름의 대소문자를 복원한다 (본문 텍스트는 건드리지 않는다)."""

    def fix_tag(match: re.Match[str]) -> str:
        return _SVG_CASE_RE.sub(lambda m: _SVG_CASE[m.group(1)], match.group(0))

    return _TAG_RE.sub(fix_tag, html)


def _anchor_id(text: str, used: set[str]) -> str:
    base = re.sub(r"[^\w가-힣]+", "-", text.strip().lower()).strip("-") or "section"
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}-{n}", n + 1
    used.add(candidate)
    return candidate


def _pick_content_root(soup: BeautifulSoup) -> Tag:
    """본문을 가장 잘 감싸는 요소를 고른다. 후보 중 텍스트가 가장 많은 것."""
    best: Tag | None = None
    best_len = -1
    for selector in config.CONTENT_ROOT_SELECTORS:
        for node in soup.select(selector):
            length = len(node.get_text(strip=True))
            if length > best_len * 1.05:
                best, best_len = node, length
        if best is not None and best_len > 400:
            break
    return best or soup


def _strip_chrome(root: Tag) -> None:
    for tag in root.find_all(list(config.DROP_TAGS)):
        tag.decompose()
    for node in root.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()


def _is_container(tag: Tag) -> bool:
    """안에 블록 요소를 품고 있으면 레이아웃용 컨테이너로 본다."""
    return tag.find(list(BLOCK_TAGS)) is not None


def _sanitize(node: Tag, inline: bool = False) -> None:
    """KEEP_TAGS 외의 태그를 정리한다.

    - 블록을 품은 컨테이너(div 등) → 껍데기만 벗긴다(unwrap)
    - 짧은 텍스트만 든 배지/라벨 div → <p class="kicker"> 로 승격
      (그냥 unwrap 하면 "Chapter 01" 같은 라벨이 문단 사이에 맨몸으로 떠버린다)
    - 아이콘 한두 글자짜리 → 버린다

    자식보다 부모의 역할을 먼저 정한다. 순서가 뒤집히면 문장 중간의 <span> 이
    블록으로 승격되어 한 문장이 여러 문단으로 찢어진다.
    """
    for child in list(node.children):
        if isinstance(child, Comment):
            child.extract()
            continue
        if not isinstance(child, Tag):
            continue

        name = child.name.lower()
        if name in config.PRESERVE_SUBTREE_TAGS:
            continue  # SVG 등은 내부를 건드리지 않는다

        if name in config.KEEP_TAGS:
            _sanitize(child, inline=inline or name in INLINE_CONTEXT)
            allowed = config.KEEP_ATTRS.get(name, set())
            child.attrs = {k: v for k, v in child.attrs.items() if k in allowed}
            continue

        text = child.get_text(" ", strip=True)
        has_media = child.find(["img", "svg", "hr", "br"]) is not None
        is_callout = bool(_CALLOUT_CLASS.search(_class_of(child)))

        if not text and not has_media:
            child.decompose()
        elif not inline and is_callout and len(text) > 10:
            # 원본의 주의/참고 박스 → blockquote 로 보존 (통일 테마가 다시 꾸민다)
            _sanitize(child, inline=not _is_container(child))
            child.name = "blockquote"
            child.attrs = {}
        elif inline or _is_container(child):
            _sanitize(child, inline=inline)
            child.unwrap()
        elif _SYMBOL_ONLY.match(text):
            child.decompose()
        else:
            # 블록 하나로 승격된다 → 내부는 인라인 맥락으로 다룬다
            _sanitize(child, inline=True)
            child.name = "p"
            child.attrs = {"class": "kicker"} if _is_label(text) else {}


def _wrap_inline_runs(container: Tag, soup: BeautifulSoup) -> None:
    """블록 사이에 맨몸으로 남은 텍스트·인라인 요소를 <p> 로 묶는다."""
    run: list[Any] = []

    def flush() -> None:
        if not run:
            return
        text = "".join(
            n.get_text(" ") if isinstance(n, Tag) else str(n) for n in run
        ).strip()
        has_media = any(isinstance(n, Tag) and n.name == "img" for n in run)
        if (not text or _SYMBOL_ONLY.match(text)) and not has_media:
            for node in run:
                node.extract()
        else:
            wrapper = soup.new_tag("p")
            run[0].insert_before(wrapper)
            for node in run:
                wrapper.append(node.extract())
        run.clear()

    for child in list(container.children):
        is_inline = (
            isinstance(child, NavigableString) and not isinstance(child, Comment)
            and str(child).strip()
        ) or (isinstance(child, Tag) and child.name in INLINE_ELEMENTS)
        is_blank = isinstance(child, NavigableString) and not str(child).strip()

        if is_inline:
            run.append(child)
        elif is_blank and run:
            run.append(child)  # 인라인 런 사이의 공백은 함께 옮긴다
        else:
            flush()
    flush()


def _collapse_empties(root: Tag) -> None:
    for tag in root.find_all(["p", "li"]):
        if not tag.get_text(strip=True) and not tag.find(["img", "svg", "br", "hr"]):
            tag.decompose()


def _build_headings(root: Tag) -> list[dict[str, Any]]:
    """h2/h3 로 목차를 만들고, 앵커 id 를 새로 부여한다."""
    used: set[str] = set()
    headings: list[dict[str, Any]] = []
    for tag in root.find_all(["h2", "h3"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        anchor = _anchor_id(text, used)
        tag["id"] = anchor
        headings.append({"level": int(tag.name[1]), "text": text, "id": anchor})
    return headings


def _find_title(soup: BeautifulSoup, root: Tag, fallback: str) -> str:
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)
    h1 = root.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    return fallback


def extract_file(path: Path, slug: str) -> dict[str, Any]:
    """HTML 파일 하나를 구조화된 dict 로 변환한다."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")

    title = _find_title(soup, soup, fallback=path.stem)

    root = _pick_content_root(soup)
    _strip_chrome(root)
    _sanitize(root)
    _wrap_inline_runs(root, soup)
    for name in WRAP_CONTAINERS:
        for node in root.find_all(name):
            _wrap_inline_runs(node, soup)
    _collapse_empties(root)

    # 제목 h1 은 템플릿이 따로 렌더링하므로 본문에서 중복 h1 을 제거한다
    for h1 in root.find_all("h1"):
        text = h1.get_text(" ", strip=True)
        if text and (text in title or title in text):
            h1.decompose()

    headings = _build_headings(root)

    body_html = _fix_svg_case(root.decode_contents())
    text = root.get_text(" ", strip=True)

    return {
        "slug": slug,
        "title": title,
        "headings": headings,
        "html": body_html,
        "text": text,
        "word_count": len(text.split()),
        "char_count": len(text),
    }


def write_extracted(data: dict[str, Any]) -> Path:
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    out = config.EXTRACTED_DIR / f"{data['slug']}.json"
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out


def load_extracted(slug: str) -> dict[str, Any] | None:
    path = config.EXTRACTED_DIR / f"{slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
