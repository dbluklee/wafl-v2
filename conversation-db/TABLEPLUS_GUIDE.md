# TablePlus로 대화 DB 확인하기

## 📱 연결 설정

TablePlus를 열고 새 연결을 생성하세요:

### PostgreSQL 연결 정보
```
Name: WAFL 대화 DB
Type: PostgreSQL
Host: localhost
Port: 55433
Database: conversation_db
User: conv_secure_user
Password: conv_secure_pass_2024!
```

(비밀번호가 .env 파일에서 다르게 설정되었다면 그 값을 사용하세요)

---

## 🔍 주요 확인 방법

### 1. 메타데이터만 보기 (빠르게 확인)

암호화된 내용은 제외하고 통계만 확인:

```sql
-- 모든 대화 세션 목록
SELECT
    conversation_uuid,
    store_id,
    category,
    total_messages,
    session_start_at,
    is_active
FROM conversations
ORDER BY session_start_at DESC;
```

```sql
-- 메시지 메타데이터 (암호화된 내용 제외)
SELECT
    c.conversation_uuid,
    cm.message_uuid,
    cm.message_length,      -- 메시지 길이
    cm.response_length,     -- 응답 길이
    cm.used_rag,            -- RAG 사용 여부
    cm.response_time_ms,    -- 응답 시간
    cm.created_at
FROM conversation_messages cm
JOIN conversations c ON cm.conversation_id = c.id
ORDER BY cm.created_at DESC
LIMIT 20;
```

### 2. 암호화된 원본 데이터 보기

⚠️ **주의**: 이 데이터는 암호화되어 있어 TablePlus에서 읽을 수 없습니다.

```sql
-- 암호화된 메시지 (읽을 수 없음)
SELECT
    user_message_encrypted,  -- Base64로 인코딩된 암호화 데이터
    bot_response_encrypted,  -- Base64로 인코딩된 암호화 데이터
    encryption_key_id
FROM conversation_messages
LIMIT 5;
```

---

## 🔓 복호화된 내용 보는 방법

암호화된 메시지를 읽으려면 **API를 사용**해야 합니다:

### 방법 1: cURL로 확인

터미널에서:
```bash
# conversation_uuid를 알아야 합니다 (TablePlus에서 확인)
curl "http://localhost:58002/api/conversations/{conversation_uuid}?decrypt=true" | jq
```

예시:
```bash
curl "http://localhost:58002/api/conversations/ac3af322-d4e8-41bf-9706-9f3f970a134d?decrypt=true" | jq
```

### 방법 2: 브라우저에서 확인

브라우저 주소창에 입력:
```
http://localhost:58002/api/conversations/{conversation_uuid}?decrypt=true
```

### 방법 3: Postman/Insomnia 사용

```
GET http://localhost:58002/api/conversations/{conversation_uuid}?decrypt=true
```

---

## 📊 유용한 분석 쿼리

### 매장별 대화 통계
```sql
SELECT
    store_id,
    COUNT(DISTINCT id) as 대화수,
    SUM(total_messages) as 총메시지수,
    AVG(total_messages) as 평균메시지수
FROM conversations
GROUP BY store_id
ORDER BY 대화수 DESC;
```

### RAG 사용률
```sql
SELECT
    COUNT(CASE WHEN used_rag THEN 1 END) as RAG_사용,
    COUNT(CASE WHEN NOT used_rag THEN 1 END) as 일반대화,
    ROUND(COUNT(CASE WHEN used_rag THEN 1 END)::numeric / COUNT(*)::numeric * 100, 2) as RAG_사용률
FROM conversation_messages;
```

### 평균 응답 시간
```sql
SELECT
    AVG(response_time_ms) as 평균응답시간_ms,
    MIN(response_time_ms) as 최소응답시간_ms,
    MAX(response_time_ms) as 최대응답시간_ms
FROM conversation_messages;
```

### 시간대별 대화량
```sql
SELECT
    DATE(created_at) as 날짜,
    EXTRACT(HOUR FROM created_at) as 시간,
    COUNT(*) as 대화수
FROM conversations
GROUP BY 날짜, 시간
ORDER BY 날짜 DESC, 시간;
```

### 최근 접근 로그
```sql
SELECT
    access_type as 접근유형,
    accessed_by as 접근자,
    access_reason as 사유,
    accessed_at as 접근시간
FROM conversation_access_logs
ORDER BY accessed_at DESC
LIMIT 30;
```

---

## 🛡️ 보안 주의사항

### ⚠️ 중요
1. **복호화는 API를 통해서만**: 암호화된 데이터를 직접 복호화하지 마세요
2. **접근 로그 확인**: 모든 복호화 작업은 `conversation_access_logs`에 기록됩니다
3. **비밀번호 보안**: DB 비밀번호를 절대 공유하지 마세요
4. **암호화 키 보관**: `CONVERSATION_ENCRYPTION_KEY`를 안전하게 보관하세요

### 접근 권한
- **읽기 전용**: 메타데이터 조회는 안전합니다
- **복호화**: API를 통해서만 가능하며, 접근 로그가 기록됩니다
- **백업**: 정기적으로 백업하세요 (`backup.sh` 사용)

---

## 🔧 문제 해결

### 연결이 안 될 때
```bash
# DB 상태 확인
docker compose ps wafl-conversation-db

# DB 로그 확인
docker compose logs wafl-conversation-db

# DB 재시작
docker compose restart wafl-conversation-db
```

### 데이터가 보이지 않을 때
```sql
-- 테이블 존재 확인
\dt

-- 데이터 개수 확인
SELECT COUNT(*) FROM conversations;
SELECT COUNT(*) FROM conversation_messages;
```

---

## 📁 추가 리소스

- 더 많은 쿼리: `queries.sql` 파일 참고
- 백업: `backup.sh` 스크립트 사용
- 복구: `restore.sh` 스크립트 사용
- 상세 문서: `README.md` 참고
