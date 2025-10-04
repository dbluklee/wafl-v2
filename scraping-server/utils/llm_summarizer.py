from openai import OpenAI
import logging
import os
from typing import List, Dict, Any
from database import SessionLocal, Review, ReviewSummary, Menu

logger = logging.getLogger(__name__)

class LLMSummarizer:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OpenAI API 키가 설정되지 않았습니다. 요약 기능이 제한됩니다.")

    def generate_review_summary(self, store_id: int) -> str:
        """
        매장 리뷰들을 분석하여 마크다운 요약 생성

        Args:
            store_id (int): 매장 ID

        Returns:
            str: 마크다운 형식의 요약
        """
        try:
            db = SessionLocal()

            # 리뷰 및 메뉴 데이터 조회
            reviews = db.query(Review).filter(Review.store_id == store_id).all()
            menus = db.query(Menu).filter(Menu.store_id == store_id).all()

            if not reviews:
                return self._generate_no_reviews_summary()

            # 리뷰 데이터 분석
            analysis = self._analyze_reviews(reviews)

            # LLM을 사용한 요약 생성
            if self.client:
                summary = self._generate_llm_summary(reviews, menus, analysis)
            else:
                summary = self._generate_basic_summary(reviews, analysis)

            # 요약 저장
            self._save_summary(db, store_id, summary)

            return summary

        except Exception as e:
            logger.error(f"리뷰 요약 생성 실패: {e}")
            return self._generate_error_summary(str(e))
        finally:
            db.close()

    def _analyze_reviews(self, reviews: List[Review]) -> Dict[str, Any]:
        """리뷰 데이터 기본 분석"""
        total_reviews = len(reviews)
        revisit_customers = len([r for r in reviews if r.revisit_count > 1])

        # 키워드 분석 (간단한 버전)
        all_content = " ".join([r.content for r in reviews])
        positive_keywords = ['맛있', '좋', '추천', '만족', '깔끔', '친절', '맛나', '훌륭']
        negative_keywords = ['맛없', '별로', '실망', '불친절', '더러', '느려', '비싸']

        positive_count = sum(all_content.count(keyword) for keyword in positive_keywords)
        negative_count = sum(all_content.count(keyword) for keyword in negative_keywords)

        return {
            'total_reviews': total_reviews,
            'revisit_customers': revisit_customers,
            'revisit_rate': (revisit_customers / total_reviews * 100) if total_reviews > 0 else 0,
            'positive_mentions': positive_count,
            'negative_mentions': negative_count,
            'sentiment_score': (positive_count - negative_count) / max(positive_count + negative_count, 1)
        }

    def _generate_llm_summary(self, reviews: List[Review], menus: List[Menu], analysis: Dict[str, Any]) -> str:
        """OpenAI API를 사용한 고급 요약 생성"""
        try:
            # 리뷰 샘플 (토큰 제한 고려)
            prompt = self._create_summary_prompt(reviews, menus, analysis)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 음식점 리뷰를 분석하여 메뉴별 인사이트와 페어링 추천을 제공하는 전문 데이터 분석가입니다. 리뷰에서 메뉴 언급을 추출하고, 시간대별 선호도, 메뉴 조합, 최근 트렌드를 파악하는 데 능숙합니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=3000,
                temperature=0.3
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            return self._generate_basic_summary(reviews, analysis)

    def _create_summary_prompt(self, reviews: List[Review], menus: List[Menu], analysis: Dict[str, Any]) -> str:
        """메뉴 중심 분석을 위한 프롬프트 생성"""

        # 메뉴 목록 생성
        menu_list = "\n".join([f"- {menu.menu_name} ({menu.price})" + (f" - {menu.recommendation}" if menu.recommendation else "") for menu in menus])

        # 리뷰 데이터 (날짜 포함)
        reviews_text = "\n".join([f"[{review.review_date}] {review.content}" for review in reviews])

        return f"""
다음은 한 음식점의 메뉴 목록과 고객 리뷰입니다. 메뉴 중심으로 심층 분석해주세요.

**메뉴 목록:**
{menu_list}

**기본 통계:**
- 총 리뷰 수: {analysis['total_reviews']}개
- 재방문 고객: {analysis['revisit_customers']}명 ({analysis['revisit_rate']:.1f}%)

**전체 리뷰 (날짜 포함):**
{reviews_text}

다음 구조로 마크다운 형식으로 분석해주세요:

# 🍽️ 메뉴별 리뷰 분석 보고서

## 📊 인기 메뉴 TOP 3
각 메뉴별로:
- 리뷰에서 언급된 횟수
- 고객들이 좋아하는 이유 (맛, 양, 가성비 등 구체적으로)
- 대표 리뷰 인용

## 🔥 최근 트렌드 (요근래 인기 메뉴)
- 날짜를 분석하여 최근(최신 리뷰 기준) 가장 많이 언급되는 메뉴
- 인기 상승 이유 분석
- 계절성이나 트렌드 고려

## 🤝 메뉴 페어링 추천
리뷰에서 함께 주문했다고 언급된 메뉴 조합:
- 메뉴 A + 메뉴 B: 왜 잘 어울리는지 설명
- 실제 고객 리뷰 인용
- 최소 2-3가지 조합 추천

## ⏰ 시간대별 메뉴 선호도
리뷰의 날짜와 내용을 바탕으로 추정:
- 점심 시간대 인기 메뉴
- 저녁 시간대 인기 메뉴
- 주말/평일 차이 (추정 가능한 경우)

## 💡 메뉴 운영 개선 제안
- 추가하면 좋을 메뉴
- 개선이 필요한 메뉴
- 프로모션 제안 (페어링 할인 등)

## 📈 고객 만족도 요약
- 재방문율: {analysis['revisit_rate']:.1f}%
- 전반적 평가
- 주의할 점

---
*분석 기준: 총 {analysis['total_reviews']}개 리뷰 / {len(menus)}개 메뉴*

**중요:**
1. 반드시 실제 리뷰에서 언급된 내용만 사용하세요
2. 추측이 필요한 부분은 "추정" 또는 "~로 보입니다"라고 명시하세요
3. 구체적인 리뷰 내용을 인용하여 근거를 제시하세요
"""

    def _generate_basic_summary(self, reviews: List[Review], analysis: Dict[str, Any]) -> str:
        """기본 통계 기반 요약"""
        sentiment = "긍정적" if analysis['sentiment_score'] > 0.2 else "부정적" if analysis['sentiment_score'] < -0.2 else "중성적"

        return f"""# 고객 리뷰 분석 요약

## 📊 기본 통계
- **총 리뷰 수**: {analysis['total_reviews']}개
- **재방문 고객**: {analysis['revisit_customers']}명 ({analysis['revisit_rate']:.1f}%)
- **전반적 sentiment**: {sentiment}

## 🎯 핵심 지표
- 긍정적 언급: {analysis['positive_mentions']}회
- 부정적 언급: {analysis['negative_mentions']}회
- 고객 만족도: {'높음' if analysis['sentiment_score'] > 0.3 else '보통' if analysis['sentiment_score'] > -0.1 else '낮음'}

## 💡 요약
재방문율 {analysis['revisit_rate']:.1f}%로 {'높은' if analysis['revisit_rate'] > 30 else '보통' if analysis['revisit_rate'] > 15 else '낮은'} 수준의 고객 충성도를 보이고 있습니다.
{'고객들의 반응이 대체로 긍정적' if analysis['sentiment_score'] > 0 else '고객 만족도 개선이 필요한 상황'}입니다.

---
*자동 생성된 요약 - 자세한 분석을 위해서는 개별 리뷰를 확인해주세요.*
"""

    def _generate_no_reviews_summary(self) -> str:
        """리뷰가 없는 경우 요약"""
        return """# 고객 리뷰 분석 요약

## 📝 현재 상태
아직 고객 리뷰가 없습니다.

## 💡 제안사항
- 고객들에게 리뷰 작성을 독려하는 이벤트를 기획해보세요
- 서비스 품질 향상을 위해 노력하여 자연스러운 리뷰 유도
- 매장 내 QR코드나 안내문을 통한 리뷰 참여 유도

고객 리뷰가 누적되면 더 상세한 분석을 제공할 수 있습니다.
"""

    def _generate_error_summary(self, error_msg: str) -> str:
        """오류 발생 시 요약"""
        return f"""# 리뷰 분석 오류

요약 생성 중 오류가 발생했습니다.

**오류 내용**: {error_msg}

관리자에게 문의하시기 바랍니다.
"""

    def _save_summary(self, db, store_id: int, summary: str):
        """요약 결과 데이터베이스 저장"""
        try:
            # 기존 요약 삭제
            db.query(ReviewSummary).filter(ReviewSummary.store_id == store_id).delete()

            # 새 요약 저장
            review_summary = ReviewSummary(
                store_id=store_id,
                summary_md=summary
            )
            db.add(review_summary)
            db.commit()

            logger.info(f"매장 {store_id} 리뷰 요약 저장 완료")

        except Exception as e:
            logger.error(f"요약 저장 실패: {e}")
            db.rollback()