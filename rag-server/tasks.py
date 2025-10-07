"""
Redis Queue Worker Tasks
백그라운드에서 실행되는 대화 저장 작업들
"""

import logging
from typing import Optional
from conversation_service import get_conversation_service

logger = logging.getLogger(__name__)


def create_conversation_task(
    store_id: int,
    category: str = "customer",
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None
) -> dict:
    """
    대화 세션 생성 작업 (백그라운드)

    Args:
        store_id: 매장 ID
        category: 대화 카테고리
        client_ip: 클라이언트 IP
        user_agent: User Agent

    Returns:
        {'success': True, 'conversation_uuid': '...'}

    Raises:
        Exception: 저장 실패 시 (RQ가 자동으로 재시도)
    """
    try:
        logger.info(f"🔄 [Worker] 대화 세션 생성 시작: store_id={store_id}")

        service = get_conversation_service()
        conversation_uuid = service.create_conversation(
            store_id=store_id,
            category=category,
            client_ip=client_ip,
            user_agent=user_agent
        )

        logger.info(f"✅ [Worker] 대화 세션 생성 완료: {conversation_uuid}")

        return {
            'success': True,
            'conversation_uuid': conversation_uuid
        }

    except Exception as e:
        logger.error(f"❌ [Worker] 대화 세션 생성 실패: {str(e)}")
        # 예외를 다시 발생시켜 RQ가 재시도하도록 함
        raise


def save_message_task(
    conversation_uuid: str,
    user_message: str,
    bot_response: str,
    used_rag: bool = False,
    response_time_ms: Optional[int] = None,
    rag_doc_count: Optional[int] = None,
    rag_max_score: Optional[float] = None,
    confidence_score: Optional[float] = None
) -> dict:
    """
    메시지 저장 작업 (백그라운드)

    이 함수는 RQ Worker에 의해 백그라운드에서 실행됩니다.

    Args:
        conversation_uuid: 대화 세션 UUID
        user_message: 사용자 메시지
        bot_response: 봇 응답
        used_rag: RAG 사용 여부
        response_time_ms: 응답 시간
        rag_doc_count: 검색된 문서 수
        rag_max_score: 최고 유사도 점수
        confidence_score: 응답 신뢰도

    Returns:
        {'success': True, 'message_id': 123}

    Raises:
        Exception: 저장 실패 시 (RQ가 자동으로 재시도)
    """
    try:
        logger.info(f"🔄 [Worker] 메시지 저장 시작: conversation={conversation_uuid}")

        # 대화 서비스를 통해 메시지 저장 (암호화 포함)
        service = get_conversation_service()
        message_id = service.save_message(
            conversation_uuid=conversation_uuid,
            user_message=user_message,
            bot_response=bot_response,
            used_rag=used_rag,
            response_time_ms=response_time_ms,
            rag_doc_count=rag_doc_count,
            rag_max_score=rag_max_score,
            confidence_score=confidence_score
        )

        logger.info(f"✅ [Worker] 메시지 저장 완료: message_id={message_id}")

        return {
            'success': True,
            'message_id': message_id,
            'conversation_uuid': conversation_uuid
        }

    except Exception as e:
        logger.error(f"❌ [Worker] 메시지 저장 실패: {str(e)}")
        logger.error(f"   대화 UUID: {conversation_uuid}")
        logger.error(f"   메시지 길이: {len(user_message)} chars")

        # 예외를 다시 발생시켜 RQ가 재시도하도록 함
        raise


def cleanup_old_conversations_task(days: int = 90) -> dict:
    """
    오래된 대화 정리 작업 (선택적)

    Args:
        days: 보관 기간 (일)

    Returns:
        {'success': True, 'deleted_count': 10}
    """
    try:
        logger.info(f"🔄 [Worker] 오래된 대화 정리 시작: {days}일 이전")

        # TODO: 실제 정리 로직 구현
        # service = get_conversation_service()
        # deleted_count = service.cleanup_old_conversations(days)

        logger.info(f"✅ [Worker] 대화 정리 완료")

        return {
            'success': True,
            'deleted_count': 0
        }

    except Exception as e:
        logger.error(f"❌ [Worker] 대화 정리 실패: {str(e)}")
        raise


if __name__ == "__main__":
    # 로컬 테스트
    print("=" * 80)
    print("Worker Task 테스트")
    print("=" * 80)

    # 메시지 저장 테스트
    result = save_message_task(
        conversation_uuid="test-uuid-12345",
        user_message="테스트 메시지입니다",
        bot_response="네, 테스트 응답입니다",
        used_rag=True,
        response_time_ms=1500,
        rag_doc_count=3,
        rag_max_score=0.92
    )

    print(f"\n결과: {result}")
    print("=" * 80)
