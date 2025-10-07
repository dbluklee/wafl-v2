#!/bin/bash
# =====================================================================
# WAFL 대화 DB 백업 스크립트
# =====================================================================
# 암호화된 대화 데이터를 안전하게 백업합니다.
# cron 작업으로 자동 실행할 수 있습니다.
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
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/conversation_db_${TIMESTAMP}.sql"
BACKUP_FILE_GZ="${BACKUP_FILE}.gz"

# 로그
LOG_FILE="${BACKUP_DIR}/backup.log"

# 함수: 로그 메시지
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "====================================================================="
log "대화 DB 백업 시작"
log "====================================================================="

# 백업 디렉토리 확인
if [ ! -d "${BACKUP_DIR}" ]; then
    log "백업 디렉토리 생성: ${BACKUP_DIR}"
    mkdir -p "${BACKUP_DIR}"
fi

# 백업 실행
log "백업 파일 생성 중: ${BACKUP_FILE}"

export PGPASSWORD="${DB_PASSWORD}"

pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --verbose \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    -f "${BACKUP_FILE}" 2>&1 | tee -a "${LOG_FILE}"

if [ $? -eq 0 ]; then
    log "✅ 백업 성공: ${BACKUP_FILE}"

    # 압축
    log "백업 파일 압축 중..."
    gzip "${BACKUP_FILE}"

    if [ $? -eq 0 ]; then
        log "✅ 압축 성공: ${BACKUP_FILE_GZ}"
        BACKUP_SIZE=$(du -h "${BACKUP_FILE_GZ}" | cut -f1)
        log "백업 크기: ${BACKUP_SIZE}"
    else
        log "❌ 압축 실패"
        exit 1
    fi
else
    log "❌ 백업 실패"
    exit 1
fi

# 오래된 백업 정리 (30일 이상된 백업 삭제)
log "오래된 백업 파일 정리 중 (30일 이상)..."
find "${BACKUP_DIR}" -name "conversation_db_*.sql.gz" -type f -mtime +30 -delete
OLD_BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "conversation_db_*.sql.gz" -type f | wc -l)
log "현재 백업 파일 수: ${OLD_BACKUP_COUNT}"

# 백업 무결성 검증 (선택)
log "백업 무결성 검증 중..."
gunzip -t "${BACKUP_FILE_GZ}" 2>&1 | tee -a "${LOG_FILE}"

if [ $? -eq 0 ]; then
    log "✅ 백업 무결성 검증 성공"
else
    log "❌ 백업 무결성 검증 실패"
    exit 1
fi

log "====================================================================="
log "백업 완료"
log "====================================================================="

# PGPASSWORD 환경변수 제거 (보안)
unset PGPASSWORD

exit 0
