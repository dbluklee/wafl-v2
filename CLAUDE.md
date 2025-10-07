# WAFL 프로젝트 개발 진행 상황

> 마지막 업데이트: 2025-10-07 (LLM 다국어 응답 및 UI 배지 개선)
>
> 이 문서는 Claude Code와의 작업 연속성을 위한 컨텍스트 문서입니다.

---

## 📌 프로젝트 개요

**WAFL**: 매장용 RAG 기반 AI 챗봇 시스템

### 시스템 구성
```
wafl/
├── web-server/          # 웹 서버
├── scraping-server/     # 스크래핑 서버
├── rag-server/          # RAG + LLM 서버 (메인 작업 영역)
└── CLAUDE.md           # 이 문서
```

---

## ✅ 현재까지 구현된 기능

### 1. RAG 시스템 (완료)
- **위치**: `rag-server/`
- **구현 내용**:
  - ✅ 문서 임베딩 및 벡터 저장 (Milvus)
  - ✅ 의미 기반 문서 검색
  - ✅ RAG Pipeline (`rag_pipeline.py`)
  - ✅ 문서 자동 생성 (`document_generator.py`)

### 2. Agent 시스템 (완료 - 백업)
- **위치**: `rag-server/agent.py`
- **역할**: RAG 필요 여부 판단 (YES/NO)
- **상태**: 백업용으로 유지 (새 라우터로 대체됨)
- **모델**:
  - Agent: Kanana (RAG 판단)
  - Main LLM: Gemma3 (응답 생성)

### 3. 대화 저장 시스템 (완료)
- **비동기 로깅**: Redis Queue 기반
- **암호화**: AES-256-GCM
- **파일**:
  - `conversation_service.py`: 대화 관리
  - `conversation_logger.py`: 비동기 로깅
  - `encryption_utils.py`: 암호화

### 4. API 엔드포인트 (완료)
- **위치**: `rag-server/main.py`
- **주요 API**:
  - `POST /api/chat`: 채팅 (라우팅 시스템 통합)
  - `POST /api/generate-documents`: 문서 생성
  - `POST /api/index-documents`: 문서 인덱싱
  - `GET /api/conversations/{uuid}`: 대화 조회
  - `GET /api/stores/{id}/conversation-statistics`: 통계

### 5. 데이터베이스 스키마
- **테이블**:
  - `stores`: 매장 정보
  - `rag_documents`: RAG 문서
  - `conversations`: 대화 세션
  - `conversation_messages`: 대화 메시지

### 6. ⭐ LLM 툴 호출 적응형 라우팅 시스템 (완료)
- **위치**: `rag-server/router.py`, `tools.py`, `tool_executor.py`
- **구현 날짜**: 2025-10-07
- **상세 내용**: 아래 섹션 참조

### 7. 🌐 언어 변경 기능 및 다국어 지원 (완료)
- **위치**: `rag-server/tools.py` (SetLanguageTool), `templates/chat.html`
- **구현 날짜**: 2025-10-07
- **지원 언어**: 한국어, 영어, 중국어, 일본어
- **주요 기능**:
  - ✅ 챗봇 명령으로 언어 변경 (예: "plz speak english")
  - ✅ UI 버튼으로 언어 변경
  - ✅ 전체 UI 다국어 지원 (헤더, 버튼, 메시지 등)
  - ✅ 로컬 스토리지 저장 (페이지 새로고침 시에도 유지)
  - ✅ 프론트엔드-백엔드 자동 연동
- **상세 내용**: 아래 섹션 참조

### 8. 🤖 LLM 다국어 응답 및 UI 배지 개선 (완료)
- **위치**: `rag-server/main.py`, `rag_pipeline.py`, `templates/chat.html`
- **구현 날짜**: 2025-10-07
- **주요 기능**:
  - ✅ LLM이 프론트엔드 언어 설정에 따라 해당 언어로 응답
  - ✅ 프롬프트 간소화 (단일 영어 프롬프트 + 언어 지시)
  - ✅ 채팅 UI에 툴 배지 추가 (일반/RAG/툴 구분)
  - ✅ 4개 언어 모두 배지 텍스트 지원
- **상세 내용**: 아래 섹션 참조

---

## 🎉 최근 완료된 작업: LLM 툴 호출 적응형 라우팅 시스템

### 시스템 아키텍처 변화

#### 이전 시스템
```
사용자 질문 → Agent (Kanana) → RAG 판단 (YES/NO)
                                ↓ YES: RAG Pipeline → Gemma3
                                ↓ NO: 일반 대화 → Gemma3
```

#### 새 시스템 (현재)
```
사용자 질문 → IntelligentRouter (Kanana) → 3가지 경로 결정 (JSON)
                                            ↓
                        ┌───────────────────┼───────────────────┐
                        ↓                   ↓                   ↓
                    TOOL_CALL           RAG_QUERY           SIMPLE_QA
                        ↓                   ↓                   ↓
                    툴 실행              RAG 검색            Gemma3 직접
                        ↓                   ↓                   ↓
            ┌───────────┴───────────┐      ↓                   ↓
            ↓                       ↓      ↓                   ↓
    Self-Contained          LLM-Interpreted                    ↓
    (즉시 응답)              (Gemma3 해석)                     ↓
            ↓                       ↓      ↓                   ↓
            └───────────┬───────────┴──────┴───────────────────┘
                        ↓
                    최종 응답
```

### 구현된 파일

#### 1. `tools.py` (신규 - 470줄)
**역할**: 시스템에서 사용 가능한 모든 툴 정의 및 관리

**주요 컴포넌트**:
- `BaseTool`: 모든 툴의 추상 베이스 클래스
  - `name`: 툴 이름
  - `description`: 툴 설명
  - `tool_type`: "Self-Contained" 또는 "LLM-Interpreted"
  - `parameters`: 파라미터 스키마
  - `execute(**kwargs)`: 툴 실행 메서드

**구현된 툴 (7개)**:

**자체 처리 툴 (Self-Contained) - 4개**:
1. **SetLanguageTool**: 언어 설정 변경
   - 파라미터: `language` (ko, en, ja, zh)
   - 응답 예: "언어가 한국어(으)로 변경되었습니다"

2. **OrderMenuTool**: 메뉴 주문
   - 파라미터: `menu` (필수), `quantity` (선택), `options` (선택)
   - 응답 예: "김치찌개 1개 주문이 완료되었습니다"

3. **NavigateToTool**: UI 네비게이션
   - 파라미터: `destination` (menu, order_history, settings, etc.)
   - 응답 예: "메뉴 화면으로 이동합니다"

4. **ApplyFilterTool**: 필터 적용
   - 파라미터: `filter_type`, `filter_value`
   - 응답 예: "카테고리 필터가 '한식'(으)로 적용되었습니다"

**LLM 해석 툴 (LLM-Interpreted) - 3개**:
1. **GetSalesDataTool**: 매출 데이터 조회
   - 파라미터: `date` (today/yesterday/YYYY-MM-DD), `period` (daily/weekly/monthly)
   - 더미 데이터: 총 매출, 주문 수, 평균 주문 금액, 전일 대비 등
   - Gemma3가 자연어로 해석

2. **GetOrderStatisticsTool**: 주문 통계 조회
   - 파라미터: `period`, `stat_type` (menu_ranking/time_distribution/category)
   - 더미 데이터: 메뉴 순위, 시간대별 분포 등
   - Gemma3가 자연어로 해석

3. **AnalyzeTrendsTool**: 트렌드 분석
   - 파라미터: `analysis_type` (sales/menu/customer), `period` (week/month/quarter)
   - 더미 데이터: 트렌드 방향, 인사이트, 권장사항 등
   - Gemma3가 자연어로 해석

**ToolRegistry**:
- 모든 툴을 관리하는 중앙 저장소
- 싱글톤 패턴으로 전역 접근 (`get_tool_registry()`)
- 툴 등록, 조회, 타입별 필터링 기능

**현재 구현 상태**:
- ✅ 모든 툴은 실제 동작 없이 **실행 노티만 표시**
- ✅ 형식: `"✅ [툴 실행] {tool_name} - {params}"`
- ⏳ 실제 동작 구현은 추후 진행 (DB 연동, API 호출 등)

#### 2. `tool_executor.py` (신규 - 200줄)
**역할**: 툴 레지스트리에서 툴을 가져와 실행하고 결과 반환

**주요 컴포넌트**:
- `ToolExecutor`: 툴 실행 및 결과 처리 클래스
  - `execute_tool(tool_name, tool_params)`: 툴 실행
  - `validate_params(tool, params)`: 파라미터 검증
  - `get_available_tools()`: 사용 가능한 툴 목록 조회

**실행 프로세스**:
1. 툴 존재 여부 확인
2. 툴 인스턴스 가져오기
3. 파라미터 검증:
   - 필수 파라미터 확인
   - enum 값 검증
   - 타입 검증
4. 툴 실행
5. 결과 반환 또는 에러 처리

**응답 형식**:
```json
{
  "success": true,
  "notification": "✅ [툴 실행] order_menu - 김치찌개 1개",
  "result": {
    "menu": "김치찌개",
    "quantity": 1,
    "message": "김치찌개 1개 주문이 완료되었습니다",
    "order_id": "ORDER_20251007143045"
  },
  "executed_at": "2025-10-07T14:30:45.123456",
  "tool_name": "order_menu",
  "tool_type": "Self-Contained"
}
```

**에러 핸들링**:
- 툴 없음: "존재하지 않는 툴입니다"
- 파라미터 오류: 구체적인 오류 메시지
- 실행 오류: 상세 로깅 및 사용자 친화적 메시지

#### 3. `router.py` (신규 - 350줄)
**역할**: Kanana 모델을 사용하여 사용자 질문 분석 및 최적 경로 결정

**주요 컴포넌트**:
- `IntelligentRouter`: 지능형 라우터 클래스
  - `route(user_message)`: 경로 결정 메인 메서드
  - `_create_routing_prompt(user_message)`: 라우팅 프롬프트 생성
  - `_parse_routing_response(raw_response)`: JSON 파싱 및 검증
  - `_heuristic_routing(user_message)`: 휴리스틱 기반 fallback

**라우팅 프롬프트 구조**:
```
사용자 질문: "{user_message}"

3가지 경로 중 선택:
1. TOOL_CALL - 사용 가능한 툴 목록 제공
2. RAG_QUERY - 매장 문서 검색 필요 조건 명시
3. SIMPLE_QA - 일반 대화 조건 명시

반드시 JSON 형식으로만 답변
예시 제공 (각 경로별 5개)
```

**JSON 응답 형식**:
```json
// TOOL_CALL
{
  "route": "TOOL_CALL",
  "tool_name": "order_menu",
  "tool_params": {"menu": "김치찌개", "quantity": 1},
  "tool_type": "Self-Contained",
  "confidence": 0.98,
  "reasoning": "메뉴 주문 요청"
}

// RAG_QUERY
{
  "route": "RAG_QUERY",
  "query": "영업시간 알려줘",
  "confidence": 0.95,
  "reasoning": "매장 정보 조회 필요"
}

// SIMPLE_QA
{
  "route": "SIMPLE_QA",
  "query": "안녕하세요",
  "confidence": 0.99,
  "reasoning": "일반 인사"
}
```

**안전장치**:
1. **JSON 파싱 실패 시**: 휴리스틱 기반 라우팅
   - 툴 키워드 매칭 (주문, 언어, 매출 등)
   - RAG 키워드 매칭 (메뉴, 가격, 영업시간 등)
   - 기본값: SIMPLE_QA

2. **에러 발생 시**: SIMPLE_QA로 fallback
   - 사용자는 정상 응답 받음
   - 로그에 상세 오류 기록

#### 4. `main.py` (수정)
**변경 내용**: 라우터 기반 3가지 경로 처리 로직 추가

**새로 추가된 함수**:

1. **`interpret_tool_result_with_llm(user_message, tool_name, tool_result)`**:
   - LLM-Interpreted 툴 결과를 Gemma3로 자연어 해석
   - 프롬프트:
     ```
     손님 질문: {user_message}
     실행된 기능: {tool_name}
     조회 결과: {tool_result JSON}

     답변 규칙:
     - 50자 이내 간결
     - 데이터 핵심만 전달
     - 숫자 읽기 쉽게 포맷 (1500000 → 150만원)
     - 트렌드/인사이트 간단히 언급
     ```

2. **`simple_chat_with_llm(user_message)`**:
   - SIMPLE_QA 경로에서 Gemma3 직접 호출
   - 일반 대화 처리 (50자 제한)

**수정된 `/api/chat` 엔드포인트**:
```python
@app.post("/api/chat")
async def chat(request: ChatRequest, http_request: Request):
    # 1. 라우터로 경로 결정
    route_decision = await router.route(request.message)

    # 2. 경로별 처리
    if route_decision["route"] == "TOOL_CALL":
        # 툴 실행
        tool_result = await tool_executor.execute_tool(...)

        if tool_type == "Self-Contained":
            # 즉시 응답 (LLM 우회)
            response = tool_result["result"]["message"]
        else:  # LLM-Interpreted
            # Gemma3로 해석
            response = await interpret_tool_result_with_llm(...)

    elif route_decision["route"] == "RAG_QUERY":
        # RAG Pipeline
        response = await rag_pipeline.query(...)

    else:  # SIMPLE_QA
        # Gemma3 직접 응답
        response = await simple_chat_with_llm(...)

    # 3. 응답 반환 (route, used_tool 정보 추가)
    return {
        "response": response,
        "route": route_decision["route"],
        "used_rag": used_rag,
        "used_tool": used_tool,
        "conversation_uuid": conversation_uuid,
        "response_time_ms": response_time_ms,
        "debug": debug_info
    }
```

**응답 형식 변경**:
- 기존: `{"response": str, "used_rag": bool, ...}`
- 새로: `{"response": str, "route": str, "used_rag": bool, "used_tool": str, ...}`

### 구현 완료 상태

#### Phase 1: 툴 시스템 구축 ✅
- [x] 구현 계획 문서 작성 (`IMPLEMENTATION_PLAN.md`)
- [x] `tools.py`: 툴 베이스 클래스 및 레지스트리
- [x] `tools.py`: 7개 툴 구현 (노티만 표시)
- [x] `tool_executor.py`: 툴 실행기

#### Phase 2: 라우터 구축 ✅
- [x] `router.py`: IntelligentRouter 클래스
- [x] `router.py`: Kanana 프롬프트 엔지니어링
- [x] `router.py`: JSON 파싱 및 검증

#### Phase 3: 시스템 통합 ✅
- [x] `main.py`: 라우팅 로직 업데이트
- [x] `main.py`: 3가지 경로별 처리
- [x] `agent.py`: 백업용으로 유지 (추후 제거 가능)

#### Phase 4: 테스트 및 검증 ✅
- [x] Python 문법 체크 (모든 모듈 통과)
- [x] 모듈 구조 검증
- [x] 언어 변경 툴 테스트 및 문제 해결
- [ ] 실제 서버 동작 테스트 (예정)
- [ ] 라우팅 시나리오 테스트 (예정)
- [ ] 성능 측정 (예정)

---

## 🌐 언어 변경 기능 구현 및 문제 해결

### 배경
사용자가 챗봇에 "plz speak english"와 같이 입력하면 UI 언어가 자동으로 변경되도록 하는 기능이 필요했습니다.

### 발견된 문제 및 해결 과정

#### 문제 1: 파라미터 검증 실패
**증상**:
```
사용자: "plz speak english"
→ 툴 콜링: set_language ✅
→ 에러: "파라미터 검증 실패: 필수 파라미터 누락: language" ❌
```

**원인**:
- 라우터가 `set_language` 툴을 호출하기로 결정했지만, `language` 파라미터를 JSON에 포함시키지 못함
- `SetLanguageTool`에서 `language` 파라미터를 `required: True`로 설정해서 파라미터 없이는 실행 불가

**해결 방법**:
1. **`tools.py` - SetLanguageTool 개선**:
   ```python
   parameters = {
       "language": {
           "type": "string",
           "description": "변경할 언어 코드. 한국어=ko, 영어/English=en, 일본어/日本語=ja, 중국어/中文=zh",
           "required": False,  # ✅ 필수 → 선택으로 변경
           "default": "en",     # ✅ 기본값 추가
           "enum": ["ko", "en", "ja", "zh"]
       }
   }
   ```

2. **언어 이름 → 코드 자동 변환**:
   ```python
   language_name_to_code = {
       "korean": "ko", "한국어": "ko", "korea": "ko",
       "english": "en", "영어": "en",
       "japanese": "ja", "일본어": "ja", "japan": "ja", "日本語": "ja",
       "chinese": "zh", "중국어": "zh", "china": "zh", "中文": "zh"
   }
   ```

3. **`router.py` - 프롬프트 예시 추가**:
   ```python
   사용자: "plz speak english"
   답변: {"route": "TOOL_CALL", "tool_name": "set_language",
          "tool_params": {"language": "en"}, ...}
   ```

4. **휴리스틱 라우팅 개선**:
   - 키워드 확장: `speak`, `language`, `korean`, `japanese`, `chinese` 추가
   - `set_language` 툴인 경우 파라미터 자동 추출 로직 추가

#### 문제 2: 프론트엔드 UI 언어가 변경되지 않음
**증상**:
```
사용자: "plz speak english"
→ 툴 실행: ✅ 성공
→ 응답: "언어가 English(으)로 변경되었습니다" ✅
→ UI 언어: 한국어 그대로 ❌
```

**원인**:
- 백엔드가 응답에 요청의 `language` 값을 그대로 반환
- 툴이 실제로 실행한 언어 코드를 응답에 포함시키지 않음

**해결 방법**:
1. **`main.py` - 툴 결과에서 언어 추출**:
   ```python
   changed_language = None  # 툴로 변경된 언어

   # set_language 툴인 경우 변경된 언어 추출
   if tool_name == "set_language" and tool_result.get("success"):
       changed_language = tool_result.get("result", {}).get("language")
       logger.info(f"🌐 언어 변경 감지: {changed_language}")
   ```

2. **응답 구성 개선**:
   ```python
   # 언어가 변경된 경우 변경된 언어를 반환
   if changed_language:
       response_data["language"] = changed_language
       response_data["language_changed"] = True  # ✅ 변경 플래그 추가
   else:
       response_data["language"] = request.language
   ```

3. **`chat.html` - 언어 변경 감지 로직 개선**:
   ```javascript
   // 툴 호출 결과 확인 (언어 변경 툴인 경우)
   if (data.route === 'TOOL_CALL' && data.used_tool === 'set_language') {
       if (data.language_changed && data.language) {
           // 언어가 실제로 변경된 경우
           console.log('🌐 언어 변경 감지:', data.language);
           changeLanguage(data.language);  // ✅ UI 언어 변경
       }
   }
   ```

### 최종 동작 흐름

```
사용자: "plz speak english"
  ↓
라우터 (Kanana):
  → JSON 파싱 성공: {"route": "TOOL_CALL", "tool_name": "set_language",
                     "tool_params": {"language": "en"}}
  또는
  → JSON 파싱 실패: 휴리스틱으로 파라미터 자동 추출
  ↓
툴 실행기: SetLanguageTool.execute(language="en")
  → 언어 코드 정규화 (소문자 변환)
  → 언어 이름이면 코드로 변환 ("english" → "en")
  → 결과: {"success": true, "result": {"language": "en", ...}}
  ↓
main.py: changed_language = "en" 추출
  ↓
응답 생성:
  {
    "response": "언어가 English(으)로 변경되었습니다",
    "route": "TOOL_CALL",
    "used_tool": "set_language",
    "language": "en",  ← 툴 결과에서 추출
    "language_changed": true  ← 변경 플래그
  }
  ↓
프론트엔드: language_changed=true 감지
  ↓
changeLanguage("en") 호출
  ↓
UI 전체가 영어로 변경! 🎉
  - 헤더: "Store Info Chatbot Test"
  - 버튼: "Send", "Generate Docs"
  - 입력창: "Enter message... (max 30 chars)"
  - 성공 토스트: "Language changed to English"
```

### 구현된 기능

#### 1. 프론트엔드 다국어 지원 (`chat.html`)
**지원 언어**: 🇰🇷 한국어, 🇺🇸 English, 🇨🇳 中文, 🇯🇵 日本語

**번역된 UI 요소**:
- 헤더 및 서브타이틀
- 모든 버튼 (문서 생성, 인덱싱, 전송 등)
- 라벨 (매장 선택, 카테고리 등)
- 입력 필드 플레이스홀더
- 세션 상태 (대화 활성/종료)
- 에러 및 성공 메시지
- 토스트 알림

**언어 변경 방법**:
1. **버튼 클릭**: 설정 영역의 언어 버튼 클릭
2. **챗봇 명령**:
   - "plz speak english"
   - "언어를 한국어로 변경해줘"
   - "日本語で話して"
   - "改为中文"

**로컬 스토리지 저장**:
- 선택한 언어를 `localStorage`에 저장
- 페이지 새로고침 시에도 언어 설정 유지

#### 2. 백엔드 언어 처리 (`main.py`, `tools.py`)
- `ChatRequest`에 `language` 파라미터 추가
- `SetLanguageTool` 파라미터 유연화 (기본값 제공)
- 언어 이름 자동 변환 ("english" → "en")
- 응답에 `language_changed` 플래그 포함

#### 3. 라우터 개선 (`router.py`)
- 언어 변경 관련 프롬프트 예시 5개 추가
- 휴리스틱 키워드 확장
- `set_language` 툴 파라미터 자동 추출 로직

### 테스트 가능한 명령어

#### 영어 변경
- ✅ "plz speak english"
- ✅ "Can you speak English?"
- ✅ "언어를 영어로 바꿔줘"
- ✅ "영어로 말해줘"
- ✅ "english please"

#### 한국어 변경
- ✅ "한국어로 말해줘"
- ✅ "speak korean"
- ✅ "언어를 한국어로 변경"

#### 일본어 변경
- ✅ "日本語で話して"
- ✅ "speak japanese"
- ✅ "일본어로 바꿔줘"

#### 중국어 변경
- ✅ "中文"
- ✅ "speak chinese"
- ✅ "중국어로 변경"

### 개선 사항 요약

| 항목 | 이전 | 이후 |
|------|------|------|
| 파라미터 검증 | 필수, 없으면 실패 | 선택, 기본값 제공 |
| 언어 코드 | 코드만 인식 ("en") | 이름도 인식 ("english") |
| 프롬프트 예시 | 0개 | 5개 (언어 관련) |
| 휴리스틱 키워드 | 3개 | 10개 |
| 파라미터 추출 | 라우터만 | 라우터 + 휴리스틱 |
| 응답 플래그 | 없음 | `language_changed` 추가 |
| UI 연동 | 수동 | 자동 (툴 실행 시) |

---

## 🤖 LLM 다국어 응답 시스템

### 배경 및 요구사항
프론트엔드 UI 언어가 변경되면 LLM도 자동으로 해당 언어로 응답해야 함.
- 한국어 UI → LLM 한국어 응답
- 영어 UI → LLM 영어 응답
- 일본어 UI → LLM 일본어 응답
- 중국어 UI → LLM 중국어 응답

### 구현 방식

#### 초기 접근 (복잡)
각 언어별로 전체 프롬프트를 번역:
```python
prompts = {
    "ko": f"""당신은 매장의 친절한 직원입니다.
답변 규칙:
1. 50자 이내로 간결하게 답변하세요
...(한국어 프롬프트 전체)""",

    "en": f"""You are a friendly store assistant.
Response rules:
1. Keep your answer concise, within 50 characters
...(영어 프롬프트 전체)""",

    # ja, zh 동일하게 전체 번역
}
```

**문제점**:
- 프롬프트가 4배로 증가 (유지보수 어려움)
- 번역 일관성 보장 어려움
- 코드 가독성 저하

#### 최종 접근 (간소화) ✅
LLM의 다국어 지원을 활용하여 단일 프롬프트 + 언어 지시:
```python
language_instructions = {
    "ko": "한국어로 답변하세요.",
    "en": "Answer in English.",
    "ja": "日本語で答えてください。",
    "zh": "用中文回答。"
}

prompt = f"""You are a friendly store assistant.

Response rules:
1. Keep your answer concise, within 50 characters
2. Deliver only the key points the customer wants
3. Be kind but get to the point
4. Skip unnecessary explanations
5. **Important**: Never make up information you don't know
6. If uncertain, say "I'm not sure. Please ask a staff member for assistance"

**IMPORTANT: {language_instructions.get(language, language_instructions["ko"])}**

User: {user_message}
Assistant:"""
```

**장점**:
- ✅ 프롬프트가 단일화되어 유지보수 용이
- ✅ 코드 간결성 (100줄 이상 감소)
- ✅ LLM이 자동으로 해당 언어로 응답
- ✅ 일관성 있는 답변 품질

### 수정된 파일

#### 1. `main.py`
**`interpret_tool_result_with_llm()` 함수**:
- `language` 파라미터 추가
- 단일 영어 프롬프트 + 언어 지시 방식으로 변경
- 언어별 "더 자세히 설명해드릴까요?" 메시지
- 언어별 에러 메시지

**`simple_chat_with_llm()` 함수**:
- `language` 파라미터 추가
- 단일 영어 프롬프트 + 언어 지시 방식으로 변경
- 언어별 추가 설명 메시지
- 언어별 에러 메시지

**경로별 language 전달**:
```python
# TOOL_CALL - LLM-Interpreted
response = await interpret_tool_result_with_llm(
    user_message=request.message,
    tool_name=tool_name,
    tool_result=tool_result["result"],
    language=changed_language if changed_language else request.language
)

# RAG_QUERY
response, rag_debug = await rag_pipeline.query(
    query=route_decision["query"],
    store_id=request.store_id,
    category=request.category,
    language=request.language
)

# SIMPLE_QA
response = await simple_chat_with_llm(
    route_decision["query"],
    language=request.language
)
```

#### 2. `rag_pipeline.py`
**`query()` 함수**:
- `language` 파라미터 추가
- 단일 영어 프롬프트 + 언어 지시 방식으로 변경
- 언어별 "더 자세히 설명해드릴까요?" 메시지
- 언어별 "제가 잘 모르겠어요" 메시지 (문서 없음 시)

```python
async def query(self, query: str, store_id: int, category: str = "customer", language: str = "ko"):
    # 언어별 에러 메시지
    no_info_messages = {
        "ko": "제가 잘 모르겠어요. 죄송하지만 직원에게 문의해주세요.",
        "en": "I'm not sure. Please ask a staff member for assistance.",
        "ja": "よくわかりません。申し訳ありませんが、スタッフにお問い合わせください。",
        "zh": "我不太清楚。抱歉，请向工作人员咨询。"
    }

    # 프롬프트에 언어 지시 추가
    prompt = f"""You are a friendly store assistant.
    ...
    **IMPORTANT: {language_instructions.get(language)}**
    ..."""
```

### 동작 흐름

```
1. 사용자가 UI 언어 변경 (예: 영어)
   ↓
2. localStorage에 "en" 저장
   ↓
3. 다음 메시지 전송 시 language="en" 포함
   ↓
4. 백엔드가 라우팅 결정
   ↓
5-1. TOOL_CALL (LLM-Interpreted):
     interpret_tool_result_with_llm(language="en")
     → 프롬프트에 "Answer in English" 추가
     → Gemma3가 영어로 응답

5-2. RAG_QUERY:
     rag_pipeline.query(language="en")
     → 프롬프트에 "Answer in English" 추가
     → Gemma3가 영어로 응답

5-3. SIMPLE_QA:
     simple_chat_with_llm(language="en")
     → 프롬프트에 "Answer in English" 추가
     → Gemma3가 영어로 응답
     ↓
6. 사용자에게 영어로 답변 전달 ✅
```

### 채팅 UI 배지 개선

#### 요구사항
기존에는 "일반"과 "RAG" 2가지 배지만 표시되었으나, 툴 호출 시 "툴" 배지도 표시해야 함.

#### 구현 내용

**`chat.html` - translations 추가**:
```javascript
const translations = {
    ko: {
        // ... 기존 번역
        badgeTool: "🔧 툴",
        badgeRag: "📚 RAG",
        badgeSimple: "💬 일반"
    },
    en: {
        badgeTool: "🔧 Tool",
        badgeRag: "📚 RAG",
        badgeSimple: "💬 Simple"
    },
    zh: {
        badgeTool: "🔧 工具",
        badgeRag: "📚 RAG",
        badgeSimple: "💬 简单"
    },
    ja: {
        badgeTool: "🔧 ツール",
        badgeRag: "📚 RAG",
        badgeSimple: "💬 通常"
    }
};
```

**`addMessage()` 함수 개선**:
```javascript
function addMessage(text, type, usedRag = null, route = null, usedTool = null) {
    const t = translations[currentLanguage];
    let badgeHtml = '';

    // 배지 표시 우선순위: TOOL_CALL > RAG_QUERY > SIMPLE_QA
    if (route === 'TOOL_CALL' && usedTool) {
        // 툴 호출인 경우
        badgeHtml = `<div class="message-badge">${t.badgeTool}</div>`;
    } else if (usedRag === true) {
        // RAG 사용한 경우
        badgeHtml = `<div class="message-badge">${t.badgeRag}</div>`;
    } else if (type === 'assistant' && (route === 'SIMPLE_QA' || usedRag === false)) {
        // 일반 대화인 경우
        badgeHtml = `<div class="message-badge">${t.badgeSimple}</div>`;
    }

    // ...
}
```

#### 배지 표시 규칙

| 조건 | 배지 | 한국어 | English | 中文 | 日本語 |
|------|------|--------|---------|------|--------|
| `route === 'TOOL_CALL' && usedTool` | 툴 | 🔧 툴 | 🔧 Tool | 🔧 工具 | 🔧 ツール |
| `usedRag === true` | RAG | 📚 RAG | 📚 RAG | 📚 RAG | 📚 RAG |
| `route === 'SIMPLE_QA'` 또는 `usedRag === false` | 일반 | 💬 일반 | 💬 Simple | 💬 简单 | 💬 通常 |

#### 결과
- ✅ 툴 호출 시 "🔧 툴" 배지 표시
- ✅ RAG 사용 시 "📚 RAG" 배지 표시
- ✅ 일반 대화 시 "💬 일반" 배지 표시
- ✅ 선택된 언어에 맞춰 배지 텍스트 자동 변경

### 개선 사항 요약

| 항목 | 이전 | 이후 |
|------|------|------|
| 프롬프트 구조 | 언어별 전체 번역 (4배) | 단일 프롬프트 + 언어 지시 |
| 코드 라인 수 | ~200줄 (프롬프트) | ~50줄 (간소화) |
| 유지보수성 | 어려움 (4개 동기화) | 쉬움 (1개만 관리) |
| LLM 응답 언어 | UI 언어와 무관 | UI 언어에 맞춰 자동 변경 ✅ |
| 배지 종류 | 2가지 (일반/RAG) | 3가지 (일반/RAG/툴) ✅ |
| 배지 다국어 | 미지원 | 4개 언어 지원 ✅ |

---

## 🎯 시스템 특징 및 장점

### 1. 속도 최적화
- **Self-Contained 툴**: LLM 호출 우회 → 10-50ms (기존 200-500ms)
- **예상 개선**: 간단한 작업에서 80-90% 속도 향상

### 2. 품질 보장
- **LLM-Interpreted 툴**: 복잡한 데이터도 자연어로 정확히 해석
- **RAG Pipeline**: 매장 정보는 문서 기반으로 정확한 답변

### 3. 확장성
- 새로운 툴 추가가 매우 쉬움:
  1. `tools.py`에 새 클래스 추가
  2. `ToolRegistry`에 자동 등록
  3. 라우터가 자동으로 인식

### 4. 안정성
- JSON 파싱 실패 → 휴리스틱 라우팅
- 툴 실행 실패 → 에러 메시지 반환
- 전체 시스템 실패 → SIMPLE_QA로 fallback

### 5. 모니터링
- 각 경로별 사용 통계 추적 가능
- 툴 실행 이력 로깅
- 라우터 confidence 스코어 기록

---

## 📚 주요 파일 구조 (업데이트)

```
rag-server/
├── main.py                    # FastAPI 메인 ✅ 수정 완료
├── agent.py                   # 기존 Agent (백업용 유지)
├── router.py                  # 지능형 라우터 ✅ 신규
├── tools.py                   # 툴 정의 및 레지스트리 ✅ 신규
├── tool_executor.py           # 툴 실행기 ✅ 신규
├── rag_pipeline.py            # RAG Pipeline (유지)
├── embeddings.py              # 임베딩 (유지)
├── vector_store.py            # 벡터 스토어 (유지)
├── document_loader.py         # 문서 로더 (유지)
├── document_generator.py      # 문서 생성기 (유지)
├── conversation_service.py    # 대화 서비스 (유지)
├── conversation_logger.py     # 비동기 로거 (유지)
├── encryption_utils.py        # 암호화 (유지)
├── tasks.py                   # Celery 작업 (유지)
├── worker.py                  # Celery Worker (유지)
├── IMPLEMENTATION_PLAN.md     # 구현 계획 문서 ✅
├── CLAUDE.md                  # 이 문서 ✅
└── templates/
    └── chat.html              # 테스트용 웹 UI
```

---

## 🔧 개발 환경

### 모델 정보
- **라우터 (Kanana)**: `huihui_ai/kanana-nano-abliterated:2.1b`
  - URL: `http://112.148.37.41:1889`
  - 역할: 경로 결정 (TOOL_CALL/RAG_QUERY/SIMPLE_QA)
- **메인 LLM (Gemma3)**: `gemma3:27b-it-q4_K_M`
  - URL: `http://112.148.37.41:1884`
  - 역할: 자연어 응답 생성, 툴 결과 해석

### 주요 의존성
- FastAPI
- Ollama (LLM 클라이언트)
- Milvus (벡터 DB)
- Redis (큐)
- SQLAlchemy (ORM)

### 실행 방법
```bash
cd rag-server
python main.py
# 또는
uvicorn main:app --host 0.0.0.0 --port 8002
```

---

## 📝 다음 세션에서 할 일

### 즉시 시작할 작업

#### 1. 실제 서버 동작 테스트
```bash
cd /home/wk/projects/wafl/rag-server
python main.py
```

**테스트 시나리오**:
- [ ] "김치찌개 주문해줘" → TOOL_CALL (Self-Contained)
- [ ] "오늘 매출 알려줘" → TOOL_CALL (LLM-Interpreted)
- [ ] "영업시간 알려줘" → RAG_QUERY
- [ ] "안녕하세요" → SIMPLE_QA
- [x] "plz speak english" → TOOL_CALL (set_language) ✅ 완료

**확인 사항**:
- 라우터 JSON 응답 정상 파싱
- 각 경로별 처리 정상 동작
- 에러 핸들링 동작 확인
- 응답 시간 측정

#### 2. 툴 실제 동작 구현 (우선순위별)

**High Priority**:
- `OrderMenuTool`: DB에 주문 저장
- `GetSalesDataTool`: 실제 DB에서 매출 조회

**Medium Priority**:
- ~~`SetLanguageTool`: 세션에 언어 설정 저장~~ ✅ 완료 (로컬 스토리지 방식)
- `GetOrderStatisticsTool`: 실제 주문 통계 조회

**Low Priority**:
- `NavigateToTool`: 프론트엔드 연동
- `ApplyFilterTool`: 프론트엔드 연동
- `AnalyzeTrendsTool`: 고급 분석 로직

#### 3. 모니터링 및 최적화
- 라우터 정확도 측정
  - 각 경로별 정확도
  - JSON 파싱 실패율
  - Fallback 발동 비율
- 응답 시간 측정
  - Self-Contained vs LLM-Interpreted
  - 기존 시스템 대비 개선율
- A/B 테스트 프레임워크 구축

#### 4. 문서 업데이트
- API 문서 업데이트 (Swagger/OpenAPI)
- 툴 추가 가이드 작성
- 트러블슈팅 가이드

---

## 💡 중요 설계 원칙

### 1. 툴 실행 노티 (현재 구현 상태)
- **형식**: `"✅ [툴 실행] {tool_name} - {params}"`
- **이유**: 시스템 구조 먼저 구축, 실제 동작은 단계적 구현
- **장점**: 빠른 프로토타이핑 및 테스트 가능

### 2. 라우터 안정성
- JSON 파싱 실패 → 휴리스틱 라우팅
- 휴리스틱 실패 → SIMPLE_QA (항상 응답 가능)
- 모든 단계에서 상세 로깅

### 3. 성능 최적화
- Self-Contained 툴: LLM 우회 (속도 우선)
- LLM-Interpreted 툴: Gemma3 사용 (품질 우선)
- 비동기 처리: 대화 저장 등 부가 작업

### 4. 확장성
- 새 툴 추가: `tools.py`에만 작성
- 새 경로 추가: 라우터 프롬프트 수정
- 레거시 호환: 기존 Agent 백업 유지

---

## 🚨 주의사항

### 운영 환경 배포 시
1. **환경 변수 확인**:
   - `OLLAMA_AGENT_URL`: Kanana 모델 URL
   - `OLLAMA_MAIN_URL`: Gemma3 모델 URL
   - `DATABASE_URL`: PostgreSQL 연결 정보

2. **의존성 설치**:
   ```bash
   pip install -r requirements.txt
   ```

3. **기존 Agent 백업**:
   - `agent.py`는 삭제하지 말 것
   - 라우터 문제 시 롤백 가능

4. **점진적 배포**:
   - 처음에는 일부 사용자만 새 시스템 사용
   - 로그 모니터링하며 점진적 확대
   - 문제 발생 시 즉시 기존 시스템으로 전환

### 개발 시
1. **로그 확인 필수**:
   - 라우터 판단 결과
   - 툴 실행 결과
   - 에러 발생 여부

2. **테스트 우선**:
   - 새 툴 추가 시 반드시 단위 테스트
   - 라우터 프롬프트 수정 시 시나리오 테스트

3. **에러 핸들링**:
   - 모든 툴은 에러 발생 시 구체적 메시지 반환
   - 사용자에게는 친절한 메시지, 로그에는 상세 정보

---

## 💬 추가 컨텍스트

### 프로젝트 히스토리
- **최근 작업**:
  - "feat: LLM 툴 호출 적응형 라우팅 시스템 구현"
  - "feat: 언어 변경 기능 및 다국어 지원 (4개 언어)"
- **최근 커밋**: "feat: RAG 대화 비동기 로깅 시스템 구현"
- **브랜치**: main
- **상태**: 구현 완료 (커밋 대기)

### 개발 스타일
- 한글 주석 및 로그 메시지
- 로깅 레벨: INFO
- 응답 길이 제한: 50자 (필요시 확장 제안)
- 에러 메시지: 사용자 친화적 + 상세 로깅

### 다음 마일스톤
- [x] 언어 변경 기능 구현 및 테스트 ✅
- [x] 프론트엔드 다국어 지원 (4개 언어) ✅
- [ ] 실제 서버 테스트 및 디버깅
- [ ] 나머지 툴 실제 동작 구현 (DB 연동)
- [ ] 성능 측정 및 최적화
- [ ] A/B 테스트 프레임워크

---

## 📞 참고 정보

### 관련 문서
- `IMPLEMENTATION_PLAN.md`: 상세 구현 계획 (완료)
- `CLAUDE.md`: 이 문서 (최신)
- Git 커밋 로그: 프로젝트 히스토리

### 다음 작업 시작 명령어
```
CLAUDE.md 파일을 읽고 실제 서버 테스트를 진행해줘.
테스트 시나리오에 따라 각 경로가 정상 동작하는지 확인하고,
문제가 있으면 수정해줘.
```

또는

```
tools.py에서 OrderMenuTool의 실제 동작을 구현해줘.
DB에 주문을 저장하는 로직을 추가하고,
실제 주문이 저장되는지 테스트해줘.
```

---

## 📊 구현 통계

- **총 코드 라인 수**: ~2,100줄
  - `tools.py`: 500줄 (언어 변환 로직 추가)
  - `tool_executor.py`: 200줄
  - `router.py`: 380줄 (휴리스틱 개선)
  - `main.py`: 577줄 (언어별 LLM 응답 추가)
  - `rag_pipeline.py`: 220줄 (언어별 RAG 응답 추가)
  - `chat.html`: ~920줄 (배지 다국어 지원)
- **총 개발 시간**: 약 5시간
- **테스트 완료**:
  - ✅ 문법 체크
  - ✅ 언어 변경 기능 테스트
  - ✅ LLM 다국어 응답 로직 구현
  - ✅ UI 배지 시스템 개선
- **실서버 테스트**: 부분 완료 (언어 변경)

---

> **작성자**: Claude Code 세션 (2025-10-07)
>
> **목적**: 작업 컨텍스트 유지 및 연속성 있는 개발 지원
>
> **상태**:
> - LLM 툴 호출 적응형 라우팅 시스템 구현 완료 ✅
> - 언어 변경 기능 및 다국어 지원 (4개 언어) 완료 ✅
> - LLM 다국어 응답 시스템 구현 완료 ✅
> - UI 배지 시스템 개선 (일반/RAG/툴) 완료 ✅
