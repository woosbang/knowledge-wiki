# Git 시작하기와 멀티 PC 동기화

GitHub 저장소를 처음 만들고, 여러 PC 에서 같은 프로젝트를 이어서 작업하는 방법을 한 페이지로 정리했다. 저장소를 연결하는 두 방식 중 무엇을 고를지, 매일 반복할 사이클, `.gitignore` 와 환경 재현, 브랜치까지 다룬다.

## 핵심 정리

- 새 프로젝트는 **GitHub 에서 먼저 만들고 clone** 하는 Remote-First 가 실수가 적다. 이미 코드가 있는 프로젝트만 Local-First 로 연결한다.
- Local-First 로 연결할 때는 GitHub 저장소를 **반드시 빈 저장소**(README·.gitignore·License 체크 해제)로 만들어야 push 가 거부되지 않는다.
- 일상 사이클은 `pull → 코딩 → add → commit → push`. **push 전에 항상 pull** 이 절대 규칙이다.
- `.gitignore` 는 **첫 커밋 전에** 만든다. 이미 올라간 파일에는 소급 적용되지 않는다.
- 라이브러리는 `requirements.txt` 가 아니라 `pyproject.toml` + `uv.lock` 으로 재현한다. 다른 PC 에서는 `uv sync` 한 번이면 된다.
- 팀 작업이면 `main` 에 직접 push 하지 말고 브랜치 → Pull Request → 리뷰 → Merge 순서를 따른다.

## 전체 흐름

GitHub 는 변경 이력까지 관리되는 클라우드 저장소다. 한 PC 에서 push 하면 다른 PC 에서 pull 로 최신 코드를 받는다. 흐름은 세 단계다.

1. **최초 세팅 (1회)** — 프로젝트를 GitHub 에 올린다.
2. **다른 PC 에 복제 (PC 마다 1회)** — `git clone` 으로 통째로 가져오고 `uv sync` 로 환경을 맞춘다.
3. **일상 동기화 (매일)** — pull → 코딩 → add → commit → push 를 반복한다.

출처: git-guide §전체 흐름 한눈에 보기

## 최초 세팅: 두 가지 방식 중 고르기

로컬 코드와 GitHub 를 연결하는 목표는 같지만 시작점이 다르다.

| | A. Remote-First (GitHub → 내 PC) | B. Local-First (내 PC → GitHub) |
|---|---|---|
| 언제 | 새 프로젝트, 아직 코드가 없을 때, Git 이 낯설 때 | 이미 코드가 상당량 있는 프로젝트를 뒤늦게 올릴 때 |
| 명령어 수 | 3개 (clone → commit → push) | 6~7개 (init → add → commit → branch -M → remote add → push -u) |
| GitHub 생성 옵션 | README·.gitignore 템플릿 체크해도 됨 | **반드시 빈 저장소** (체크박스 모두 해제) |
| 원격 주소·브랜치 | clone 이 자동 설정 | `remote add`, `branch -M main` 을 직접 |
| 실수 가능성 | 낮음 | 높음 (빈 저장소 미생성, .gitignore 누락) |

초보자에게는 **A 를 권한다.** 초기 설정 명령어를 하나라도 빠뜨리면 에러가 나는데, clone 한 번이면 전부 자동으로 잡힌다. 다만 실무에서는 "급하게 코딩부터" 시작하는 일이 많으니 B 도 알아 둔다.

출처: git-methods-comparison §두 방법의 흐름 한눈에 보기, git-methods-comparison §항목별 상세 비교, git-methods-comparison §최종 추천

### A. Remote-First — GitHub 에서 만들고 clone

github.com → **New repository** → 이름과 공개 범위를 정하고, 원하면 README·.gitignore 템플릿을 체크한 뒤 생성한다. 저장소 페이지의 **Code** 버튼에서 HTTPS 주소를 복사한다.

```bash
# 원하는 작업 디렉토리로 이동
cd ~/projects

# GitHub 저장소를 내 PC에 복제
git clone https://github.com/내이름/프로젝트.git

# 생성된 프로젝트 폴더로 이동
cd 프로젝트
```

이 시점에 Git 초기화와 원격 주소 연결, 기본 브랜치 `main` 설정이 이미 끝나 있다. 코딩한 뒤에는 `git add .` → `git commit` → `git push` 만 하면 된다. VS Code / Cursor 에서는 **Clone Repository** 버튼 한 번이다.

출처: git-methods-comparison §Remote-First: GitHub에서 먼저 만들고 Clone

### B. Local-First — 내 PC 에서 시작해 GitHub 에 연결

이미 코드가 있는 폴더에서 Git 을 켜고, **첫 커밋 전에** `.gitignore` 를 만든다. 한 번 올라간 파일은 나중에 `.gitignore` 에 넣어도 계속 추적된다.

```bash
# 프로젝트 폴더로 이동
cd ~/projects/내프로젝트

# Git 초기화 (.git 폴더가 생성됩니다)
git init
```

```bash
# .gitignore 파일 생성 후 편집
# 최소한 아래 내용은 넣어주세요:
.venv/
__pycache__/
.env
node_modules/
data_*/
.DS_Store
```

첫 커밋을 만든 뒤 GitHub 에서 **빈 저장소**를 만든다. 로컬에도 커밋이 있고 GitHub 에도 커밋(README 등)이 있으면 두 기록이 달라 push 가 거부된다. 생성 후 나온 HTTPS 주소로 연결하고 올린다.

```bash
# 브랜치 이름을 main으로 변경 (Git 기본값이 master일 수 있으므로)
git branch -M main

# GitHub 주소를 origin이라는 이름으로 연결
git remote add origin https://github.com/내이름/프로젝트.git

# GitHub 서버로 전송 (-u는 기본 연결 설정, 최초 1회만)
git push -u origin main
```

빈 저장소가 아닌 곳에 push 하면 `Updates were rejected because the remote contains work...` 에러가 난다. 초보자라면 저장소를 지우고 빈 저장소로 다시 만드는 편이 안전하다. (`git pull --rebase origin main` 후 push 하는 방법도 있다.)

VS Code / Cursor GUI 로는 소스 제어 탭 → **Initialize Repository** → **Stage All** → 메시지 입력 후 **Commit** → ⋯ → Remote → **Add Remote** → **Publish Branch** 순서다.

출처: git-methods-comparison §Local-First: 내 PC에서 시작 후 GitHub에 연결, git-guide §최초 세팅: 프로젝트를 GitHub에 올리기

## 다른 PC 에서 이어받기

PC2 에서는 최초 1회만 clone 하고 환경을 맞춘다. 이후에는 pull 만 하면 된다.

```bash
# 1. 프로젝트 통째로 복제
git clone https://github.com/이름/프로젝트.git

# 2. 프로젝트 폴더로 이동
cd 프로젝트

# 3. Python 환경 동기화 (uv 사용 시)
uv sync

# 또는 poetry 사용 시:
poetry install
```

`uv sync` 는 `pyproject.toml` 과 `uv.lock` 을 읽어 PC1 과 같은 라이브러리를 같은 버전으로 설치한다. `requirements.txt` 를 손으로 관리할 필요가 없다.

출처: git-guide §다른 PC에서 프로젝트 가져오기 (Clone)

## 일상 동기화: pull → 코딩 → push

가장 중요한 습관이다. 어느 PC 에서든 패턴은 같다.

```bash
# ── 시작 전 ──
git pull origin main
uv sync

# ── 코딩 작업... ──

# ── 마무리 ──
git add .
git commit -m "작업 내용 요약"
git push
```

**절대 규칙: push 전에 항상 pull.** 다른 PC 에서 올린 변경을 받지 않고 push 하면 충돌이 난다. 시작 전 `git pull` 은 새 라이브러리가 추가됐을 수 있으니 `uv sync` 와 짝으로 쓴다.

GUI 로는 하단 바의 순환 화살표(↻)가 pull, **Sync Changes** 버튼이 add → commit → push 에 해당한다.

핵심 습관 세 가지: ① 코딩 시작 전 `git pull` ② 작업 단위마다 commit ③ 퇴근 전 `git push`.

출처: git-guide §일상 동기화: Pull → 코딩 → Push, git-guide §치트시트: 복사해서 바로 쓰세요

## .gitignore: 올리지 않을 파일

비밀키, 대용량 데이터, 가상환경처럼 GitHub 에 올리면 안 되는 파일의 '출입 금지 명단'이다. 프로젝트 최상위에 두고 첫 커밋 전에 만든다.

```text
# Python 가상환경 (각 PC에서 개별 생성)
.venv/
__pycache__/

# 비밀키 · 환경변수 (절대 올리면 안 됨!)
.env
config.json

# 대용량 데이터 폴더
data_*/
*.csv
*.xlsx

# Node.js 의존성
node_modules/

# OS 자동 생성 파일
.DS_Store
Thumbs.db
```

제외한 파일은 당연히 다른 PC 에 없다. 표준 대응 세 가지:

- **설정 파일** — 비밀키가 든 `.env` 대신 항목만 적은 `.env.example` 을 올린다. 다른 PC 에서 복사해 `.env` 로 이름을 바꾸고 값을 채운다.
- **데이터 파일** — 구글 드라이브·S3 등에 따로 두고 README 에 링크를 적거나, 소량 샘플만 `data/sample.csv` 로 포함한다.
- **폴더 구조** — Git 은 빈 폴더를 인식하지 못하므로 폴더 안에 빈 `.gitkeep` 을 둔다. clone 시 폴더가 생겨 `FileNotFoundError` 를 막는다.

무엇보다 README 에 "실행하려면 이 파일들을 직접 준비해야 한다"고 적어 둔다.

출처: git-guide §.gitignore: 올리지 않을 파일 관리, git-methods-comparison §.gitignore 생성 (중요!)

## 환경 재현: pyproject.toml + uv

`uv.lock` 덕에 모든 PC 에서 라이브러리 버전이 소수점까지 일치하고, `.venv` 는 올리지 않아 전송이 빠르다.

```bash
# 새 라이브러리 설치 (pyproject.toml이 자동 업데이트됨)
uv add pandas

# 코딩 작업 후 커밋 & 푸시
git add .      # pyproject.toml, uv.lock 포함
git commit -m "Add pandas for data analysis"
git push
```

다른 PC 에서는 `git pull origin main` → `uv sync` 로 새 라이브러리가 자동 설치된다.

- 올라가는 것: `pyproject.toml`, `uv.lock`, 코드, `.gitignore`, `.gitkeep`
- 안 올라가는 것: `.venv/`, `.env`, `data_*/`, `__pycache__/`

출처: git-guide §환경 관리: pyproject.toml + uv/poetry

## 브랜치와 Pull Request

브랜치는 메인 줄기를 건드리지 않고 새 기능을 만드는 '가지'다. 혼자 작업할 때도 실험에 유용하다.

| 작업 | 터미널 | GUI |
|---|---|---|
| 새 브랜치 만들기 | `git branch feature-login` | 하단 바 main 클릭 → Create new branch |
| 브랜치 이동 | `git checkout feature-login` | 하단 바 클릭 → 목록에서 선택 |
| 만들면서 이동 | `git checkout -b feature-login` | 생성 시 자동 이동 |

기능이 끝나면 `main` 에 합친다.

```bash
# 1. main 브랜치로 이동
git checkout main

# 2. 기능 브랜치를 main에 합치기
git merge feature-login

# 3. 합친 결과를 GitHub에 올리기
git push
```

같은 줄을 동시에 고쳐 충돌이 나면 에디터의 **Accept Current**(내 코드) / **Accept Incoming**(상대 코드) 중 하나를 고르고 다시 커밋한다.

팀 프로젝트에서는 `main` 에 직접 push 하지 않는다. `pull → 브랜치 생성 → 코딩 → 브랜치 push → GitHub 에서 Pull Request → 리뷰 → Merge` 순서다.

```bash
# 1. 출근 후 최신 코드 받기
git checkout main
git pull

# 2. 오늘 작업용 브랜치 만들기
git checkout -b feature-login

# 3. 작업 완료 후 커밋
git add .
git commit -m "feat: 로그인 페이지 구현"

# 4. 내 브랜치를 GitHub에 올리기
git push origin feature-login

# 5. GitHub 웹사이트에서 Pull Request 생성
# → 팀원 리뷰 → 승인 → Merge 버튼 클릭!
```

출처: git-guide §브랜치: 안전한 협업의 핵심

## 상태 확인과 간단한 되돌리기

```bash
git status          # 현재 변경된 파일 목록 보기
git log --oneline    # 커밋 히스토리 간략히 보기
git remote -v        # 연결된 GitHub 주소 확인
git branch           # 현재 브랜치 목록 보기
git diff             # 수정된 내용 상세 비교
```

자주 쓰는 복구: 커밋 메시지를 잘못 썼으면 `git reset --soft HEAD~1`, 수정을 버리려면 `git checkout -- 파일명`, 주소를 잘못 연결했으면 `git remote set-url origin 새주소`, add 를 취소하려면 `git reset HEAD 파일명`. `git push --force` 는 협업 중 남의 코드를 덮어쓸 수 있으니 혼자일 때만 쓴다.

커밋·푸시 단계별 되돌리기와 로컬·원격이 갈라진 상황은 [Git 되돌리기와 갈라짐(diverge) 복구](../t/git-undo-recovery.html) 에서 따로 다룬다.

출처: git-guide §실수 복구: "되돌리기" 모음, git-guide §상태 확인 명령어

## 원문과 다른 점

| 무엇을 | 채택 | 대신 | 이유 |
|---|---|---|---|
| "GitHub 저장소는 반드시 빈 저장소로" 라는 조건 | git-methods-comparison — Local-First 에만 해당 | git-guide — 모든 경우의 규칙처럼 서술 | git-guide 는 Local-First 만 다루므로 그 안에서는 맞다. 두 문서를 나란히 놓으면 Remote-First 에서는 README·.gitignore 를 체크해도 된다는 점이 드러나 조건부로 고쳐 썼다 |
| 최초 세팅의 기본 권장 방식 | git-methods-comparison — Remote-First 권장 | git-guide — Local-First 절차만 제시 | 비교 문서가 두 방식을 모두 놓고 이유를 들어 권장했다. git-guide 의 절차는 Local-First 항목으로 그대로 살렸다 |

## 근거 문서

- git-guide — 멀티 PC 개발자를 위한 Git & GitHub 완벽 가이드 (2026-02-18)
- git-methods-comparison — GitHub 저장소 연결 방법 비교: Remote-First vs Local-First (2026-02-18)
