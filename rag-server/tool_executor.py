"""
툴 실행기

툴 레지스트리에서 툴을 가져와 실행하고 결과를 반환합니다.
파라미터 검증 및 에러 핸들링을 담당합니다.
"""

import logging
from typing import Dict, Any, Optional
from tools import get_tool_registry, BaseTool, ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """툴 실행 및 결과 처리"""

    def __init__(self):
        """툴 실행기 초기화"""
        self.registry: ToolRegistry = get_tool_registry()
        logger.info("✅ 툴 실행기 초기화 완료")

    async def execute_tool(
        self,
        tool_name: str,
        tool_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        툴 실행

        Args:
            tool_name: 실행할 툴 이름
            tool_params: 툴 파라미터 딕셔너리

        Returns:
            {
                "success": bool,
                "result": Any,
                "notification": str,
                "tool_name": str,
                "tool_type": str,
                "error": str (if failed)
            }
        """
        if tool_params is None:
            tool_params = {}

        logger.info("="*80)
        logger.info(f"🔧 [툴 실행기] 툴 실행 시작: {tool_name}")
        logger.info(f"📝 파라미터: {tool_params}")
        logger.info("="*80)

        try:
            # 1. 툴 존재 여부 확인
            if not self.registry.tool_exists(tool_name):
                error_msg = f"존재하지 않는 툴입니다: {tool_name}"
                logger.error(f"❌ {error_msg}")
                return self._create_error_response(error_msg, tool_name)

            # 2. 툴 가져오기
            tool = self.registry.get_tool(tool_name)
            if tool is None:
                error_msg = f"툴을 가져올 수 없습니다: {tool_name}"
                logger.error(f"❌ {error_msg}")
                return self._create_error_response(error_msg, tool_name)

            # 3. 파라미터 검증
            validation_result = self.validate_params(tool, tool_params)
            if not validation_result["valid"]:
                error_msg = f"파라미터 검증 실패: {validation_result['error']}"
                logger.error(f"❌ {error_msg}")
                return self._create_error_response(error_msg, tool_name)

            # 4. 툴 실행
            logger.info(f"▶️  툴 실행 중: {tool_name} ({tool.tool_type})")
            result = tool.execute(**tool_params)

            logger.info(f"✅ 툴 실행 완료: {tool_name}")
            logger.info(f"📦 결과: {result.get('notification', '')}")
            logger.info("="*80)

            return result

        except TypeError as e:
            error_msg = f"파라미터 타입 오류: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return self._create_error_response(error_msg, tool_name)

        except Exception as e:
            error_msg = f"툴 실행 중 오류 발생: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return self._create_error_response(error_msg, tool_name)

    def validate_params(
        self,
        tool: BaseTool,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        툴 파라미터 검증

        Args:
            tool: 검증할 툴
            params: 검증할 파라미터

        Returns:
            {
                "valid": bool,
                "error": str (if invalid),
                "missing_params": list (if invalid)
            }
        """
        try:
            tool_params_schema = tool.parameters

            # 필수 파라미터 확인
            missing_params = []
            for param_name, param_info in tool_params_schema.items():
                if param_info.get("required", False):
                    if param_name not in params or params[param_name] is None:
                        missing_params.append(param_name)

            if missing_params:
                return {
                    "valid": False,
                    "error": f"필수 파라미터 누락: {', '.join(missing_params)}",
                    "missing_params": missing_params
                }

            # enum 값 검증 (있는 경우)
            for param_name, param_value in params.items():
                if param_name in tool_params_schema:
                    param_info = tool_params_schema[param_name]
                    enum_values = param_info.get("enum")

                    if enum_values and param_value not in enum_values:
                        return {
                            "valid": False,
                            "error": f"'{param_name}' 파라미터는 다음 값 중 하나여야 합니다: {', '.join(enum_values)}",
                            "allowed_values": enum_values
                        }

            # 타입 검증 (기본적인 검증만)
            for param_name, param_value in params.items():
                if param_name in tool_params_schema:
                    param_info = tool_params_schema[param_name]
                    expected_type = param_info.get("type")

                    if expected_type == "string" and not isinstance(param_value, str):
                        return {
                            "valid": False,
                            "error": f"'{param_name}' 파라미터는 문자열이어야 합니다"
                        }
                    elif expected_type == "integer" and not isinstance(param_value, int):
                        # 숫자 문자열은 자동 변환 시도
                        try:
                            params[param_name] = int(param_value)
                        except (ValueError, TypeError):
                            return {
                                "valid": False,
                                "error": f"'{param_name}' 파라미터는 정수여야 합니다"
                            }

            return {"valid": True}

        except Exception as e:
            logger.error(f"파라미터 검증 중 오류: {str(e)}")
            return {
                "valid": False,
                "error": f"파라미터 검증 중 오류 발생: {str(e)}"
            }

    def _create_error_response(
        self,
        error_msg: str,
        tool_name: str
    ) -> Dict[str, Any]:
        """
        에러 응답 생성

        Args:
            error_msg: 에러 메시지
            tool_name: 툴 이름

        Returns:
            에러 응답 딕셔너리
        """
        return {
            "success": False,
            "error": error_msg,
            "tool_name": tool_name,
            "notification": f"❌ [툴 실행 실패] {tool_name} - {error_msg}"
        }

    def get_available_tools(self) -> list:
        """
        사용 가능한 모든 툴 정보 조회

        Returns:
            툴 정보 리스트
        """
        return self.registry.get_all_tools_info()

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        특정 툴 정보 조회

        Args:
            tool_name: 툴 이름

        Returns:
            툴 정보 또는 None
        """
        return self.registry.get_tool_info(tool_name)


# 전역 툴 실행기 인스턴스
_global_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """
    전역 툴 실행기 인스턴스 가져오기 (싱글톤)

    Returns:
        ToolExecutor 인스턴스
    """
    global _global_executor
    if _global_executor is None:
        _global_executor = ToolExecutor()
    return _global_executor
