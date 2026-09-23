---
description: docs/ 의 새 문서를 읽어 분류하고 위키를 다시 빌드한다
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# /wiki-sync — 위키 동기화

`docs/` 에 새로 들어왔거나 내용이 바뀐 HTML 을 찾아 분류하고, 사이트를 다시 만든다.

## 절차

### 1. 스캔

```bash
uv run wiki scan
uv run wiki status --json
```

`status --json` 이 빈 배열이면 분류할 것이 없다. **3번(빌드)으로 바로 간다.**

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
`word_count`, `headings`, `notes`

`classifier_hash` 를 빠뜨리면 다음 실행에서 같은 문서를 또 분류하게 된다. 꼭 채운다.

### 3. 기존 문서 관계 갱신

새 문서가 기존 문서와 이어진다면, **기존 문서의 `related` 에도 새 slug 를 추가**한다.
관계는 양방향이어야 사이트에서 서로 찾아간다.

### 4. 빌드와 점검

```bash
uv run wiki audit
uv run wiki build
```

`wiki/reports/health.md` 를 읽고, 사용자에게 다음을 한국어로 짧게 보고한다:

- 새로 분류한 문서와 각각의 카테고리
- 중복 의심 쌍이 있으면 그 목록과 네 판단
- 카테고리 체계를 손봐야 할 것 같으면 그 제안

## 하지 말 것

- `docs/` 의 원본 HTML 을 수정하거나 삭제하지 않는다. 사용자의 자산이다.
- `wiki/taxonomy.yaml` 을 임의로 고치지 않는다. 제안은 `wiki/reports/taxonomy-proposals.md` 에 덧붙인다.
- `site/` 를 직접 편집하지 않는다. 빌드 산출물이다.
- 확신 없는 문서를 `outdated`/`superseded` 로 감추지 않는다. `overlaps` 에 남기고 사람에게 묻는다.
