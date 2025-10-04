from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os
import logging

logger = logging.getLogger(__name__)

class SeleniumDriver:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless

    def __enter__(self):
        self.start_driver()
        return self.driver

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit_driver()

    def start_driver(self):
        """Chrome WebDriver 시작"""
        try:
            options = Options()

            if self.headless:
                options.add_argument("--headless")

            # Chrome 옵션 설정
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            # 도커 환경에서 Chrome 경로 설정
            if os.path.exists('/usr/bin/google-chrome'):
                options.binary_location = '/usr/bin/google-chrome'

            # ChromeDriver 서비스 설정
            # 시스템에 설치된 ChromeDriver를 먼저 확인
            system_chromedriver = '/usr/local/bin/chromedriver'
            if os.path.exists(system_chromedriver):
                logger.info(f"시스템 ChromeDriver 사용: {system_chromedriver}")
                service = Service(system_chromedriver)
            else:
                # 시스템에 없으면 ChromeDriverManager 사용
                try:
                    driver_path = ChromeDriverManager().install()
                    # ChromeDriverManager가 잘못된 파일을 반환하는 경우 수정
                    if 'THIRD_PARTY_NOTICES' in driver_path or not driver_path.endswith('chromedriver'):
                        driver_dir = os.path.dirname(driver_path)
                        chromedriver_path = os.path.join(driver_dir, 'chromedriver')
                        if os.path.exists(chromedriver_path):
                            driver_path = chromedriver_path
                            # 실행 권한 확인 및 부여
                            if not os.access(driver_path, os.X_OK):
                                os.chmod(driver_path, 0o755)
                                logger.info(f"ChromeDriver 실행 권한 부여: {driver_path}")

                    logger.info(f"ChromeDriver 경로: {driver_path}")
                    service = Service(driver_path)
                except Exception as e:
                    logger.warning(f"ChromeDriverManager 실패, 기본 chromedriver 사용: {e}")
                    service = Service()

            self.driver = webdriver.Chrome(service=service, options=options)

            # 자동화 감지 우회
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logger.info("Chrome WebDriver 시작 완료")
            return self.driver

        except Exception as e:
            logger.error(f"Chrome WebDriver 시작 실패: {e}")
            raise

    def quit_driver(self):
        """Chrome WebDriver 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Chrome WebDriver 종료 완료")
            except Exception as e:
                logger.error(f"Chrome WebDriver 종료 중 오류: {e}")

    def wait_for_element(self, by, value, timeout=10):
        """요소가 나타날 때까지 대기"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def wait_for_clickable(self, by, value, timeout=10):
        """요소가 클릭 가능할 때까지 대기"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def safe_click(self, element):
        """안전한 클릭 (JavaScript 사용)"""
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            logger.warning(f"JavaScript 클릭 실패: {e}")
            try:
                element.click()
                return True
            except Exception as e2:
                logger.error(f"일반 클릭도 실패: {e2}")
                return False