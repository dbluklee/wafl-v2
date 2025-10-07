"""
지능형 라우터 (Intelligent Router)

Kanana 모델을 사용하여 사용자 질문을 분석하고 최적의 처리 경로를 결정합니다.

라우팅 결과:
- TOOL_CALL: 툴 호출이 필요한 경우
- RAG_QUERY: RAG 검색이 필요한 경우
- SIMPLE_QA: 일반 대화
"""

import os
import json
import logging
import re
from typing import Dict, Any, Optional
import ollama

from tool_executor import get_tool_executor

logger = logging.getLogger(__name__)


class IntelligentRouter:
    """지능형 라우터 - Kanana 기반 경로 결정"""

    def __init__(self):
        """라우터 초기화"""
        # Kanana 모델 초기화
        self.router_url = os.getenv("OLLAMA_AGENT_URL", "http://112.148.37.41:1889")
        self.router_client = ollama.Client(host=self.router_url)
        self.router_model = "huihui_ai/kanana-nano-abliterated:2.1b"

        # 툴 실행기 (툴 정보 조회용)
        self.tool_executor = get_tool_executor()

        logger.info("✅ 지능형 라우터 초기화 완료")

    async def route(self, user_message: str) -> Dict[str, Any]:
        """
        사용자 메시지를 분석하여 최적의 경로 결정

        Args:
            user_message: 사용자 메시지

        Returns:
            라우팅 결정 딕셔너리:
            {
                "route": "TOOL_CALL" | "RAG_QUERY" | "SIMPLE_QA",
                "tool_name": str (TOOL_CALL인 경우),
                "tool_params": dict (TOOL_CALL인 경우),
                "tool_type": str (TOOL_CALL인 경우),
                "query": str (RAG_QUERY/SIMPLE_QA인 경우),
                "confidence": float (0-1),
                "reasoning": str
            }
        """
        try:
            logger.info("="*80)
            logger.info("🧭 [라우터] 경로 결정 시작")
            logger.info("="*80)
            logger.info(f"📝 사용자 메시지: {user_message}")

            # 프롬프트 생성
            prompt = self._create_routing_prompt(user_message)

            logger.info(f"📋 라우터 프롬프트 생성 완료 (길이: {len(prompt)} 문자)")

            # Kanana 모델 호출
            response = self.router_client.generate(
                model=self.router_model,
                prompt=prompt
            )

            raw_response = response['response'].strip()
            logger.info(f"💬 라우터 응답:\n{raw_response}")

            # JSON 파싱
            routing_decision = self._parse_routing_response(raw_response, user_message)

            logger.info(f"✅ 라우팅 결정: {routing_decision['route']}")
            if routing_decision['route'] == 'TOOL_CALL':
                logger.info(f"   🔧 툴: {routing_decision.get('tool_name')} ({routing_decision.get('tool_type')})")
                logger.info(f"   📦 파라미터: {routing_decision.get('tool_params')}")
            logger.info("="*80)

            return routing_decision

        except Exception as e:
            logger.error(f"❌ 라우팅 오류: {str(e)}", exc_info=True)
            # 오류 시 SIMPLE_QA로 fallback
            return self._create_fallback_decision(user_message, str(e))

    def _create_routing_prompt(self, user_message: str) -> str:
        """
        라우팅 프롬프트 생성

        Args:
            user_message: 사용자 메시지

        Returns:
            프롬프트 문자열
        """
        # 사용 가능한 툴 목록 생성
        tools_info = self._format_tools_info()

        prompt = f"""당신은 사용자 질문을 분석하여 최적의 처리 경로를 결정하는 라우터입니다.

사용자 질문: "{user_message}"

다음 3가지 경로 중 하나를 선택하세요:

1. TOOL_CALL - 툴 호출이 필요한 경우
   사용 가능한 툴:
{tools_info}

2. RAG_QUERY - 매장 문서 검색이 필요한 경우
   - 매장 정보 (위치, 연락처, 영업시간, SNS)
   - 메뉴 정보 (가격, 설명, 재료)
   - 메뉴 추천 및 조합

3. SIMPLE_QA - 일반 대화
   - 인사말
   - 간단한 질문
   - 툴이나 문서 검색이 불필요한 대화

반드시 다음 JSON 형식으로만 답변하세요:

TOOL_CALL인 경우:
{{
  "route": "TOOL_CALL",
  "tool_name": "툴이름",
  "tool_params": {{"param1": "value1"}},
  "tool_type": "Self-Contained 또는 LLM-Interpreted",
  "confidence": 0.95,
  "reasoning": "선택 이유"
}}

RAG_QUERY인 경우:
{{
  "route": "RAG_QUERY",
  "query": "검색할 질문",
  "confidence": 0.9,
  "reasoning": "선택 이유"
}}

SIMPLE_QA인 경우:
{{
  "route": "SIMPLE_QA",
  "query": "사용자 질문",
  "confidence": 0.85,
  "reasoning": "선택 이유"
}}

예시:

사용자: "김치찌개 주문해줘"
답변: {{"route": "TOOL_CALL", "tool_name": "order_menu", "tool_params": {{"menu": "김치찌개", "quantity": 1}}, "tool_type": "Self-Contained", "confidence": 0.98, "reasoning": "메뉴 주문 요청"}}

사용자: "언어를 영어로 바꿔줘"
답변: {{"route": "TOOL_CALL", "tool_name": "set_language", "tool_params": {{"language": "en"}}, "tool_type": "Self-Contained", "confidence": 0.99, "reasoning": "언어 변경 요청"}}

사용자: "plz speak english"
답변: {{"route": "TOOL_CALL", "tool_name": "set_language", "tool_params": {{"language": "en"}}, "tool_type": "Self-Contained", "confidence": 0.98, "reasoning": "언어 변경 요청 (영어)"}}

사용자: "Can you speak English?"
답변: {{"route": "TOOL_CALL", "tool_name": "set_language", "tool_params": {{"language": "en"}}, "tool_type": "Self-Contained", "confidence": 0.98, "reasoning": "언어 변경 요청"}}

사용자: "한국어로 말해줘"
답변: {{"route": "TOOL_CALL", "tool_name": "set_language", "tool_params": {{"language": "ko"}}, "tool_type": "Self-Contained", "confidence": 0.99, "reasoning": "언어 변경 요청"}}

사용자: "영업시간 알려줘"
답변: {{"route": "RAG_QUERY", "query": "영업시간 알려줘", "confidence": 0.95, "reasoning": "매장 정보 조회 필요"}}

사용자: "안녕하세요"
답변: {{"route": "SIMPLE_QA", "query": "안녕하세요", "confidence": 0.99, "reasoning": "일반 인사"}}

사용자: "오늘 매출 알려줘"
답변: {{"route": "TOOL_CALL", "tool_name": "get_sales_data", "tool_params": {{"date": "today", "period": "daily"}}, "tool_type": "LLM-Interpreted", "confidence": 0.97, "reasoning": "매출 데이터 조회"}}

이제 위 사용자 질문에 대해 JSON으로만 답변하세요:"""

        return prompt

    def _format_tools_info(self) -> str:
        """
        툴 정보를 프롬프트용 문자열로 포맷팅

        Returns:
            포맷팅된 툴 정보 문자열
        """
        tools = self.tool_executor.get_available_tools()

        lines = []
        for tool in tools:
            tool_name = tool['name']
            description = tool['description']
            tool_type = tool['tool_type']
            params = tool['parameters']

            param_strs = []
            for param_name, param_info in params.items():
                required = "필수" if param_info.get('required', False) else "선택"
                param_type = param_info.get('type', 'any')
                param_strs.append(f"{param_name}({param_type}, {required})")

            params_str = ", ".join(param_strs) if param_strs else "파라미터 없음"

            lines.append(f"   - {tool_name} ({tool_type}): {description}")
            lines.append(f"     파라미터: {params_str}")

        return "\n".join(lines)

    def _parse_routing_response(
        self,
        raw_response: str,
        user_message: str
    ) -> Dict[str, Any]:
        """
        라우터 응답 파싱

        Args:
            raw_response: 라우터 원본 응답
            user_message: 사용자 메시지

        Returns:
            파싱된 라우팅 결정
        """
        try:
            # JSON 블록 추출 시도
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                decision = json.loads(json_str)

                # 필수 필드 검증
                if "route" not in decision:
                    raise ValueError("'route' 필드가 없습니다")

                route = decision["route"]

                # 경로별 추가 검증
                if route == "TOOL_CALL":
                    if "tool_name" not in decision:
                        raise ValueError("TOOL_CALL에는 'tool_name' 필드가 필요합니다")
                    if "tool_params" not in decision:
                        decision["tool_params"] = {}
                    if "tool_type" not in decision:
                        # 툴 정보에서 tool_type 조회
                        tool_info = self.tool_executor.get_tool_info(decision["tool_name"])
                        if tool_info:
                            decision["tool_type"] = tool_info["tool_type"]
                        else:
                            raise ValueError(f"존재하지 않는 툴: {decision['tool_name']}")

                elif route in ["RAG_QUERY", "SIMPLE_QA"]:
                    if "query" not in decision:
                        decision["query"] = user_message

                else:
                    raise ValueError(f"알 수 없는 route 값: {route}")

                # confidence 기본값 설정
                if "confidence" not in decision:
                    decision["confidence"] = 0.8

                # reasoning 기본값 설정
                if "reasoning" not in decision:
                    decision["reasoning"] = "자동 결정"

                return decision

            else:
                raise ValueError("JSON 형식을 찾을 수 없습니다")

        except Exception as e:
            logger.warning(f"⚠️ JSON 파싱 실패: {str(e)}")
            logger.warning(f"⚠️ 원본 응답: {raw_response}")

            # 휴리스틱 기반 fallback
            return self._heuristic_routing(user_message, raw_response)

    def _heuristic_routing(
        self,
        user_message: str,
        raw_response: str
    ) -> Dict[str, Any]:
        """
        휴리스틱 기반 라우팅 (JSON 파싱 실패 시 fallback)

        Args:
            user_message: 사용자 메시지
            raw_response: 라우터 원본 응답

        Returns:
            라우팅 결정
        """
        logger.info("🔄 휴리스틱 기반 라우팅 시도")

        message_lower = user_message.lower()

        # 1. 툴 호출 키워드 체크
        tool_keywords = {
            "order_menu": ["주문", "시켜", "먹고싶", "먹을게"],
            "set_language": ["언어", "영어", "english", "일본어", "중국어", "speak", "language", "korean", "japanese", "chinese", "한국어", "말해"],
            "navigate_to": ["화면", "페이지", "이동", "보여줘", "가기"],
            "get_sales_data": ["매출", "판매", "수익"],
            "get_order_statistics": ["통계", "순위", "인기"],
            "analyze_trends": ["트렌드", "분석", "추세"]
        }

        for tool_name, keywords in tool_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                tool_info = self.tool_executor.get_tool_info(tool_name)
                if tool_info:
                    logger.info(f"✅ 휴리스틱 매칭: {tool_name}")

                    # 특별 처리: set_language 툴인 경우 파라미터 추출 시도
                    tool_params = {}
                    if tool_name == "set_language":
                        # 언어 키워드 추출
                        lang_map = {
                            "english": "en", "영어": "en",
                            "korean": "ko", "한국어": "ko",
                            "japanese": "ja", "일본어": "ja",
                            "chinese": "zh", "중국어": "zh"
                        }
                        for lang_keyword, lang_code in lang_map.items():
                            if lang_keyword in message_lower:
                                tool_params = {"language": lang_code}
                                break

                        # 파라미터를 찾지 못한 경우 기본값 사용
                        if not tool_params:
                            tool_params = {"language": "en"}  # 기본값

                    return {
                        "route": "TOOL_CALL",
                        "tool_name": tool_name,
                        "tool_params": tool_params,
                        "tool_type": tool_info["tool_type"],
                        "confidence": 0.6,
                        "reasoning": "휴리스틱 기반 매칭"
                    }

        # 2. RAG 키워드 체크
        rag_keywords = ["메뉴", "가격", "영업시간", "위치", "전화", "추천", "어디", "언제", "얼마"]
        if any(keyword in message_lower for keyword in rag_keywords):
            logger.info("✅ 휴리스틱 매칭: RAG_QUERY")
            return {
                "route": "RAG_QUERY",
                "query": user_message,
                "confidence": 0.65,
                "reasoning": "휴리스틱 기반 매칭 (매장 정보 키워드)"
            }

        # 3. 기본값: SIMPLE_QA
        logger.info("✅ 휴리스틱 매칭: SIMPLE_QA (기본값)")
        return {
            "route": "SIMPLE_QA",
            "query": user_message,
            "confidence": 0.5,
            "reasoning": "휴리스틱 기반 기본값"
        }

    def _create_fallback_decision(
        self,
        user_message: str,
        error_msg: str
    ) -> Dict[str, Any]:
        """
        에러 발생 시 fallback 결정 생성

        Args:
            user_message: 사용자 메시지
            error_msg: 에러 메시지

        Returns:
            Fallback 라우팅 결정
        """
        logger.warning(f"⚠️ Fallback 라우팅: SIMPLE_QA")
        return {
            "route": "SIMPLE_QA",
            "query": user_message,
            "confidence": 0.3,
            "reasoning": f"에러 발생으로 인한 fallback: {error_msg}"
        }


# 전역 라우터 인스턴스
_global_router: Optional[IntelligentRouter] = None


def get_router() -> IntelligentRouter:
    """
    전역 라우터 인스턴스 가져오기 (싱글톤)

    Returns:
        IntelligentRouter 인스턴스
    """
    global _global_router
    if _global_router is None:
        _global_router = IntelligentRouter()
    return _global_router
