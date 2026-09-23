# Git 되돌리기와 갈라짐(diverge) 복구

실수한 변경을 어디까지 진행했는지(커밋 전 / 로컬 커밋 후 / 푸시 후)에 따라 되돌리는 방법을 고르고, 로컬과 원격이 서로 다른 커밋을 갖게 된 diverge 상태를 merge 또는 rebase 로 푸는 방법을 정리했다.

## 핵심 정리

- 되돌리기 전에 `git status` · `git log --oneline` · `git fetch` + `git log origin/main..HEAD` 로 **어느 시나리오인지 먼저 확정**한다.
- **커밋 전**이면 살릴 가능성이 조금이라도 있을 때 `git stash -u`, 완전히 버릴 때 `git checkout -- .` + `git clean -fd`.
- **로컬 커밋 후 푸시 전**이면 `git reset --soft origin/main` 이 가장 안전하다. 코드는 남고 커밋만 사라진다.
- **푸시 후**에는 `git revert` 가 기본이다. 히스토리를 지우는 `reset --hard` + `push --force` 는 혼자 쓰는 feature 브랜치에서만.
- `git status` 에 **diverged** 가 뜨면 문제가 아니라 양쪽에 커밋이 생긴 자연스러운 상태다. `git pull`(merge) 또는 `git pull --rebase` 로 합친 뒤 push 한다.
- `main` 에 Vercel 자동 배포가 걸려 있으면 revert 도 force push 도 곧바로 재배포를 부른다.

## 먼저 현재 상태를 확인한다

세 명령의 결과를 종합하면 아래 세 시나리오 중 어디인지 알 수 있다.

```bash
# 어떤 파일이 변경되었는지 확인
git status

# 변경 내용 상세 확인 (혹시 살려야 할 코드가 있을 수 있음)
git diff
```

```bash
# 원격 정보 최신화
git fetch origin

# 로컬이 원격보다 앞서 있는 커밋 수 확인
git log origin/main..HEAD --oneline
```

마지막 명령의 출력이 없으면 로컬과 원격이 같은 상태이고, 커밋이 나오면 아직 푸시하지 않은 로컬 커밋이다.

출처: git-revert-guide §되돌리기 전 — 현재 상태 확인하기

## 시나리오 A. 수정만 했고 커밋은 안 했다

가장 쉬운 경우다. 마지막 커밋 시점으로 작업 디렉토리를 깨끗하게 되돌린다. 코드를 재활용할 가능성이 조금이라도 있으면 stash, 완전히 버려도 되면 checkout.

**방법 1 — 임시 저장 후 되돌리기 (추천).** 저장 즉시 작업 디렉토리가 깨끗해지므로 이것만으로 되돌리기가 끝난다.

```bash
# 변경사항을 임시 보관함에 저장 (저장 즉시 작업 디렉토리가 깨끗해짐)
git stash -u

# -u 옵션: 새로 만든 파일(untracked)도 함께 저장

# 나중에 다시 꺼내고 싶으면:
git stash pop

# 필요 없으면 삭제:
git stash drop

# 임시 저장 목록 확인:
git stash list
```

**방법 2 — 완전히 버리기.**

```bash
# 1) 수정한 파일을 마지막 커밋 상태로 되돌리기
git checkout -- .

# 2) 새로 추가한 파일(untracked) 삭제
git clean -fd
```

`git reset --hard HEAD` 도 같은 효과에 staging area 까지 초기화한다. 어느 쪽이든 새 파일 삭제는 `git clean -fd` 를 따로 실행해야 한다.

| 명령어 | 역할 | 대상 |
|---|---|---|
| `git stash -u` | 임시 보관 후 작업 디렉토리 복원 | 추적 중인 파일 + 새 파일 (복구 가능) |
| `git checkout -- .` | 수정된 파일을 마지막 커밋 상태로 | 추적 중인 파일 |
| `git clean -fd` | Git 이 모르는 새 파일·폴더 삭제 | untracked |
| `git reset --hard HEAD` | checkout 과 동일 + staging 초기화 | 추적 중인 파일 + staging |

끝나면 `git status` 에 `nothing to commit, working tree clean` 이 보여야 한다.

출처: git-revert-guide §수정만 했고 커밋은 아직 안 한 상태

## 시나리오 B. 로컬에서 커밋했지만 푸시는 안 했다

커밋이 로컬에만 있으므로 GitHub 에 영향 없이 되돌릴 수 있다. 무엇을 남길지에 따라 고른다.

| 방법 | 명령어 | 커밋 기록 | 파일 변경사항 |
|---|---|---|---|
| 완전히 버리기 | `git reset --hard origin/main` | 삭제 | 삭제 |
| 커밋만 취소 (코드 유지) | `git reset --soft origin/main` | 삭제 | 유지 (staged) |
| 커밋 취소 + unstage | `git reset origin/main` | 삭제 | 유지 (unstaged) |

가장 안전한 선택은 `--soft` 다. 코드가 남아 있으니 일부만 골라 다시 커밋하거나, 다 필요 없으면 그때 `--hard` 로 정리하면 된다.

```bash
# 커밋만 취소, 변경 코드는 staged 상태로 유지
git reset --soft origin/main

# 확인하면 변경사항이 staged 상태로 남아있음
git status
```

`--hard` 는 커밋 기록과 파일 변경이 즉시 사라진다. 실수로 실행했다면 `git reflog` 에서 되돌리고 싶은 커밋 해시를 찾아 `git reset --hard [해시]` 로 복구할 수 있다. 단, 커밋하지 않은 파일 변경은 복구되지 않는다.

출처: git-revert-guide §로컬에서 커밋했지만 푸시는 안 한 상태

## 시나리오 C. 이미 푸시까지 했다

원격 히스토리에 영향을 주므로 가장 신중해야 한다.

**방법 ① `git revert` — 되돌리는 새 커밋을 만든다 (추천).** 기존 커밋을 지우지 않고 그 변경을 취소하는 커밋을 덧붙인다. 히스토리가 보존되어 팀 작업에서도 안전하다.

```bash
# 2) 최신 커밋부터 역순으로 revert (하나씩)
git revert a3f7b2c --no-edit
git revert e1d9c4a --no-edit

# 3) 또는 범위로 한 번에 revert
git revert b8f2d1a..HEAD --no-edit

# 4) 원격에 push
git push origin main
```

**방법 ② `reset` + force push — 히스토리 자체를 지운다.** 혼자 작업할 때만. 다른 사람이 이미 pull 한 상태에서 force push 하면 그 사람의 작업이 꼬인다.

```bash
# 1) 돌아갈 커밋으로 로컬 리셋
git reset --hard b8f2d1a

# 2) 원격 히스토리를 강제로 덮어쓰기
git push origin main --force
```

| 기준 | revert | reset + force push |
|---|---|---|
| 안전성 | 안전 | 위험 |
| 히스토리 | 보존 (되돌린 기록이 남음) | 삭제 |
| 팀 작업 | 문제 없음 | 팀원 작업이 꼬일 수 있음 |
| 추천 상황 | `main`, 팀 프로젝트, 대부분의 경우 | 1인 개발의 feature 브랜치 |

feature 브랜치는 대개 본인만 쓰고, revert 커밋이 쌓이면 main 에 머지할 때 히스토리가 지저분해지므로 거기서는 force push 가 오히려 적합하다. `main` 에 직접 푸시한 경우라면 revert 를 쓴다.

출처: git-revert-guide §이미 푸시까지 완료한 상태

## 로컬과 원격이 갈라졌다 (diverge)

같은 커밋에서 출발해 로컬과 원격이 **각자 다른 커밋**을 만든 상태다. 원격에만 커밋이 추가된 **behind** 와는 다르다. behind 는 `git pull` 로 fast-forward 되지만, diverge 는 두 갈래를 merge 나 rebase 로 합쳐야 한다.

```
로컬 main :  A → B → C → E (내가 만든 커밋)
origin/main :  A → B → C → D (원격에 추가된 커밋)
```

이 상태에서 push 하면 `! [rejected] main -> main (fetch first)` 로 거부된다. 팀원이 같은 브랜치에서 작업할 때, GitHub 웹에서 직접 파일을 고친 뒤 로컬에서도 커밋했을 때, pull 없이 오래 작업했을 때, 이미 push 한 커밋을 `commit --amend` 나 `rebase` 로 고쳤을 때 생긴다.

diverge 는 문제가 아니라 여러 사람이 서로 막히지 않고 독립적으로 작업할 수 있게 Git 이 허용한 상태다.

| | `git pull` (merge, 기본값) | `git pull --rebase` |
|---|---|---|
| 결과 | 병합 커밋이 자동 생성됨 | 내 커밋이 원격 커밋 뒤로 재배치되어 직선이 됨 |
| 히스토리 | 모두 보존, 다소 복잡 | 깔끔한 직선, 커밋 해시가 바뀜 |
| 권장 | 초보자 — 안전하고 직관적 | 깔끔한 히스토리가 필요할 때. 충돌 해결이 조금 더 복잡 |

합친 뒤 `git push` 로 반영한다.

| 상태 | `git status` 메시지 | 해결 |
|---|---|---|
| Up to date | `Your branch is up to date` | 없음 |
| Behind | `behind ... can be fast-forwarded` | `git pull` |
| Ahead | `ahead of 'origin/main' by N commits` | `git push` |
| Diverged | `have diverged` | `git pull` 또는 `git pull --rebase` |
| Diverged + Conflict | `CONFLICT` | 수동 해결 → add → commit → push |

출처: git-diverge-guide §01 Diverge란 무엇인가, git-diverge-guide §02 Behind vs Diverge 차이, git-diverge-guide §03 Diverge는 언제 발생하는가, git-diverge-guide §05 Diverge 해결 방법, git-diverge-guide §07 상황별 요약 정리

## 충돌(conflict) 해결

합칠 때 로컬과 원격이 **같은 파일의 같은 부분**을 고쳤으면 Git 이 자동으로 합치지 못하고 `CONFLICT (content): Merge conflict in src/auth.ts` 를 낸다. 파일에는 `<<<<<<< HEAD` (내 코드) / `=======` / `>>>>>>> origin/main` (원격 코드) 표시가 생긴다.

1. VS Code 에서 파일을 열어 **Accept Current / Accept Incoming / Accept Both** 중 고르거나 직접 고친다.
2. `git add .` 으로 스테이징한다.
3. `git commit` 으로 병합 커밋을 완성하고 `git push` 한다.

충돌을 줄이는 방법은 자주 pull 하는 것이다. 작업 시작 전 `git pull` 을 습관으로 삼으면 diverge 자체가 잘 생기지 않고, 생겨도 충돌 범위가 작다.

출처: git-diverge-guide §06 충돌(Conflict) 해결하기

## Vercel 자동 배포가 걸려 있을 때

Vercel 은 `main` 의 변경을 감지하면 자동 배포한다. 따라서 `main` 에서 revert 든 force push 든 하면 **되돌린 코드로 곧바로 재배포**된다. feature 브랜치에서의 reset 은 main 이 바뀌지 않으므로 배포에 영향이 없다.

DB 스키마 변경을 이미 운영 Supabase 에 적용한 뒤 코드만 되돌리면 코드는 이전 버전인데 DB 는 바뀐 상태가 된다. 이때는 운영 DB 의 스키마 변경(예: 추가한 컬럼)도 함께 롤백해야 한다.

출처: git-revert-guide §Vercel 자동 배포와의 관계

## 부록: git stash 명령어

| 명령어 | 설명 |
|---|---|
| `git stash` | 현재 변경사항을 임시 저장 (추적 중인 파일만) |
| `git stash -u` | 새로 만든 파일(untracked)까지 함께 |
| `git stash push -m "설명"` | 설명을 붙여 저장 |
| `git stash list` | 목록 확인 |
| `git stash pop` | 가장 최근 저장본을 적용하고 보관함에서 삭제 |
| `git stash apply` | 적용하되 보관함에 남김 |
| `git stash drop` | 적용하지 않고 삭제 |
| `git stash show -p` | 저장된 변경 내용 상세 확인 |

출처: git-revert-guide §부록: git stash 완전 가이드

## 빠른 참조

| 상황 | 명령어 | 위험도 |
|---|---|---|
| 수정 파일 되돌리기 (커밋 전) | `git checkout -- .` | 변경 사라짐 |
| 새 파일도 함께 삭제 (커밋 전) | `git checkout -- . && git clean -fd` | 변경 사라짐 |
| 커밋 전 한 방에 리셋 | `git reset --hard HEAD && git clean -fd` | 변경 사라짐 |
| 로컬 커밋 취소 (코드 유지) | `git reset --soft origin/main` | 코드 보존 |
| 로컬 커밋 + 코드 모두 버리기 | `git reset --hard origin/main` | 전부 사라짐 |
| 푸시 후 안전하게 되돌리기 | `git revert [커밋해시]` → push | 히스토리 보존 |
| 푸시 후 히스토리까지 삭제 (1인 개발) | `git reset --hard [해시]` → `push --force` | 히스토리 삭제 |
| 변경사항 임시 저장 (보험) | `git stash -u` | 안전 |
| 로컬·원격이 갈라짐 | `git pull` 또는 `git pull --rebase` → push | 보통 |

출처: git-revert-guide §빠른 참조 — 상황별 한 줄 요약, git-diverge-guide §07 상황별 요약 정리

## 원문과 다른 점

없음. 두 원문은 다루는 상황이 달라(되돌리기 / 갈라짐) 충돌 없이 이어 붙였다. 빠른 참조 표의 마지막 행만 두 문서를 잇기 위해 추가했다.

## 근거 문서

- git-revert-guide — Git 되돌리기 가이드 — 변경사항을 마지막 커밋으로 복원하기 (2026-03-08)
- git-diverge-guide — Git Diverge 완벽 가이드 (2026-03-08)
