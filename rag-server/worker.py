#!/usr/bin/env python3
"""
Redis Queue Worker
대화 저장 작업을 백그라운드에서 처리하는 워커

실행 방법:
    python worker.py
    또는
    rq worker conversation_logging --with-scheduler
"""

import os
import sys
import logging
from redis import Redis
from rq import Worker, Queue, Connection

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """워커 시작"""
    # Redis 연결 설정
    redis_host = os.getenv("REDIS_HOST", "wafl-redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "1"))

    logger.info("=" * 80)
    logger.info("🚀 대화 저장 워커 시작")
    logger.info(f"   Redis: {redis_host}:{redis_port}/{redis_db}")
    logger.info("=" * 80)

    # Redis 연결
    try:
        redis_conn = Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )

        # 연결 테스트
        redis_conn.ping()
        logger.info("✅ Redis 연결 성공")

    except Exception as e:
        logger.error(f"❌ Redis 연결 실패: {str(e)}")
        sys.exit(1)

    # 워커 실행
    with Connection(redis_conn):
        # 'conversation_logging' 큐에서 작업 처리
        queues = [Queue('conversation_logging')]

        logger.info("📋 큐 목록:")
        for q in queues:
            logger.info(f"   - {q.name} ({len(q)} 작업 대기중)")

        # 워커 생성 및 시작
        worker = Worker(
            queues,
            connection=redis_conn,
            name=f"conversation-worker-{os.getpid()}"
        )

        logger.info(f"👷 워커 시작: {worker.name}")
        logger.info("⏳ 작업 대기 중...\n")

        # 워커 실행 (무한 루프, SIGTERM/SIGINT로 종료)
        worker.work(with_scheduler=True, logging_level='INFO')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⏹️  워커 종료 (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n\n❌ 워커 오류: {str(e)}")
        sys.exit(1)
