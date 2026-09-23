# Knowledge Wiki

공부한 내용을 정리한 HTML 을 `docs/` 에 넣기만 하면,
AI 가 읽고 분류해서 카테고리별 위키로 묶고, GitHub Pages 에 배포한다.

```
docs/*.html  →  scan(추출)  →  AI 분류  →  build  →  site/  →  GitHub Pages
    ↑                                                  
 내가 하는 일은 여기까지
```

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
| `uv run wiki status` | AI 분류가 필요한 문서를 보여준다 (`--json` 지원) |
| `uv run wiki audit` | 중복·노후·미분류 리포트를 `wiki/reports/health.md` 에 쓴다 |
| `uv run wiki build` | `site/` 에 정적 위키를 생성한다 |
| `uv run wiki sync` | scan → audit → build |
| `uv run wiki serve` | `site/` 로컬 미리보기 |
| `uv run wiki classify` | (선택) Anthropic API 로 무인 분류 — `uv sync --extra api` 필요 |

## 폴더

| 경로 | 성격 | 누가 고치나 |
|---|---|---|
| `docs/` | 원본 HTML. **파이프라인은 읽기만 한다** | 사람 |
| `wiki/taxonomy.yaml` | 카테고리 체계 — 분류의 기준 | 사람 (AI 는 제안만) |
| `wiki/entries/*.json` | 문서별 메타데이터 | AI (사람이 덮어쓸 수 있음) |
| `wiki/extracted/*.json` | 추출 본문 캐시 | 파이프라인 |
| `wiki/reports/` | 건강검진 리포트 | 파이프라인 |
| `pipeline/` | 파이썬 코드 | 사람 |
| `site/` | 빌드 산출물 (git 제외) | 파이프라인 |

## 더 읽을 것

| 문서 | 내용 |
|---|---|
| [PRD.md](PRD.md) | 왜 이렇게 설계했는가, 남은 Phase |
| [CLAUDE.md](CLAUDE.md) | 작업 규칙과 폴더별 소유권 |
| [DEVLOG.md](DEVLOG.md) | 개발 기록 — 부딪힌 문제, 검증 결과, 인수인계 |

