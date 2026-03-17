# 쿠팡 모니터링 대시보드 배포 가이드 (GitHub + Vercel + Neon)

## 개요

- **GitHub**: 소스 저장소 (이미 연동됨)
- **Vercel**: 프론트(대시보드) 또는 전체 앱 배포
- **Neon**: PostgreSQL (현재 앱은 DB 미사용, 추후 확장 시 사용)

이 프로젝트는 **Flask 백엔드(API) + HTML/JS 대시보드** 구조라서, API 서버가 반드시 필요합니다. 아래 두 가지 중 하나를 선택하면 됩니다.

---

## 방식 1: Vercel + Serverless API (전부 Vercel에 배포)

Vercel에 대시보드와 API를 모두 올리는 방법입니다. 엑셀 파일은 저장소에 포함해 두면 배포 시 함께 올라갑니다.

### 1) 사전 준비

- GitHub 저장소에 이 프로젝트 푸시
- [Vercel](https://vercel.com) 로그인 후 해당 저장소 Import

### 2) Vercel 프로젝트 설정

- **Root Directory**: `3_쿠팡 모니터링` (또는 이 프로젝트가 있는 하위 폴더)
- **Framework Preset**: Other
- **Build Command**: 비움 (또는 `pip install -r requirements.txt` 등 필요 시)
- **Output Directory**: 비움
- **Install Command**: `pip install -r requirements.txt` (선택)

### 3) Serverless API 구성

Vercel은 요청별로 함수를 실행하므로, Flask 앱을 그대로 쓰려면 진입점을 하나 두는 방식이 필요합니다.

- **api/** 폴더에 진입용 파일 추가 (예: `api/index.py` 또는 `api/[[...path]].py`)
- 그 안에서 Flask `app`을 import 하고, 들어온 요청을 WSGI 규격으로 넘겨 처리하도록 래퍼 작성
- `vercel.json`에서 라우팅 설정:
  - `/` → 대시보드 HTML
  - `/api/*` → 위에서 만든 API 함수로 전달

자세한 코드 예시는 [Vercel Python 문서](https://vercel.com/docs/functions/serverless-functions/runtimes#python)와 “Flask on Vercel” 검색 결과를 참고하면 됩니다.  
(동일 앱을 그대로 쓰려면 `vercel-wsgi` 같은 패키지로 WSGI 래퍼를 두는 방식이 일반적입니다.)

### 4) 환경 변수 (선택)

- 네이버 뉴스 API: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`  
  Vercel 대시보드 → Project → Settings → Environment Variables 에 추가

---

## 방식 2: 백엔드는 Railway/Render, 프론트는 Vercel (권장)

API는 항상 켜져 있는 서버에서, 대시보드는 Vercel에서 제공하는 구성입니다.

### Step 1: Flask 백엔드 배포 (Railway 또는 Render)

**Railway 예시**

1. [railway.app](https://railway.app) 로그인 → GitHub 연동
2. New Project → Deploy from GitHub repo → 이 저장소 선택
3. Root Directory를 `3_쿠팡 모니터링` 으로 지정
4. 설정:
   - **Start Command**: `python app.py` 또는 `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
   - **Port**: Railway/Render가 부여하는 `PORT` 환경 변수 사용 (보통 자동 주입)
5. 배포 후 생성된 URL 확인 (예: `https://xxx.railway.app`)

**Render 예시**

1. [render.com](https://render.com) 로그인 → GitHub 연동
2. New → Web Service → 저장소 선택
3. Root Directory: `3_쿠팡 모니터링`
4. Build: `pip install -r requirements.txt`
5. Start: `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
6. 배포 후 URL 확인 (예: `https://xxx.onrender.com`)

**중요**: 엑셀 파일(`쿠팡 일간 결제액 모니터링.xlsx`, `쿠팡 WAU 모니터링.xlsx`)은 저장소에 포함해 두어야 배포된 서버에서 읽을 수 있습니다.

### Step 2: 대시보드에서 API 주소 지정

배포된 백엔드 URL을 쓰려면, 대시보드가 해당 URL로 API 요청을 보내야 합니다.

- **같은 도메인에서 서빙하는 경우** (Flask가 HTML과 API를 함께 서빙):  
  별도 설정 없이 상대 경로 `/api/...` 그대로 사용하면 됩니다. (방식 1에서 전부 Flask로 서빙할 때와 동일)

- **프론트만 Vercel, API는 Railway/Render인 경우**:
  - `templates/dashboard.html` 안의 `const API = '/api'` 를 백엔드 URL로 변경  
    예: `const API = 'https://xxx.railway.app/api'`
  - Vercel에서 빌드 시 환경 변수로 API URL을 넣고, HTML에 주입하는 방식으로 설정할 수 있습니다.

### Step 3: Vercel에 프론트 배포 (선택)

- 대시보드만 정적로 서빙하려면: `templates/dashboard.html` 내용을 복사해 프로젝트 루트에 `index.html` 로 두고, Vercel에서 해당 폴더를 정적 사이트로 배포합니다.
- 이때 위에서 정한 API URL이 `index.html` 내부에 반영되어 있어야 합니다.

---

## Neon (PostgreSQL) 사용

현재 이 앱은 **DB를 사용하지 않습니다**. 데이터는 엑셀 파일과 메모리/캐시로만 처리됩니다.

- **나중에** 로그 저장, 사용자 설정, 메타데이터 저장 등을 넣을 때:
  1. [Neon](https://neon.tech)에서 PostgreSQL 프로젝트 생성
  2. 연결 문자열(Connection String) 복사
  3. Railway/Render(또는 사용하는 백엔드)의 환경 변수에 `DATABASE_URL` 등으로 설정
  4. Flask 앱에서 `DATABASE_URL`을 읽어 SQLAlchemy/psycopg2 등으로 DB 연결 후 사용

지금 단계에서는 GitHub + Vercel만으로도 배포 가능하고, Neon은 DB 기능을 추가할 때 연동하면 됩니다.

---

## 요약 체크리스트

| 항목 | 내용 |
|------|------|
| GitHub | 저장소 푸시 후 Vercel/Railway/Render와 연동 |
| 엑셀 | `쿠팡 일간 결제액 모니터링.xlsx`, `쿠팡 WAU 모니터링.xlsx` 를 repo에 포함 |
| 포트 | 로컬은 `app.py` 에서 `port=5000` (또는 5001). 배포 시 Railway/Render는 `PORT` 사용 |
| 뉴스 API | 배포 환경에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 설정 시 뉴스 표시 가능 |
| Neon | DB 기능 추가 시 Neon PostgreSQL 생성 후 `DATABASE_URL` 연결 |

---

## 로컬에서 포트 충돌 시

맥에서 5000 포트가 이미 쓰일 때 (예: AirPlay):

```bash
# app.py 마지막 줄을 port=5001 로 바꾼 뒤
.venv/bin/python app.py
# 브라우저: http://localhost:5001
```

이렇게 하면 GitHub·Vercel·Neon을 활용한 배포와 로컬 실행을 모두 정리할 수 있습니다.
