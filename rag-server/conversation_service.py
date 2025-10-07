"""
대화 저장 서비스
모든 RAG 대화를 암호화하여 안전하게 저장
"""

import os
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, text, pool
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager

from encryption_utils import encrypt_message, decrypt_message, hash_ip_address, hash_user_agent, get_encryption_manager

logger = logging.getLogger(__name__)


class ConversationService:
    """대화 저장 및 관리 서비스"""

    def __init__(self):
        """대화 전용 데이터베이스 연결 초기화"""
        self.db_url = os.getenv(
            "CONVERSATION_DB_URL",
            "postgresql://conv_secure_user:conv_secure_pass_2024!@localhost:55433/conversation_db"
        )

        # 연결 풀 설정 (보안 및 성능 최적화)
        self.engine = create_engine(
            self.db_url,
            poolclass=pool.QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # 연결 헬스 체크
            pool_recycle=3600,   # 1시간마다 연결 재생성
            echo=False
        )

        self.encryption_manager = get_encryption_manager()
        logger.info("✅ ConversationService 초기화 완료")

    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        conn = self.engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"데이터베이스 오류: {str(e)}")
            raise
        finally:
            conn.close()

    def create_conversation(
        self,
        store_id: int,
        category: str = "customer",
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        새로운 대화 세션 생성

        Args:
            store_id: 매장 ID
            category: 대화 카테고리 (customer/owner)
            client_ip: 클라이언트 IP (해시하여 저장)
            user_agent: User Agent (해시하여 저장)

        Returns:
            conversation_uuid: 대화 세션 UUID
        """
        try:
            conversation_uuid = str(uuid.uuid4())

            # IP와 User Agent 해싱 (원본 저장 안함)
            ip_hash = hash_ip_address(client_ip) if client_ip else None
            ua_hash = hash_user_agent(user_agent) if user_agent else None

            with self.get_connection() as conn:
                query = text("""
                    INSERT INTO conversations
                    (conversation_uuid, store_id, category, client_ip_hash, user_agent_hash)
                    VALUES (:uuid, :store_id, :category, :ip_hash, :ua_hash)
                    RETURNING id, conversation_uuid
                """)

                result = conn.execute(query, {
                    "uuid": conversation_uuid,
                    "store_id": store_id,
                    "category": category,
                    "ip_hash": ip_hash,
                    "ua_hash": ua_hash
                })

                row = result.fetchone()
                logger.info(f"✅ 새 대화 세션 생성: {conversation_uuid} (store_id={store_id})")

                # 접근 로그 기록
                self._log_access(
                    conn,
                    conversation_id=row[0],
                    access_type="write",
                    accessed_by="system",
                    access_reason="새 대화 세션 생성",
                    ip_hash=ip_hash
                )

                return conversation_uuid

        except SQLAlchemyError as e:
            logger.error(f"대화 세션 생성 실패: {str(e)}")
            raise

    def save_message(
        self,
        conversation_uuid: str,
        user_message: str,
        bot_response: str,
        used_rag: bool = False,
        response_time_ms: Optional[int] = None,
        rag_doc_count: Optional[int] = None,
        rag_max_score: Optional[float] = None,
        confidence_score: Optional[float] = None
    ) -> int:
        """
        대화 메시지 저장 (암호화)

        Args:
            conversation_uuid: 대화 세션 UUID
            user_message: 사용자 메시지 (암호화됨)
            bot_response: 봇 응답 (암호화됨)
            used_rag: RAG 사용 여부
            response_time_ms: 응답 시간 (밀리초)
            rag_doc_count: 검색된 문서 수
            rag_max_score: 최고 유사도 점수
            confidence_score: 응답 신뢰도

        Returns:
            message_id: 메시지 ID
        """
        try:
            # 메시지 암호화
            encrypted_user_msg, key_id = encrypt_message(user_message)
            encrypted_bot_resp, _ = encrypt_message(bot_response)

            with self.get_connection() as conn:
                # 대화 세션 ID 조회
                conv_query = text("""
                    SELECT id FROM conversations
                    WHERE conversation_uuid = :uuid
                """)
                conv_result = conn.execute(conv_query, {"uuid": conversation_uuid})
                conv_row = conv_result.fetchone()

                if not conv_row:
                    raise ValueError(f"대화 세션을 찾을 수 없습니다: {conversation_uuid}")

                conversation_id = conv_row[0]

                # 메시지 저장
                msg_query = text("""
                    INSERT INTO conversation_messages
                    (conversation_id, user_message_encrypted, bot_response_encrypted,
                     encryption_key_id, message_length, response_length,
                     used_rag, response_time_ms, rag_doc_count, rag_max_score,
                     confidence_score)
                    VALUES (:conv_id, :user_msg, :bot_resp, :key_id,
                            :msg_len, :resp_len, :used_rag, :resp_time,
                            :doc_count, :max_score, :confidence)
                    RETURNING id, message_uuid
                """)

                result = conn.execute(msg_query, {
                    "conv_id": conversation_id,
                    "user_msg": encrypted_user_msg,
                    "bot_resp": encrypted_bot_resp,
                    "key_id": key_id,
                    "msg_len": len(user_message),
                    "resp_len": len(bot_response),
                    "used_rag": used_rag,
                    "resp_time": response_time_ms,
                    "doc_count": rag_doc_count,
                    "max_score": rag_max_score,
                    "confidence": confidence_score
                })

                row = result.fetchone()
                message_id = row[0]

                logger.info(f"✅ 메시지 저장 완료: {row[1]} (대화={conversation_uuid})")

                # 접근 로그 기록
                self._log_access(
                    conn,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    access_type="write",
                    accessed_by="system",
                    access_reason="새 메시지 저장"
                )

                return message_id

        except SQLAlchemyError as e:
            logger.error(f"메시지 저장 실패: {str(e)}")
            raise

    def get_conversation_messages(
        self,
        conversation_uuid: str,
        decrypt: bool = True
    ) -> List[Dict[str, Any]]:
        """
        대화 세션의 모든 메시지 조회

        Args:
            conversation_uuid: 대화 세션 UUID
            decrypt: 메시지 복호화 여부

        Returns:
            메시지 리스트
        """
        try:
            with self.get_connection() as conn:
                query = text("""
                    SELECT
                        cm.id,
                        cm.message_uuid,
                        cm.user_message_encrypted,
                        cm.bot_response_encrypted,
                        cm.used_rag,
                        cm.response_time_ms,
                        cm.created_at
                    FROM conversation_messages cm
                    JOIN conversations c ON cm.conversation_id = c.id
                    WHERE c.conversation_uuid = :uuid
                    ORDER BY cm.created_at ASC
                """)

                result = conn.execute(query, {"uuid": conversation_uuid})
                rows = result.fetchall()

                messages = []
                for row in rows:
                    msg = {
                        "id": row[0],
                        "message_uuid": str(row[1]),
                        "user_message": decrypt_message(row[2]) if decrypt else "[암호화됨]",
                        "bot_response": decrypt_message(row[3]) if decrypt else "[암호화됨]",
                        "used_rag": row[4],
                        "response_time_ms": row[5],
                        "created_at": row[6].isoformat()
                    }
                    messages.append(msg)

                # 접근 로그 기록
                conv_query = text("SELECT id FROM conversations WHERE conversation_uuid = :uuid")
                conv_result = conn.execute(conv_query, {"uuid": conversation_uuid})
                conv_row = conv_result.fetchone()

                if conv_row:
                    self._log_access(
                        conn,
                        conversation_id=conv_row[0],
                        access_type="decrypt" if decrypt else "read",
                        accessed_by="system",
                        access_reason="대화 내역 조회"
                    )

                logger.info(f"✅ 대화 메시지 조회: {conversation_uuid} ({len(messages)}개)")
                return messages

        except SQLAlchemyError as e:
            logger.error(f"메시지 조회 실패: {str(e)}")
            raise

    def end_conversation(self, conversation_uuid: str):
        """
        대화 세션 종료

        Args:
            conversation_uuid: 대화 세션 UUID
        """
        try:
            with self.get_connection() as conn:
                query = text("""
                    UPDATE conversations
                    SET session_end_at = CURRENT_TIMESTAMP,
                        is_active = FALSE
                    WHERE conversation_uuid = :uuid
                """)

                conn.execute(query, {"uuid": conversation_uuid})
                logger.info(f"✅ 대화 세션 종료: {conversation_uuid}")

        except SQLAlchemyError as e:
            logger.error(f"대화 세션 종료 실패: {str(e)}")
            raise

    def get_store_statistics(self, store_id: int, days: int = 30) -> Dict[str, Any]:
        """
        매장의 대화 통계 조회

        Args:
            store_id: 매장 ID
            days: 조회 기간 (일)

        Returns:
            통계 정보
        """
        try:
            with self.get_connection() as conn:
                query = text("""
                    SELECT
                        COUNT(DISTINCT c.id) as total_conversations,
                        COUNT(cm.id) as total_messages,
                        AVG(c.total_messages) as avg_messages_per_conversation,
                        SUM(CASE WHEN cm.used_rag THEN 1 ELSE 0 END) as rag_usage_count,
                        AVG(cm.response_time_ms) as avg_response_time_ms
                    FROM conversations c
                    LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
                    WHERE c.store_id = :store_id
                      AND c.created_at >= CURRENT_TIMESTAMP - INTERVAL :days DAY
                """)

                result = conn.execute(query, {"store_id": store_id, "days": f"{days} days"})
                row = result.fetchone()

                stats = {
                    "store_id": store_id,
                    "period_days": days,
                    "total_conversations": row[0] or 0,
                    "total_messages": row[1] or 0,
                    "avg_messages_per_conversation": float(row[2]) if row[2] else 0.0,
                    "rag_usage_count": row[3] or 0,
                    "avg_response_time_ms": float(row[4]) if row[4] else 0.0
                }

                return stats

        except SQLAlchemyError as e:
            logger.error(f"통계 조회 실패: {str(e)}")
            raise

    def _log_access(
        self,
        conn,
        conversation_id: int,
        access_type: str,
        accessed_by: str,
        access_reason: Optional[str] = None,
        message_id: Optional[int] = None,
        ip_hash: Optional[str] = None
    ):
        """
        데이터 접근 로그 기록 (내부 메서드)

        Args:
            conn: 데이터베이스 연결
            conversation_id: 대화 ID
            access_type: 접근 타입 (read/write/decrypt/export/delete/backup)
            accessed_by: 접근자
            access_reason: 접근 사유
            message_id: 메시지 ID (선택)
            ip_hash: 해시된 IP 주소 (선택)
        """
        try:
            query = text("""
                INSERT INTO conversation_access_logs
                (conversation_id, message_id, access_type, accessed_by,
                 access_reason, ip_address_hash, access_result)
                VALUES (:conv_id, :msg_id, :type, :by, :reason, :ip, 'success')
            """)

            conn.execute(query, {
                "conv_id": conversation_id,
                "msg_id": message_id,
                "type": access_type,
                "by": accessed_by,
                "reason": access_reason,
                "ip": ip_hash
            })

        except SQLAlchemyError as e:
            # 로그 기록 실패는 중요하지만 메인 작업을 중단하지 않음
            logger.error(f"접근 로그 기록 실패: {str(e)}")


# 전역 서비스 인스턴스 (싱글톤)
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """전역 대화 서비스 인스턴스 반환"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service


if __name__ == "__main__":
    # 테스트
    print("=" * 80)
    print("대화 저장 서비스 테스트")
    print("=" * 80)

    service = get_conversation_service()

    # 새 대화 세션 생성
    conv_uuid = service.create_conversation(
        store_id=1,
        category="customer",
        client_ip="192.168.1.100",
        user_agent="Mozilla/5.0"
    )
    print(f"\n✅ 대화 세션 생성: {conv_uuid}")

    # 메시지 저장
    message_id = service.save_message(
        conversation_uuid=conv_uuid,
        user_message="영업시간이 어떻게 되나요?",
        bot_response="평일 오전 10시부터 오후 8시까지 영업합니다.",
        used_rag=True,
        response_time_ms=1234,
        rag_doc_count=5,
        rag_max_score=0.85
    )
    print(f"✅ 메시지 저장: ID={message_id}")

    # 메시지 조회
    messages = service.get_conversation_messages(conv_uuid)
    print(f"\n✅ 저장된 메시지 ({len(messages)}개):")
    for msg in messages:
        print(f"  - 사용자: {msg['user_message']}")
        print(f"  - 봇: {msg['bot_response']}")

    # 대화 종료
    service.end_conversation(conv_uuid)
    print(f"\n✅ 대화 세션 종료")

    print("\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)
