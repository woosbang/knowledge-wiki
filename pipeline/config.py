"""경로와 상수를 한곳에 모아둔다. 다른 모듈은 여기서만 경로를 가져온다."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCS_DIR = ROOT / "docs"                  # 사용자가 HTML 을 떨어뜨리는 유일한 입력 폴더
WIKI_DIR = ROOT / "wiki"                  # AI/파이프라인이 만든 메타데이터 (git 추적)
ENTRIES_DIR = WIKI_DIR / "entries"        # 문서 1개 = entries/<slug>.json
EXTRACTED_DIR = WIKI_DIR / "extracted"    # 추출된 본문 캐시 (재분류 시 AI 가 읽는 원천)
REPORTS_DIR = WIKI_DIR / "reports"        # 중복/노후 리포트 (사람이 읽는 마크다운)
TAXONOMY_PATH = WIKI_DIR / "taxonomy.yaml"
INDEX_PATH = WIKI_DIR / "index.json"

SITE_DIR = ROOT / "site"                  # 빌드 산출물 (GitHub Pages 배포 대상)
TEMPLATES_DIR = Path(__file__).parent / "templates"
ASSETS_DIR = Path(__file__).parent / "assets"

# 사이트 메타
SITE_TITLE = "Knowledge Wiki"
SITE_DESCRIPTION = "공부한 것을 쌓아두는 개인 지식 위키"
# 사이트 내부 링크는 모두 상대 경로다. 어떤 하위 경로에 올려도 그대로 동작하므로
# 배포 위치에 따라 고칠 설정이 없다.

# 추출 시 통째로 버리는 요소 (사이트 크롬 — 위키가 다시 만들어 준다)
DROP_TAGS = {
    "script", "style", "noscript", "link", "meta", "head",
    "nav", "aside", "footer", "iframe", "button", "form", "input",
}

# 추출 결과에 남기는 의미 태그. 나머지 태그는 껍데기만 벗기고 자식은 살린다.
KEEP_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "pre", "code", "kbd", "samp",
    "blockquote", "a", "img", "figure", "figcaption",
    "strong", "b", "em", "i", "u", "mark", "sup", "sub", "small",
    "br", "hr", "details", "summary",
}

# 태그별로 살려두는 속성
KEEP_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "th": {"colspan", "rowspan", "scope"},
    "td": {"colspan", "rowspan"},
    "code": {"class"},   # 하이라이팅 언어 클래스 (language-python 등)
    "pre": {"class"},
    "details": {"open"},
}

# SVG 다이어그램은 자체 완결적이므로 통째로 보존한다 (내용 손실 방지)
PRESERVE_SUBTREE_TAGS = {"svg"}

# 본문 루트 후보 — 앞쪽이 우선
CONTENT_ROOT_SELECTORS = [
    "main", "article", ".page", ".content", ".container",
    ".wrapper", "#content", "#main", "body",
]
