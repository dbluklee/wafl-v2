#!/bin/bash
# =====================================================================
# WAFL 대화 DB 복구 스크립트
# =====================================================================
# 백업 파일로부터 데이터베이스를 복구합니다.
# =====================================================================

set -e  # 오류 발생시 즉시 종료

# 환경 변수
DB_HOST="${CONVERSATION_DB_HOST:-localhost}"
DB_PORT="${CONVERSATION_DB_PORT:-55433}"
DB_NAME="${CONVERSATION_DB_NAME:-conversation_db}"
DB_USER="${CONVERSATION_DB_USER:-conv_secure_user}"
DB_PASSWORD="${CONVERSATION_DB_PASSWORD:-conv_secure_pass_2024!}"

# 백업 디렉토리
BACKUP_DIR="/home/wk/projects/wafl/conversation-db/backups"

# 로그
LOG_FILE="${BACKUP_DIR}/restore.log"

# 함수: 로그 메시지
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "====================================================================="
log "대화 DB 복구 스크립트"
log "====================================================================="

# 백업 파일 선택
echo ""
echo "사용 가능한 백업 파일:"
echo "---------------------------------------------------------------------"
ls -lh "${BACKUP_DIR}"/conversation_db_*.sql.gz 2>/dev/null || echo "백업 파일이 없습니다."
echo "---------------------------------------------------------------------"
echo ""

# 사용자 입력
read -p "복구할 백업 파일명 (예: conversation_db_20250107_120000.sql.gz): " BACKUP_FILENAME

BACKUP_FILE_GZ="${BACKUP_DIR}/${BACKUP_FILENAME}"

# 백업 파일 존재 확인
if [ ! -f "${BACKUP_FILE_GZ}" ]; then
    log "❌ 백업 파일을 찾을 수 없습니다: ${BACKUP_FILE_GZ}"
    exit 1
fi

log "복구 파일: ${BACKUP_FILE_GZ}"

# 확인
echo ""
echo "⚠️  경고: 이 작업은 현재 데이터베이스의 모든 데이터를 삭제하고 백업으로 대체합니다."
read -p "정말 복구하시겠습니까? (yes/no): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    log "복구 취소됨"
    exit 0
fi

log "====================================================================="
log "복구 시작"
log "====================================================================="

# 압축 해제
BACKUP_FILE="${BACKUP_DIR}/temp_restore.sql"
log "백업 파일 압축 해제 중..."
gunzip -c "${BACKUP_FILE_GZ}" > "${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    log "✅ 압축 해제 성공"
else
    log "❌ 압축 해제 실패"
    exit 1
fi

# 복구 실행
log "데이터베이스 복구 중..."

export PGPASSWORD="${DB_PASSWORD}"

psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -f "${BACKUP_FILE}" 2>&1 | tee -a "${LOG_FILE}"

if [ $? -eq 0 ]; then
    log "✅ 복구 성공"
else
    log "❌ 복구 실패"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# 임시 파일 삭제
rm -f "${BACKUP_FILE}"

# 복구 후 검증
log "복구 검증 중..."
CONVERSATION_COUNT=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM conversations;" 2>/dev/null | tr -d ' ')
MESSAGE_COUNT=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM conversation_messages;" 2>/dev/null | tr -d ' ')

log "복구된 데이터:"
log "  - 대화 세션: ${CONVERSATION_COUNT}개"
log "  - 메시지: ${MESSAGE_COUNT}개"

log "====================================================================="
log "복구 완료"
log "====================================================================="

# PGPASSWORD 환경변수 제거 (보안)
unset PGPASSWORD

exit 0
