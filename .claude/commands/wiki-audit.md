---
description: 위키 전체를 점검해 중복·노후·분류 문제를 정리하고 정비안을 제안한다
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# /wiki-audit — 위키 정비

`/wiki-sync` 가 '새 문서 넣기'라면, 이 커맨드는 '쌓인 것 정리하기'다.
한 달에 한 번, 또는 문서가 10개쯤 늘었을 때 돌린다.

## 절차

### 1. 리포트 생성

```bash
uv run wiki audit
```

`wiki/reports/health.md` 를 읽는다.

### 2. 중복 의심 쌍 판정

리포트의 각 쌍에 대해 양쪽 `wiki/extracted/<slug>.json` 을 읽고 판단한다.

| 상황 | 조치 |
|---|---|
| 한쪽이 다른 쪽의 상위 호환 | 구버전 entry: `status: "superseded"`, `superseded_by: "<신버전 slug>"` / 신버전 entry: `supersedes` 에 구버전 추가 |
| 주제는 같지만 관점이 다름 | 양쪽 `related` 에 서로 추가 |
| 일부만 겹침 | 양쪽 `overlaps` 에 기록만 |
| 유사도는 높지만 실제로는 무관 | 아무것도 하지 않는다 (형식이 비슷해서 걸린 경우) |

**원본 HTML 은 절대 지우거나 합치지 않는다.** 메타데이터로만 관계를 표현한다.

### 3. 카테고리 체계 점검

- `misc` 에 문서가 3개 이상 쌓였는가 → 새 카테고리 제안
- 한 카테고리에 12개 이상 몰렸는가 → 하위 분류(subcategory) 제안
- `taxonomy.yaml` 에 없는 카테고리를 쓰는 문서가 있는가 → 재분류

제안은 `wiki/reports/taxonomy-proposals.md` 에 **덧붙인다**(기존 내용 삭제 금지).
`taxonomy.yaml` 을 직접 고치는 것은 사용자가 승인한 뒤에만 한다.

### 4. 노후 문서 점검

리포트의 '오래된 문서' 목록에서, 본문에 버전·도구 이름이 명시된 것들을 확인한다.
명백히 구식이면 `status: "outdated"`. 애매하면 손대지 말고 보고만 한다.

### 5. 재빌드와 보고

```bash
uv run wiki build
```

사용자에게 한국어로 보고한다: 무엇을 바꿨는지, 무엇을 판단하지 못해 남겨뒀는지,
사용자가 결정해야 할 것은 무엇인지.
