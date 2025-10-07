"""
비동기 대화 로깅 시스템
Redis Queue를 사용하여 응답 지연 없이 안전하게 대화 저장
"""

import os
import logging
from typing import Optional
from redis import Redis
from rq import Queue
from rq.job import Job

logger = logging.getLogger(__name__)


class ConversationLogger:
    """Redis Queue 기반 비동기 대화 로깅"""

    def __init__(self):
        """Redis 연결 및 Queue 초기화"""
        # Docker 환경에서는 서비스명 사용
        redis_host = os.getenv("REDIS_HOST", "wafl-redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "1"))  # DB 1 사용 (다른 서비스와 분리)

        try:
            self.redis_conn = Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=False,  # RQ는 bytes 사용
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )

            # 연결 테스트
            self.redis_conn.ping()

            # Queue 생성 (대화 저장 전용)
            self.queue = Queue(
                'conversation_logging',
                connection=self.redis_conn,
                default_timeout=300  # 5분 타임아웃
            )

            logger.info(f"✅ ConversationLogger 초기화 완료 (Redis: {redis_host}:{redis_port})")

        except Exception as e:
            logger.error(f"❌ Redis 연결 실패: {str(e)}")
            self.redis_conn = None
            self.queue = None

    def is_available(self) -> bool:
        """로거 사용 가능 여부 확인"""
        return self.queue is not None

    def enqueue_conversation_creation(
        self,
        store_id: int,
        category: str = "customer",
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[str]:
        """
        대화 세션 생성 작업을 큐에 추가

        Returns:
            job_id: RQ Job ID (작업 추적용)
        """
        if not self.is_available():
            logger.warning("⚠️ Redis Queue 사용 불가 - 대화 세션 생성 스킵")
            return None

        try:
            job = self.queue.enqueue(
                'tasks.create_conversation_task',
                store_id=store_id,
                category=category,
                client_ip=client_ip,
                user_agent=user_agent,
                job_timeout=30,  # 30초 타임아웃
                failure_ttl=86400  # 실패한 작업 24시간 보관
            )

            logger.info(f"📤 대화 세션 생성 작업 큐 추가: job_id={job.id}")
            return job.id

        except Exception as e:
            logger.error(f"❌ 대화 세션 생성 큐 추가 실패: {str(e)}")
            return None

    def enqueue_message_save(
        self,
        conversation_uuid: str,
        user_message: str,
        bot_response: str,
        used_rag: bool = False,
        response_time_ms: Optional[int] = None,
        rag_doc_count: Optional[int] = None,
        rag_max_score: Optional[float] = None,
        confidence_score: Optional[float] = None
    ) -> Optional[str]:
        """
        메시지 저장 작업을 큐에 추가 (비동기)

        이 함수는 즉시 반환되며, 실제 저장은 백그라운드 워커가 처리합니다.

        Returns:
            job_id: RQ Job ID (작업 추적용)
        """
        if not self.is_available():
            logger.warning("⚠️ Redis Queue 사용 불가 - 메시지 저장 스킵")
            return None

        try:
            # 큐에 작업 추가 (즉시 반환, ~1ms 소요)
            job = self.queue.enqueue(
                'tasks.save_message_task',  # Worker에서 실행할 함수
                conversation_uuid=conversation_uuid,
                user_message=user_message,
                bot_response=bot_response,
                used_rag=used_rag,
                response_time_ms=response_time_ms,
                rag_doc_count=rag_doc_count,
                rag_max_score=rag_max_score,
                confidence_score=confidence_score,
                job_timeout=60,  # 1분 타임아웃
                failure_ttl=86400  # 실패한 작업 24시간 보관
            )

            logger.info(f"📤 메시지 저장 작업 큐 추가: job_id={job.id}, conversation={conversation_uuid}")
            return job.id

        except Exception as e:
            logger.error(f"❌ 메시지 저장 큐 추가 실패: {str(e)}")
            return None

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """
        작업 상태 조회

        Returns:
            {
                'status': 'queued|started|finished|failed',
                'result': 작업 결과 (성공 시),
                'error': 에러 메시지 (실패 시)
            }
        """
        if not self.is_available():
            return None

        try:
            job = Job.fetch(job_id, connection=self.redis_conn)

            return {
                'status': job.get_status(),
                'result': job.result if job.is_finished else None,
                'error': str(job.exc_info) if job.is_failed else None,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'ended_at': job.ended_at.isoformat() if job.ended_at else None
            }

        except Exception as e:
            logger.error(f"❌ 작업 상태 조회 실패: {str(e)}")
            return None

    def get_queue_info(self) -> dict:
        """큐 상태 정보 조회"""
        if not self.is_available():
            return {'available': False}

        try:
            return {
                'available': True,
                'queued_jobs': len(self.queue),
                'failed_jobs': len(self.queue.failed_job_registry),
                'started_jobs': len(self.queue.started_job_registry),
                'finished_jobs': len(self.queue.finished_job_registry),
                'scheduled_jobs': len(self.queue.scheduled_job_registry)
            }
        except Exception as e:
            logger.error(f"❌ 큐 정보 조회 실패: {str(e)}")
            return {'available': False, 'error': str(e)}


# 전역 싱글톤 인스턴스
_logger_instance: Optional[ConversationLogger] = None


def get_conversation_logger() -> ConversationLogger:
    """전역 ConversationLogger 인스턴스 반환"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ConversationLogger()
    return _logger_instance


if __name__ == "__main__":
    # 테스트
    print("=" * 80)
    print("비동기 대화 로깅 시스템 테스트")
    print("=" * 80)

    logger_test = get_conversation_logger()

    if logger_test.is_available():
        print("✅ Redis Queue 연결 성공")

        # 큐 정보 출력
        info = logger_test.get_queue_info()
        print(f"\n큐 상태: {info}")

        # 테스트 작업 추가
        job_id = logger_test.enqueue_message_save(
            conversation_uuid="test-uuid-12345",
            user_message="테스트 메시지",
            bot_response="테스트 응답",
            used_rag=True,
            response_time_ms=1000
        )

        if job_id:
            print(f"\n✅ 테스트 작업 추가 성공: {job_id}")

            # 작업 상태 확인
            import time
            time.sleep(1)
            status = logger_test.get_job_status(job_id)
            print(f"작업 상태: {status}")
    else:
        print("❌ Redis Queue 연결 실패")

    print("\n" + "=" * 80)
