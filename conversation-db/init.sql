-- =====================================================================
-- WAFL 대화 저장 시스템 - 보안 및 데이터 안정성 최우선 설계
-- =====================================================================
-- 이 데이터베이스는 RAG 대화 내용을 안전하게 보관하는 핵심 자산입니다.
-- 모든 민감한 데이터는 암호화되며, 접근 로그가 기록됩니다.
-- =====================================================================

-- 확장 기능 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================================
-- 1. 대화 세션 테이블
-- =====================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    conversation_uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,

    -- 매장 정보
    store_id INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'customer',

    -- 세션 정보
    session_start_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    session_end_at TIMESTAMP,
    total_messages INTEGER DEFAULT 0,

    -- 보안 메타데이터 (해시로 저장, 원본 저장 안함)
    client_ip_hash VARCHAR(64),
    user_agent_hash VARCHAR(64),

    -- 상태 관리
    is_active BOOLEAN DEFAULT TRUE,
    archived_at TIMESTAMP,

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 인덱스
CREATE INDEX idx_conversations_store_id ON conversations(store_id);
CREATE INDEX idx_conversations_created_at ON conversations(created_at DESC);
CREATE INDEX idx_conversations_uuid ON conversations(conversation_uuid);
CREATE INDEX idx_conversations_active ON conversations(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_conversations_category ON conversations(category);

-- 코멘트
COMMENT ON TABLE conversations IS '대화 세션 메타데이터 - 보안 및 감사 추적 포함';
COMMENT ON COLUMN conversations.client_ip_hash IS 'SHA256 해시된 클라이언트 IP (원본 저장 안함)';
COMMENT ON COLUMN conversations.user_agent_hash IS 'SHA256 해시된 User Agent';


-- =====================================================================
-- 2. 대화 메시지 테이블 (암호화 저장)
-- =====================================================================
CREATE TABLE IF NOT EXISTS conversation_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    message_uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,

    -- 암호화된 메시지 내용 (AES-256-GCM)
    user_message_encrypted TEXT NOT NULL,
    bot_response_encrypted TEXT NOT NULL,
    encryption_key_id VARCHAR(50) NOT NULL,

    -- 메타데이터 (검색/분석용, 비암호화)
    message_length INTEGER,
    response_length INTEGER,
    used_rag BOOLEAN DEFAULT FALSE,
    response_time_ms INTEGER,

    -- RAG 메타데이터
    rag_doc_count INTEGER,
    rag_max_score FLOAT,

    -- 품질 지표
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 제약조건
    CONSTRAINT fk_messages_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    -- 데이터 무결성 체크
    CONSTRAINT chk_message_length CHECK (message_length > 0),
    CONSTRAINT chk_response_length CHECK (response_length > 0)
);

-- 인덱스
CREATE INDEX idx_messages_conversation_id ON conversation_messages(conversation_id);
CREATE INDEX idx_messages_created_at ON conversation_messages(created_at DESC);
CREATE INDEX idx_messages_uuid ON conversation_messages(message_uuid);
CREATE INDEX idx_messages_used_rag ON conversation_messages(used_rag);
CREATE INDEX idx_messages_encryption_key ON conversation_messages(encryption_key_id);

-- 코멘트
COMMENT ON TABLE conversation_messages IS '암호화된 대화 메시지 - AES-256-GCM 암호화';
COMMENT ON COLUMN conversation_messages.user_message_encrypted IS 'AES-256-GCM으로 암호화된 사용자 메시지';
COMMENT ON COLUMN conversation_messages.bot_response_encrypted IS 'AES-256-GCM으로 암호화된 봇 응답';


-- =====================================================================
-- 3. 암호화 키 관리 테이블
-- =====================================================================
CREATE TABLE IF NOT EXISTS encryption_keys (
    id SERIAL PRIMARY KEY,
    key_id VARCHAR(50) UNIQUE NOT NULL,
    key_hash VARCHAR(64) NOT NULL,

    -- 키 로테이션 관리
    is_active BOOLEAN DEFAULT TRUE,
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deactivated_at TIMESTAMP,

    -- 메타데이터
    algorithm VARCHAR(50) DEFAULT 'AES-256-GCM' NOT NULL,
    created_by VARCHAR(100) DEFAULT 'system',

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 제약조건
    CONSTRAINT chk_key_deactivation CHECK (
        deactivated_at IS NULL OR deactivated_at > activated_at
    )
);

-- 인덱스
CREATE UNIQUE INDEX idx_encryption_keys_active_key ON encryption_keys(key_id) WHERE is_active = TRUE;
CREATE INDEX idx_encryption_keys_key_id ON encryption_keys(key_id);

-- 코멘트
COMMENT ON TABLE encryption_keys IS '암호화 키 관리 및 로테이션 (실제 키는 환경변수에 보관)';
COMMENT ON COLUMN encryption_keys.key_hash IS 'SHA256 해시된 키 (실제 키는 환경변수/보안 저장소에 보관)';


-- =====================================================================
-- 4. 데이터 접근 감사 로그
-- =====================================================================
CREATE TABLE IF NOT EXISTS conversation_access_logs (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER,
    message_id INTEGER,

    -- 접근 정보
    access_type VARCHAR(50) NOT NULL,
    accessed_by VARCHAR(100),
    access_reason TEXT,
    access_result VARCHAR(50),

    -- 보안 메타데이터
    ip_address_hash VARCHAR(64),

    -- 타임스탬프
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 제약조건
    CONSTRAINT fk_access_logs_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_access_logs_message
        FOREIGN KEY (message_id)
        REFERENCES conversation_messages(id)
        ON DELETE SET NULL,
    CONSTRAINT chk_access_type CHECK (
        access_type IN ('read', 'write', 'export', 'delete', 'decrypt', 'backup')
    )
);

-- 인덱스
CREATE INDEX idx_access_logs_conversation_id ON conversation_access_logs(conversation_id);
CREATE INDEX idx_access_logs_message_id ON conversation_access_logs(message_id);
CREATE INDEX idx_access_logs_accessed_at ON conversation_access_logs(accessed_at DESC);
CREATE INDEX idx_access_logs_access_type ON conversation_access_logs(access_type);
CREATE INDEX idx_access_logs_accessed_by ON conversation_access_logs(accessed_by);

-- 코멘트
COMMENT ON TABLE conversation_access_logs IS '데이터 접근 감사 로그 - 모든 접근 기록';


-- =====================================================================
-- 5. 대화 통계 집계 테이블
-- =====================================================================
CREATE TABLE IF NOT EXISTS conversation_statistics (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL,
    date DATE NOT NULL,

    -- 통계
    total_conversations INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    rag_usage_count INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT,
    avg_conversation_length FLOAT,
    avg_message_length FLOAT,

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT unique_store_date UNIQUE (store_id, date)
);

-- 인덱스
CREATE INDEX idx_statistics_store_id ON conversation_statistics(store_id);
CREATE INDEX idx_statistics_date ON conversation_statistics(date DESC);

-- 코멘트
COMMENT ON TABLE conversation_statistics IS '대화 통계 집계 - 성능 최적화를 위한 사전 계산';


-- =====================================================================
-- 6. 트리거 함수
-- =====================================================================

-- updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 대화 메시지 수 자동 업데이트
CREATE OR REPLACE FUNCTION update_conversation_message_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE conversations
        SET total_messages = total_messages + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.conversation_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE conversations
        SET total_messages = total_messages - 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.conversation_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 접근 로그 자동 기록 (읽기)
CREATE OR REPLACE FUNCTION log_message_access()
RETURNS TRIGGER AS $$
BEGIN
    -- 실제 운영 환경에서는 애플리케이션 레벨에서 처리하는 것이 좋음
    -- 여기서는 구조만 제공
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- 7. 트리거 생성
-- =====================================================================

-- updated_at 자동 업데이트 트리거
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_encryption_keys_updated_at
    BEFORE UPDATE ON encryption_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_statistics_updated_at
    BEFORE UPDATE ON conversation_statistics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 메시지 수 자동 카운트 트리거
CREATE TRIGGER update_conversation_message_count_insert
    AFTER INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_message_count();

CREATE TRIGGER update_conversation_message_count_delete
    AFTER DELETE ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_message_count();


-- =====================================================================
-- 8. 초기 데이터 삽입
-- =====================================================================

-- 기본 암호화 키 등록 (실제 키는 환경변수에서 관리)
INSERT INTO encryption_keys (key_id, key_hash, created_by)
VALUES ('key-001', encode(digest('placeholder', 'sha256'), 'hex'), 'system')
ON CONFLICT (key_id) DO NOTHING;


-- =====================================================================
-- 9. 보안 정책 및 권한 설정
-- =====================================================================

-- Row Level Security 활성화 (필요시)
-- ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;

-- 특정 사용자만 암호화 키 테이블 접근 가능
-- REVOKE ALL ON encryption_keys FROM PUBLIC;


-- =====================================================================
-- 10. 유용한 뷰
-- =====================================================================

-- 최근 대화 요약 뷰 (암호화된 내용 제외)
CREATE OR REPLACE VIEW recent_conversations_summary AS
SELECT
    c.id,
    c.conversation_uuid,
    c.store_id,
    c.category,
    c.total_messages,
    c.session_start_at,
    c.session_end_at,
    c.is_active,
    COUNT(cm.id) as message_count,
    AVG(cm.response_time_ms) as avg_response_time,
    SUM(CASE WHEN cm.used_rag THEN 1 ELSE 0 END) as rag_usage_count
FROM conversations c
LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
GROUP BY c.id, c.conversation_uuid, c.store_id, c.category,
         c.total_messages, c.session_start_at, c.session_end_at, c.is_active;

COMMENT ON VIEW recent_conversations_summary IS '최근 대화 요약 - 암호화된 내용 제외';


-- 매장별 대화 통계 뷰
CREATE OR REPLACE VIEW store_conversation_stats AS
SELECT
    store_id,
    COUNT(DISTINCT id) as total_conversations,
    SUM(total_messages) as total_messages,
    AVG(total_messages) as avg_messages_per_conversation,
    MIN(created_at) as first_conversation,
    MAX(created_at) as last_conversation
FROM conversations
GROUP BY store_id;

COMMENT ON VIEW store_conversation_stats IS '매장별 대화 통계';


-- =====================================================================
-- 11. 데이터베이스 설정
-- =====================================================================

-- 타임존 설정
SET timezone = 'Asia/Seoul';

-- 로그 설정 (보안 감사용)
-- ALTER DATABASE conversation_db SET log_statement = 'mod';
-- ALTER DATABASE conversation_db SET log_connections = on;
-- ALTER DATABASE conversation_db SET log_disconnections = on;


-- =====================================================================
-- 초기화 완료
-- =====================================================================
SELECT 'WAFL Conversation DB 초기화 완료' as status;
