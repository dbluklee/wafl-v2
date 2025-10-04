from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
import re
import os
import requests
import logging
from database import SessionLocal, Store
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

app = FastAPI(title="WAFL - 네이버 스토어 스크래핑 서비스")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 정적 파일과 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Pydantic 모델
class StoreRegistration(BaseModel):
    store_name: str
    store_address: str
    business_number: str
    owner_name: str
    owner_phone: str
    naver_store_url: str

def extract_store_id(naver_url: str) -> Optional[str]:
    """네이버 스토어 URL에서 store_id 추출"""
    try:
        # naver.me 단축 URL인 경우 리다이렉트 URL 가져오기
        if 'naver.me' in naver_url:
            response = requests.head(naver_url, allow_redirects=True, timeout=10)
            naver_url = response.url

        patterns = [
            r'place/(\d+)',
            r'entry/place/(\d+)',
            r'restaurant/(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, naver_url)
            if match:
                return match.group(1)
        return None
    except Exception as e:
        logger.error(f"URL 처리 오류: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """회원가입 페이지"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/jusoPopup", response_class=HTMLResponse)
async def juso_popup_get(request: Request):
    """주소 검색 팝업 페이지 (GET)"""
    juso_api_key = os.getenv("JUSO_API_KEY", "")
    return templates.TemplateResponse("jusoPopup.html", {
        "request": request,
        "JUSO_API_KEY": juso_api_key,
        "inputYn": ""
    })

@app.post("/jusoPopup", response_class=HTMLResponse)
async def juso_popup_post(
    request: Request,
    inputYn: str = Form(default=""),
    roadFullAddr: str = Form(default=""),
    roadAddrPart1: str = Form(default=""),
    roadAddrPart2: str = Form(default=""),
    addrDetail: str = Form(default=""),
    engAddr: str = Form(default=""),
    jibunAddr: str = Form(default=""),
    zipNo: str = Form(default=""),
    admCd: str = Form(default=""),
    rnMgtSn: str = Form(default=""),
    bdMgtSn: str = Form(default=""),
    detBdNmList: str = Form(default=""),
    bdNm: str = Form(default=""),
    bdKdcd: str = Form(default=""),
    siNm: str = Form(default=""),
    sggNm: str = Form(default=""),
    emdNm: str = Form(default=""),
    liNm: str = Form(default=""),
    rn: str = Form(default=""),
    udrtYn: str = Form(default=""),
    buldMnnm: str = Form(default=""),
    buldSlno: str = Form(default=""),
    mtYn: str = Form(default=""),
    lnbrMnnm: str = Form(default=""),
    lnbrSlno: str = Form(default=""),
    emdNo: str = Form(default="")
):
    """주소 검색 팝업 페이지 (POST - 주소 API 콜백)"""
    juso_api_key = os.getenv("JUSO_API_KEY", "")
    return templates.TemplateResponse("jusoPopup.html", {
        "request": request,
        "JUSO_API_KEY": juso_api_key,
        "inputYn": inputYn,
        "roadFullAddr": roadFullAddr,
        "roadAddrPart1": roadAddrPart1,
        "roadAddrPart2": roadAddrPart2,
        "addrDetail": addrDetail,
        "engAddr": engAddr,
        "jibunAddr": jibunAddr,
        "zipNo": zipNo,
        "admCd": admCd,
        "rnMgtSn": rnMgtSn,
        "bdMgtSn": bdMgtSn,
        "detBdNmList": detBdNmList,
        "bdNm": bdNm,
        "bdKdcd": bdKdcd,
        "siNm": siNm,
        "sggNm": sggNm,
        "emdNm": emdNm,
        "liNm": liNm,
        "rn": rn,
        "udrtYn": udrtYn,
        "buldMnnm": buldMnnm,
        "buldSlno": buldSlno,
        "mtYn": mtYn,
        "lnbrMnnm": lnbrMnnm,
        "lnbrSlno": lnbrSlno,
        "emdNo": emdNo
    })

@app.post("/api/stores/register")
async def register_store(
    store_name: str = Form(...),
    store_address: str = Form(...),
    business_number: str = Form(...),
    owner_name: str = Form(...),
    owner_phone: str = Form(...),
    naver_store_url: str = Form(...)
):
    """매장 등록 API"""

    # 네이버 스토어 ID 추출
    store_id = extract_store_id(naver_store_url)
    if not store_id:
        raise HTTPException(status_code=400, detail="올바른 네이버 스토어 URL을 입력해주세요.")

    # 데이터베이스에 저장
    db = SessionLocal()
    try:
        new_store = Store(
            store_name=store_name,
            store_address=store_address,
            business_number=business_number,
            owner_name=owner_name,
            owner_phone=owner_phone,
            naver_store_url=naver_store_url,
            store_id=store_id
        )

        db.add(new_store)
        db.commit()
        db.refresh(new_store)

        # 매장 등록 후 자동으로 스크래핑 작업 시작
        try:
            scraping_server_url = os.getenv("SCRAPING_SERVER_URL", "http://wafl-scraping-server:8001")
            response = requests.post(
                f"{scraping_server_url}/api/scraping/start",
                json={"store_id": new_store.id},
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"매장 {new_store.id} 스크래핑 작업이 큐에 추가되었습니다.")
            else:
                logger.warning(f"스크래핑 작업 추가 실패: {response.text}")
        except Exception as e:
            logger.error(f"스크래핑 작업 추가 오류: {e}")
            # 스크래핑 시작 실패해도 매장 등록은 성공으로 처리

        return JSONResponse(
            status_code=201,
            content={
                "message": "매장이 성공적으로 등록되었습니다. 스크래핑이 자동으로 시작됩니다.",
                "store_id": new_store.id,
                "naver_store_id": store_id
            }
        )

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="이미 등록된 사업자등록번호입니다.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"등록 중 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()

@app.get("/api/stores/{store_id}")
async def get_store(store_id: int):
    """매장 정보 조회 API"""
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        return {
            "id": store.id,
            "store_name": store.store_name,
            "store_address": store.store_address,
            "business_number": store.business_number,
            "owner_name": store.owner_name,
            "owner_phone": store.owner_phone,
            "naver_store_url": store.naver_store_url,
            "store_id": store.store_id,
            "scraping_status": store.scraping_status,
            "created_at": store.created_at
        }
    finally:
        db.close()

@app.get("/api/stores")
async def list_stores():
    """매장 목록 조회 API"""
    db = SessionLocal()
    try:
        stores = db.query(Store).order_by(Store.created_at.desc()).all()
        return [
            {
                "id": store.id,
                "store_name": store.store_name,
                "store_address": store.store_address,
                "scraping_status": store.scraping_status,
                "created_at": store.created_at
            }
            for store in stores
        ]
    finally:
        db.close()

@app.delete("/api/stores/{store_id}")
async def delete_store(store_id: int):
    """매장 삭제 API (DB에서 완전히 삭제, CASCADE로 메뉴/리뷰/요약도 함께 삭제)"""
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        store_name = store.store_name
        db.delete(store)
        db.commit()

        logger.info(f"매장 삭제 완료: {store_name} (ID: {store_id})")

        return {
            "message": f"매장 '{store_name}'이(가) 성공적으로 삭제되었습니다.",
            "deleted_store_id": store_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"매장 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"매장 삭제 중 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()

@app.post("/api/scraping/start")
async def start_scraping_proxy(store_id: int = Form(...)):
    """스크래핑 시작 API (스크래핑 서버로 프록시)"""
    try:
        import requests

        # 스크래핑 서버로 요청 전달
        scraping_server_url = os.getenv("SCRAPING_SERVER_URL", "http://wafl-scraping-server:8001")
        response = requests.post(
            f"{scraping_server_url}/api/scraping/start",
            json={"store_id": store_id},
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except requests.exceptions.RequestException as e:
        logger.error(f"스크래핑 서버 연결 오류: {e}")
        raise HTTPException(status_code=503, detail="스크래핑 서버에 연결할 수 없습니다.")
    except Exception as e:
        logger.error(f"스크래핑 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """대시보드 페이지"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/stores/{store_id}/detail")
async def get_store_detail(store_id: int):
    """매장 상세 정보 조회 API (매장 정보 + 메뉴 + 리뷰 + 요약)"""
    import requests

    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        # 스크래핑 서버에서 메뉴, 리뷰, 요약 데이터 가져오기
        scraping_server_url = os.getenv("SCRAPING_SERVER_URL", "http://wafl-scraping-server:8001")

        try:
            # 메뉴 조회
            menus_response = requests.get(f"{scraping_server_url}/api/scraping/store/{store_id}/menus", timeout=10)
            menus_data = menus_response.json() if menus_response.status_code == 200 else {"menus": [], "total": 0}

            # 리뷰 조회
            reviews_response = requests.get(f"{scraping_server_url}/api/scraping/store/{store_id}/reviews", timeout=10)
            reviews_data = reviews_response.json() if reviews_response.status_code == 200 else {"reviews": [], "total": 0}

            # 요약 조회
            summary_response = requests.get(f"{scraping_server_url}/api/scraping/store/{store_id}/summary", timeout=10)
            summary_data = summary_response.json() if summary_response.status_code == 200 else {"summary": "", "status": "not_found"}

        except requests.exceptions.RequestException as e:
            logger.error(f"스크래핑 서버 연결 오류: {e}")
            menus_data = {"menus": [], "total": 0}
            reviews_data = {"reviews": [], "total": 0}
            summary_data = {"summary": "", "status": "error"}

        return {
            "store_info": {
                "id": store.id,
                "store_name": store.store_name,
                "store_address": store.store_address,
                "business_number": store.business_number,
                "owner_name": store.owner_name,
                "owner_phone": store.owner_phone,
                "naver_store_url": store.naver_store_url,
                "store_id": store.store_id,
                "scraped_store_name": store.scraped_store_name,
                "scraped_category": store.scraped_category,
                "scraped_description": store.scraped_description,
                "scraped_store_address": store.scraped_store_address,
                "scraped_phone": store.scraped_phone,
                "scraped_sns": store.scraped_sns,
                "scraped_intro": store.scraped_intro,
                "scraped_services": store.scraped_services,
                "scraping_status": store.scraping_status,
                "created_at": store.created_at,
                "updated_at": store.updated_at
            },
            "menus": menus_data.get("menus", []),
            "menu_count": menus_data.get("total", 0),
            "reviews": reviews_data.get("reviews", []),
            "review_count": reviews_data.get("total", 0),
            "summary": summary_data.get("summary", ""),
            "summary_status": summary_data.get("status", "not_found")
        }
    finally:
        db.close()

@app.get("/store/{store_id}/summary", response_class=HTMLResponse)
async def view_summary(request: Request, store_id: int):
    """매장 리뷰 요약 페이지"""
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        return templates.TemplateResponse("summary.html", {
            "request": request,
            "store_id": store_id,
            "store_name": store.scraped_store_name or store.store_name,
            "store_address": store.scraped_store_address or store.store_address
        })
    finally:
        db.close()

@app.get("/store/{store_id}/detail", response_class=HTMLResponse)
async def view_store_detail(request: Request, store_id: int):
    """매장 상세보기 페이지"""
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        return templates.TemplateResponse("store_detail.html", {
            "request": request,
            "store_id": store_id
        })
    finally:
        db.close()

@app.get("/api/scraping/store/{store_id}/summary")
async def get_store_summary_proxy(store_id: int):
    """매장 리뷰 요약 조회 API (스크래핑 서버로 프록시)"""
    try:
        import requests

        scraping_server_url = os.getenv("SCRAPING_SERVER_URL", "http://wafl-scraping-server:8001")
        response = requests.get(
            f"{scraping_server_url}/api/scraping/store/{store_id}/summary",
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except requests.exceptions.RequestException as e:
        logger.error(f"스크래핑 서버 연결 오류: {e}")
        raise HTTPException(status_code=503, detail="스크래핑 서버에 연결할 수 없습니다.")
    except Exception as e:
        logger.error(f"요약 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scraping/store/{store_id}/summary/regenerate")
async def regenerate_summary_proxy(store_id: int):
    """리뷰 요약 재생성 API (스크래핑 서버로 프록시)"""
    try:
        import requests

        scraping_server_url = os.getenv("SCRAPING_SERVER_URL", "http://wafl-scraping-server:8001")
        response = requests.post(
            f"{scraping_server_url}/api/scraping/store/{store_id}/summary/regenerate",
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except requests.exceptions.RequestException as e:
        logger.error(f"스크래핑 서버 연결 오류: {e}")
        raise HTTPException(status_code=503, detail="스크래핑 서버에 연결할 수 없습니다.")
    except Exception as e:
        logger.error(f"요약 재생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """헬스체크 API"""
    return {"status": "healthy", "service": "web-server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)