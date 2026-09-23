# Knowledge Wiki

공부한 내용을 정리한 HTML 을 `docs/` 에 넣기만 하면,
AI 가 읽고 분류하고 **주제별로 정돈된 토픽 페이지**를 써서 위키로 묶고, GitHub Pages 에 배포한다.

```
docs/*.html  →  scan(추출)  →  AI 분류 → 토픽 배정 → 정돈본 작성  →  build  →  site/  →  GitHub Pages
    ↑
 내가 하는 일은 여기까지
```

배포 주소: https://woosbang.github.io/knowledge-wiki/

## 위키의 두 층

| 층 | 경로 | 무엇 |
|---|---|---|
| **토픽** (위키의 얼굴) | `site/t/<id>.html` | 같은 주제의 원본 여러 편을 AI 가 한 편으로 정돈한 것. 근거가 1편뿐이면 원본을 그대로 보여준다 |
| **원본 문서** (근거) | `site/d/<slug>.html`, `site/raw/<slug>.html` | 원본 한 편씩. 합쳐지지도 지워지지도 않는다. 토픽의 각 절에서 출처 링크로 도달한다 |

정돈본은 원문에 없는 내용을 보태지 않고, 원문끼리 어긋난 곳은 "원문과 다른 점" 절에 표로 남긴다.

## 빠른 시작

```bash
uv sync                  # 의존성 설치 (최초 1회)
uv run wiki sync         # 스캔 → 건강검진 → 빌드
uv run wiki serve        # http://127.0.0.1:8765 에서 확인
```

문서를 추가한 뒤에는:

```bash
# Claude Code 안에서
/wiki-sync
```

## 명령어

| 명령 | 하는 일 |
|---|---|
| `uv run wiki scan` | `docs/` 를 훑어 본문을 추출하고 entry 골격을 만든다 |
| `uv run wiki status` | AI 가 할 일 — 분류할 문서, 토픽 미배정 문서, 정돈본을 써야 할 토픽 (`--json` 지원) |
| `uv run wiki audit` | 중복·노후·미분류·토픽 리포트를 `wiki/reports/health.md` 에 쓴다 |
| `uv run wiki build` | `site/` 에 정적 위키를 생성한다 |
| `uv run wiki sync` | scan → audit → build |
| `uv run wiki serve` | `site/` 로컬 미리보기 |
| `uv run wiki topic-init <id> …` | 토픽을 만들고 근거 문서를 배정한다 |
| `uv run wiki topic-add <id> <slug>…` | 기존 토픽에 근거 문서를 추가한다 |
| `uv run wiki synth-done <id>` | 정돈본(.md)을 쓴 뒤 해시를 기록하고 인용·코드·분량 검사를 돌린다 |
| `uv run wiki classify` / `synthesize` | (선택) Anthropic API 로 무인 실행 — `uv sync --extra api` 필요 |

## 폴더

| 경로 | 성격 | 누가 고치나 |
|---|---|---|
| `docs/` | 원본 HTML. **파이프라인은 읽기만 한다** | 사람 |
| `wiki/taxonomy.yaml` | 카테고리 체계 — 분류의 기준 | 사람 (AI 는 제안만) |
| `wiki/entries/*.json` | 문서별 메타데이터 | AI (사람이 덮어쓸 수 있음) |
| `wiki/topics/*.json` `*.md` | 토픽 메타데이터와 정돈본 | AI 초안, 사람 수정 가능 (`locked`, `<!-- memo -->` 는 사람 전용) |
| `wiki/extracted/*.json` | 추출 본문 캐시 | 파이프라인 |
| `wiki/reports/` | 건강검진 리포트 | 파이프라인 |
| `pipeline/` | 파이썬 코드, 템플릿, AI 지침(`prompts/`) | 사람 |
| `site/` | 빌드 산출물 (git 제외) | 파이프라인 |

## 더 읽을 것

| 문서 | 내용 |
|---|---|
| [PRD.md](PRD.md) | 왜 이렇게 설계했는가, 토픽 층 설계(8절), 남은 Phase |
| [CLAUDE.md](CLAUDE.md) | 작업 규칙과 폴더별 소유권 |
| [DEVLOG.md](DEVLOG.md) | 개발 기록 — 부딪힌 문제, 검증 결과, 인수인계 |
