import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.auth import router as auth_router
from .api.kb import router as kb_router
from .api.routes import router as api_router
from .api.slack_webhook import router as slack_router
from .api.users import router as users_router
from .services.scheduler import poll_emails_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_emails_loop())
    logging.getLogger(__name__).info("Mailki Email Agent started")
    yield
    task.cancel()
    logging.getLogger(__name__).info("Mailki Email Agent stopped")


app = FastAPI(title="Mailki Email Agent", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(slack_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(kb_router, prefix="/api")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
