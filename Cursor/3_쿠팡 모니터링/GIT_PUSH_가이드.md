# 코드 수정 후 Git 푸시로 배포하기

코드를 수정한 뒤 GitHub에 푸시하면, Vercel이 자동으로 새 배포를 진행합니다.

> **참고**: Git 루트가 `/Users/user` 이므로, `git add` 시 프로젝트 경로를 포함해야 합니다.

---

## 1. 기본 배포 흐름 (터미널)

```bash
cd /Users/user
```

```bash
git add "Cursor/3_쿠팡 모니터링/src/excel_loader.py" "Cursor/3_쿠팡 모니터링/templates/dashboard.html" "Cursor/3_쿠팡 모니터링/GIT_PUSH_가이드.md"
```

```bash
git commit -m "WoW 최신일(맨 아래 행) 기준 표시, 주석 보완"
```

```bash
git push origin main
```

**한 번에 실행:**
```bash
cd /Users/user && git add "Cursor/3_쿠팡 모니터링/src/excel_loader.py" "Cursor/3_쿠팡 모니터링/templates/dashboard.html" "Cursor/3_쿠팡 모니터링/GIT_PUSH_가이드.md" && git commit -m "WoW 최신일(맨 아래 행) 기준 표시, 주석 보완" && git push origin main
```

> **커밋 메시지 예시**
> - `WAU 차트 Y축 최대값 3000 고정, 상단 버튼 4개로 변경`
> - `뉴스 수집기 로직 개선`
> - `대시보드 UI 수정`

---

## 2. 변경 사항만 선택해서 푸시하기

전체가 아니라 특정 파일만 커밋하고 싶을 때:

```bash
cd "/Users/user/Cursor/3_쿠팡 모니터링"

# 스테이징할 파일만 지정
git add src/news_collector.py templates/dashboard.html

git commit -m "변경 내용 요약"
git push origin main
```

---

## 3. 푸시 전 확인

### 3-1. 상태 확인
```bash
git status
```
- 수정된 파일 목록 확인
- `.env`, `config.yaml` 등 민감한 파일이 포함되지 않았는지 확인 (`.gitignore`에 있어야 함)

### 3-2. 변경 내용 미리보기
```bash
git diff
```

---

## 4. 푸시 후 확인

1. **GitHub**: [github.com/onlyhana23-creator/hana](https://github.com/onlyhana23-creator/hana) 에서 커밋 반영 여부 확인
2. **Vercel**: [vercel.com](https://vercel.com) 대시보드 → 프로젝트 → **Deployments** 에서 자동 빌드/배포 진행 확인
3. 배포 완료 후 사이트 URL에서 실제 반영 여부 확인

---

## 5. 자주 쓰는 명령어 모음

| 명령어 | 설명 |
|--------|------|
| `git status` | 현재 변경/스테이징 상태 확인 |
| `git add .` | 모든 변경 파일 스테이징 |
| `git add 파일경로` | 특정 파일만 스테이징 |
| `git commit -m "메시지"` | 스테이징된 내용 커밋 |
| `git push origin main` | `main` 브랜치를 원격 저장소로 푸시 |
| `git pull origin main` | 원격 저장소에서 최신 코드 가져오기 (푸시 전 동기화) |

---

## 6. 문제 해결

### 푸시 거부 (rejected)
- 다른 곳에서 이미 푸시한 커밋이 있을 수 있음
```bash
git pull origin main
# 충돌 해결 후
git push origin main
```

### 커밋 취소
- 방금 한 커밋만 취소 (변경 내용은 유지):
```bash
git reset --soft HEAD~1
```

### 스테이징 취소
```bash
git restore --staged .
# 또는 특정 파일만: git restore --staged 파일경로
```
