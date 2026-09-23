# CLAUDE.md

이 저장소에서 작업할 때 지켜야 할 규칙.

작업을 시작하기 전에 [DEVLOG.md](DEVLOG.md) 의 '구현 중 실제로 부딪힌 문제'와
'다음 세션을 위한 인수인계'를 훑어라. 이미 밟은 함정이 거기 적혀 있다.

## 이 프로젝트가 하는 일

사용자가 공부한 내용을 정리한 HTML 을 `docs/` 에 넣으면,
파이프라인이 본문을 추출하고 → AI 가 분류하고 → 정적 위키로 빌드해서 → GitHub Pages 에 배포한다.

사용자가 하는 일은 `docs/` 에 파일을 넣는 것뿐이어야 한다. 그 외의 수작업을 늘리는 설계는 틀린 설계다.

## 절대 규칙

1. **`docs/` 의 HTML 을 수정·삭제·이동하지 않는다.** 사용자가 직접 만든 자산이고, 파이프라인에게는 읽기 전용 입력이다. 내용이 잘못됐다고 판단해도 고치지 말고 보고한다. 각 원본 문서간에는 중복된 내용도 있을 수 있고, 수정이 필요한 내용이 있을 수도 있다. wiki 문서에는 이런 문제가 해결되어 정돈된 최신 정보로 표시되어야 한다.
2. **`wiki/taxonomy.yaml` 을 사용자 승인 없이 고치지 않는다.** 카테고리 체계가 AI 판단으로 멋대로 늘어나면 위키가 무너진다. 제안은 `wiki/reports/taxonomy-proposals.md` 에 덧붙인다.
3. **`site/` 를 직접 편집하지 않는다.** 빌드 산출물이며 매번 통째로 지워지고 다시 만들어진다.
4. **`wiki/entries/*.json` 의 `notes` 필드를 덮어쓰지 않는다.** 사람이 쓰는 칸이다.
5. **원본 문서 페이지를 병합하거나 감추지 않는다.** 정돈된 내용은 토픽(`wiki/topics/`)에 따로 쓰고, 원본 페이지는 근거로 남긴다. 원본끼리의 관계는 메타데이터(`related`, `overlaps`, `superseded_by`)로 표현한다.
6. **토픽 정돈본에 원문에 없는 내용을 보태지 않는다.** 충돌은 최신을 따르되 "원문과 다른 점"에 기록하고, `locked: true` 인 토픽과 `<!-- memo -->` 블록은 AI 가 다시 쓰지 않는다. (PRD 8절)

## 폴더별 소유권

| 경로 | 고치는 주체 | 비고 |
|---|---|---|
| `docs/` | 사람만 | 원본 HTML. 읽기 전용 입력 |
| `wiki/taxonomy.yaml` | 사람만 | AI 는 제안만 |
| `wiki/entries/*.json` | AI + 사람 | `notes` 는 사람 전용. `topic` 은 `wiki topic-init/topic-add` 명령으로만 채운다 |
| `wiki/topics/*.json` `*.md` | AI + 사람 | 정돈된 위키 본문. `notes`·`<!-- memo -->`·`locked` 는 사람 전용 |
| `wiki/extracted/*.json` | 파이프라인만 | 손으로 고쳐도 다음 scan 에 덮어써진다 |
| `wiki/reports/` | 파이프라인 + AI | `health.md` 는 자동 생성, `taxonomy-proposals.md` 는 누적 |
| `pipeline/` | 사람 (+ 요청 시 AI) | 파이썬 코드와 템플릿 |
| `site/` | 파이프라인만 | git 제외 |

## 명령어

```bash
uv sync                  # 최초 1회
uv run wiki scan         # docs/ 스캔 + 본문 추출
uv run wiki status --json  # 분류가 필요한 문서 (AI 가 읽기 좋은 형식)
uv run wiki audit        # 중복/노후 리포트 생성
uv run wiki build        # site/ 생성
uv run wiki sync         # scan → audit → build
uv run wiki serve        # 로컬 미리보기 (http://127.0.0.1:8765)
```

파이썬은 반드시 **uv 로 실행**한다. 전역 `python` 을 부르지 않는다.

## 자주 쓰는 작업

- 새 문서를 분류하고 배포까지: `/wiki-sync`
- 쌓인 문서를 정리: `/wiki-audit`
- 분류 기준을 바꾸고 싶다: `pipeline/prompts/classify.md` 를 고친다 (슬래시 커맨드와 API 가 공유)
- 정돈본 작성 기준을 바꾸고 싶다: `pipeline/prompts/synthesize.md` 를 고친다 (마찬가지로 공유)

## 설계에서 놓치기 쉬운 것

- **추출은 실패할 수 있다.** 그래서 원본 HTML 을 `site/raw/<slug>.html` 로 함께 배포하고, 모든 문서 페이지에 '원본 그대로 보기' 링크를 둔다. 이 안전장치를 없애지 않는다.
- **`classifier_hash` 가 재분류 여부를 결정한다.** entry 를 채울 때 이 값을 `source_hash` 와 맞춰두지 않으면 매번 다시 분류한다.
- **토픽의 `synth_hash` 는 손으로 쓰지 않는다.** 본문을 쓴 뒤 `uv run wiki synth-done <id>` 가 계산해 기록하고 인용·코드·분량 검사까지 돌린다. `pipeline/prompts/synthesize.md` 를 고치면 모든 토픽이 재합성 대상이 된다.
- **근거가 1개뿐인 토픽은 AI 가 쓰지 않는다(`mode: mirror`).** 원본 추출본이 그대로 토픽 본문이 된다. 근거가 2개가 되거나 `outdated` 가 섞이면 자동으로 `synthesized` 로 바뀐다.
- **lxml 은 SVG 속성을 소문자로 만든다.** `extract._fix_svg_case()` 가 `viewBox` 등을 복원한다. 이걸 지우면 다이어그램 비율이 깨진다.
- **한국어 문서가 기본이다.** 요약·핵심 정리·리포트는 한국어로 쓴다.

## 콘솔 인코딩

Windows 기본 콘솔은 cp949 라서 한글 출력이 깨져 보일 수 있다. 파일 내용은 멀쩡하다.
출력을 확인해야 하면 파일로 쓴 뒤 Read 로 읽는다.
