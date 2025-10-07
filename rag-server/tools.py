"""
툴 정의 및 레지스트리

이 모듈은 시스템에서 사용할 수 있는 모든 툴을 정의하고 관리합니다.
현재는 실제 동작 없이 실행 노티만 표시합니다.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """툴 베이스 클래스"""

    name: str = ""
    description: str = ""
    tool_type: str = ""  # "Self-Contained" or "LLM-Interpreted"
    parameters: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        툴 실행 (현재는 노티만 표시)

        Returns:
            {
                "success": bool,
                "notification": str,
                "result": Any,
                "executed_at": str
            }
        """
        pass

    def _create_notification(self, params_str: str = "") -> str:
        """노티 메시지 생성"""
        if params_str:
            return f"✅ [툴 실행] {self.name} - {params_str}"
        return f"✅ [툴 실행] {self.name}"

    def _create_response(self, notification: str, result: Any = None) -> Dict[str, Any]:
        """표준 응답 형식 생성"""
        return {
            "success": True,
            "notification": notification,
            "result": result,
            "executed_at": datetime.now().isoformat(),
            "tool_name": self.name,
            "tool_type": self.tool_type
        }


# ============================================================================
# 자체 처리 툴 (Self-Contained Tools)
# LLM 해석 없이 즉시 응답 가능한 툴
# ============================================================================

class SetLanguageTool(BaseTool):
    """언어 설정 변경 툴"""

    name = "set_language"
    description = "사용자 인터페이스 언어를 변경합니다. 영어(en), 한국어(ko), 일본어(ja), 중국어(zh) 지원"
    tool_type = "Self-Contained"
    parameters = {
        "language": {
            "type": "string",
            "description": "변경할 언어 코드. 한국어=ko, 영어/English=en, 일본어/日本語=ja, 중국어/中文=zh",
            "required": False,  # 기본값이 있으므로 선택사항으로 변경
            "default": "en",
            "enum": ["ko", "en", "ja", "zh"]
        }
    }

    def execute(self, language: str = "en", **kwargs) -> Dict[str, Any]:
        """
        언어 설정 변경

        Args:
            language: 언어 코드 (ko, en, ja, zh). 기본값은 en
        """
        # 언어 코드 정규화 (소문자 변환)
        language = language.lower().strip()

        # 언어 이름 매핑
        language_names = {
            "ko": "한국어",
            "en": "English",
            "ja": "日本語",
            "zh": "中文"
        }

        # 언어 이름을 코드로 변환 (예: "english" -> "en")
        language_name_to_code = {
            "korean": "ko", "한국어": "ko", "korea": "ko",
            "english": "en", "영어": "en",
            "japanese": "ja", "일본어": "ja", "japan": "ja", "日本語": "ja",
            "chinese": "zh", "중국어": "zh", "china": "zh", "中文": "zh"
        }

        # 언어 이름이 입력된 경우 코드로 변환
        if language in language_name_to_code:
            language = language_name_to_code[language]

        # 지원하지 않는 언어인 경우 기본값 사용
        if language not in language_names:
            logger.warning(f"지원하지 않는 언어: {language}, 기본값(en) 사용")
            language = "en"

        lang_name = language_names.get(language, language)
        notification = self._create_notification(f"언어를 {lang_name}(으)로 변경")

        logger.info(notification)

        return self._create_response(
            notification=notification,
            result={
                "language": language,
                "language_name": lang_name,
                "message": f"언어가 {lang_name}(으)로 변경되었습니다"
            }
        )


class OrderMenuTool(BaseTool):
    """메뉴 주문 툴"""

    name = "order_menu"
    description = "고객이 원하는 메뉴를 주문합니다"
    tool_type = "Self-Contained"
    parameters = {
        "menu": {
            "type": "string",
            "description": "주문할 메뉴명",
            "required": True
        },
        "quantity": {
            "type": "integer",
            "description": "주문 수량",
            "required": False,
            "default": 1
        },
        "options": {
            "type": "string",
            "description": "추가 옵션 (예: '맵게', '덜 맵게')",
            "required": False
        }
    }

    def execute(self, menu: str, quantity: int = 1, options: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        메뉴 주문

        Args:
            menu: 메뉴명
            quantity: 수량
            options: 추가 옵션
        """
        params_parts = [f"{menu} {quantity}개"]
        if options:
            params_parts.append(f"옵션: {options}")

        notification = self._create_notification(", ".join(params_parts))
        logger.info(notification)

        result_message = f"{menu} {quantity}개 주문이 완료되었습니다"
        if options:
            result_message += f" (옵션: {options})"

        return self._create_response(
            notification=notification,
            result={
                "menu": menu,
                "quantity": quantity,
                "options": options,
                "message": result_message,
                "order_id": f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
        )


class NavigateToTool(BaseTool):
    """UI 네비게이션 툴"""

    name = "navigate_to"
    description = "사용자를 특정 화면이나 페이지로 이동시킵니다"
    tool_type = "Self-Contained"
    parameters = {
        "destination": {
            "type": "string",
            "description": "이동할 화면/페이지",
            "required": True,
            "enum": ["menu", "order_history", "settings", "store_info", "reviews", "home"]
        }
    }

    def execute(self, destination: str, **kwargs) -> Dict[str, Any]:
        """
        화면 이동

        Args:
            destination: 이동할 화면 (menu, order_history, settings, store_info, reviews, home)
        """
        destination_names = {
            "menu": "메뉴 화면",
            "order_history": "주문 내역",
            "settings": "설정 화면",
            "store_info": "매장 정보",
            "reviews": "리뷰 화면",
            "home": "홈 화면"
        }

        dest_name = destination_names.get(destination, destination)
        notification = self._create_notification(f"{dest_name}으로 이동")

        logger.info(notification)

        return self._create_response(
            notification=notification,
            result={
                "destination": destination,
                "destination_name": dest_name,
                "message": f"{dest_name}으로 이동합니다"
            }
        )


class ApplyFilterTool(BaseTool):
    """필터 적용 툴"""

    name = "apply_filter"
    description = "메뉴나 상품 목록에 필터를 적용합니다"
    tool_type = "Self-Contained"
    parameters = {
        "filter_type": {
            "type": "string",
            "description": "필터 유형",
            "required": True,
            "enum": ["category", "price", "popularity", "spicy_level"]
        },
        "filter_value": {
            "type": "string",
            "description": "필터 값",
            "required": True
        }
    }

    def execute(self, filter_type: str, filter_value: str, **kwargs) -> Dict[str, Any]:
        """
        필터 적용

        Args:
            filter_type: 필터 유형 (category, price, popularity, spicy_level)
            filter_value: 필터 값
        """
        filter_type_names = {
            "category": "카테고리",
            "price": "가격",
            "popularity": "인기도",
            "spicy_level": "매운맛"
        }

        type_name = filter_type_names.get(filter_type, filter_type)
        notification = self._create_notification(f"{type_name} 필터 적용: {filter_value}")

        logger.info(notification)

        return self._create_response(
            notification=notification,
            result={
                "filter_type": filter_type,
                "filter_value": filter_value,
                "message": f"{type_name} 필터가 '{filter_value}'(으)로 적용되었습니다"
            }
        )


# ============================================================================
# LLM 해석 툴 (LLM-Interpreted Tools)
# 툴 실행 결과를 Gemma3가 자연어로 해석해야 하는 툴
# ============================================================================

class GetSalesDataTool(BaseTool):
    """매출 데이터 조회 툴"""

    name = "get_sales_data"
    description = "특정 기간의 매출 데이터를 조회합니다"
    tool_type = "LLM-Interpreted"
    parameters = {
        "date": {
            "type": "string",
            "description": "조회할 날짜 (today, yesterday, YYYY-MM-DD)",
            "required": False,
            "default": "today"
        },
        "period": {
            "type": "string",
            "description": "조회 기간 (daily, weekly, monthly)",
            "required": False,
            "default": "daily"
        }
    }

    def execute(self, date: str = "today", period: str = "daily", **kwargs) -> Dict[str, Any]:
        """
        매출 데이터 조회

        Args:
            date: 조회 날짜
            period: 조회 기간
        """
        notification = self._create_notification(f"{date} 매출 데이터 조회 (기간: {period})")
        logger.info(notification)

        # 실제로는 DB에서 조회하지만, 현재는 더미 데이터 반환
        dummy_data = {
            "date": date,
            "period": period,
            "total_sales": 1500000,  # 150만원
            "order_count": 45,
            "average_order_value": 33333,
            "comparison": {
                "previous_period": 1350000,
                "change_percent": 11.1
            },
            "top_menu": "김치찌개",
            "peak_hour": "12:00-13:00"
        }

        return self._create_response(
            notification=notification,
            result=dummy_data
        )


class GetOrderStatisticsTool(BaseTool):
    """주문 통계 조회 툴"""

    name = "get_order_statistics"
    description = "주문 통계 정보를 조회합니다"
    tool_type = "LLM-Interpreted"
    parameters = {
        "period": {
            "type": "string",
            "description": "통계 기간 (today, week, month)",
            "required": False,
            "default": "today"
        },
        "stat_type": {
            "type": "string",
            "description": "통계 유형 (menu_ranking, time_distribution, category)",
            "required": False,
            "default": "menu_ranking"
        }
    }

    def execute(self, period: str = "today", stat_type: str = "menu_ranking", **kwargs) -> Dict[str, Any]:
        """
        주문 통계 조회

        Args:
            period: 통계 기간
            stat_type: 통계 유형
        """
        notification = self._create_notification(f"{period} 주문 통계 조회 (유형: {stat_type})")
        logger.info(notification)

        # 더미 통계 데이터
        dummy_data = {
            "period": period,
            "stat_type": stat_type,
            "total_orders": 45,
            "menu_ranking": [
                {"rank": 1, "menu": "김치찌개", "count": 15, "percentage": 33.3},
                {"rank": 2, "menu": "된장찌개", "count": 12, "percentage": 26.7},
                {"rank": 3, "menu": "비빔밥", "count": 10, "percentage": 22.2},
                {"rank": 4, "menu": "불고기", "count": 5, "percentage": 11.1},
                {"rank": 5, "menu": "냉면", "count": 3, "percentage": 6.7}
            ],
            "time_distribution": {
                "morning": 5,
                "lunch": 25,
                "afternoon": 8,
                "dinner": 7
            }
        }

        return self._create_response(
            notification=notification,
            result=dummy_data
        )


class AnalyzeTrendsTool(BaseTool):
    """트렌드 분석 툴"""

    name = "analyze_trends"
    description = "매출 및 주문 트렌드를 분석합니다"
    tool_type = "LLM-Interpreted"
    parameters = {
        "analysis_type": {
            "type": "string",
            "description": "분석 유형 (sales, menu, customer)",
            "required": False,
            "default": "sales"
        },
        "period": {
            "type": "string",
            "description": "분석 기간 (week, month, quarter)",
            "required": False,
            "default": "week"
        }
    }

    def execute(self, analysis_type: str = "sales", period: str = "week", **kwargs) -> Dict[str, Any]:
        """
        트렌드 분석

        Args:
            analysis_type: 분석 유형
            period: 분석 기간
        """
        notification = self._create_notification(f"{analysis_type} 트렌드 분석 ({period})")
        logger.info(notification)

        # 더미 트렌드 데이터
        dummy_data = {
            "analysis_type": analysis_type,
            "period": period,
            "trend": "increasing",  # increasing, decreasing, stable
            "trend_percentage": 15.5,
            "insights": [
                "주말 매출이 평일 대비 20% 높습니다",
                "점심 시간대(12-13시) 주문이 집중되어 있습니다",
                "김치찌개가 지속적으로 1위를 유지하고 있습니다"
            ],
            "recommendations": [
                "점심 시간대 직원 배치 강화 권장",
                "인기 메뉴 재고 관리 필요"
            ],
            "data_points": [
                {"date": "2025-10-01", "value": 1200000},
                {"date": "2025-10-02", "value": 1350000},
                {"date": "2025-10-03", "value": 1400000},
                {"date": "2025-10-04", "value": 1450000},
                {"date": "2025-10-05", "value": 1600000},
                {"date": "2025-10-06", "value": 1750000},
                {"date": "2025-10-07", "value": 1500000}
            ]
        }

        return self._create_response(
            notification=notification,
            result=dummy_data
        )


# ============================================================================
# 툴 레지스트리
# ============================================================================

class ToolRegistry:
    """툴 레지스트리 - 모든 툴을 관리하는 중앙 저장소"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """기본 툴 등록"""
        # 자체 처리 툴
        self.register_tool(SetLanguageTool())
        self.register_tool(OrderMenuTool())
        self.register_tool(NavigateToTool())
        self.register_tool(ApplyFilterTool())

        # LLM 해석 툴
        self.register_tool(GetSalesDataTool())
        self.register_tool(GetOrderStatisticsTool())
        self.register_tool(AnalyzeTrendsTool())

        logger.info(f"✅ 툴 레지스트리 초기화 완료: {len(self._tools)}개 툴 등록")

    def register_tool(self, tool: BaseTool):
        """
        툴 등록

        Args:
            tool: 등록할 툴 인스턴스
        """
        if not tool.name:
            raise ValueError("툴 이름이 없습니다")

        self._tools[tool.name] = tool
        logger.debug(f"툴 등록: {tool.name} ({tool.tool_type})")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        툴 조회

        Args:
            tool_name: 툴 이름

        Returns:
            BaseTool 또는 None
        """
        return self._tools.get(tool_name)

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """
        모든 툴 조회

        Returns:
            툴 딕셔너리 {tool_name: tool_instance}
        """
        return self._tools.copy()

    def get_tools_by_type(self, tool_type: str) -> Dict[str, BaseTool]:
        """
        특정 유형의 툴만 조회

        Args:
            tool_type: "Self-Contained" 또는 "LLM-Interpreted"

        Returns:
            필터링된 툴 딕셔너리
        """
        return {
            name: tool
            for name, tool in self._tools.items()
            if tool.tool_type == tool_type
        }

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        툴 정보 조회 (라우터에서 사용)

        Args:
            tool_name: 툴 이름

        Returns:
            툴 정보 딕셔너리 또는 None
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "tool_type": tool.tool_type,
            "parameters": tool.parameters
        }

    def get_all_tools_info(self) -> list:
        """
        모든 툴의 정보 조회 (라우터 프롬프트 생성용)

        Returns:
            툴 정보 리스트
        """
        return [
            self.get_tool_info(tool_name)
            for tool_name in self._tools.keys()
        ]

    def tool_exists(self, tool_name: str) -> bool:
        """툴 존재 여부 확인"""
        return tool_name in self._tools


# 전역 툴 레지스트리 인스턴스
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    전역 툴 레지스트리 인스턴스 가져오기 (싱글톤)

    Returns:
        ToolRegistry 인스턴스
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
