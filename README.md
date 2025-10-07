# 🍽️ WAFL (We Are Food Lovers)

네이버 플레이스 음식점 정보 자동 스크래핑 및 AI 리뷰 분석 시스템

---

## 📋 목차

1. [프로젝트 개요](#-프로젝트-개요)
2. [시스템 아키텍처](#-시스템-아키텍처)
3. [주요 기능](#-주요-기능)
4. [기술 스택](#-기술-스택)
5. [시스템 구조](#-시스템-구조)
6. [데이터베이스 스키마](#-데이터베이스-스키마)
7. [API 문서](#-api-문서)
8. [설치 및 실행](#-설치-및-실행)
9. [사용 가이드](#-사용-가이드)
10. [문제 해결](#-문제-해결)

---

## 🎯 프로젝트 개요

WAFL은 음식점 운영자를 위한 **네이버 플레이스 데이터 자동화 수집 및 분석 시스템**입니다.

### 핵심 가치

- ✅ **자동화**: 수작업으로 하던 매장 정보, 메뉴, 리뷰 수집 자동화
- 🤖 **AI 분석**: GPT-4를 활용한 리뷰 인사이트 도출
- 📊 **데이터 기반 의사결정**: 메뉴 페어링, 트렌드, 시간대별 선호도 분석
- 🔄 **실시간 동기화**: 네이버 플레이스와 실시간 데이터 동기화

### 해결하는 문제

1. **매장 정보 수동 관리의 번거로움**
   - 네이버 플레이스 정보를 일일이 확인하고 입력
   - 메뉴 변경 시 수동 업데이트 필요

2. **리뷰 분석의 어려움**
   - 수백 개의 리뷰를 일일이 읽고 분석
   - 트렌드와 고객 선호도 파악 시간 소요

3. **데이터 기반 의사결정 부재**
   - 어떤 메뉴가 인기 있는지 감으로 판단
   - 메뉴 조합 추천 데이터 부족

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        사용자 (브라우저)                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway (Nginx)                           │
│                    Port: 50080                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Web Server   │ │ Scraping API │ │ Static Files (Media) │    │
│  │ :8000        │ │ :8001        │ │ /media/*             │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘    │
└──────────┬────────────────┬────────────────────────────────────┘
           │                │
           │                └──────────────────┐
           ▼                                   ▼
┌──────────────────────┐         ┌─────────────────────────────┐
│   Web Server         │         │   Scraping Server           │
│   (FastAPI)          │◄────────┤   (FastAPI)                 │
│   Port: 8000         │ Proxy   │   Port: 8001                │
│                      │         │                             │
│ • 사용자 인터페이스   │         │ • 스크래핑 작업 관리         │
│ • 매장 등록/관리     │         │ • Celery 태스크 시작         │
│ • 요약 페이지 제공   │         │ • API 엔드포인트 제공        │
└──────────┬───────────┘         └──────────┬──────────────────┘
           │                                │
           │                                │ Task Queue
           │                                ▼
           │                     ┌─────────────────────────────┐
           │                     │   Celery Worker             │
           │                     │   (Background Jobs)         │
           │                     │                             │
           │                     │ • 웹 스크래핑 (Selenium)    │
           │                     │ • 이미지 다운로드           │
           │                     │ • AI 리뷰 요약 생성         │
           │                     └──────────┬──────────────────┘
           │                                │
           │                                │ OpenAI API
           │                                ▼
           │                     ┌─────────────────────────────┐
           │                     │   OpenAI GPT-4o-mini        │
           │                     │                             │
           │                     │ • 리뷰 분석 및 요약         │
           │                     │ • 메뉴 페어링 추천          │
           │                     │ • 트렌드 분석               │
           │                     └─────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         공통 인프라                              │
│                                                                  │
│  ┌──────────────────────┐         ┌───────────────────────┐    │
│  │   PostgreSQL         │         │   Redis               │    │
│  │   Port: 55432        │         │   Port: 56379         │    │
│  │                      │         │                       │    │
│  │ • 매장 정보          │         │ • Celery 메시지 큐    │    │
│  │ • 메뉴               │         │ • 태스크 상태 관리    │    │
│  │ • 리뷰               │         │                       │    │
│  │ • 리뷰 요약          │         │                       │    │
│  └──────────────────────┘         └───────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

                    ▲ 스크래핑 대상 ▲
                    │              │
        ┌───────────┴──────────────┴───────────┐
        │     네이버 플레이스 (Naver Place)     │
        │   https://m.place.naver.com/...      │
        └──────────────────────────────────────┘
```

### 데이터 흐름

```
1. 사용자 매장 등록
   User → Web Server → PostgreSQL (매장 정보 저장)

2. 스크래핑 시작
   User → Web Server → Scraping API → Redis (Celery Task)
                                    ↓
                              Celery Worker
                                    ↓
                            Selenium (네이버 스크래핑)
                                    ↓
                              PostgreSQL (데이터 저장)

3. AI 요약 생성
   Celery Worker → PostgreSQL (리뷰 조회)
                ↓
           OpenAI API (GPT-4o-mini)
                ↓
           PostgreSQL (요약 저장)

4. 결과 조회
   User → Web Server → Scraping API → PostgreSQL → User
```

---

## ✨ 주요 기능

### 1. 매장 정보 자동 수집

네이버 플레이스에서 다음 정보를 자동으로 수집합니다:

```
📍 기본 정보
├── 매장명
├── 카테고리
├── 주소
├── 전화번호
├── 매장 소개
└── 제공 서비스

🍔 메뉴 정보
├── 메뉴명
├── 가격
├── 설명
├── 추천 여부
└── 메뉴 이미지 (자동 다운로드 및 최적화)

💬 리뷰 정보
├── 리뷰 내용
├── 작성일
└── 재방문 횟수
```

**예시:**
```bash
# 스크래핑 시작
curl -X POST "http://localhost:58001/api/scraping/start" \
  -H "Content-Type: application/json" \
  -d '{"store_id": 1}'

# 진행 상태 확인
curl "http://localhost:58001/api/scraping/status/[task_id]"
```

### 2. AI 기반 리뷰 분석

GPT-4o-mini를 활용하여 리뷰에서 인사이트를 도출합니다:

#### 📊 인기 메뉴 TOP 3
```
1. 비빔냉면 (15회 언급)
   - 고객 선호 이유: 매콤하면서도 깔끔한 맛
   - 대표 리뷰: "비빔냉면은 너무 좋아합니다💕"

2. 물냉면 (12회 언급)
   - 고객 선호 이유: 담백하고 깔끔한 육수
   - 대표 리뷰: "평양냉면의 비주얼이지만 전혀 다른 맛..."

3. 제육 (10회 언급)
   - 고객 선호 이유: 부드러운 식감, 냉면과의 조화
   - 대표 리뷰: "제육은 늘 먹을 때마다 감탄하게 된다"
```

#### 🤝 메뉴 페어링 추천
```
추천 조합 1: 비빔냉면 + 제육
└── 매콤함과 부드러운 식감의 조화
    실제 리뷰: "비빔냉면에 제육 추가해서 먹었습니다😉"

추천 조합 2: 물냉면 + 비빔오이
└── 담백함과 아삭한 식감의 조화
    실제 리뷰: "냉면 위에 제육을 아주 좋아합니다"
```

#### ⏰ 시간대별 선호도
```
점심 (11:00-14:00)
└── 비빔냉면, 물냉면 (시원한 냉면 선호)

저녁 (18:00-21:00)
└── 제육 + 냉면 조합 (술과 함께 즐기는 경향)

주말
└── 가족 단위 방문 증가, 제육+비빔냉면 조합 인기
```

### 3. 대시보드

직관적인 웹 인터페이스로 모든 정보를 한눈에 확인:

```
┌─────────────────────────────────────────────────┐
│  매장 대시보드                                   │
├─────────────────────────────────────────────────┤
│                                                  │
│  [매장 정보] [메뉴] [리뷰] [AI 요약]            │
│                                                  │
│  📊 통계                                         │
│  ├── 총 메뉴: 9개                                │
│  ├── 총 리뷰: 48개                               │
│  └── 재방문율: 39.6%                             │
│                                                  │
│  🍔 메뉴 목록                                    │
│  ┌────────┬────────┬────────┐                   │
│  │ 비빔냉면│ 물냉면  │ 제육   │                   │
│  │ 12,000 │ 12,000 │ 15,000 │                   │
│  └────────┴────────┴────────┘                   │
│                                                  │
│  💡 AI 인사이트                                  │
│  └── "비빔냉면과 제육 조합이 인기 상승 중"       │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## 🛠️ 기술 스택

### Backend
```
FastAPI (Python 3.11)
├── Web Server (사용자 인터페이스)
└── Scraping API (스크래핑 관리)

Celery (분산 태스크 큐)
├── Worker 1: 웹 스크래핑
├── Worker 2: 이미지 처리
└── Worker N: AI 요약 생성
```

### Frontend
```
HTML5 + JavaScript
├── Jinja2 템플릿 엔진
├── Marked.js (Markdown 렌더링)
└── Vanilla JS (프레임워크 없음)
```

### Infrastructure
```
Docker Compose
├── PostgreSQL 15 (데이터 저장)
├── Redis 7 (메시지 큐)
├── Nginx (API Gateway)
└── Selenium + Chrome (웹 스크래핑)
```

### AI/ML
```
OpenAI API
└── GPT-4o-mini
    ├── 리뷰 분석
    ├── 메뉴 추천
    └── 트렌드 예측
```

---

## 🔧 시스템 구조

### 1. Web Server (포트: 8000)

사용자 인터페이스를 제공하는 FastAPI 애플리케이션

**주요 기능:**
- 매장 등록/조회/삭제
- 대시보드 제공
- 스크래핑 서버 API 프록시

**주요 엔드포인트:**
```python
GET  /                              # 메인 페이지
GET  /register                      # 매장 등록 페이지
POST /api/stores/register           # 매장 등록 API
GET  /dashboard                     # 대시보드
GET  /store/{store_id}/detail       # 매장 상세
GET  /store/{store_id}/summary      # AI 요약 페이지
```

**디렉토리 구조:**
```
web-server/
├── main.py                 # FastAPI 앱
├── database.py             # DB 모델
├── templates/              # Jinja2 템플릿
│   ├── base.html
│   ├── index.html
│   ├── dashboard.html
│   ├── store_detail.html
│   └── summary.html
└── Dockerfile
```

### 2. Scraping Server (포트: 8001)

스크래핑 작업을 관리하는 FastAPI 애플리케이션

**주요 기능:**
- Celery 태스크 시작/모니터링
- 스크래핑된 데이터 조회
- 요약 생성 트리거

**주요 엔드포인트:**
```python
POST /api/scraping/start                              # 스크래핑 시작
GET  /api/scraping/status/{task_id}                   # 태스크 상태
GET  /api/scraping/store/{store_id}                   # 매장 데이터 조회
GET  /api/scraping/store/{store_id}/menus             # 메뉴 목록
GET  /api/scraping/store/{store_id}/reviews           # 리뷰 목록
GET  /api/scraping/store/{store_id}/summary           # AI 요약 조회
POST /api/scraping/store/{store_id}/summary/regenerate # 요약 재생성
```

**디렉토리 구조:**
```
scraping-server/
├── main.py                 # FastAPI 앱
├── database.py             # DB 모델
├── celery_app.py           # Celery 설정
├── tasks/
│   └── scraping_tasks.py   # 스크래핑 태스크
├── utils/
│   ├── selenium_driver.py  # Selenium 드라이버
│   ├── image_downloader.py # 이미지 처리
│   └── llm_summarizer.py   # AI 요약 생성
└── Dockerfile
```

### 3. Celery Worker

백그라운드에서 실행되는 스크래핑 및 AI 작업 처리

**태스크 종류:**

```python
# 1. 매장 데이터 스크래핑 (scrape_store_data)
매장 기본 정보 수집
    ↓
메뉴 정보 수집 (이미지 다운로드 포함)
    ↓
리뷰 정보 수집 (최대 50페이지)
    ↓
데이터 검증 및 저장
    ↓
AI 요약 태스크 자동 시작

# 2. AI 리뷰 요약 생성 (generate_review_summary)
리뷰 데이터 조회
    ↓
메뉴 목록 조회
    ↓
GPT-4o-mini 프롬프트 생성
    ↓
OpenAI API 호출
    ↓
마크다운 요약 저장
```

**Celery 설정:**
```python
# celery_app.py
broker_url = 'redis://wafl-redis:6379/0'
result_backend = 'redis://wafl-redis:6379/0'

task_routes = {
    'tasks.scraping_tasks.*': {'queue': 'scraping'},
    'tasks.scraping_tasks.generate_review_summary': {'queue': 'summary'}
}
```

### 4. Selenium Driver

네이버 플레이스 웹 스크래핑을 담당

**주요 기능:**
```python
class SeleniumDriver:
    def __init__(self, headless=True):
        """Chrome 드라이버 초기화"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')      # 헤드리스 모드
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

    def get(self, url):
        """페이지 로드 및 대기"""
        self.driver.get(url)
        time.sleep(3)  # 동적 콘텐츠 로드 대기

    def find_elements(self, by, selector):
        """요소 찾기 (여러 개)"""
        return self.driver.find_elements(by, selector)
```

**스크래핑 예시:**
```python
# 메뉴 정보 수집
menus = driver.find_elements(By.CSS_SELECTOR, 'li.E2jtL')
for li in menus:
    menu_name = li.find_element(By.CSS_SELECTOR, "span.lPzHi").text
    menu_price = li.find_element(By.CSS_SELECTOR, "div.GXS1X em").text
    menu_image = li.find_element(By.CSS_SELECTOR, "img").get_attribute('src')
```

### 5. Image Downloader

메뉴 이미지 다운로드 및 최적화

**처리 과정:**
```
1. 이미지 URL 다운로드
   ├── 네이버 CDN에서 이미지 가져오기
   └── 임시 파일로 저장

2. 이미지 최적화
   ├── Pillow 라이브러리 사용
   ├── 최대 크기: 800x800
   ├── JPEG 품질: 85%
   └── 파일 크기: 평균 100KB 이하

3. 파일 저장
   └── /media/images/stores/{store_id}/menus/{순번}_{해시}.jpg
```

**코드 예시:**
```python
def download_and_save_image(self, image_url, store_id, menu_order):
    # 이미지 다운로드
    response = requests.get(image_url, timeout=10)

    # Pillow로 최적화
    image = Image.open(BytesIO(response.content))
    image.thumbnail((800, 800), Image.Resampling.LANCZOS)

    # 저장
    filename = f"{menu_order}_{random_hash}.jpg"
    filepath = f"/app/media/images/stores/{store_id}/menus/{filename}"
    image.save(filepath, 'JPEG', quality=85, optimize=True)
```

### 6. LLM Summarizer

OpenAI GPT-4o-mini를 활용한 리뷰 요약 생성

**프롬프트 구조:**
```python
prompt = f"""
다음은 한 음식점의 메뉴 목록과 고객 리뷰입니다. 메뉴 중심으로 심층 분석해주세요.

**메뉴 목록:**
- 비빔냉면 (12,000원) - 대표
- 물냉면 (12,000원)
- 제육 (15,000원)

**전체 리뷰 (날짜 포함):**
[2024.03.15] 비빔냉면 맛있어요. 제육도 곁들이면 최고!
[2024.03.14] 물냉면 육수가 정말 깔끔합니다...

다음 구조로 마크다운 형식으로 분석해주세요:

# 🍽️ 메뉴별 리뷰 분석 보고서

## 📊 인기 메뉴 TOP 3
각 메뉴별로:
- 리뷰에서 언급된 횟수
- 고객들이 좋아하는 이유 (맛, 양, 가성비 등 구체적으로)
- 대표 리뷰 인용

## 🔥 최근 트렌드 (요근래 인기 메뉴)
- 날짜를 분석하여 최근 가장 많이 언급되는 메뉴
- 인기 상승 이유 분석

## 🤝 메뉴 페어링 추천
리뷰에서 함께 주문했다고 언급된 메뉴 조합

## ⏰ 시간대별 메뉴 선호도
리뷰의 날짜와 내용을 바탕으로 추정

## 💡 메뉴 운영 개선 제안
- 추가하면 좋을 메뉴
- 개선이 필요한 메뉴
"""
```

**비용 최적화:**
```python
# GPT-4o-mini 사용 (GPT-4 대비 1/60 가격)
model = "gpt-4o-mini"
max_tokens = 3000
temperature = 0.3  # 일관성 있는 분석을 위해 낮은 값

# 예상 비용 (리뷰 50개 기준)
# - 입력: ~2,000 토큰 × $0.150/1M = $0.0003
# - 출력: ~2,000 토큰 × $0.600/1M = $0.0012
# - 총: ~$0.0015 (약 2원)
```

---

## 💾 데이터베이스 스키마

### ERD (Entity Relationship Diagram)

```
┌─────────────────────────┐
│       stores            │
├─────────────────────────┤
│ id (PK)                 │──┐
│ store_name              │  │
│ store_address           │  │
│ business_number (UNIQUE)│  │
│ owner_name              │  │
│ owner_phone             │  │
│ naver_store_url         │  │
│ store_id                │  │
│                         │  │
│ // 스크래핑된 정보      │  │
│ scraped_store_name      │  │
│ scraped_category        │  │
│ scraped_description     │  │
│ scraped_store_address   │  │
│ scraped_phone           │  │
│ scraped_intro           │  │
│ scraped_services        │  │
│                         │  │
│ // 상태 관리            │  │
│ scraping_status         │  │
│ scraping_error_message  │  │
│ created_at              │  │
│ updated_at              │  │
└─────────────────────────┘  │
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│     menus       │  │    reviews      │  │  review_summaries   │
├─────────────────┤  ├─────────────────┤  ├─────────────────────┤
│ id (PK)         │  │ id (PK)         │  │ id (PK)             │
│ store_id (FK)   │  │ store_id (FK)   │  │ store_id (FK)       │
│ menu_name       │  │ content         │  │ summary_md          │
│ price           │  │ review_date     │  │ created_at          │
│ description     │  │ revisit_count   │  └─────────────────────┘
│ recommendation  │  │ created_at      │
│ image_file_path │  └─────────────────┘
│ image_url       │
│ created_at      │
└─────────────────┘

┌─────────────────────┐
│  scraping_tasks     │
├─────────────────────┤
│ id (PK)             │
│ store_id (FK)       │
│ task_id (UNIQUE)    │
│ status              │
│ result              │
│ error_message       │
│ created_at          │
│ updated_at          │
└─────────────────────┘
```

### 테이블 상세

#### 1. stores (매장 정보)

```sql
CREATE TABLE stores (
    id SERIAL PRIMARY KEY,

    -- 사용자 입력 정보
    store_name VARCHAR(255) NOT NULL,
    store_address VARCHAR(500) NOT NULL,
    business_number VARCHAR(50) NOT NULL UNIQUE,
    owner_name VARCHAR(100) NOT NULL,
    owner_phone VARCHAR(20) NOT NULL,
    naver_store_url VARCHAR(500),
    store_id VARCHAR(50),  -- 네이버 스토어 ID

    -- 스크래핑된 정보
    scraped_store_name VARCHAR(255),
    scraped_category VARCHAR(100),
    scraped_description TEXT,
    scraped_store_address VARCHAR(500),
    scraped_directions TEXT,
    scraped_phone VARCHAR(20),
    scraped_sns VARCHAR(500),
    scraped_etc_info TEXT,
    scraped_intro TEXT,
    scraped_services TEXT,

    -- 상태 관리
    scraping_status VARCHAR(50) DEFAULT 'pending',
    -- 상태: pending, in_progress, completed, mismatch, error
    scraping_error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stores_business_number ON stores(business_number);
CREATE INDEX idx_stores_store_id ON stores(store_id);
```

#### 2. menus (메뉴 정보)

```sql
CREATE TABLE menus (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    menu_name VARCHAR(255),
    price VARCHAR(100),
    description TEXT,
    recommendation VARCHAR(100),  -- 예: "대표", "인기" 등
    image_file_path VARCHAR(500),
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_menus_store_id ON menus(store_id);

-- 예시 데이터
INSERT INTO menus (store_id, menu_name, price, recommendation, image_file_path)
VALUES (1, '비빔냉면', '12,000', '대표', '/media/images/stores/1/menus/1_abc123.jpg');
```

#### 3. reviews (리뷰 정보)

```sql
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    review_date VARCHAR(50),      -- 예: "2024.03.15"
    revisit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reviews_store_id ON reviews(store_id);

-- 예시 데이터
INSERT INTO reviews (store_id, content, review_date, revisit_count)
VALUES (1, '비빔냉면 맛있어요!', '2024.03.15', 2);
```

#### 4. review_summaries (AI 요약)

```sql
CREATE TABLE review_summaries (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    summary_md TEXT NOT NULL,  -- Markdown 형식의 요약
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_review_summaries_store_id ON review_summaries(store_id);

-- 예시 데이터
INSERT INTO review_summaries (store_id, summary_md)
VALUES (1, '# 🍽️ 메뉴별 리뷰 분석 보고서\n\n## 📊 인기 메뉴 TOP 3...');
```

#### 5. scraping_tasks (스크래핑 작업 이력)

```sql
CREATE TABLE scraping_tasks (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    task_id VARCHAR(255) UNIQUE,  -- Celery 태스크 ID
    status VARCHAR(50) DEFAULT 'pending',
    -- 상태: pending, started, success, failure
    result TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scraping_tasks_store_id ON scraping_tasks(store_id);
CREATE INDEX idx_scraping_tasks_task_id ON scraping_tasks(task_id);
```

### 데이터 예시

**매장 등록 후 스크래핑 완료 상태:**

```sql
-- stores 테이블
id | store_name | store_address           | scraped_store_name | scraping_status
---+------------+-------------------------+--------------------+-----------------
1  | 돼자옥     | 서울 송파구 마천로...   | 돼자옥             | completed

-- menus 테이블
id | store_id | menu_name   | price   | recommendation
---+----------+-------------+---------+----------------
1  | 1        | 비빔냉면    | 12,000  | 대표
2  | 1        | 물냉면      | 12,000  |
3  | 1        | 제육        | 15,000  |

-- reviews 테이블
id | store_id | content                          | review_date | revisit_count
---+----------+----------------------------------+-------------+--------------
1  | 1        | 비빔냉면 맛있어요!                | 2024.03.15  | 2
2  | 1        | 제육이 부드럽고 좋습니다          | 2024.03.14  | 1

-- review_summaries 테이블
id | store_id | summary_md                                    | created_at
---+----------+-----------------------------------------------+-------------------
1  | 1        | # 🍽️ 메뉴별 리뷰 분석 보고서\n\n...        | 2024-03-15 10:00:00
```

---

## 📡 API 문서

### Web Server API

#### 매장 관리

**1. 매장 등록**
```http
POST /api/stores/register
Content-Type: application/x-www-form-urlencoded

store_name=돼자옥
store_address=서울 송파구 마천로51가길 33
business_number=123-45-67890
owner_name=홍길동
owner_phone=010-1234-5678
naver_store_url=https://naver.me/xxxxx

Response 201:
{
  "message": "매장이 성공적으로 등록되었습니다.",
  "store_id": 1,
  "naver_store_id": "1234567890"
}
```

**2. 매장 목록 조회**
```http
GET /api/stores

Response 200:
[
  {
    "id": 1,
    "store_name": "돼자옥",
    "store_address": "서울 송파구 마천로51가길 33",
    "scraping_status": "completed",
    "created_at": "2024-03-15T10:00:00"
  }
]
```

**3. 매장 상세 조회**
```http
GET /api/stores/1/detail

Response 200:
{
  "store_info": {
    "id": 1,
    "store_name": "돼자옥",
    "scraped_category": "냉면",
    "scraped_phone": "02-1234-5678",
    "scraping_status": "completed"
  },
  "menus": [
    {
      "id": 1,
      "menu_name": "비빔냉면",
      "price": "12,000",
      "recommendation": "대표",
      "image_url": "/media/images/stores/1/menus/1_abc123.jpg"
    }
  ],
  "menu_count": 9,
  "reviews": [
    {
      "id": 1,
      "content": "비빔냉면 맛있어요!",
      "review_date": "2024.03.15",
      "revisit_count": 2
    }
  ],
  "review_count": 48,
  "summary": "# 🍽️ 메뉴별 리뷰 분석 보고서...",
  "summary_status": "completed"
}
```

**4. 매장 삭제**
```http
DELETE /api/stores/1

Response 200:
{
  "message": "매장 '돼자옥'이(가) 성공적으로 삭제되었습니다.",
  "deleted_store_id": 1
}
```

### Scraping Server API

#### 스크래핑 작업

**1. 스크래핑 시작**
```http
POST /api/scraping/start
Content-Type: application/json

{
  "store_id": 1
}

Response 200:
{
  "task_id": "abc123-def456-ghi789",
  "status": "started",
  "message": "스크래핑이 시작되었습니다."
}
```

**2. 태스크 상태 조회**
```http
GET /api/scraping/status/abc123-def456-ghi789

Response 200 (진행 중):
{
  "task_id": "abc123-def456-ghi789",
  "status": "in_progress",
  "progress": 60
}

Response 200 (완료):
{
  "task_id": "abc123-def456-ghi789",
  "status": "completed",
  "result": {
    "store_id": 1,
    "status": "completed",
    "menu_count": 9,
    "review_count": 48
  }
}
```

#### 데이터 조회

**3. 메뉴 목록 조회**
```http
GET /api/scraping/store/1/menus?skip=0&limit=100

Response 200:
{
  "store_id": 1,
  "menus": [
    {
      "id": 1,
      "menu_name": "비빔냉면",
      "price": "12,000",
      "description": "",
      "recommendation": "대표",
      "image_url": "/media/images/stores/1/menus/1_abc123.jpg",
      "created_at": "2024-03-15T10:00:00"
    }
  ],
  "total": 9
}
```

**4. 리뷰 목록 조회**
```http
GET /api/scraping/store/1/reviews?skip=0&limit=50

Response 200:
{
  "store_id": 1,
  "reviews": [
    {
      "id": 1,
      "content": "비빔냉면 맛있어요!",
      "review_date": "2024.03.15",
      "revisit_count": 2,
      "created_at": "2024-03-15T10:00:00"
    }
  ],
  "total": 48
}
```

**5. AI 요약 조회**
```http
GET /api/scraping/store/1/summary

Response 200:
{
  "store_id": 1,
  "summary": "# 🍽️ 메뉴별 리뷰 분석 보고서\n\n## 📊 인기 메뉴 TOP 3...",
  "created_at": "2024-03-15T10:30:00",
  "status": "completed"
}
```

**6. AI 요약 재생성**
```http
POST /api/scraping/store/1/summary/regenerate

Response 200:
{
  "task_id": "xyz789-abc123-def456",
  "message": "리뷰 요약 재생성이 시작되었습니다.",
  "store_id": 1
}
```

### 에러 응답

```http
Response 400 (잘못된 요청):
{
  "detail": "올바른 네이버 스토어 URL을 입력해주세요."
}

Response 404 (찾을 수 없음):
{
  "detail": "매장을 찾을 수 없습니다."
}

Response 500 (서버 오류):
{
  "detail": "등록 중 오류가 발생했습니다: ..."
}

Response 503 (서비스 사용 불가):
{
  "detail": "스크래핑 서버에 연결할 수 없습니다."
}
```

---

## 🚀 설치 및 실행

### 사전 요구사항

```
✅ Docker 24.0 이상
✅ Docker Compose 2.20 이상
✅ 8GB 이상 RAM
✅ 10GB 이상 디스크 공간
```

### 1단계: 프로젝트 클론 및 환경 설정

```bash
# 프로젝트 디렉토리로 이동
cd /home/wk/projects/wafl

# .env 파일 설정
cat > .env << 'EOF'
# OpenAI API 키 (선택사항)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx

# 데이터베이스 설정
DATABASE_URL=postgresql://wafl_user:wafl_password@wafl-postgresql:5432/wafl_db
REDIS_URL=redis://wafl-redis:6379/0

# 서비스 포트
WEB_SERVER_PORT=58000
SCRAPING_SERVER_PORT=58001
API_GATEWAY_PORT=50080
POSTGRES_PORT=55432
REDIS_PORT=56379

# 스크래핑 서버 URL (컨테이너 내부 통신용)
SCRAPING_SERVER_URL=http://wafl-scraping-server:8001
EOF
```

### 2단계: Docker Compose 실행

```bash
# 컨테이너 빌드 및 시작
docker compose up -d --build

# 로그 확인
docker compose logs -f

# 특정 서비스 로그만 확인
docker compose logs -f wafl-web-server
docker compose logs -f wafl-scraping-worker
```

### 3단계: 서비스 상태 확인

```bash
# 모든 컨테이너 실행 확인
docker compose ps

# 예상 출력:
# NAME                   STATUS
# wafl-api-gateway       Up
# wafl-web-server        Up
# wafl-scraping-server   Up
# wafl-scraping-worker   Up
# wafl-postgresql        Up
# wafl-redis             Up

# 헬스체크
curl http://localhost:50080/health
curl http://localhost:58000/health
curl http://localhost:58001/health
```

### 4단계: 데이터베이스 초기화 확인

```bash
# PostgreSQL 접속
PGPASSWORD=wafl_password psql -h localhost -p 55432 -U wafl_user -d wafl_db

# 테이블 확인
\dt

# 예상 출력:
#              List of relations
#  Schema |      Name        | Type  |   Owner
# --------+------------------+-------+-----------
#  public | stores           | table | wafl_user
#  public | menus            | table | wafl_user
#  public | reviews          | table | wafl_user
#  public | review_summaries | table | wafl_user
#  public | scraping_tasks   | table | wafl_user
```

### 5단계: 웹 인터페이스 접속

```bash
# 브라우저에서 접속
http://localhost:50080            # API Gateway를 통한 접속 (권장)
http://localhost:58000            # Web Server 직접 접속
http://localhost:58001            # Scraping Server 직접 접속
```

---

## 📖 사용 가이드

### 1. 매장 등록하기

**웹 인터페이스 사용:**

1. 브라우저에서 `http://localhost:50080` 접속
2. "매장 등록" 버튼 클릭
3. 폼 입력:
   ```
   매장명: 돼자옥
   주소: 서울 송파구 마천로51가길 33 1층 1호
   사업자등록번호: 123-45-67890
   대표자명: 홍길동
   대표자 연락처: 010-1234-5678
   네이버 스토어 URL: https://naver.me/xxxxx
   ```
4. "등록하기" 클릭

**API 사용:**

```bash
curl -X POST "http://localhost:50080/api/stores/register" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "store_name=돼자옥" \
  -d "store_address=서울 송파구 마천로51가길 33" \
  -d "business_number=123-45-67890" \
  -d "owner_name=홍길동" \
  -d "owner_phone=010-1234-5678" \
  -d "naver_store_url=https://naver.me/xxxxx"
```

### 2. 스크래핑 실행하기

**웹 인터페이스:**

1. 대시보드 접속: `http://localhost:50080/dashboard`
2. 매장 카드에서 "스크래핑 시작" 버튼 클릭
3. 진행 상태 실시간 확인 (10초마다 자동 갱신)

**API 사용:**

```bash
# 스크래핑 시작
TASK_ID=$(curl -X POST "http://localhost:50080/api/scraping/start" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "store_id=1" | jq -r '.task_id')

echo "Task ID: $TASK_ID"

# 진행 상태 확인
while true; do
  STATUS=$(curl -s "http://localhost:58001/api/scraping/status/$TASK_ID" | jq -r '.status')
  echo "Status: $STATUS"

  if [ "$STATUS" == "completed" ]; then
    echo "스크래핑 완료!"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo "스크래핑 실패!"
    break
  fi

  sleep 5
done
```

**예상 소요 시간:**
```
매장 기본 정보: 약 5초
메뉴 수집 (10개): 약 15초
리뷰 수집 (50개): 약 30초
AI 요약 생성: 약 20초
─────────────────────────
총: 약 1분 10초
```

### 3. 스크래핑 결과 확인하기

**매장 상세 페이지:**

```bash
# 브라우저에서 접속
http://localhost:50080/store/1/detail
```

**탭별 정보:**
```
┌─────────────────────────────────────────────┐
│  [매장 정보] [메뉴] [리뷰] [AI 요약]        │
├─────────────────────────────────────────────┤
│                                              │
│  매장 정보 탭:                               │
│  ├── 기본 정보 (이름, 주소, 전화번호)        │
│  ├── 등록 정보 (사업자번호, 대표자)          │
│  ├── 매장 소개                               │
│  └── 제공 서비스                             │
│                                              │
│  메뉴 탭:                                    │
│  └── 그리드 형태로 메뉴 카드 표시            │
│      ├── 메뉴 이미지                         │
│      ├── 메뉴명                              │
│      ├── 가격                                │
│      └── 설명                                │
│                                              │
│  리뷰 탭:                                    │
│  └── 리스트 형태로 리뷰 표시 (최대 50개)     │
│      ├── 작성 날짜                           │
│      ├── 리뷰 내용                           │
│      └── 재방문 횟수                         │
│                                              │
│  AI 요약 탭:                                 │
│  └── 마크다운 형식으로 요약 표시             │
│      ├── 인기 메뉴 TOP 3                     │
│      ├── 최근 트렌드                         │
│      ├── 메뉴 페어링 추천                    │
│      ├── 시간대별 선호도                     │
│      └── 운영 개선 제안                      │
│                                              │
└─────────────────────────────────────────────┘
```

### 4. AI 요약 전체 페이지

```bash
# 브라우저에서 접속
http://localhost:50080/store/1/summary
```

**기능:**
- 📄 전체 화면으로 AI 요약 표시
- 🔄 요약 재생성 버튼
- 📅 마지막 업데이트 시간 표시
- 🎨 마크다운 렌더링 (제목, 리스트, 강조 등)

### 5. 요약 재생성하기

**언제 재생성이 필요한가요?**
- 새로운 리뷰가 많이 추가되었을 때
- 메뉴가 변경되었을 때
- 분석 결과가 최신 트렌드를 반영하지 못할 때

**재생성 방법:**

```bash
# 웹 인터페이스
1. 요약 페이지 접속: http://localhost:50080/store/1/summary
2. "🔄 요약 재생성" 버튼 클릭
3. 약 20초 대기
4. 자동 새로고침

# API 사용
curl -X POST "http://localhost:50080/api/scraping/store/1/summary/regenerate"
```

### 6. 매장 삭제하기

**주의:** CASCADE 설정으로 메뉴, 리뷰, 요약도 함께 삭제됩니다.

```bash
# 웹 인터페이스
1. 대시보드 접속
2. 매장 카드에서 "삭제" 버튼 클릭
3. 확인 대화상자에서 "확인"

# API 사용
curl -X DELETE "http://localhost:50080/api/stores/1"
```

---

## 🛠️ 문제 해결

### 일반적인 문제

#### 1. 컨테이너가 시작되지 않음

**증상:**
```bash
docker compose ps
# NAME                 STATUS
# wafl-web-server      Exit 1
```

**원인:**
- 포트 충돌
- 환경 변수 미설정
- 이미지 빌드 실패

**해결:**
```bash
# 1. 포트 사용 확인
netstat -tuln | grep -E '50080|58000|58001|55432|56379'

# 2. 로그 확인
docker compose logs wafl-web-server

# 3. 컨테이너 재시작
docker compose down
docker compose up -d --build

# 4. .env 파일 확인
cat .env
```

#### 2. 스크래핑이 실패함

**증상:**
```
scraping_status: error
scraping_error_message: "..."
```

**가능한 원인:**

**A. 네이버 스토어 ID가 잘못됨**
```bash
# 해결: URL 확인
# 올바른 URL 형식:
https://m.place.naver.com/restaurant/1234567890/home
https://naver.me/xxxxx (자동 리다이렉트)

# 잘못된 URL:
https://blog.naver.com/...
```

**B. Selenium 드라이버 오류**
```bash
# 로그 확인
docker compose logs wafl-scraping-worker | grep -i error

# Chrome 버전 확인
docker compose exec wafl-scraping-worker google-chrome --version
docker compose exec wafl-scraping-worker chromedriver --version

# 버전 불일치 시 재빌드
docker compose build wafl-scraping-worker --no-cache
```

**C. 네트워크 오류**
```bash
# 컨테이너 내부에서 네이버 접속 테스트
docker compose exec wafl-scraping-worker curl -I https://m.place.naver.com

# DNS 문제 시 /etc/hosts 수정 또는 Docker DNS 설정
```

#### 3. OpenAI API 오류

**증상:**
```
OpenAI API 호출 실패
```

**원인 및 해결:**

**A. API 키 오류**
```bash
# 로그 확인
docker compose logs wafl-scraping-worker | grep -i openai

# 일반적인 오류:
# - "Incorrect API key provided"
# - "You exceeded your current quota"
# - "Rate limit reached"

# .env 파일 확인
grep OPENAI_API_KEY .env

# API 키 유효성 확인
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 크레딧 확인
# https://platform.openai.com/account/usage
```

**B. 크레딧 부족**
```bash
# 기본 요약 모드로 전환 (OpenAI API 없이)
# llm_summarizer.py에서 자동으로 fallback됨

# 로그에서 확인:
# "OpenAI API 키가 설정되지 않았습니다. 요약 기능이 제한됩니다."
```

#### 4. 메뉴 이미지가 표시되지 않음

**증상:**
- 메뉴 카드에 이미지가 깨져 보임
- 404 Not Found 오류

**원인:**
- 이미지 다운로드 실패
- 파일 권한 문제
- Nginx 설정 오류

**해결:**
```bash
# 1. 이미지 파일 확인
ls -la media/images/stores/1/menus/

# 2. 파일 권한 확인 및 수정
sudo chown -R 1000:1000 media/
sudo chmod -R 755 media/

# 3. Nginx 로그 확인
docker compose logs wafl-api-gateway | grep -E '404|403'

# 4. 이미지 URL 확인
curl -I http://localhost:50080/media/images/stores/1/menus/1_abc123.jpg
```

#### 5. 대시보드가 로딩되지 않음

**증상:**
- 빈 페이지 또는 무한 로딩

**원인:**
- API 서버 응답 없음
- CORS 오류
- JavaScript 오류

**해결:**
```bash
# 1. 브라우저 개발자 도구 (F12) 확인
#    - Console 탭: JavaScript 오류
#    - Network 탭: API 호출 실패 확인

# 2. API 직접 호출 테스트
curl http://localhost:50080/api/stores

# 3. 서버 로그 확인
docker compose logs wafl-web-server

# 4. 프록시 설정 확인
docker compose exec wafl-web-server env | grep SCRAPING_SERVER_URL
```

### 고급 문제 해결

#### Celery 태스크가 실행되지 않음

```bash
# 1. Redis 연결 확인
docker compose exec wafl-scraping-worker redis-cli -h wafl-redis ping
# 예상 출력: PONG

# 2. Celery 워커 상태 확인
docker compose exec wafl-scraping-worker celery -A celery_app.celery inspect active

# 3. 태스크 큐 확인
docker compose exec wafl-redis redis-cli
> LLEN celery
> LRANGE celery 0 -1

# 4. 워커 재시작
docker compose restart wafl-scraping-worker
```

#### 데이터베이스 연결 오류

```bash
# 1. PostgreSQL 상태 확인
docker compose exec wafl-postgresql pg_isready -U wafl_user

# 2. 연결 테스트
docker compose exec wafl-web-server python3 << 'EOF'
from database import engine
try:
    conn = engine.connect()
    print("✅ 데이터베이스 연결 성공")
    conn.close()
except Exception as e:
    print(f"❌ 연결 실패: {e}")
EOF

# 3. 데이터베이스 로그 확인
docker compose logs wafl-postgresql | tail -50
```

---

## 🔍 개발 과정에서 해결한 주요 문제

### 1. 메뉴명 표시 오류 (2024-10-04)

**문제:**
- 웹 페이지에서 메뉴명이 표시되지 않음
- DB에는 정상적으로 저장되어 있음

**원인:**
```javascript
// store_detail.html (잘못된 코드)
menu.name  // ❌ undefined

// 실제 API 응답
{
  "menu_name": "비빔냉면",  // ✅ 올바른 필드명
  "price": "12,000"
}
```

**해결:**
```javascript
// 수정된 코드
menu.menu_name  // ✅ 올바른 접근
```

**교훈:**
- API 스키마와 프론트엔드 코드의 일관성 중요
- 타입스크립트 도입 시 이런 오류 방지 가능

### 2. 요약 API 프록시 누락 (2024-10-04)

**문제:**
- summary.html에서 `/api/scraping/store/{store_id}/summary` 호출
- Web Server에 해당 엔드포인트 없음 → 404 오류

**원인:**
- Web Server가 Scraping Server의 프록시 역할을 해야 하는데 엔드포인트 누락

**해결:**
```python
# web-server/main.py에 추가
@app.get("/api/scraping/store/{store_id}/summary")
async def get_store_summary_proxy(store_id: int):
    """매장 리뷰 요약 조회 API (스크래핑 서버로 프록시)"""
    scraping_server_url = os.getenv("SCRAPING_SERVER_URL")
    response = requests.get(f"{scraping_server_url}/api/scraping/store/{store_id}/summary")
    return response.json()
```

**교훈:**
- 마이크로서비스 아키텍처에서 API Gateway/Proxy 설계 중요
- 프론트엔드와 백엔드 간 API 계약(Contract) 명확히 정의

### 3. OpenAI API 기본 요약 문제 (2024-10-04)

**문제:**
- API 키는 설정되어 있으나 기본 통계 요약만 생성됨
- 상세한 LLM 요약이 생성되지 않음

**원인:**
- 초기 스크래핑 시 OpenAI API 키가 환경변수로 전달되지 않음
- Celery Worker가 API 키를 읽지 못함

**해결:**
```yaml
# docker-compose.yml
wafl-scraping-worker:
  environment:
    - OPENAI_API_KEY=${OPENAI_API_KEY}  # ✅ 추가
```

**교훈:**
- Docker Compose 환경변수 주입 주의
- Celery Worker는 별도 프로세스이므로 명시적 환경변수 전달 필요

### 4. 이미지 최적화 및 저장 (개발 초기)

**문제:**
- 네이버에서 다운로드한 이미지가 너무 큼 (1-2MB)
- 페이지 로딩 속도 저하

**해결:**
```python
# image_downloader.py
def optimize_image(self, image):
    # 1. 크기 조정
    image.thumbnail((800, 800), Image.Resampling.LANCZOS)

    # 2. 품질 최적화
    image.save(filepath, 'JPEG', quality=85, optimize=True)

    # 결과: 평균 100KB 이하로 감소 (90% 절약)
```

**교훈:**
- 이미지 최적화는 필수
- Pillow 라이브러리의 thumbnail + optimize 조합 효과적

### 5. Selenium 안정성 개선 (개발 초기)

**문제:**
- 동적 콘텐츠 로딩 전 스크래핑 시도 → 요소를 찾지 못함
- 간헐적 실패 발생

**해결:**
```python
# selenium_driver.py
# Before: 고정 대기
time.sleep(3)  # ❌ 불안정

# After: 명시적 대기
WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.fvwqf'))
)  # ✅ 안정적
```

**교훈:**
- Selenium에서는 명시적 대기(Explicit Wait)가 암묵적 대기보다 안정적
- 중요한 요소는 WebDriverWait 사용

---

## 📊 프로젝트 통계

### 코드 통계

```
언어별 코드 라인 수:
Python         : ~2,500 줄
JavaScript     : ~1,200 줄
HTML/CSS       : ~2,000 줄
SQL            : ~200 줄
Dockerfile     : ~100 줄
YAML           : ~150 줄
───────────────────────────
총             : ~6,150 줄
```

### 파일 구조

```
wafl/
├── web-server/            # 웹 서버 (FastAPI)
│   ├── main.py           (325 줄)
│   ├── database.py       (84 줄)
│   └── templates/        (5개 파일, ~2000 줄)
│
├── scraping-server/       # 스크래핑 서버 (FastAPI + Celery)
│   ├── main.py           (443 줄)
│   ├── database.py       (84 줄)
│   ├── celery_app.py     (50 줄)
│   ├── tasks/
│   │   └── scraping_tasks.py  (435 줄)
│   └── utils/
│       ├── selenium_driver.py      (100 줄)
│       ├── image_downloader.py     (150 줄)
│       └── llm_summarizer.py       (244 줄)
│
├── api-gateway/           # Nginx 설정
│   └── nginx.conf        (80 줄)
│
├── docker-compose.yml    (124 줄)
├── init.sql              (100 줄)
├── .env                  (15 줄)
├── SETUP_GUIDE.md        (173 줄)
└── README.md             (이 파일)
```

### 성능 지표

```
스크래핑 속도:
├── 매장 기본 정보: 5초
├── 메뉴 수집 (10개): 15초
├── 리뷰 수집 (50개): 30초
└── AI 요약 생성: 20초
    총: ~70초

이미지 최적화:
├── 원본: 평균 1.2MB
├── 최적화 후: 평균 95KB
└── 절감률: ~92%

AI 요약 비용:
├── 리뷰 50개 기준: $0.0015 (~2원)
├── 월 100개 매장: $1.50 (~2,000원)
└── GPT-4 대비 비용: 1/60
```

---

## 🔮 향후 개선 사항

### 단기 (1-2주)

- [ ] 스크래핑 재시도 로직 개선
- [ ] 에러 알림 시스템 (이메일/Slack)
- [ ] 이미지 CDN 연동
- [ ] 스크래핑 스케줄러 (주기적 자동 업데이트)

### 중기 (1-2개월)

- [ ] 대시보드 차트/그래프 추가
- [ ] 매장 비교 기능
- [ ] 엑셀 내보내기
- [ ] 모바일 반응형 개선

### 장기 (3개월 이상)

- [ ] 사용자 인증/권한 관리
- [ ] 멀티 테넌시 지원
- [ ] 실시간 알림 (WebSocket)
- [ ] AI 챗봇 (매장 운영 컨설팅)

---

## 📞 지원

### 문서

- **설정 가이드**: [SETUP_GUIDE.md](./SETUP_GUIDE.md)
- **API 문서**: 이 README의 [API 문서](#-api-문서) 섹션
- **문제 해결**: 이 README의 [문제 해결](#-문제-해결) 섹션

### 로그 확인

```bash
# 전체 로그
docker compose logs -f

# 서비스별 로그
docker compose logs -f wafl-web-server
docker compose logs -f wafl-scraping-server
docker compose logs -f wafl-scraping-worker

# 에러만 필터링
docker compose logs | grep -i error
```

### 디버깅 팁

```bash
# 1. 컨테이너 내부 접속
docker compose exec wafl-web-server bash
docker compose exec wafl-scraping-worker bash

# 2. Python 대화형 쉘
docker compose exec wafl-web-server python3
>>> from database import SessionLocal, Store
>>> db = SessionLocal()
>>> stores = db.query(Store).all()
>>> print(stores)

# 3. PostgreSQL 직접 접속
docker compose exec wafl-postgresql psql -U wafl_user -d wafl_db

# 4. Redis 직접 접속
docker compose exec wafl-redis redis-cli
```

---

## 📄 라이선스

이 프로젝트는 내부 사용 목적으로 개발되었습니다.

---

## 👥 기여자

- 개발자: [Your Name]
- 기간: 2024년 10월
- AI 지원: Claude (Anthropic)

---

## 🙏 감사의 글

이 프로젝트는 다음 오픈소스 프로젝트를 활용했습니다:

- **FastAPI**: 빠르고 현대적인 Python 웹 프레임워크
- **Celery**: 분산 태스크 큐
- **Selenium**: 웹 브라우저 자동화
- **PostgreSQL**: 강력한 오픈소스 데이터베이스
- **Redis**: 인메모리 데이터 스토어
- **OpenAI**: GPT-4o-mini API
- **Docker**: 컨테이너화 플랫폼

---

**마지막 업데이트**: 2024년 10월 4일
**버전**: 1.0.0
