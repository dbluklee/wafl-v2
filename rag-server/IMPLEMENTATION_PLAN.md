# LLM 툴 호출 적응형 라우팅 시스템 구현 계획

## 📌 프로젝트 개요

### 현재 시스템
```
사용자 질문 → Agent (Kanana) → RAG 판단 (YES/NO) → Gemma3 → 응답
```

### 목표 시스템
```
사용자 질문 → 지능형 라우터 (Kanana) → 3가지 경로 결정 (JSON)
                                        ├─ TOOL_CALL → 툴 실행
                                        │              ├─ Self-Contained → 즉시 응답 (LLM 우회)
                                        │              └─ LLM-Interpreted → Gemma3 해석
                                        ├─ RAG_QUERY → RAG Pipeline → Gemma3
                                        └─ SIMPLE_QA → Gemma3 직접 응답
```

## 🎯 핵심 개념

### 1. 지능형 라우터 (Intelligent Router)
- **역할**: 시스템의 최전방에서 모든 사용자 질문을 받아 최적의 처리 경로 결정
- **모델**: Kanana (기존 Agent의 역할 확장)
- **출력**: 구조화된 JSON 응답

### 2. 툴 유형 분류

#### A. 자체 처리 툴 (Self-Contained Tool)
- **특징**: LLM 해석 없이 즉시 실행 후 응답 완료
- **장점**: 빠른 속도, 낮은 비용
- **예시**:
  - `set_language`: 언어 설정 변경
  - `order_menu`: 메뉴 주문
  - `navigate_to`: UI 네비게이션
  - `apply_filter`: 필터 적용

#### B. LLM 해석 툴 (LLM-Interpreted Tool)
- **특징**: 툴 실행 결과를 Gemma3가 자연어로 해석 필요
- **장점**: 신뢰성, 품질 높은 응답
- **예시**:
  - `get_sales_data`: 매출 데이터 조회
  - `get_order_statistics`: 주문 통계 분석
  - `analyze_trends`: 트렌드 분석

### 3. 라우터 JSON 출력 구조

#### Route Type 1: TOOL_CALL
```json
{
  "route": "TOOL_CALL",
  "tool_name": "order_menu",
  "tool_params": {
    "menu": "김치찌개",
    "quantity": 1
  },
  "tool_type": "Self-Contained"
}
```

#### Route Type 2: RAG_QUERY
```json
{
  "route": "RAG_QUERY",
  "query": "매장 운영시간 알려줘"
}
```

#### Route Type 3: SIMPLE_QA
```json
{
  "route": "SIMPLE_QA",
  "query": "안녕하세요"
}
```

## 📊 처리 시나리오 예시

| 사용자 질문 | 라우터 판단 | Route | 툴 유형 | 실행 결과 및 최종 응답 |
|-----------|-----------|-------|--------|---------------------|
| "Can you speak English?" | TOOL_CALL | `set_language` | Self-Contained | 실행 후 즉시 "Language changed to English" 응답 |
| "김치찌개 주문해줘" | TOOL_CALL | `order_menu` | Self-Contained | 실행 후 "김치찌개 주문이 완료되었습니다" 응답 |
| "오늘 매출 알려줘" | TOOL_CALL | `get_sales_data` | LLM-Interpreted | 툴 실행 → 데이터 조회 → Gemma3가 "오늘 매출은 150만원입니다. 전날 대비 10% 증가했습니다" 응답 |
| "매장 운영시간은?" | RAG_QUERY | N/A | N/A | RAG 검색 → Gemma3가 "평일 오전 11시부터 오후 10시까지입니다" 응답 |
| "안녕하세요" | SIMPLE_QA | N/A | N/A | Gemma3가 "안녕하세요! 무엇을 도와드릴까요?" 응답 |

## 🏗️ 구현 아키텍처

### 파일 구조
```
rag-server/
├── router.py              # 지능형 라우터 (Kanana 기반) [신규]
├── tools.py               # 툴 정의 및 레지스트리 [신규]
├── tool_executor.py       # 툴 실행기 [신규]
├── agent.py               # 기존 Agent (백업 또는 삭제)
├── rag_pipeline.py        # RAG Pipeline (유지)
├── main.py                # 메인 API (수정)
└── IMPLEMENTATION_PLAN.md # 이 문서
```

### 컴포넌트 상세 설계

#### 1. `router.py` - 지능형 라우터
```python
class IntelligentRouter:
    """
    Kanana 모델을 사용하여 사용자 질문을 분석하고 최적의 처리 경로 결정
    """

    def __init__(self):
        # Kanana 모델 초기화
        pass

    async def route(self, user_message: str) -> dict:
        """
        사용자 메시지를 분석하여 라우팅 결정

        Returns:
            {
                "route": "TOOL_CALL" | "RAG_QUERY" | "SIMPLE_QA",
                "tool_name": str (if TOOL_CALL),
                "tool_params": dict (if TOOL_CALL),
                "tool_type": "Self-Contained" | "LLM-Interpreted" (if TOOL_CALL),
                "query": str (if RAG_QUERY or SIMPLE_QA)
            }
        """
        pass
```

#### 2. `tools.py` - 툴 정의
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """툴 베이스 클래스"""

    name: str
    description: str
    tool_type: str  # "Self-Contained" or "LLM-Interpreted"

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """툴 실행 (현재는 노티만 표시)"""
        pass

class ToolRegistry:
    """툴 레지스트리 - 모든 툴 관리"""

    def register_tool(self, tool: BaseTool):
        pass

    def get_tool(self, tool_name: str) -> BaseTool:
        pass

    def get_all_tools(self) -> list:
        pass
```

**구현할 툴 목록:**

**자체 처리 툴 (Self-Contained):**
- `SetLanguageTool`: 언어 설정 변경
- `OrderMenuTool`: 메뉴 주문
- `NavigateToTool`: UI 네비게이션
- `ApplyFilterTool`: 필터 적용

**LLM 해석 툴 (LLM-Interpreted):**
- `GetSalesDataTool`: 매출 데이터 조회
- `GetOrderStatisticsTool`: 주문 통계 분석
- `AnalyzeTrendsTool`: 트렌드 분석

#### 3. `tool_executor.py` - 툴 실행기
```python
class ToolExecutor:
    """툴 실행 및 결과 처리"""

    def __init__(self):
        self.registry = ToolRegistry()

    async def execute_tool(self, tool_name: str, tool_params: dict) -> dict:
        """
        툴 실행

        Returns:
            {
                "success": bool,
                "result": Any,
                "error": str (if failed)
            }
        """
        pass

    def validate_params(self, tool: BaseTool, params: dict) -> bool:
        """파라미터 검증"""
        pass
```

#### 4. `main.py` - 라우팅 로직 업데이트
```python
@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 1. 라우터로 경로 결정
    route_decision = await router.route(request.message)

    # 2. 경로별 처리
    if route_decision["route"] == "TOOL_CALL":
        # 2-1. 툴 실행
        tool_result = await tool_executor.execute_tool(
            route_decision["tool_name"],
            route_decision["tool_params"]
        )

        # 2-2. 툴 유형별 처리
        if route_decision["tool_type"] == "Self-Contained":
            # 즉시 응답
            response = tool_result["result"]
        else:  # LLM-Interpreted
            # Gemma3로 해석
            response = await main_llm.interpret(tool_result)

    elif route_decision["route"] == "RAG_QUERY":
        # RAG Pipeline 실행
        response = await rag_pipeline.query(route_decision["query"])

    else:  # SIMPLE_QA
        # Gemma3 직접 응답
        response = await main_llm.chat(route_decision["query"])

    return {"response": response}
```

## 🔄 처리 흐름 상세

### 시나리오 1: 자체 처리 툴 (Self-Contained)
```
사용자: "김치찌개 주문해줘"
  ↓
라우터 (Kanana):
  - 질문 분석
  - 판단: 메뉴 주문 → TOOL_CALL
  - 툴: order_menu
  - 유형: Self-Contained
  ↓
출력: {
  "route": "TOOL_CALL",
  "tool_name": "order_menu",
  "tool_params": {"menu": "김치찌개"},
  "tool_type": "Self-Contained"
}
  ↓
툴 실행기:
  - order_menu.execute(menu="김치찌개")
  - 결과: "✅ [툴 실행] order_menu - 김치찌개 주문"
  ↓
즉시 응답: "김치찌개 주문이 완료되었습니다"
```

### 시나리오 2: LLM 해석 툴 (LLM-Interpreted)
```
사용자: "오늘 매출 알려줘"
  ↓
라우터 (Kanana):
  - 판단: 매출 조회 → TOOL_CALL
  - 툴: get_sales_data
  - 유형: LLM-Interpreted
  ↓
출력: {
  "route": "TOOL_CALL",
  "tool_name": "get_sales_data",
  "tool_params": {"date": "today"},
  "tool_type": "LLM-Interpreted"
}
  ↓
툴 실행기:
  - get_sales_data.execute(date="today")
  - 결과: {"total": 1500000, "count": 45, "notification": "✅ [툴 실행] get_sales_data"}
  ↓
Gemma3 해석:
  - 입력: 툴 결과 데이터
  - 출력: "오늘 매출은 150만원이며, 45건의 주문이 있었습니다. 전날 대비 증가 추세입니다!"
```

### 시나리오 3: RAG 검색
```
사용자: "매장 운영시간은?"
  ↓
라우터 (Kanana):
  - 판단: 매장 정보 조회 → RAG_QUERY
  ↓
출력: {
  "route": "RAG_QUERY",
  "query": "매장 운영시간은?"
}
  ↓
RAG Pipeline:
  - 벡터 검색
  - 관련 문서 조회
  - Gemma3로 답변 생성
  ↓
응답: "평일은 오전 11시부터 오후 10시까지 영업합니다"
```

### 시나리오 4: 단순 대화
```
사용자: "안녕하세요"
  ↓
라우터 (Kanana):
  - 판단: 일반 인사 → SIMPLE_QA
  ↓
출력: {
  "route": "SIMPLE_QA",
  "query": "안녕하세요"
}
  ↓
Gemma3 직접 응답:
  ↓
응답: "안녕하세요! 무엇을 도와드릴까요?"
```

## 📝 구현 단계

### Phase 1: 툴 시스템 구축
1. ✅ 구현 계획 문서 작성
2. ⏳ `tools.py`: 툴 베이스 클래스 및 레지스트리 구현
3. ⏳ `tools.py`: 7개 툴 구현 (노티만 표시)
4. ⏳ `tool_executor.py`: 툴 실행기 구현

### Phase 2: 라우터 구축
5. ⏳ `router.py`: IntelligentRouter 클래스 구현
6. ⏳ `router.py`: Kanana 프롬프트 엔지니어링
7. ⏳ `router.py`: JSON 파싱 및 검증 로직

### Phase 3: 시스템 통합
8. ⏳ `main.py`: 라우팅 로직 업데이트
9. ⏳ `main.py`: 3가지 경로별 처리 구현
10. ⏳ `agent.py`: 백업 또는 삭제

### Phase 4: 테스트 및 검증
11. ⏳ 각 툴별 단위 테스트
12. ⏳ 라우팅 시나리오 테스트
13. ⏳ 성능 측정 (응답 속도)

## 💡 기대 효과

### 성능 개선
- ⚡ **속도 향상**: 자체 처리 툴 사용 시 200-500ms → 10-50ms
- 💰 **비용 절감**: 불필요한 LLM 호출 감소 (약 30-40% 예상)

### 시스템 품질
- 🎯 **정확도 향상**: 라우팅 기반 최적 처리 경로 선택
- 🔧 **확장성**: 새로운 툴 추가 용이
- 📊 **모니터링**: 각 경로별 사용 통계 추적 가능

### 사용자 경험
- ⚡ **빠른 응답**: 간단한 작업은 즉시 처리
- 💬 **자연스러운 대화**: 복잡한 질문은 LLM이 해석
- 🎨 **다양한 기능**: 툴 확장으로 더 많은 기능 제공

## 🚨 주의사항

### 현재 구현 범위
- **툴 실제 동작**: 현재는 구현하지 않음 (추후 구현)
- **툴 실행 알림**: "✅ [툴 실행] {tool_name} - {params}" 형태로 표시
- **에러 처리**: 기본적인 검증만 구현

### 향후 개선 사항
- 툴 실제 동작 구현 (DB 연동, API 호출 등)
- 툴 실행 이력 저장 및 모니터링
- 라우터 성능 최적화 (캐싱, 병렬 처리)
- A/B 테스트 프레임워크 구축

## 📚 참고 자료
- OpenAI Function Calling
- LangChain Tools
- Anthropic Claude Tool Use
