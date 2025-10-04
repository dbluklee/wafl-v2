from celery import current_task
from celery_app import celery
from sqlalchemy.orm import sessionmaker
from database import engine, Store, Menu, Review, ScrapingTask
from utils.selenium_driver import SeleniumDriver
from utils.image_downloader import ImageDownloader
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import traceback

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터베이스 세션
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@celery.task(bind=True, max_retries=3)
def scrape_store_data(self, store_id):
    """
    매장 데이터 스크래핑 메인 태스크

    Args:
        store_id (int): 매장 ID

    Returns:
        dict: 스크래핑 결과
    """
    db = SessionLocal()
    task_id = self.request.id

    try:
        # 매장 정보 조회
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise ValueError(f"매장을 찾을 수 없습니다: {store_id}")

        if not store.store_id:
            raise ValueError(f"네이버 스토어 ID가 없습니다: {store_id}")

        # 태스크 상태 업데이트
        store.scraping_status = 'in_progress'
        db.commit()

        # 스크래핑 태스크 기록
        scraping_task = ScrapingTask(
            store_id=store_id,
            task_id=task_id,
            status='started'
        )
        db.add(scraping_task)
        db.commit()

        # 스크래핑 진행상황 업데이트
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': '매장 기본 정보 수집 시작'})

        # 매장 기본 정보 스크래핑
        store_info = scrape_store_info(store.store_id, db, store_id)
        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': '메뉴 정보 수집 시작'})

        # 메뉴 정보 스크래핑
        menu_info = scrape_menu_info(store.store_id, db, store_id)
        self.update_state(state='PROGRESS', meta={'progress': 60, 'status': '리뷰 정보 수집 시작'})

        # 리뷰 정보 스크래핑
        review_info = scrape_review_info(store.store_id, db, store_id)
        self.update_state(state='PROGRESS', meta={'progress': 90, 'status': '데이터 저장 중'})

        # 스크래핑 결과를 매장 정보에 업데이트
        if store_info:
            for key, value in store_info.items():
                if hasattr(store, key):
                    setattr(store, key, value)

        # 매장 정보 비교 및 상태 설정
        is_match = compare_store_info(store)
        store.scraping_status = 'completed' if is_match else 'mismatch'

        db.commit()

        # 태스크 완료 기록
        scraping_task.status = 'success'
        scraping_task.result = f"매장 정보: {len(store_info) if store_info else 0}개, 메뉴: {menu_info['count'] if menu_info else 0}개, 리뷰: {review_info['count'] if review_info else 0}개"
        db.commit()

        # 리뷰 요약 태스크 시작
        if review_info and review_info['count'] > 0:
            generate_review_summary.delay(store_id)

        result = {
            'store_id': store_id,
            'status': 'completed',
            'store_info': store_info,
            'menu_count': menu_info['count'] if menu_info else 0,
            'review_count': review_info['count'] if review_info else 0,
            'is_match': is_match
        }

        logger.info(f"매장 {store_id} 스크래핑 완료: {result}")
        return result

    except Exception as e:
        logger.error(f"매장 {store_id} 스크래핑 오류: {e}")
        logger.error(traceback.format_exc())

        # 오류 상태 업데이트
        if 'store' in locals():
            store.scraping_status = 'error'
            store.scraping_error_message = str(e)
            db.commit()

        if 'scraping_task' in locals():
            scraping_task.status = 'failure'
            scraping_task.error_message = str(e)
            db.commit()

        # 재시도 로직
        if self.request.retries < self.max_retries:
            logger.info(f"매장 {store_id} 스크래핑 재시도 ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (self.request.retries + 1))

        raise

    finally:
        db.close()

def scrape_store_info(naver_store_id, db, store_id):
    """매장 기본 정보 스크래핑"""
    try:
        with SeleniumDriver(headless=True) as driver:
            # 매장 기본 정보 페이지
            store_page = f'https://m.place.naver.com/restaurant/{naver_store_id}/home'
            driver.get(store_page)
            time.sleep(3)

            store_info = {}

            # CSS 선택자 정의
            selectors = {
                'scraped_store_name': 'span.GHAhO',
                'scraped_category': 'span.lnJFt',
                'scraped_description': 'div.XtBbS',
                'scraped_store_address': 'span.LDgIH',
                'scraped_directions': 'span.zPfVt',
                'scraped_phone': 'span.xlx7Q',
                'scraped_sns': 'div.jO09N a',
                'scraped_etc_info': 'div.xPvPE'
            }

            # 기본 정보 수집
            for field, selector in selectors.items():
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        if field == 'scraped_sns':
                            store_info[field] = elements[0].get_attribute('href')
                        else:
                            store_info[field] = elements[0].text.strip()
                except Exception as e:
                    logger.warning(f"{field} 수집 실패: {e}")
                    store_info[field] = None

            # 전화번호 팝업 처리
            if not store_info.get('scraped_phone'):
                try:
                    phone_button = driver.find_elements(By.CSS_SELECTOR, 'a.BfF3H')
                    if phone_button:
                        driver.execute_script("arguments[0].click();", phone_button[0])
                        time.sleep(1)
                        phone_elements = driver.find_elements(By.CSS_SELECTOR, 'div.J7eF_ em')
                        if phone_elements:
                            store_info['scraped_phone'] = phone_elements[0].text.strip()
                except Exception as e:
                    logger.warning(f"전화번호 팝업 처리 실패: {e}")

            # 추가 정보 페이지
            info_page = f'https://m.place.naver.com/restaurant/{naver_store_id}/information'
            driver.get(info_page)
            time.sleep(3)

            # 매장 소개
            try:
                intro_elements = driver.find_elements(By.CSS_SELECTOR, 'div.T8RFa')
                if intro_elements:
                    store_info['scraped_intro'] = intro_elements[0].text.strip()
            except Exception as e:
                logger.warning(f"매장 소개 수집 실패: {e}")

            # 편의시설 및 서비스
            try:
                services = []
                service_elements = driver.find_elements(By.CSS_SELECTOR, 'li.c7TR6')
                for li in service_elements:
                    try:
                        service = li.find_element(By.CSS_SELECTOR, 'div.owG4q').text.strip()
                        extra_elements = li.find_elements(By.CSS_SELECTOR, 'span.place_blind')
                        if extra_elements:
                            extra = extra_elements[0].text.strip()
                            service_name = f'{service} ({extra})'
                        else:
                            service_name = service

                        if service_name:
                            services.append(service_name)
                    except:
                        continue

                store_info['scraped_services'] = ", ".join(services) if services else None
            except Exception as e:
                logger.warning(f"편의시설 수집 실패: {e}")

            return store_info

    except Exception as e:
        logger.error(f"매장 정보 스크래핑 실패: {e}")
        return None

def scrape_menu_info(naver_store_id, db, store_id):
    """메뉴 정보 스크래핑"""
    try:
        with SeleniumDriver(headless=True) as driver:
            menu_page = f'https://m.place.naver.com/restaurant/{naver_store_id}/menu/list'
            driver.get(menu_page)
            time.sleep(3)

            # 기존 메뉴 삭제
            db.query(Menu).filter(Menu.store_id == store_id).delete()
            db.commit()

            # 더보기 버튼 클릭
            while True:
                try:
                    more_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.fvwqf'))
                    )
                    driver.execute_script("arguments[0].click();", more_button)
                    time.sleep(2)
                except:
                    break

            # 메뉴 수집
            menus = driver.find_elements(By.CSS_SELECTOR, 'li.E2jtL')
            image_downloader = ImageDownloader()
            menu_count = 0

            for li in menus:
                try:
                    menu_name = ""
                    menu_desc = ""
                    menu_price = ""
                    menu_recommendation = ""
                    image_file_path = None
                    image_url = None

                    # 메뉴명
                    name_elements = li.find_elements(By.CSS_SELECTOR, "span.lPzHi")
                    if name_elements:
                        menu_name = name_elements[0].text.strip()

                    # 메뉴 설명
                    desc_elements = li.find_elements(By.CSS_SELECTOR, "div.kPogF")
                    if desc_elements:
                        menu_desc = desc_elements[0].text.strip()

                    # 추천 여부
                    rec_elements = li.find_elements(By.CSS_SELECTOR, "span.QM_zp span")
                    if rec_elements:
                        menu_recommendation = rec_elements[0].text.strip()

                    # 가격
                    price_em_elements = li.find_elements(By.CSS_SELECTOR, "div.GXS1X em")
                    if price_em_elements:
                        menu_price = price_em_elements[0].text.strip()
                    else:
                        price_div_elements = li.find_elements(By.CSS_SELECTOR, "div.GXS1X")
                        if price_div_elements:
                            menu_price = price_div_elements[0].text.strip()

                    # 이미지
                    img_elements = li.find_elements(By.CSS_SELECTOR, "img")
                    if img_elements:
                        image_url = img_elements[0].get_attribute('src')
                        if image_url and image_url.startswith('http'):
                            image_file_path = image_downloader.download_and_save_image(
                                image_url, store_id, menu_count + 1
                            )

                    # 메뉴 정보가 있을 경우에만 저장
                    if menu_name or menu_desc or menu_price:
                        menu = Menu(
                            store_id=store_id,
                            menu_name=menu_name,
                            price=menu_price,
                            description=menu_desc,
                            recommendation=menu_recommendation,
                            image_file_path=image_file_path,
                            image_url=image_url
                        )
                        db.add(menu)
                        menu_count += 1

                except Exception as e:
                    logger.warning(f"메뉴 항목 처리 실패: {e}")
                    continue

            db.commit()
            logger.info(f"메뉴 {menu_count}개 수집 완료")
            return {'count': menu_count}

    except Exception as e:
        logger.error(f"메뉴 정보 스크래핑 실패: {e}")
        return {'count': 0}

def scrape_review_info(naver_store_id, db, store_id, max_iterations=50):
    """리뷰 정보 스크래핑"""
    try:
        with SeleniumDriver(headless=True) as driver:
            review_page = f'https://m.place.naver.com/restaurant/{naver_store_id}/review/visitor'
            driver.get(review_page)
            time.sleep(3)

            # 기존 리뷰 삭제
            db.query(Review).filter(Review.store_id == store_id).delete()
            db.commit()

            # 더보기 버튼 클릭
            count = 0
            while True:
                if max_iterations > 0 and count >= max_iterations:
                    break

                try:
                    more_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.fvwqf'))
                    )
                    driver.execute_script("arguments[0].click();", more_button)
                    count += 1
                    time.sleep(2)
                except:
                    break

            # 리뷰 수집
            reviews = driver.find_elements(By.CSS_SELECTOR, 'li.place_apply_pui.EjjAW')
            review_count = 0

            for r in reviews:
                try:
                    content = r.find_element(By.CSS_SELECTOR, 'div.pui__vn15t2').text.strip()
                    date = r.find_element(By.CSS_SELECTOR, 'span.pui__gfuUIT > time').text.strip()

                    revisit_elements = r.find_elements(By.CSS_SELECTOR, 'span.pui__gfuUIT')
                    revisit_text = revisit_elements[1].text.strip() if len(revisit_elements) > 1 else ''

                    revisit_count = 0
                    if "번째 방문" in revisit_text:
                        try:
                            revisit_count = int(revisit_text.replace('번째 방문', '').strip())
                        except ValueError:
                            revisit_count = 0

                    review = Review(
                        store_id=store_id,
                        content=content,
                        review_date=date,
                        revisit_count=revisit_count
                    )
                    db.add(review)
                    review_count += 1

                except Exception as e:
                    logger.warning(f"리뷰 항목 처리 실패: {e}")
                    continue

            db.commit()
            logger.info(f"리뷰 {review_count}개 수집 완료")
            return {'count': review_count}

    except Exception as e:
        logger.error(f"리뷰 정보 스크래핑 실패: {e}")
        return {'count': 0}

def normalize_address(address):
    """주소 정규화 - 광역시/특별시 등을 통일"""
    if not address:
        return ""

    # 공백 제거 및 소문자 변환
    normalized = address.replace(' ', '').lower()

    # 광역시/특별시 등을 축약형으로 통일
    normalized = normalized.replace('서울특별시', '서울')
    normalized = normalized.replace('부산광역시', '부산')
    normalized = normalized.replace('대구광역시', '대구')
    normalized = normalized.replace('인천광역시', '인천')
    normalized = normalized.replace('광주광역시', '광주')
    normalized = normalized.replace('대전광역시', '대전')
    normalized = normalized.replace('울산광역시', '울산')
    normalized = normalized.replace('세종특별자치시', '세종')
    normalized = normalized.replace('경기도', '경기')
    normalized = normalized.replace('강원도', '강원')
    normalized = normalized.replace('충청북도', '충북')
    normalized = normalized.replace('충청남도', '충남')
    normalized = normalized.replace('전라북도', '전북')
    normalized = normalized.replace('전라남도', '전남')
    normalized = normalized.replace('경상북도', '경북')
    normalized = normalized.replace('경상남도', '경남')
    normalized = normalized.replace('제주특별자치도', '제주')

    return normalized

def compare_store_info(store):
    """사용자 입력 정보와 스크래핑 정보 비교"""
    try:
        # 매장명 비교
        if store.store_name and store.scraped_store_name:
            if store.store_name.strip() != store.scraped_store_name.strip():
                return False

        # 주소 비교 - 사용자 입력 기본 주소(상세주소 제외)가 스크래핑된 주소에 포함되면 일치
        # 예: 사용자 입력 "서울특별시 서초구 강남대로8길 49" -> "서울서초구강남대로8길49"
        #     스크래핑 "서울 서초구 강남대로8길 49 1층" -> "서울서초구강남대로8길491층"
        #     => 일치
        if store.store_address and store.scraped_store_address:
            user_addr = normalize_address(store.store_address)
            scraped_addr = normalize_address(store.scraped_store_address)
            if user_addr not in scraped_addr:
                logger.warning(f"주소 불일치 - 사용자: {user_addr}, 스크래핑: {scraped_addr}")
                return False

        return True

    except Exception as e:
        logger.warning(f"매장 정보 비교 중 오류: {e}")
        return True  # 비교 실패 시 일치하는 것으로 간주

@celery.task(bind=True)
def generate_review_summary(self, store_id):
    """리뷰 요약 생성 태스크"""
    try:
        from utils.llm_summarizer import LLMSummarizer

        logger.info(f"매장 {store_id}의 리뷰 요약 생성 시작")

        # LLM 요약 생성
        summarizer = LLMSummarizer()
        summary = summarizer.generate_review_summary(store_id)

        logger.info(f"매장 {store_id}의 리뷰 요약 생성 완료")

        return {
            'status': 'completed',
            'store_id': store_id,
            'summary_length': len(summary)
        }

    except Exception as e:
        logger.error(f"리뷰 요약 생성 실패: {e}")
        logger.error(traceback.format_exc())

        # 재시도 로직
        if self.request.retries < self.max_retries:
            logger.info(f"매장 {store_id} 요약 생성 재시도 ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (self.request.retries + 1))

        raise