-- 데이터베이스 초기화 SQL 스크립트
-- WAFL 네이버 스토어 스크래핑 서비스

-- 매장 정보 테이블
CREATE TABLE stores (
    id SERIAL PRIMARY KEY,
    -- 사용자 입력 정보
    store_name VARCHAR(255) NOT NULL,
    store_address VARCHAR(500) NOT NULL,
    business_number VARCHAR(50) NOT NULL UNIQUE,
    owner_name VARCHAR(100) NOT NULL,
    owner_phone VARCHAR(20) NOT NULL,
    naver_store_url VARCHAR(500),
    store_id VARCHAR(50), -- 네이버 스토어 ID

    -- 스크래핑된 매장 정보 (선택적 필드)
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

    -- 스크래핑 상태
    scraping_status VARCHAR(50) DEFAULT 'pending' CHECK (scraping_status IN ('pending', 'in_progress', 'completed', 'mismatch', 'error')),
    scraping_error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 메뉴 정보 테이블
CREATE TABLE menus (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    menu_name VARCHAR(255),
    price VARCHAR(100),
    description TEXT,
    recommendation VARCHAR(100),
    image_file_path VARCHAR(500), -- 로컬 저장 경로
    image_url VARCHAR(500), -- 원본 이미지 URL (백업용)
    created_at TIMESTAMP DEFAULT NOW()
);

-- 후기 테이블
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    review_date VARCHAR(50),
    revisit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 후기 요약 테이블 (RAG용)
CREATE TABLE review_summaries (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    summary_md TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 스크래핑 작업 큐 테이블 (Celery 보조용)
CREATE TABLE scraping_tasks (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    task_id VARCHAR(255) UNIQUE, -- Celery task ID
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'started', 'success', 'failure', 'retry')),
    result TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스 생성 (성능 최적화)
CREATE INDEX idx_stores_store_id ON stores(store_id);
CREATE INDEX idx_stores_scraping_status ON stores(scraping_status);
CREATE INDEX idx_stores_business_number ON stores(business_number);
CREATE INDEX idx_menus_store_id ON menus(store_id);
CREATE INDEX idx_reviews_store_id ON reviews(store_id);
CREATE INDEX idx_scraping_tasks_task_id ON scraping_tasks(task_id);
CREATE INDEX idx_scraping_tasks_status ON scraping_tasks(status);

-- 트리거 함수: updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 생성
CREATE TRIGGER update_stores_updated_at
    BEFORE UPDATE ON stores
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scraping_tasks_updated_at
    BEFORE UPDATE ON scraping_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RAG 문서 관리 테이블
CREATE TABLE rag_documents (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL CHECK (category IN ('customer', 'owner')),
    doc_path VARCHAR(500) NOT NULL, -- md 문서 경로
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX idx_rag_documents_store_id ON rag_documents(store_id);
CREATE INDEX idx_rag_documents_category ON rag_documents(category);

-- 트리거 생성
CREATE TRIGGER update_rag_documents_updated_at
    BEFORE UPDATE ON rag_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 초기 데이터 삽입 (테스트용)
INSERT INTO stores (
    store_name,
    store_address,
    business_number,
    owner_name,
    owner_phone,
    naver_store_url,
    store_id
) VALUES (
    '테스트 카페',
    '서울특별시 강남구 테헤란로 123',
    '123-45-67890',
    '홍길동',
    '010-1234-5678',
    'https://naver.me/FvExPxZs',
    '1054849411'
);

-- RAG 문서 초기 데이터
INSERT INTO rag_documents (store_id, category, doc_path) VALUES
(1, 'customer', '/app/media/documents/test_cafe_customer.md');

-- 권한 설정
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO wafl_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO wafl_user;