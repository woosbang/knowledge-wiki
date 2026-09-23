# DEVLOG — 개발 기록

이 프로젝트가 **어떻게 지금 모습이 되었는지**를 남긴 문서다.
세션이 끊겨도 다음 사람(또는 다음 세션의 AI)이 맥락을 복원할 수 있게 하는 것이 목적이다.

- **왜 이렇게 설계했는가** → [PRD.md](PRD.md)
- **작업할 때 지킬 규칙** → [CLAUDE.md](CLAUDE.md)
- **어떻게 쓰는가** → [README.md](README.md)
- **무슨 일이 있었는가** → 이 문서

> `docs/` 에는 이 문서를 두지 않는다. 그 폴더는 위키 스캔 대상이라 넣는 순간 위키 문서로 잡힌다.

---

## 세션 1 — 2026-09-23 · 기반 구축

### 시작 상태

```
knowledge-wiki/
└── docs/   (HTML 12개, 그 외 아무것도 없음)
```

git 저장소도 아니었고 파이썬 프로젝트도 아니었다. `docs/` 에는 2026-01 ~ 2026-03 사이에
정리한 HTML 12개만 있었다. 각 파일은 **자체 CSS·폰트·테마를 가진 완결된 문서**였다
(다크 테마, 라이트 테마, 세리프, 모노스페이스가 파일마다 제각각).

이미 이 시점에 중복 징후가 있었다 — `git-*` 문서 4개, RAG 가이드 2개(`★` / `보안추가★`).

### 요구사항

> "docs 폴더에 html을 추가하기만 하면 AI가 주기적으로 폴더의 내용을 읽고 분류하여
> 카테고리별로 wiki 문서 형태로 구성해 주는 workflow를 만들고 싶다. 최종 wiki 문서는 웹에 배포."

### 착수 전에 물어본 것과 그 답

각 HTML이 자체 디자인을 가졌다는 사실이 설계 전체를 가르는 변수여서, 코드를 쓰기 전에 세 가지를 물었다.

| 질문 | 선택된 답 | 비고 |
|---|---|---|
| 원본 디자인을 어떻게 다룰까 | **본문 추출 후 통일 템플릿** | 원본 커스텀 디자인 손실 위험을 알렸으나 통일을 선택 → `site/raw/` 동시 배포로 완화 |
| 배포처 | **GitHub Pages** | `docs/` 에 사내 자료가 있어 private 권장 (PRD 7절) |
| AI 실행 방식 | **둘 다 (단계적)** | 슬래시 커맨드 우선, API 경로는 인터페이스만 분리해 준비 |

**"원본 보존" 옵션을 권했으나 사용자가 "통일 템플릿"을 선택했다.** 그래서 요구대로 통일 템플릿으로
가되, 추출 실패 시 내용이 유실되지 않도록 **원본 HTML을 `site/raw/<slug>.html` 로 그대로 함께
배포하고 모든 문서 페이지에 "원본 그대로 보기" 링크를 넣는 안전장치**를 설계에 포함시켰다.
이 장치는 없애면 안 된다 — PRD의 "내용 보존 0건 유실" 기준이 이것에 의존한다.

### 만든 순서

1. 폴더 골격 + `pyproject.toml` (uv, Python 3.12)
2. `config.py` — 경로·태그 정책을 한곳에 모음
3. `models.py` — `Entry` 스키마 (Claude Code와 API가 공유하는 계약)
4. `extract.py` — HTML → 의미 HTML
5. `scan.py` — 해시 기반 변경 감지, 슬러그 생성
6. `taxonomy.yaml` — 카테고리 체계 seed
7. `build.py` + 템플릿 + CSS/JS — 정적 사이트
8. `audit.py` — 중복·노후 리포트
9. `cli.py` — `wiki` 명령
10. `prompts/classify.md` — **분류 지침 단일 원천**
11. `classify_api.py` — Phase 3용 API 경로
12. `.claude/commands/` — `/wiki-sync`, `/wiki-audit`
13. CLAUDE.md · PRD.md · README.md · GitHub Actions
14. 기존 12개 문서 실제 분류 → 빌드 → 검증

---

## 구현 중 실제로 부딪힌 문제

여기가 이 문서의 핵심이다. 같은 함정을 다시 밟지 않기 위한 기록.

### 1. lxml이 SVG `viewBox`를 소문자로 만든다 ★ 가장 위험했던 버그

`BeautifulSoup(raw, "lxml")` 은 **HTML 파서**라서 태그·속성 이름을 전부 소문자로 바꾼다.
HTML에서는 문제없지만 SVG는 대소문자를 구분한다. `viewBox` → `viewbox` 가 되면
브라우저가 무시하고, 다이어그램의 크기·비율이 통째로 깨진다.

`Claude_제품_관계도.html` 처럼 SVG 다이어그램이 본문의 핵심인 문서에서는 내용 손실에 가깝다.
조용히 깨지기 때문에 발견도 늦는다.

**해결**: `extract._fix_svg_case()` — 직렬화된 HTML에서 **태그 안쪽에서만** 정규식으로
원래 표기를 복원한다(`viewBox`, `preserveAspectRatio`, `linearGradient`, `refX` 등 40여 개).
본문 텍스트에 같은 단어가 나와도 건드리지 않도록 `<[^>]+>` 안으로 치환 범위를 제한했다.

**검증 방법**: `grep -c 'viewbox=' site/d/*.html` 가 0이어야 한다.

### 2. 배지/라벨 `div` 가 맨몸 텍스트로 흩어진다

원본들은 "Chapter 01", "Step 2", "PART 01", "bash", "Terminal — 최초 업로드" 같은
라벨을 `<div class="badge">` 로 넣어 CSS로 꾸며 놨다. `div` 를 단순 unwrap 하면
이 텍스트들이 문단 사이에 맨몸으로 떠서 본문과 구분되지 않는다.

**해결**: 블록 요소를 품지 않은 짧은 텍스트 컨테이너는 `<p class="kicker">` 로 **승격**시키고,
통일 테마가 작은 대문자 라벨로 다시 꾸민다. 아이콘 한두 글자(`⚠`, `🗺️`)만 든 것은 버린다.

### 3. 문장 중간의 `<span>` 이 블록으로 승격돼 문장이 찢어진다

2번을 구현한 직후 이런 결과가 나왔다:

```html
<p class="kicker">rm</p><p>은 복구가 안 되므로, 익숙해지기 전까지는</p><p class="kicker">rm -i</p>...
```

원인은 **재귀 순서**였다. 자식을 먼저 정리하고 부모의 역할을 나중에 정하면,
아직 부모가 `<p>` 가 될지 모르는 상태에서 자식 `<span>` 들이 이미 블록으로 승격돼 버린다.

**해결**: `_sanitize()` 에서 **부모의 역할을 먼저 정하고**, 그 결정에 따라 `inline` 플래그를
자식에게 내려보낸다. 부모가 `<p>` 가 될 운명이면 자식은 무조건 unwrap 된다.
이 순서를 뒤집으면 같은 버그가 재발한다.

### 4. 콜아웃 박스가 평범한 문단이 된다

원본의 "⚠ 주의", "💡 팁" 박스가 그냥 문단으로 납작해졌다.

**해결**: 클래스 이름에 `callout|warn|note|tip|info|danger|...` 가 있으면 `<blockquote>` 로
변환한다. 통일 테마가 좌측 보더로 다시 꾸민다. 클래스 이름에 의존하는 휴리스틱이라
원본이 다른 네이밍을 쓰면 놓친다 — 완벽을 노리지 않고, 놓쳐도 내용은 남는 쪽을 택했다.

### 5. `BASE_URL` 설정 → 상대 경로로 전환

처음엔 `config.BASE_URL` 로 `/repo-name` 접두사를 붙이는 방식이었다.
GitHub Pages 프로젝트 사이트는 하위 경로에 배포되기 때문이다.

문제는 (a) 배포 위치가 바뀔 때마다 고쳐야 하고, (b) 로컬에서 파일로 열어볼 수 없다는 점.

**해결**: 모든 내부 링크를 상대 경로로 바꾸고 `BASE_URL` 을 **삭제**했다.
각 페이지 렌더링 시 `root` 를 넘긴다 (`""` 또는 `"../"`). 검색 JS는 `data-index` 속성에서
같은 접두사를 역산한다. 이제 어떤 하위 경로에 올려도 그대로 동작하고, 설정할 것이 없다.

### 6. Bash 히어독으로 큰 CSS 파일 쓰기 실패

`cat > wiki.css <<'CEOF'` 방식이 `unexpected EOF while looking for matching '` 로 실패했다
(약 270줄 CSS). 원인을 특정하지 않고 Write 도구로 전환해 해결.
**큰 파일은 히어독 대신 Write 도구를 쓸 것.**

### 7. Windows 콘솔 cp949 인코딩

`uv run wiki scan` 의 한글 출력이 전부 깨져 보인다. **파일 내용은 멀쩡하다.**
파이썬 스크립트에서 한글을 `print` 하면 `UnicodeEncodeError` 로 죽기도 한다.

**대응**: 출력을 확인해야 하면 UTF-8 파일로 쓴 뒤 Read 도구로 읽는다.
이 프로젝트에서는 스크래치패드에 `extract-check.txt`, `digest.txt` 를 쓰는 방식으로 검수했다.

### 8. Chrome 확장이 로컬 서버에 접근하지 못함 — 미해결

`uv run wiki serve` 로 띄운 사이트를 브라우저 자동화로 스크린샷 찍으려 했으나
`127.0.0.1`, `localhost`, `file://` 모두 "Frame with ID 0 is showing error page" 로 실패했다.
`curl` 은 200을 반환하므로 서버 자체는 정상이었다. 서버 바인딩을 `("", port)` 로 바꿔
IPv6 문제 가능성을 제거했지만 그래도 실패 → 확장의 사이트 권한/샌드박스 문제로 추정.

**대응**: 시각 검수 대신 **구조 검증**으로 대체했다(아래 참조).
**다음 세션에 할 일**: 사용자가 직접 `uv run wiki serve` 후 브라우저로 확인.
확장 권한 설정을 손보면 자동 스크린샷 검수를 파이프라인에 넣을 수 있다.

---

## 검증 결과 (2026-09-23 기준)

시각 검수를 못 했으므로 산출물을 프로그램으로 검사했다.

| 항목 | 결과 |
|---|---|
| 내부 링크 전수 검사 | 166개 중 깨짐 **0건** |
| 미처리 Jinja 구문 | 0건 |
| 문서 페이지 / 카테고리 페이지 | 12 / 4 |
| 원본 사본 (`site/raw/`) | 12 (입력과 동일) |
| SVG `viewBox` 보존 | 4개 보존, 소문자 `viewbox` 0건 |
| 검색 색인 | 12문서 / 86KB |

재현용 스니펫은 이 문서 맨 아래 "검증 스크립트" 참조.

### 추출 분량 대조

원본 텍스트 대비 추출 텍스트 길이를 비교해 큰 누락이 없음을 확인했다.
(bash-guide 1,704 → 2,048 / git-guide 5,854 → 7,238 / RAG-보안추가 11,589 → 14,907.
추출 쪽이 더 큰 것은 공백 처리 방식 차이 때문이며, 누락이 아니다.)

---

## 초기 분류 결과

12개 문서를 4개 카테고리에 배치했다. `/wiki-sync` 의 2단계를 사람이 아닌 이 세션에서
직접 수행한 것이며, 이후에는 슬래시 커맨드가 같은 일을 한다.

| 카테고리 | 문서 |
|---|---|
| `version-control` (4) | git-guide, git-methods-comparison, git-revert-guide, git-diverge-guide |
| `ai-ml` (4) | confusion-matrix-guide, claude-제품-관계도, RAG 가이드 2종 |
| `dev-environment` (2) | bash-guide, uv-환경-guidebook |
| `dev-workflow` (2) | dev-workflow-guide, webapp-development-workflow-guide |

### 중복 판정

기계적 유사도 탐지가 **RAG 가이드 2개를 0.86으로 검출**했다. 양쪽을 읽고 판정한 결과
`보안추가★` 쪽이 보안 장(4-9절)이 독립·확장된 상위 버전이어서:

- 초판 → `status: "superseded"`, `superseded_by: "사내문서-rag-챗봇-구축-가이드-보안추가"`
- 개정판 → `supersedes: ["사내문서-rag-챗봇-구축-가이드"]`

`git-guide` ↔ `git-methods-comparison` 은 최초 세팅 절차가 겹치지만 관점이 달라
`overlaps`(severity: medium)에만 기록하고 양쪽 `related` 로 연결했다.
`dev-workflow-guide` ↔ `webapp-development-workflow-guide` 도 같은 처리
(스택은 같고 단계가 다름 — 운영 중 수정 vs 신규 개발).

> 판정 후 `audit.py` 에 **"✅ 대체 관계 기록됨"** 표시를 추가했다.
> 이미 처리한 쌍을 매달 다시 검토하지 않게 하려는 것이다.

---

## 현재 상태

### 동작하는 것

- `uv run wiki scan / status / audit / build / sync / serve` 전부 동작
- 12개 문서 분류 완료, 사이트 빌드 완료, 링크 검증 통과
- `/wiki-sync`, `/wiki-audit` 슬래시 커맨드 정의됨

### 아직 안 한 것

- [x] `git init` 및 GitHub 저장소 생성 — 세션 2에서 완료. **공개 저장소** `woosbang/knowledge-wiki`
- [x] GitHub Pages 실제 배포 — https://woosbang.github.io/knowledge-wiki/ (push 마다 Actions 가 자동 배포)
- [ ] `/wiki-sync` 슬래시 커맨드 실사용 검증 — 커맨드 정의는 했으나 아직 실행해 본 적 없음.
      **다음 세션에서 문서를 하나 추가해 실제로 돌려보고, 지침이 충분한지 확인할 것**
- [ ] `classify_api.py` 실행 검증 — 코드만 작성, API 호출은 한 번도 하지 않았다
- [x] 브라우저 렌더링 육안 확인 — 세션 2에서 Edge 헤드리스로 완료 (아래 참조)

---

## 세션 2 — 2026-09-24 · 검수와 시각 확인

### 한 일

1. `uv run wiki sync` 재실행 → 신규 0 · 변경 0 · 유지 12. 세션 1 상태 그대로 재현됨.
2. 구조 검증 스크립트 재실행 → 내부 링크 166개 깨짐 0, `viewbox=` 0, `site/raw/` 12개 원본과 해시 일치,
   모든 entry 에 `category`·`summary`·`key_points` 있고 `classifier_hash == source_hash`.
3. 추출 누락 대조: 원본 텍스트 대비 추출 텍스트 0.86 ~ 0.99 (버려진 것은 nav/aside/footer 크롬).
4. **시각 검수 완료** — 홈, 카테고리, 문서(일반 / SVG 다이어그램 / superseded), 다크 모드.

### 세션 2에서 부딪힌 문제

#### 9. 코드블록 글자가 라이트 모드에서 보이지 않았다 ★ (수정함)

`.prose pre` 는 어두운 배경(`--code-bg`)만 지정하고 글자색은 `.prose pre code` 에만 있었다.
원본이 `<pre><span class="comment">…</span></pre>` 처럼 **`<code>` 없이** 쓴 문서는
span 이 벗겨진 뒤 본문 글자색(진한 갈색)이 어두운 배경 위에 얹혀 **검은 박스만 보였다.**
다크 모드에서는 본문색이 밝아서 우연히 보였기 때문에 세션 1의 구조 검증으로는 잡히지 않았다.

영향: 코드블록 111개 중 62개 (dev-workflow 18, git-revert 19, git-guide 15, git-methods 8, RAG 각 1).

**해결**: `wiki.css` 의 `.prose pre` 에 `color: var(--code-text)` 한 줄 추가.

**검증 방법**: `site/d/git-guide.html` 의 첫 터미널 블록에 글자가 보이는지 라이트 모드로 확인.

#### 10. 시각 검수는 Edge 헤드리스로 한다 (Chrome 확장 8번 문제의 우회)

Chrome 확장은 여전히 `127.0.0.1`, `localhost` 모두 "Frame with ID 0 is showing error page".
대신 Windows 기본 Edge 를 헤드리스로 돌리면 스크린샷이 나온다:

```bash
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new --disable-gpu \
  --hide-scrollbars --user-data-dir=/tmp/edgeprof --window-size=1366,2400 \
  --screenshot=/tmp/index.png http://127.0.0.1:8765/
# 다크 모드: --force-dark-mode 추가
```

주의 두 가지:
- **같은 `--user-data-dir` 을 재사용하면 CSS 가 캐시된다.** 수정 후에는 프로필 폴더를 지우거나 새 이름을 쓴다.
- **창 폭은 492px 미만으로 줄어들지 않는다.** 390px 로 찍으면 492px 로 레이아웃된 화면이 잘려서
  "모바일에서 가로로 넘친다"고 오판하게 된다. 실제 반응형(`@media (max-width: 900px)`)은 정상이다.

#### 11. 리포트가 존재하지 않는 `/wiki-classify` 를 안내했다 (수정함)

`audit.py` 의 미분류 안내 문구를 `/wiki-sync` 로 고쳤다.

### 남겨둔 것 (판단만 하고 손대지 않음)

- `related` 가 한쪽만 걸린 쌍 4개: `dev-workflow-guide → git-guide`,
  `RAG-보안추가 → uv-환경-guidebook`, `RAG-보안추가 → claude-제품-관계도`,
  `RAG-초판 → RAG-보안추가`(대체 관계라 단방향이 맞음). 나머지 셋은 `/wiki-audit` 때 양방향으로 맞출지 결정.
- `사내문서-rag-챗봇-구축-가이드` 본문에 h1 이 하나 더 남는다. 원본 h1 이 "사내 문서 기반 / RAG 챗봇…" 로
  줄바꿈돼 `<title>` 과 부분 일치하지 않아 중복 제거 휴리스틱을 통과했다. 내용 손실은 아니라 그대로 둠.
- 같은 문서 상단의 기술 스택 배지(`Pydantic AI Claude API ChromaDB …`)가 맨몸 문단으로 나온다. 위와 같은 이유.

### 확인되지 않은 가정

- `classify_api.py` 의 tool-use 응답 처리와 프롬프트 캐싱 설정은 **실행해 본 적이 없다.**
  Phase 3 착수 시 `--dry-run` 으로 먼저 검증할 것.
- 추출기는 현재 12개 문서로만 검증했다. 새 문서의 마크업 패턴이 다르면
  (예: `<div>` 대신 `<section>` 남용, CSS Grid 레이아웃) 결과가 달라질 수 있다.
  새 문서를 넣을 때마다 `site/d/<slug>.html` 를 한 번은 눈으로 볼 것.

---

## 다음 세션을 위한 인수인계

### 먼저 읽을 것

1. `CLAUDE.md` — 절대 규칙 5개 (특히 `docs/` 불변, `taxonomy.yaml` 사람 소유)
2. 이 문서의 "구현 중 실제로 부딪힌 문제" — 같은 함정 재발 방지
3. `PRD.md` 5절 — Phase별 남은 일

### 환경 복원

```bash
cd C:/Users/Windows11/Workcosmos/knowledge-wiki
uv sync          # .venv 재생성
uv run wiki sync # 현재 상태 재확인 (scan → audit → build)
```

`.venv/` 와 `site/` 는 git 제외 대상이라 클론 직후에는 없다. 위 두 명령으로 복원된다.

### 손대면 안 되는 것

| 대상 | 이유 |
|---|---|
| `extract._fix_svg_case()` | 지우면 SVG 다이어그램이 조용히 깨진다 |
| `_sanitize()` 의 부모-우선 재귀 순서 | 뒤집으면 문장이 문단으로 찢어진다 |
| `site/raw/` 동시 배포와 "원본 보기" 링크 | 내용 보존의 마지막 안전장치 |
| `classifier_hash` 갱신 | 빠뜨리면 매 실행마다 전체 문서를 다시 분류한다 |
| `docs/` 의 원본 HTML | 사용자 자산. 읽기 전용 |

### 분류 기준을 바꾸고 싶다면

`pipeline/prompts/classify.md` **한 파일만** 고친다.
슬래시 커맨드와 API 스크립트가 이 파일을 공유하므로 두 경로가 자동으로 같이 바뀐다.

---

## 부록

### 환경

| 항목 | 버전 |
|---|---|
| OS | Windows 11 Home 26200 |
| uv | 0.9.18 |
| Python | 3.12.12 (uv 관리) |
| beautifulsoup4 / lxml | 4.15.0 / 6.1.3 |
| jinja2 / pyyaml | 3.1.6 / 6.0.3 |

전역 `python` 은 PATH에 없다(Microsoft Store 스텁만 있음). **반드시 `uv run` 으로 실행.**

### 검증 스크립트

빌드 후 산출물을 점검할 때 쓴 코드. 필요하면 `pipeline/` 에 정식 명령으로 승격시킬 것.

```python
# 내부 링크 전수 검사 + 미처리 템플릿 구문 탐지
import re
from pathlib import Path
from urllib.parse import unquote

site, bad, checked = Path("site"), [], 0
for page in site.rglob("*.html"):
    if page.parent.name == "raw":
        continue
    html = page.read_text(encoding="utf-8")
    if "{{" in html or "{%" in html:
        bad.append(f"{page}: 미처리 Jinja 구문")
    for href in re.findall(r'(?:href|src)="([^"#][^"]*)"', html):
        if href.startswith(("http", "mailto:", "data:", "#")):
            continue
        checked += 1
        if not (page.parent / unquote(href.split("#")[0])).resolve().exists():
            bad.append(f"{page.relative_to(site)} -> {href}")
print(f"검사 {checked}개 / 깨짐 {len(bad)}개")
```

```bash
# SVG 대소문자 회귀 검사 — 0 이어야 한다
grep -c 'viewbox=' site/d/*.html | grep -v ':0$'
```

### 세션 1에서 만든 파일

```
CLAUDE.md  PRD.md  README.md  DEVLOG.md  pyproject.toml  .gitignore  .python-version
pipeline/{__init__,config,models,extract,scan,build,audit,cli,classify_api}.py
pipeline/prompts/classify.md
pipeline/templates/{base,_nav,index,category,doc}.html
pipeline/assets/{wiki.css,wiki.js}
wiki/taxonomy.yaml  wiki/index.json
wiki/entries/*.json (12)  wiki/extracted/*.json (12)
wiki/reports/{health.md,taxonomy-proposals.md}
.claude/commands/{wiki-sync,wiki-audit}.md
.github/workflows/deploy.yml
```
