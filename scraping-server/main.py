from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from celery_app import celery
from tasks.scraping_tasks import scrape_store_data
from database import SessionLocal, Store, Menu, Review, ScrapingTask, ReviewSummary
from sqlalchemy.orm import joinedload
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WAFL 스크래핑 서버", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic 모델
class ScrapingRequest(BaseModel):
    store_id: int

class ScrapingResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class StoreDataResponse(BaseModel):
    store_info: Dict[str, Any]
    menu_count: int
    review_count: int
    scraping_status: str

@app.get("/")
async def root():
    """스크래핑 서버 상태 확인"""
    return {
        "service": "WAFL 스크래핑 서버",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """헬스체크 API"""
    try:
        # Celery 연결 상태 확인
        inspect = celery.control.inspect()
        active_tasks = inspect.active()

        # 데이터베이스 연결 상태 확인
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()

        return {
            "status": "healthy",
            "celery": "connected" if active_tasks is not None else "disconnected",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.post("/api/scraping/start", response_model=ScrapingResponse)
async def start_scraping(request: ScrapingRequest):
    """스크래핑 시작 API"""
    try:
        db = SessionLocal()

        # 매장 존재 확인
        store = db.query(Store).filter(Store.id == request.store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        if not store.store_id:
            raise HTTPException(status_code=400, detail="네이버 스토어 ID가 설정되지 않았습니다.")

        # 이미 진행 중인 태스크 확인
        if store.scraping_status == 'in_progress':
            # 진행 중인 태스크 찾기
            active_task = db.query(ScrapingTask).filter(
                ScrapingTask.store_id == request.store_id,
                ScrapingTask.status.in_(['pending', 'started'])
            ).first()

            if active_task:
                return ScrapingResponse(
                    task_id=active_task.task_id,
                    status="already_running",
                    message="이미 스크래핑이 진행 중입니다."
                )

        # 새 스크래핑 태스크 시작
        task = scrape_store_data.delay(request.store_id)

        logger.info(f"매장 {request.store_id} 스크래핑 시작: {task.id}")

        return ScrapingResponse(
            task_id=task.id,
            status="started",
            message="스크래핑이 시작되었습니다."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스크래핑 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/scraping/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """태스크 상태 조회 API"""
    try:
        # Celery 태스크 상태 조회
        task = celery.AsyncResult(task_id)

        response = TaskStatusResponse(
            task_id=task_id,
            status=task.status.lower() if task.status else "unknown"
        )

        if task.state == 'PENDING':
            response.status = "pending"
        elif task.state == 'PROGRESS':
            response.status = "in_progress"
            if task.info:
                response.progress = task.info.get('progress', 0)
        elif task.state == 'SUCCESS':
            response.status = "completed"
            response.result = task.result
        elif task.state == 'FAILURE':
            response.status = "failed"
            response.error = str(task.info)

        return response

    except Exception as e:
        logger.error(f"태스크 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scraping/store/{store_id}", response_model=StoreDataResponse)
async def get_store_data(store_id: int):
    """매장 스크래핑 데이터 조회 API"""
    try:
        db = SessionLocal()

        # 매장 정보 조회
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        # 메뉴 개수 조회
        menu_count = db.query(Menu).filter(Menu.store_id == store_id).count()

        # 리뷰 개수 조회
        review_count = db.query(Review).filter(Review.store_id == store_id).count()

        # 매장 정보 구성
        store_info = {
            "id": store.id,
            "store_name": store.store_name,
            "store_address": store.store_address,
            "business_number": store.business_number,
            "owner_name": store.owner_name,
            "owner_phone": store.owner_phone,
            "naver_store_url": store.naver_store_url,
            "store_id": store.store_id,

            # 스크래핑된 정보
            "scraped_store_name": store.scraped_store_name,
            "scraped_category": store.scraped_category,
            "scraped_description": store.scraped_description,
            "scraped_store_address": store.scraped_store_address,
            "scraped_directions": store.scraped_directions,
            "scraped_phone": store.scraped_phone,
            "scraped_sns": store.scraped_sns,
            "scraped_etc_info": store.scraped_etc_info,
            "scraped_intro": store.scraped_intro,
            "scraped_services": store.scraped_services,

            "created_at": store.created_at,
            "updated_at": store.updated_at
        }

        return StoreDataResponse(
            store_info=store_info,
            menu_count=menu_count,
            review_count=review_count,
            scraping_status=store.scraping_status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"매장 데이터 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/scraping/store/{store_id}/menus")
async def get_store_menus(store_id: int, skip: int = 0, limit: int = 100):
    """매장 메뉴 목록 조회 API"""
    try:
        db = SessionLocal()

        # 매장 존재 확인
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        # 메뉴 목록 조회
        menus = db.query(Menu).filter(Menu.store_id == store_id).offset(skip).limit(limit).all()

        menu_list = []
        for menu in menus:
            menu_data = {
                "id": menu.id,
                "menu_name": menu.menu_name,
                "price": menu.price,
                "description": menu.description,
                "recommendation": menu.recommendation,
                "image_url": menu.image_file_path.replace('/app/media', '/media') if menu.image_file_path else None,
                "created_at": menu.created_at
            }
            menu_list.append(menu_data)

        return {
            "store_id": store_id,
            "menus": menu_list,
            "total": db.query(Menu).filter(Menu.store_id == store_id).count()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"메뉴 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/scraping/store/{store_id}/reviews")
async def get_store_reviews(store_id: int, skip: int = 0, limit: int = 50):
    """매장 리뷰 목록 조회 API"""
    try:
        db = SessionLocal()

        # 매장 존재 확인
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        # 리뷰 목록 조회 (최신순)
        reviews = db.query(Review).filter(Review.store_id == store_id).order_by(Review.id.desc()).offset(skip).limit(limit).all()

        review_list = []
        for review in reviews:
            review_data = {
                "id": review.id,
                "content": review.content,
                "review_date": review.review_date,
                "revisit_count": review.revisit_count,
                "created_at": review.created_at
            }
            review_list.append(review_data)

        return {
            "store_id": store_id,
            "reviews": review_list,
            "total": db.query(Review).filter(Review.store_id == store_id).count()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.delete("/api/scraping/store/{store_id}")
async def delete_store_data(store_id: int):
    """매장 스크래핑 데이터 삭제 API"""
    try:
        db = SessionLocal()

        # 매장 존재 확인
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        # 스크래핑된 데이터만 삭제 (사용자 입력 정보는 유지)
        store.scraped_store_name = None
        store.scraped_category = None
        store.scraped_description = None
        store.scraped_store_address = None
        store.scraped_directions = None
        store.scraped_phone = None
        store.scraped_sns = None
        store.scraped_etc_info = None
        store.scraped_intro = None
        store.scraped_services = None
        store.scraping_status = 'pending'
        store.scraping_error_message = None

        # 메뉴와 리뷰 삭제
        db.query(Menu).filter(Menu.store_id == store_id).delete()
        db.query(Review).filter(Review.store_id == store_id).delete()
        db.query(ScrapingTask).filter(ScrapingTask.store_id == store_id).delete()

        db.commit()

        return {"message": "매장 스크래핑 데이터가 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"매장 데이터 삭제 오류: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/scraping/store/{store_id}/summary")
async def get_review_summary(store_id: int):
    """매장 리뷰 요약 조회 API"""
    try:
        db = SessionLocal()

        # 매장 존재 확인
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        # 리뷰 요약 조회
        summary = db.query(ReviewSummary).filter(ReviewSummary.store_id == store_id).first()

        if not summary:
            # 요약이 없으면 리뷰 개수 확인
            review_count = db.query(Review).filter(Review.store_id == store_id).count()
            if review_count == 0:
                return {
                    "store_id": store_id,
                    "summary": "아직 리뷰가 없어 요약을 생성할 수 없습니다.",
                    "status": "no_reviews"
                }
            else:
                return {
                    "store_id": store_id,
                    "summary": "요약이 아직 생성되지 않았습니다. 스크래핑 완료 후 자동으로 생성됩니다.",
                    "status": "pending"
                }

        return {
            "store_id": store_id,
            "summary": summary.summary_md,
            "created_at": summary.created_at,
            "status": "completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 요약 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/scraping/store/{store_id}/summary/regenerate")
async def regenerate_review_summary(store_id: int):
    """리뷰 요약 재생성 API"""
    try:
        from tasks.scraping_tasks import generate_review_summary

        db = SessionLocal()

        # 매장 존재 확인
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

        # 리뷰 개수 확인
        review_count = db.query(Review).filter(Review.store_id == store_id).count()
        if review_count == 0:
            raise HTTPException(status_code=400, detail="리뷰가 없어 요약을 생성할 수 없습니다.")

        # 요약 재생성 태스크 시작
        task = generate_review_summary.delay(store_id)

        return {
            "task_id": task.id,
            "message": "리뷰 요약 재생성이 시작되었습니다.",
            "store_id": store_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 요약 재생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/scraping/tasks")
async def get_active_tasks():
    """진행 중인 태스크 목록 조회"""
    try:
        # Celery에서 활성 태스크 조회
        inspect = celery.control.inspect()
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()

        result = {
            "active_tasks": active_tasks or {},
            "scheduled_tasks": scheduled_tasks or {}
        }

        return result

    except Exception as e:
        logger.error(f"활성 태스크 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)