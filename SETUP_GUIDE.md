# 🚀 WAFL 설정 가이드

## OpenAI API 키 설정 및 사용법

### 1단계: OpenAI API 키 발급

1. **OpenAI 계정 생성**
   - https://platform.openai.com/signup 에서 회원가입

2. **API 키 발급**
   - https://platform.openai.com/api-keys 접속
   - "Create new secret key" 클릭
   - 키 이름 입력 후 생성
   - **⚠️ 중요: 생성된 키는 한 번만 표시되므로 안전한 곳에 저장하세요**

3. **과금 설정 (필요 시)**
   - https://platform.openai.com/account/billing/overview
   - 신용카드 등록 (무료 크레딧 소진 후 과금)

### 2단계: API 키 설정

프로젝트 루트의 `.env` 파일을 열어 API 키를 입력합니다:

```bash
# .env 파일 수정
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3단계: 서비스 재시작

```bash
# 기존 컨테이너 중지
docker compose down

# 이미지 재빌드 및 시작
docker compose build wafl-scraping-server wafl-scraping-worker
docker compose up -d
```

---

## 📊 리뷰 요약 페이지 사용법

### 1. 스크래핑 실행

```bash
# 방법 1: API 직접 호출
curl -X POST "http://localhost:58001/api/scraping/start" \
  -H "Content-Type: application/json" \
  -d '{"store_id": 1}'

# 방법 2: 대시보드에서 버튼 클릭
```

### 2. 요약 페이지 접속

스크래핑 완료 후 다음 URL로 접속:
```
http://localhost:58000/store/{store_id}/summary
```

예시:
```
http://localhost:58000/store/1/summary
```

### 3. 요약 내용

페이지에서 다음 정보를 확인할 수 있습니다:

#### 📊 인기 메뉴 TOP 3
- 각 메뉴의 언급 횟수
- 고객들이 좋아하는 이유 (맛, 양, 가성비 등)
- 대표 리뷰 인용

#### 🔥 최근 트렌드
- 요근래 가장 인기 있는 메뉴
- 인기 상승 이유 분석
- 계절성/트렌드 고려

#### 🤝 메뉴 페어링 추천
- 함께 주문하면 좋은 메뉴 조합
- 페어링 이유 설명
- 실제 고객 리뷰 인용

#### ⏰ 시간대별 선호도
- 점심 시간대 인기 메뉴
- 저녁 시간대 인기 메뉴
- 주말/평일 차이 (추정)

#### 💡 운영 개선 제안
- 추가하면 좋을 메뉴
- 개선이 필요한 메뉴
- 프로모션 아이디어

---

## 🔄 요약 재생성

요약 페이지의 "🔄 요약 재생성" 버튼을 클릭하면:
- 최신 리뷰 데이터로 새로운 분석 생성
- 약 10-30초 소요 (리뷰 개수에 따라 다름)
- 자동으로 페이지 새로고침

---

## 💰 비용 정보

### OpenAI GPT-4o-mini 가격 (2025년 기준)
- **입력**: $0.150 / 1M tokens
- **출력**: $0.600 / 1M tokens

### 예상 비용 (리뷰 50개 기준)
- 1회 요약 생성: 약 $0.01 ~ $0.03
- 월 100개 매장 요약: 약 $1 ~ $3

**무료 크레딧**: 신규 가입 시 $5 무료 크레딧 제공 (3개월간 유효)

---

## 🐛 문제 해결

### API 키 오류
```
OpenAI API 키가 설정되지 않았습니다
```
**해결**: `.env` 파일에 올바른 API 키 입력 후 재시작

### 요약 생성 실패
```
OpenAI API 호출 실패
```
**원인**:
1. API 키가 만료되었거나 잘못됨
2. 크레딧 부족
3. 네트워크 오류

**해결**:
1. API 키 확인
2. https://platform.openai.com/account/usage 에서 크레딧 확인
3. 로그 확인: `docker compose logs wafl-scraping-worker`

### 요약이 표시되지 않음
```
요약이 아직 생성되지 않았습니다
```
**원인**: 스크래핑이 완료되지 않았거나 리뷰가 없음

**해결**:
1. 스크래핑 상태 확인
2. 리뷰 개수 확인
3. 요약 재생성 버튼 클릭

---

## 📝 API 키 없이 사용

API 키가 없어도 기본 통계 요약은 생성됩니다:
- 총 리뷰 수
- 재방문율
- 긍정/부정 키워드 개수
- 전반적인 sentiment

단, 고급 분석(메뉴 페어링, 트렌드 등)은 OpenAI API가 필요합니다.

---

## 🔗 관련 링크

- [OpenAI Platform](https://platform.openai.com/)
- [OpenAI API 문서](https://platform.openai.com/docs/api-reference)
- [GPT-4o-mini 가격](https://openai.com/api/pricing/)
