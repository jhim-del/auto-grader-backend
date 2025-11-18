# 프롬프트 경진대회 자동 평가 플랫폼

GPT-4o 기반 자동 채점 시스템 - 완전체 버전

## 🚀 기능

### ✅ 구현 완료
1. **대회 관리**
   - 대회 생성 및 조회
   - 과제 등록 (프롬프트 기반)
   
2. **참가자 관리**
   - CSV 파일 업로드 (name, email, student_id)
   - 참가자 목록 조회
   
3. **제출물 관리**
   - ZIP 파일 업로드 (participantname_assignmentname.txt)
   - 제출물 목록 조회
   
4. **자동 채점**
   - GPT-4o 기반 평가 (3회 실행 평균)
   - 백그라운드 작업 처리
   - 실시간 진행 상황 모니터링
   
5. **리더보드**
   - 실시간 순위 표시
   - 참가자별 평균 점수
   
6. **분석 리포트** ⭐ NEW
   - 전체 통계 (평균, 중앙값, 표준편차)
   - 점수 분포 차트
   - 과제별 통계 차트
   - 상위 10명 순위

### 🎨 프론트엔드
- **완전한 웹 UI** (Railway 단일 도메인)
- **색상 테마**: #FA0030, #93E6F5, #850028
- **폰트**: Pretendard
- **반응형 디자인**
- **비개발자 친화적**

## 📋 API 엔드포인트

### Competition
- `POST /competitions` - 대회 생성
- `GET /competitions` - 대회 목록
- `GET /competitions/{id}` - 대회 상세

### Assignments
- `POST /competitions/{id}/assignments` - 과제 생성
- `GET /competitions/{id}/assignments` - 과제 목록

### Participants
- `POST /competitions/{id}/participants/upload` - CSV 업로드
- `GET /competitions/{id}/participants` - 참가자 목록

### Submissions
- `POST /competitions/{id}/submissions/upload` - ZIP 업로드
- `GET /competitions/{id}/submissions` - 제출물 목록

### Grading
- `POST /competitions/{id}/grade` - 채점 시작
- `GET /competitions/{id}/grading-status` - 진행 상황

### Leaderboard
- `GET /competitions/{id}/leaderboard` - 순위표

### Report ⭐ NEW
- `GET /competitions/{id}/report` - 분석 리포트

### Frontend
- `GET /app` - 웹 UI

## 🔧 Railway 배포

### 환경 변수
```
OPENAI_API_KEY=sk-...
PORT=8000
```

### 빌드 설정
- Build Command: (자동)
- Start Command: `python main.py`

## 📁 파일 구조

```
.
├── main.py              # FastAPI 메인 애플리케이션
├── grading_engine.py    # GPT-4o 채점 엔진
├── requirements.txt     # Python 의존성
├── static/
│   └── index.html      # 프론트엔드 (완전체)
└── auto_grader.db      # SQLite 데이터베이스
```

## 🎯 사용 방법

1. **Railway에서 프론트엔드 접속**: `/app`
2. **참가자 업로드**: CSV 파일
3. **제출물 업로드**: ZIP 파일
4. **채점 시작**: 버튼 클릭
5. **결과 확인**: 리더보드 & 분석 리포트

## 📊 분석 리포트 기능

- ✅ 전체 통계 (평균, 중앙값, 표준편차, 최저/최고)
- ✅ 점수 분포 막대 그래프
- ✅ 과제별 평균 점수 차트
- ✅ 상위 10명 순위표
- ✅ Chart.js 기반 시각화

## 🚀 배포 완료

Railway에서 자동 배포됨:
- 프론트엔드: `/app`
- API 문서: `/docs`
- Health Check: `/health`
