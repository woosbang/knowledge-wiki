---
description: docs/ 의 새 문서를 읽어 분류하고, 토픽에 배정하고, 정돈본을 쓰고, 위키를 다시 빌드한다
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# /wiki-sync — 위키 동기화

`docs/` 에 새로 들어왔거나 내용이 바뀐 HTML 을 찾아 **분류 → 토픽 배정 → 정돈본 작성 → 빌드** 한다.
위키는 두 층이다: 원본 문서(`d/`)는 근거로 그대로 남고, 토픽(`t/`)이 정돈된 얼굴이 된다. (PRD 8절)

## 절차

### 1. 스캔

```bash
uv run wiki scan
uv run wiki status --json
```

출력의 세 목록이 각각 할 일이다. 셋 다 비어 있으면 **5번(빌드)으로 바로 간다.**

- `classify` — 분류가 필요한 문서 (신규 또는 원본 변경)
- `assign_topic` — 분류는 됐지만 토픽이 없는 문서
- `synthesize` — 본문을 (다시) 써야 하는 토픽

### 2. 분류

분류 지침은 `pipeline/prompts/classify.md` 에 있다. **먼저 이 파일을 읽어라.**
슬래시 커맨드와 API 스크립트가 같은 지침을 쓰므로, 기준을 바꾸려면 그 파일을 고친다.

그다음 맥락을 읽는다:

- `wiki/taxonomy.yaml` — 카테고리 체계 (여기 있는 id 안에서만 분류)
- `wiki/index.json` — 이미 분류된 문서들 (태그와 요약 톤을 맞추기 위해)

대상 문서마다 `wiki/extracted/<slug>.json` 을 읽는다. `text` 필드가 본문이다.
길면 앞 12,000자와 `headings` 만 봐도 분류에는 충분하다.

읽고 나서 `wiki/entries/<slug>.json` 의 아래 필드를 **Edit 으로** 채운다:

`category`, `subcategory`, `tags`, `summary`, `key_points`, `level`,
`related`, `overlaps`, `status`, `supersedes`, `superseded_by`,
`classified_at`(오늘 날짜), `classified_by`(`"claude-code"`),
`classifier_hash`(같은 파일의 `source_hash` 값을 그대로 복사)

**건드리지 말 것**: `slug`, `source`, `source_hash`, `title`, `doc_date`,
`word_count`, `headings`, `topic`(3단계에서 명령으로 채운다), `notes`

`classifier_hash` 를 빠뜨리면 다음 실행에서 같은 문서를 또 분류하게 된다. 꼭 채운다.

새 문서가 기존 문서와 이어진다면 **기존 문서의 `related` 에도 새 slug 를 추가**한다.

### 3. 토픽 배정

`status --json` 의 `topics` 목록(기존 토픽)을 보고, 분류가 끝난 문서마다 판단한다:

- 같은 주제를 다루는 토픽이 이미 있다 → 합류
  ```bash
  uv run wiki topic-add <topic-id> <slug>
  ```
- 없다 → 새 토픽. id 는 영문 소문자-하이픈, 같은 카테고리 안에서 고유하게
  ```bash
  uv run wiki topic-init <topic-id> --title "…" --category <cat> --subcategory <sub> \
    --summary "…" --tags a b c --sources <slug> [<slug>…]
  ```

판단 기준: **"이 주제를 처음 배우는 사람이 한 페이지에서 읽고 싶은 범위"** 가 토픽 하나다.
`overlaps` 나 `superseded_by` 로 묶인 문서들은 거의 항상 같은 토픽이다.
`related` 만으로 이어진 문서는 주제가 다르면 다른 토픽이다.

명령이 `mode=synthesized` 라고 출력하면(근거 2개 이상) 4단계 대상이 된다.
`mode=mirror` 면 원본이 그대로 토픽 본문이 되므로 쓸 것이 없다.

### 4. 정돈본 작성

합성 지침은 `pipeline/prompts/synthesize.md` 에 있다. **먼저 이 파일을 읽어라.** 골격과 규칙이 거기 있다.

`status --json` 의 `synthesize` 목록에 있는 토픽마다:

1. `wiki/topics/<id>.json` 과 근거 문서들의 `wiki/extracted/<slug>.json`(`text`, `headings`),
   `wiki/entries/<slug>.json`(`doc_date`, `status`) 을 읽는다.
2. `has_md: true` 면 기존 `wiki/topics/<id>.md` 도 읽는다. `<!-- memo -->` 블록은 새 본문 끝에 그대로 옮긴다.
3. 지침의 골격대로 `wiki/topics/<id>.md` 를 **Write 로** 쓴다.
4. 기록하고 검사한다:
   ```bash
   uv run wiki synth-done <id>
   ```
   경고가 나오면(인용 누락 / 출처 불명 코드 / 분량 초과) 본문을 고치고 다시 실행한다.

핵심 규칙 세 가지만 다시: 원문에 없는 내용을 만들지 않는다 · 충돌은 최신을 따르되
"원문과 다른 점"에 기록한다 · 절마다 `출처:` 를 단다.

### 5. 빌드와 점검

```bash
uv run wiki audit
uv run wiki build
```

`wiki/reports/health.md` 를 읽고, 사용자에게 다음을 한국어로 짧게 보고한다:

- 새로 분류한 문서와 각각의 카테고리·토픽
- 새로 쓰거나 다시 쓴 토픽, "원문과 다른 점"에 적은 판단
- 중복 의심 쌍이 있으면 그 목록과 네 판단
- 카테고리 체계를 손봐야 할 것 같으면 그 제안 (`wiki/reports/taxonomy-proposals.md` 에 덧붙인다)

## 하지 말 것

- `docs/` 의 원본 HTML 을 수정하거나 삭제하지 않는다. 사용자의 자산이다.
- `wiki/taxonomy.yaml` 을 임의로 고치지 않는다. 제안은 `wiki/reports/taxonomy-proposals.md` 에 덧붙인다.
- `site/` 를 직접 편집하지 않는다. 빌드 산출물이다.
- `locked: true` 인 토픽의 `.md` 를 다시 쓰지 않는다. 근거가 바뀌었으면 리포트에만 남긴다.
- entry 와 topic 의 `notes`, `.md` 의 `<!-- memo -->` 블록을 지우지 않는다. 사람의 것이다.
- 확신 없는 문서를 `outdated`/`superseded` 로 감추지 않는다. `overlaps` 에 남기고 사람에게 묻는다.
- 정돈본에 원문에 없는 내용을 보태지 않는다. 고쳤으면 반드시 "원문과 다른 점"에 적는다.
