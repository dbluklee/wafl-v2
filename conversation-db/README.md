# WAFL 대화 저장 시스템

RAG 대화 내용을 암호화하여 안전하게 저장하는 독립 데이터베이스 시스템입니다.

## 🔐 보안 특징

- **AES-256-GCM 암호화**: 모든 대화 내용을 군사급 암호화로 보호
- **독립 데이터베이스**: 기존 시스템과 완전히 분리된 PostgreSQL 인스턴스
- **해시된 메타데이터**: IP 주소, User Agent 등은 SHA-256 해시로 저장
- **접근 감사 로그**: 모든 데이터 접근을 추적 및 기록
- **키 로테이션 지원**: 암호화 키 변경 및 관리 기능
- **자동 백업**: 일일 자동 백업 및 30일 보관

## 📦 구성 요소

```
conversation-db/
├── init.sql           # 데이터베이스 초기 스키마
├── backup.sh          # 자동 백업 스크립트
├── restore.sh         # 복구 스크립트
├── backups/           # 백업 파일 저장 디렉토리
└── README.md          # 이 문서
```

## 🚀 설치 및 설정

### 1. 환경 변수 설정

`.env` 파일에 다음 환경 변수를 추가:

```bash
# 데이터베이스 비밀번호 (강력한 비밀번호 사용!)
CONVERSATION_DB_PASSWORD=your-very-strong-password-here

# 암호화 키 (32자 이상, 절대 공유하지 마세요!)
CONVERSATION_ENCRYPTION_KEY=your-super-secret-encryption-key-here
```

**⚠️ 중요**: 암호화 키를 잃어버리면 모든 대화 내용을 복호화할 수 없습니다. 안전한 곳에 별도로 백업하세요!

### 2. 데이터베이스 시작

```bash
# Docker Compose로 시작
docker-compose up -d wafl-conversation-db

# 상태 확인
docker-compose ps wafl-conversation-db

# 로그 확인
docker-compose logs wafl-conversation-db
```

### 3. 연결 테스트

```bash
# PostgreSQL 클라이언트로 연결
psql -h localhost -p 55433 -U conv_secure_user -d conversation_db

# 테이블 확인
\dt
```

## 📊 데이터베이스 스키마

### conversations (대화 세션)
- `conversation_uuid`: 대화 세션 고유 ID
- `store_id`: 매장 ID
- `category`: 대화 카테고리 (customer/owner)
- `total_messages`: 메시지 수
- `client_ip_hash`: 해시된 클라이언트 IP
- `user_agent_hash`: 해시된 User Agent

### conversation_messages (암호화된 메시지)
- `user_message_encrypted`: 암호화된 사용자 메시지
- `bot_response_encrypted`: 암호화된 봇 응답
- `encryption_key_id`: 사용된 암호화 키 ID
- `used_rag`: RAG 사용 여부
- `response_time_ms`: 응답 시간

### encryption_keys (암호화 키 관리)
- `key_id`: 키 ID
- `key_hash`: 해시된 키
- `is_active`: 활성화 여부

### conversation_access_logs (접근 로그)
- `access_type`: 접근 유형 (read/write/decrypt/export/delete/backup)
- `accessed_by`: 접근자
- `accessed_at`: 접근 시간

## 💾 백업 및 복구

### 자동 백업 설정

cron으로 매일 자동 백업:

```bash
# crontab 편집
crontab -e

# 매일 새벽 2시에 백업 (예시)
0 2 * * * /home/wk/projects/wafl/conversation-db/backup.sh
```

### 수동 백업

```bash
./conversation-db/backup.sh
```

백업 파일은 `conversation-db/backups/` 디렉토리에 저장됩니다.

### 복구

```bash
./conversation-db/restore.sh
```

복구할 백업 파일을 선택하라는 메시지가 표시됩니다.

## 🔍 API 엔드포인트

### 대화 저장
```http
POST /api/chat
Content-Type: application/json

{
  "message": "영업시간이 어떻게 되나요?",
  "store_id": 1,
  "category": "customer",
  "conversation_uuid": "optional-existing-uuid"
}
```

### 대화 조회
```http
GET /api/conversations/{conversation_uuid}?decrypt=false
```

### 대화 종료
```http
POST /api/conversations/{conversation_uuid}/end
```

### 매장 통계
```http
GET /api/stores/{store_id}/conversation-statistics?days=30
```

## 📈 모니터링

### 저장된 대화 수 확인

```sql
SELECT COUNT(*) FROM conversations;
SELECT COUNT(*) FROM conversation_messages;
```

### 최근 대화 요약

```sql
SELECT * FROM recent_conversations_summary
ORDER BY session_start_at DESC
LIMIT 10;
```

### 매장별 통계

```sql
SELECT * FROM store_conversation_stats;
```

### 접근 로그 확인

```sql
SELECT * FROM conversation_access_logs
ORDER BY accessed_at DESC
LIMIT 20;
```

## 🛡️ 보안 체크리스트

- [x] 강력한 데이터베이스 비밀번호 설정
- [x] 암호화 키를 환경 변수로 관리
- [x] 암호화 키를 안전한 곳에 별도 백업
- [x] `.env` 파일을 `.gitignore`에 추가
- [x] 정기적인 자동 백업 설정
- [x] 백업 파일도 암호화된 저장소에 보관
- [x] 접근 로그 정기적으로 검토
- [x] 오래된 백업 파일 자동 삭제 (30일)
- [x] 데이터베이스 연결 풀 최적화
- [x] 헬스 체크 활성화

## 🔧 문제 해결

### 연결 실패
```bash
# 컨테이너 상태 확인
docker-compose ps wafl-conversation-db

# 로그 확인
docker-compose logs wafl-conversation-db

# 재시작
docker-compose restart wafl-conversation-db
```

### 백업 실패
```bash
# 백업 로그 확인
cat conversation-db/backups/backup.log

# 수동으로 pg_dump 실행
docker exec wafl-conversation-db pg_dump -U conv_secure_user conversation_db
```

### 암호화/복호화 오류
```python
# 암호화 테스트
python3 rag-server/encryption_utils.py
```

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. 환경 변수가 올바르게 설정되었는지
2. 데이터베이스 컨테이너가 실행 중인지
3. 암호화 키가 올바른지
4. 백업 디렉토리 권한이 올바른지

## 📝 라이선스

이 프로젝트는 WAFL의 일부입니다.
