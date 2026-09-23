# AI 코딩 도구로 웹 앱 개발·배포하기

비개발자가 Claude Code 로 Next.js · Supabase · Vercel 웹 앱을 기획부터 배포까지 끌고 가는 절차와, 그렇게 배포한 서비스를 **운영 중에 안전하게 고치는** 절차를 한 페이지로 정리했다. 앞부분은 처음 만들 때, 뒷부분은 이미 사용자가 있을 때 읽는다.

## 핵심 정리

- 새 앱의 핵심은 **좋은 기획 문서 → AI 에게 정확한 지시 → 반복 수정**. 가장 중요한 단계는 플랜 문서 작성이다.
- `.env.local` 에는 비밀키가 들어 있다. GitHub 에 올리지 않고, 외부에 공유하지 않는다.
- Vercel 배포 후에는 Supabase **Site URL 과 Redirect URLs** 에 배포 URL 을 등록해야 로그인이 된다.
- 운영 중 수정은 **main 을 직접 건드리지 않는다.** feature 브랜치 + 개발용 Supabase 프로젝트 + Vercel Preview 에서 확인한 뒤 PR 을 머지한다.
- 운영용과 개발용은 Supabase 프로젝트도, OAuth 앱도, 환경 변수도 **전부 분리**한다.
- DB 스키마를 바꿨다면 **운영 DB 마이그레이션을 PR 머지보다 먼저** 적용한다. 순서가 바뀌면 없는 컬럼을 참조해 장애가 난다.

## 1부. 처음 만들 때: 10단계

| 단계 | 할 일 | 산출물 / 확인 |
|---|---|---|
| 1 아이디어 구상 | 누가 쓰는가, 어떤 문제를 푸는가, 가장 중요한 기능 3가지 | 메모, 노션, Claude 대화 |
| 2 플랜 문서 작성 | Claude 와 대화하며 기술 스택, DB 스키마, API 명세, 페이지·디렉토리 구조, 스타일 가이드까지 구체화 | 개발 계획서 (.md) |
| 3 Supabase 셋업 | supabase.com 가입 → 새 프로젝트 (리전 Northeast Asia · Tokyo) | Settings → API 의 Project URL, anon key, service_role key |
| 4 환경 변수 설정 | `.env.local` 에 키 작성. GitHub 에 절대 올리지 않음 | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_APP_URL` |
| 5 Claude Code 로 코드 생성 | 플랜 문서 기반 프롬프트(.md)를 전달 | API Routes, 페이지, 컴포넌트, 설정 파일 전체 |
| 6 DB 마이그레이션 적용 | 생성된 SQL 을 Supabase 대시보드 → SQL Editor 에 붙여넣고 Run | Table Editor 에서 테이블 확인. 에러면 Claude Code 에 전달 |
| 7 로컬 실행 테스트 | `npm install` → `npm run dev` → `localhost:3000` | 핵심 기능과 모바일 레이아웃 |
| ⟳ 수정·반복 | 문제를 구체적으로 설명해 Claude Code 에 수정 요청 | 5→7 을 문제가 없을 때까지 반복 |
| 8 GitHub 저장소 생성 | New repository → Private, README·.gitignore 체크 해제(빈 상태) → 프로젝트 폴더에서 `git init` | 빈 저장소 |
| 9 GitHub 푸시 | 아래 명령으로 첫 업로드. 이후에는 `add → commit → push` | 변경 이력 기록 시작 |
| 10 Vercel 배포 | Vercel 가입 → GitHub 저장소 Import → 환경 변수 등록 → Deploy. 이후 push 마다 자동 배포 | 배포 URL |

9단계의 첫 업로드 명령:

```bash
# 모든 파일을 스테이지에 올리기
git add .

# 첫 번째 커밋
git commit -m "Initial commit"

# 브랜치 이름을 main으로 변경 (Git 기본값이 master일 수 있으므로)
git branch -M main

# GitHub 주소를 origin이라는 이름으로 연결
git remote add origin https://github.com/내이름/프로젝트.git

# GitHub 서버로 전송 (-u는 기본 연결 설정, 최초 1회만)
git push -u origin main
```

**배포 후 필수:** 생성된 URL(예: `https://프로젝트.vercel.app`)을 Supabase 대시보드 → Authentication → URL Configuration 의 **Site URL** 에 등록하고 **Redirect URLs** 에도 추가한다. Supabase Auth 를 쓰면 이 설정 없이는 인증 리다이렉트가 실패한다. `NEXT_PUBLIC_APP_URL` 도 실제 URL 로 바꾼다.

비개발자를 위한 팁: 프롬프트는 한국어로 써도 되고 기술 용어만 영문으로 두면 된다. 한 번에 완성되는 일은 드물다. "이 버튼 색상을 빨간색으로 바꿔줘" 처럼 자연어로 고쳐 달라고 한다. 배포 후 문제는 Vercel 대시보드 → Deployments → Logs 에서 본다.

출처: webapp-development-workflow-guide §사용 도구 한눈에 보기, webapp-development-workflow-guide §비개발자를 위한 핵심 팁

## 2부. 운영 중인 서비스를 고칠 때

이미 사용자가 있는 서비스는 운영 환경(`main` + 운영 Supabase + Vercel Production)을 건드리지 않고 고친다. 흐름은 이렇다.

1. `feature/xxx` 브랜치를 만든다.
2. 개발용 Supabase 프로젝트를 만들어 로컬에서 연결한다.
3. push → Pull Request → Vercel 이 자동으로 Preview 배포를 만든다. Preview URL(개발 DB 연결)에서 확인한다.
4. (필요 시) 운영 DB 마이그레이션 → PR 머지 → Vercel 이 Production 배포 → 운영 반영.

출처: dev-workflow-guide §전체 흐름 한눈에 보기

### 개발 브랜치

```bash
# 최신 상태 동기화
git checkout main
git pull origin main

# 작업용 브랜치 생성 및 이동
git checkout -b feature/새기능이름
```

브랜치 이름은 `feature/add-search`, `fix/login-bug` 처럼 내용을 알 수 있게 짓는다.

출처: dev-workflow-guide §개발 브랜치 생성

### 개발용 Supabase 프로젝트

운영 DB 에서 직접 개발하면 사용자 데이터가 지워지거나 테이블 구조가 깨질 수 있고, Auth 설정이 꼬이면 기존 사용자가 로그인 불가 상태에 빠진다. 개발 전용 프로젝트를 따로 만든다.

- **생성** — supabase.com/dashboard → New Project. 이름은 `myapp-dev` 처럼 구분되게, 리전은 운영과 동일하게.
- **스키마 복제** — 운영 프로젝트 SQL Editor 에서 각 테이블의 DDL 을 뽑아 개발 프로젝트 SQL Editor 에서 실행한다. 사용자 데이터는 가져오지 않는다. 테이블이 적으면 Table Editor 에서 구조를 보고 수동으로 만들어도 된다. (DDL 추출 SQL 은 원문 참조.)
- **더미 데이터** — 개발 프로젝트에 테스트용 행을 넣는다. Auth 를 쓰는 테이블이면 먼저 소셜 로그인 설정을 끝내고 테스트 계정으로 가입한 뒤 그 UUID 를 쓴다 (Authentication → Users).
- **RLS · Functions · Triggers 복제** — 테이블 구조만 복사하면 이것들이 빠진다. 운영 프로젝트에서 `pg_policies`, `information_schema.routines`, `information_schema.triggers` 를 조회해 확인하고 개발 프로젝트에 동일하게 만든다. (조회 SQL 은 원문 참조.)

이 SQL 들을 `supabase/seed.sql` 한 파일로 정리해 두면 개발 프로젝트를 다시 만들 때 한 번에 적용할 수 있다.

출처: dev-workflow-guide §Supabase 개발용 프로젝트 생성, dev-workflow-guide §RLS · Functions · Triggers 복제

### Auth 와 OAuth 개발 환경

이 단계를 빠뜨리면 개발 환경에서 로그인 자체가 안 된다.

**Supabase Auth** — 개발 프로젝트 → Authentication → URL Configuration. Site URL 을 `http://localhost:3000` 으로, Redirect URLs 에 아래 두 개를 등록한다. 운영 프로젝트의 Redirect URLs 는 건드리지 않는다.

```text
# 로컬 개발 환경
http://localhost:3000/**

# Vercel Preview 배포 (와일드카드로 모든 Preview URL 허용)
# 아래의 username 을 본인의 Vercel 계정명으로 교체하세요
https://*-username.vercel.app/**
```

**Google OAuth** — Google Cloud Console 에서 개발 전용 Client ID 를 새로 만들고, 승인된 리디렉션 URI 에 개발 프로젝트의 콜백 URL 을 넣는다. 그 ID/Secret 을 개발 Supabase → Authentication → Providers → Google 에 입력한다.

```text
# 개발 Supabase 프로젝트의 콜백 URL 형식
https://[개발프로젝트-ref].supabase.co/auth/v1/callback
```

`[개발프로젝트-ref]` 는 Settings → API 의 Project URL 서브도메인이다.

**GitHub OAuth** — GitHub Developer Settings → OAuth Apps → New OAuth App (개발 전용). Homepage URL 은 `http://localhost:3000`, callback URL 은 위와 같다. 생성된 ID/Secret 을 개발 Supabase → Providers → GitHub 에 입력한다.

운영용 OAuth 앱에 localhost 를 추가하지 않는다. 보안에 좋지 않고 나중에 정리하기 어렵다.

출처: dev-workflow-guide §Auth & OAuth 개발 환경 설정

### 환경 변수로 운영 / 개발 분리

같은 코드가 환경에 따라 다른 Supabase 프로젝트에 붙도록 한다.

```text
# ── Supabase 개발 프로젝트 ──
NEXT_PUBLIC_SUPABASE_URL=https://[개발프로젝트-ref].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOi...개발키...

# 서버 사이드에서 사용하는 경우
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...개발서비스키...
```

| 환경 | 환경 변수 위치 | Supabase | OAuth 앱 |
|---|---|---|---|
| 로컬 개발 | `.env.local` | 개발 프로젝트 | 개발용 |
| Vercel Preview | Vercel 대시보드 (Preview) | 개발 프로젝트 | 개발용 |
| Vercel Production | Vercel 대시보드 (Production) | 운영 프로젝트 | 운영용 |

Vercel 대시보드 → Settings → Environment Variables 에서 같은 키 이름으로 Production 에는 운영 값, Preview 에는 개발 값을 넣으면 자동으로 분리된다. `SUPABASE_SERVICE_ROLE_KEY` 를 쓰면 이것도 환경별로 나눈다.

출처: dev-workflow-guide §환경 변수로 운영 / 개발 분리

### 로컬 수정과 테스트

`npm run dev` 로 띄우고 `http://localhost:3000` 에서 확인한다. 소셜 로그인, RLS(본인 데이터만 보이는지), DB Functions, Triggers, 새로 고친 기능을 점검한다.

DB 스키마를 바꿔야 하면 개발 프로젝트의 Table Editor 나 SQL Editor 에서 바꾸고, **변경 SQL 을 반드시 따로 기록**한다. `supabase/migrations/` 에 날짜별 파일(예: `20250308_add_category_column.sql`)로 저장해 Git 에 커밋한다. RLS 정책이나 트리거 변경도 함께 기록한다.

출처: dev-workflow-guide §로컬에서 수정 개발 & 테스트

### 푸시 → Vercel Preview 에서 최종 테스트

```bash
git add .
git commit -m "feat: 검색 기능 추가"
git push origin feature/새기능이름
```

`main` 이 아닌 브랜치가 푸시되면 Vercel 이 자동으로 Preview URL(예: `https://myapp-git-feature-xxx-username.vercel.app`)을 만든다. GitHub 에서 **Compare & pull request** → 설명 작성 → Create pull request 하면 PR 페이지 하단에 Preview 링크가 달린다.

Preview 에서 반드시 볼 것: 소셜 로그인(Preview URL 이 Redirect URI 에 등록돼 있어야 동작), 데이터 CRUD(RLS 때문에 로컬과 다를 수 있음), 새 기능. Preview 는 개발 Supabase 에 연결돼 있으므로 운영 데이터는 안전하다.

출처: dev-workflow-guide §커밋 → 푸시 → Vercel Preview로 최종 테스트

### PR 머지 → 운영 배포

**코드만 바뀐 경우** — PR 페이지에서 Merge pull request → Vercel 이 Production 배포 → 운영 사이트 확인.

**DB 스키마 / RLS / Functions / Triggers 가 바뀐 경우** — 순서가 매우 중요하다. 코드가 먼저 배포되면 아직 없는 컬럼·함수를 참조해 장애가 난다.

1. 운영 Supabase → SQL Editor 에서 기록해 둔 마이그레이션 SQL 을 실행한다.
2. Table Editor 에서 정상 적용을 확인한다.
3. 그 다음 PR 을 머지한다.
4. Production 배포 뒤 운영 사이트에서 최종 확인한다.

```sql
-- 개발 시 기록해둔 마이그레이션 SQL을 그대로 실행
-- 예: supabase/migrations/20250308_add_category_column.sql

ALTER TABLE posts
ADD COLUMN category text DEFAULT 'general';

-- RLS 정책 변경이 있었다면 함께 실행
-- Functions/Triggers 변경이 있었다면 함께 실행
```

출처: dev-workflow-guide §PR 머지 → 운영 배포

### 배포 전 체크리스트

```text
□  feature 브랜치에서 작업했는가
□  .env.local은 개발 Supabase를 가리키는가
□  운영 Supabase에 직접 연결한 적이 없는가
□  로컬에서 주요 기능 테스트를 완료했는가
□  Vercel Preview URL에서 정상 동작을 확인했는가
□  PR을 생성하고 변경 내용을 최종 검토했는가
```

Auth 를 쓰면 개발 Supabase 의 Redirect URL, 개발용 OAuth 앱의 콜백 URL, Preview 에서의 소셜 로그인과 RLS 를 추가로 확인한다. DB 를 바꿨으면 마이그레이션 SQL·RLS·Functions·Triggers 변경을 기록했는지, 운영 DB 에 **머지 전에** 적용하고 확인했는지 본다.

출처: dev-workflow-guide §배포 전 체크리스트

## 원문과 다른 점

| 무엇을 | 채택 | 대신 | 이유 |
|---|---|---|---|
| 두 문서의 관계 | 1부(신규) → 2부(운영 중 수정) 순서로 이어 붙임 | — | 같은 스택의 다른 단계를 다루므로 충돌은 없다. 1부의 10단계 표는 원문의 카드 형식을 표로 바꾼 것이고 내용은 그대로다 |
| 긴 SQL (DDL 추출, RLS·Functions·Triggers 조회, 정책 생성 예시) | 본문에 싣지 않고 원문 링크로 대체 | dev-workflow-guide 의 SQL 블록 6개 | 지침 5(긴 코드는 가리킨다). 필요할 때 출처 링크로 원문의 해당 절에서 복사한다 |

## 근거 문서

- dev-workflow-guide — 운영 중 수정 개발 & 배포 가이드 — Next.js · Supabase · Vercel (2026-03-08)
- webapp-development-workflow-guide — 웹 앱 개발 워크플로우 가이드 (2026-03-15)
