-- =====================================================================
-- TablePlus에서 사용할 수 있는 유용한 쿼리들
-- =====================================================================

-- 1. 모든 대화 세션 보기 (메타데이터만)
SELECT
    conversation_uuid,
    store_id,
    category,
    total_messages,
    session_start_at,
    is_active
FROM conversations
ORDER BY session_start_at DESC
LIMIT 20;


-- 2. 특정 대화의 메시지 목록 (암호화된 상태)
SELECT
    cm.id,
    cm.message_uuid,
    cm.user_message_encrypted,  -- 암호화된 메시지
    cm.bot_response_encrypted,  -- 암호화된 응답
    cm.used_rag,
    cm.response_time_ms,
    cm.created_at
FROM conversation_messages cm
JOIN conversations c ON cm.conversation_id = c.id
WHERE c.conversation_uuid = 'ac3af322-d4e8-41bf-9706-9f3f970a134d'
ORDER BY cm.created_at ASC;


-- 3. 메시지 메타데이터만 보기 (암호화된 내용 제외)
SELECT
    c.conversation_uuid,
    c.store_id,
    cm.message_uuid,
    cm.message_length,
    cm.response_length,
    cm.used_rag,
    cm.response_time_ms,
    cm.rag_doc_count,
    cm.rag_max_score,
    cm.created_at
FROM conversation_messages cm
JOIN conversations c ON cm.conversation_id = c.id
ORDER BY cm.created_at DESC
LIMIT 20;


-- 4. 매장별 대화 통계
SELECT
    store_id,
    COUNT(DISTINCT id) as total_conversations,
    SUM(total_messages) as total_messages,
    AVG(total_messages) as avg_messages_per_conversation,
    MIN(created_at) as first_conversation,
    MAX(created_at) as last_conversation
FROM conversations
GROUP BY store_id
ORDER BY total_conversations DESC;


-- 5. RAG 사용 통계
SELECT
    c.store_id,
    COUNT(CASE WHEN cm.used_rag THEN 1 END) as rag_used,
    COUNT(CASE WHEN NOT cm.used_rag THEN 1 END) as rag_not_used,
    AVG(CASE WHEN cm.used_rag THEN cm.response_time_ms END) as avg_rag_response_time,
    AVG(CASE WHEN NOT cm.used_rag THEN cm.response_time_ms END) as avg_normal_response_time
FROM conversation_messages cm
JOIN conversations c ON cm.conversation_id = c.id
GROUP BY c.store_id;


-- 6. 최근 접근 로그 확인
SELECT
    cal.id,
    c.conversation_uuid,
    cal.access_type,
    cal.accessed_by,
    cal.access_reason,
    cal.access_result,
    cal.accessed_at
FROM conversation_access_logs cal
LEFT JOIN conversations c ON cal.conversation_id = c.id
ORDER BY cal.accessed_at DESC
LIMIT 30;


-- 7. 암호화 키 정보
SELECT
    key_id,
    is_active,
    algorithm,
    activated_at,
    created_by
FROM encryption_keys
ORDER BY activated_at DESC;


-- 8. 시간대별 대화 분포
SELECT
    DATE(created_at) as date,
    EXTRACT(HOUR FROM created_at) as hour,
    COUNT(*) as conversation_count
FROM conversations
GROUP BY DATE(created_at), EXTRACT(HOUR FROM created_at)
ORDER BY date DESC, hour;


-- 9. 응답 시간 분석
SELECT
    CASE
        WHEN response_time_ms < 1000 THEN '1초 미만'
        WHEN response_time_ms < 3000 THEN '1-3초'
        WHEN response_time_ms < 5000 THEN '3-5초'
        WHEN response_time_ms < 10000 THEN '5-10초'
        ELSE '10초 이상'
    END as response_time_range,
    COUNT(*) as count,
    AVG(response_time_ms) as avg_ms
FROM conversation_messages
GROUP BY response_time_range
ORDER BY avg_ms;


-- 10. 가장 활발한 대화 세션
SELECT
    c.conversation_uuid,
    c.store_id,
    c.total_messages,
    c.session_start_at,
    c.session_end_at,
    EXTRACT(EPOCH FROM (c.session_end_at - c.session_start_at))/60 as duration_minutes
FROM conversations c
WHERE c.session_end_at IS NOT NULL
ORDER BY c.total_messages DESC
LIMIT 10;
