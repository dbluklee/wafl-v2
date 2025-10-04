import os
import logging
import ollama

logger = logging.getLogger(__name__)


class Agent:
    """에이전트 시스템: RAG 필요 여부 판단 및 일반 대화"""

    def __init__(self):
        # 에이전트용 LLM (RAG 필요 여부 판단용)
        self.agent_url = os.getenv("OLLAMA_AGENT_URL", "http://112.148.37.41:1889")
        self.agent_client = ollama.Client(host=self.agent_url)
        self.agent_model = "huihui_ai/kanana-nano-abliterated:2.1b"

        # 메인 LLM (실제 대화용)
        self.main_url = os.getenv("OLLAMA_MAIN_URL", "http://112.148.37.41:1884")
        self.main_client = ollama.Client(host=self.main_url)
        self.main_model = "gemma3:27b-it-q4_K_M"

    async def needs_rag(self, user_message: str) -> tuple[bool, dict]:
        """
        사용자 메시지가 RAG가 필요한지 판단

        RAG가 필요한 경우:
        - 매장 정보 문의
        - 메뉴 문의
        - 운영 시간, 위치 등 정보 요청

        RAG가 불필요한 경우:
        - 일반 인사
        - 간단한 질문
        - 메뉴 주문 (Function Calling으로 처리 - 추후 구현)

        Returns:
            tuple[bool, dict]: (RAG 필요 여부, 디버그 정보)
        """
        try:
            prompt = f"""다음 사용자 메시지가 아래 카테고리에 해당하는지 판단하세요.

매장 문서 검색이 필요한 카테고리:
1. 매장 정보 (위치, 연락처, 영업시간, SNS 등)
2. 메뉴 추천
3. 메뉴 질문 (가격, 설명, 재료 등)
4. 메뉴 조합 추천 (페어링, 함께 먹으면 좋은 메뉴)

사용자 메시지: {user_message}

위 카테고리에 해당하면 "YES", 해당하지 않으면 "NO"로만 답변하세요.

예시:
- "메뉴 추천해줘" -> YES (메뉴 추천)
- "비빔냉면 가격이 얼마야?" -> YES (메뉴 질문)
- "뭐랑 같이 먹으면 좋아?" -> YES (메뉴 조합)
- "영업시간 알려줘" -> YES (매장 정보)
- "전화번호 알려줘" -> YES (매장 정보)
- "안녕하세요" -> NO (일반 인사)
- "고마워" -> NO (일반 대화)
- "날씨 어때?" -> NO (매장 무관)

답변:"""

            logger.info("="*80)
            logger.info("🤖 [에이전트] RAG 필요 여부 판단")
            logger.info("="*80)
            logger.info(f"📝 프롬프트:\n{prompt}")

            response = self.agent_client.generate(
                model=self.agent_model,
                prompt=prompt
            )

            answer = response['response'].strip().upper()
            needs_rag = "YES" in answer

            logger.info(f"💬 에이전트 응답: {answer}")
            logger.info(f"✅ RAG 필요 여부: {needs_rag}")
            logger.info("="*80)

            debug_info = {
                "agent_prompt": prompt,
                "agent_response": answer,
                "agent_model": self.agent_model
            }

            return needs_rag, debug_info

        except Exception as e:
            logger.error(f"RAG 판단 오류: {str(e)}")
            # 오류 시 안전하게 RAG 사용
            return True, {"error": str(e)}

    async def chat(self, user_message: str) -> tuple[str, dict]:
        """일반 대화 (RAG 불필요) - 메인 LLM 사용

        Returns:
            tuple[str, dict]: (응답, 디버그 정보)
        """
        try:
            prompt = f"""당신은 매장의 친절한 직원입니다.

답변 규칙:
1. 50자 이내로 간결하게 답변하세요
2. 손님이 원하는 핵심 내용만 전달하세요
3. 친절하지만 요점만 말하세요
4. 불필요한 설명은 생략하세요
5. **중요**: 모르는 내용은 절대 지어내지 마세요
6. 확실하지 않으면 "제가 잘 모르겠어요. 죄송하지만 직원에게 문의해주세요"라고 답변하세요

사용자: {user_message}
직원:"""

            logger.info("="*80)
            logger.info("💬 [메인 LLM] 일반 대화")
            logger.info("="*80)
            logger.info(f"📝 프롬프트:\n{prompt}")

            # 메인 LLM 사용 (Gemma3)
            response = self.main_client.generate(
                model=self.main_model,
                prompt=prompt
            )

            answer = response['response'].strip()

            # 50자 제한 체크 및 추가 설명 제안
            if len(answer) > 50:
                answer = answer[:50] + "..."
                answer += "\n\n더 자세히 설명해드릴까요?"

            logger.info(f"💬 메인 LLM 응답: {answer}")
            logger.info("="*80)

            debug_info = {
                "chat_prompt": prompt,
                "chat_response": answer,
                "chat_model": self.main_model
            }

            return answer, debug_info

        except Exception as e:
            logger.error(f"대화 오류: {str(e)}")
            return "죄송합니다. 일시적인 오류가 발생했습니다.", {"error": str(e)}
