# 쿠팡 모니터링 (주간)

네이버 멤버십 기획용 **쿠팡 일간 결제액**·**WAU(Android+IOS 사용자 수)**를 엑셀에서 읽어 주차별로 정리하고, 위키용 보고서를 생성합니다.

---

## 데이터 소스 (엑셀만 업데이트하면 됨)

| 파일 | 내용 |
|------|------|
| **쿠팡 일간 결제액 모니터링.xlsx** | 일간 순 결제금액 → 주차별 합산(억 원)으로 집계 |
| **쿠팡 WAU 모니터링.xlsx** | **Android+IOS 사용자 수**만 사용 (WAU). 주간 데이터 |

두 엑셀 파일을 프로젝트 루트에 두고, 앞으로 여기만 업데이트하면 됩니다.

---

## 대시보드 실행 (웹)

결제·WAU·뉴스를 한 화면에서 보려면 대시보드를 실행하세요.

```bash
# 가상환경 활성화 후
pip install -r requirements.txt
python app.py
```

브라우저에서 **http://localhost:5000** 에 접속하면 됩니다.

- **상단**: 쿠팡 일간 결제액 (순 결제금액 / 총 결제횟수 / 총 결제자) + 직전일 대비 증가율, 최근 30일 차트 (일간 ↔ 주간 평균 전환)
- **중단**: 쿠팡 WAU(Android+iOS), 주차 조정 버튼(이전 주/다음 주)
- **하단**: 쿠팡 관련 뉴스 표(기사제목 / 링크)

주차 표기는 **YY/MM/DD 주차** (해당 주 월요일 기준)로 통일되어 있습니다.

**배포 (GitHub / Vercel / Neon)**: [DEPLOY.md](DEPLOY.md) 참고.

---

## 사용 방법 (CLI 보고서)

```bash
# 가상환경
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 최근 주차 보고서 생성 (reports/ 에 저장)
python -m src.cli

# 특정 주차
python -m src.cli 2026-10

# 내용만 출력 (위키 붙여넣기용)
python -m src.cli 2026-10 --print
```

생성되는 보고서에는 다음이 포함됩니다.

1. **주차별 쿠팡 결제액** – 일간 결제액을 주 단위로 합산한 값(억 원)
2. **주차별 WAU** – Android+IOS 사용자 수만(만 명)
3. **(선택) 쿠팡 관련 뉴스** – `config.yaml`에 네이버 검색 API를 넣으면 해당 주차 뉴스 요약 추가

---

## 위키에 매주 정리

- Cursor에서 **「이번 주 쿠팡 모니터링 위키에 올려줘」** 또는  
  **「reports/coupang_monitor_2026-10.md 내용으로 위키 페이지 만들어줘」** 요청 시  
  생성된 마크다운으로 Confluence 페이지 생성·업데이트 가능합니다.
- `config.example.yaml`을 복사해 `config.yaml`을 만든 뒤 `confluence.space_key`에 스페이스 키를 넣으면 됩니다.

---

## 엑셀 형식 요약

- **결제액 엑셀**: 시트 `주요지표`, 6행부터 일자(기간)·순 결제금액(원) 컬럼 사용. 일자 기준으로 주차(월요일 시작) 자동 집계.
- **WAU 엑셀**: 첫 번째 시트에서 `날짜`, `Android+IOS 사용자 수` 컬럼을 찾아 사용. 날짜 형식은 `YYYY-MM-DD ~ YYYY-MM-DD` (주간 구간).

필요 시 `config.yaml`의 `paths.payment_excel`, `paths.wau_excel`로 파일명을 바꿀 수 있습니다.
