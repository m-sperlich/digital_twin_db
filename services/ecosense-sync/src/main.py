import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import BackgroundTasks, FastAPI, HTTPException

from .config import settings
from .sync import EcosenseSync

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

sync_service = EcosenseSync()


def scheduled_sync():
    logger.info("Running scheduled sync...")
    try:
        sync_service.sync_all(days_back=settings.DEFAULT_DAYS_BACK)
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scheduled_sync,
        "interval",
        minutes=settings.SYNC_INTERVAL_MINUTES,
        id="ecosense_sync",
    )
    scheduler.start()
    logger.info(
        f"Scheduler started with interval {settings.SYNC_INTERVAL_MINUTES} minutes"
    )

    # Run initial sync on startup
    logger.info("Triggering initial sync on startup...")
    scheduler.add_job(scheduled_sync, "date")

    yield

    # Shutdown
    scheduler.shutdown()


app = FastAPI(title="Ecosense Data Sync Service", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/sync/all")
def trigger_sync_all(background_tasks: BackgroundTasks, days_back: int = 7):
    """Trigger a full sync (metadata + readings)"""
    background_tasks.add_task(sync_service.sync_all, days_back)
    return {"message": "Full sync triggered in background", "days_back": days_back}


@app.post("/sync/metadata")
def trigger_sync_metadata(background_tasks: BackgroundTasks):
    """Trigger metadata sync only"""
    background_tasks.add_task(sync_service.sync_metadata)
    return {"message": "Metadata sync triggered in background"}


@app.post("/sync/readings")
def trigger_sync_readings(
    background_tasks: BackgroundTasks,
    days_back: int = 7,
    sensor_ids: Optional[List[str]] = None,
):
    """Trigger readings sync for specific sensors or all"""
    background_tasks.add_task(sync_service.sync_readings, days_back, sensor_ids)
    return {
        "message": "Readings sync triggered in background",
        "days_back": days_back,
        "sensors": sensor_ids,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
