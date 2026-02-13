from fastapi import FastAPI

from .api.auth import router as auth_router
from .api.routes import router as api_router
from .api.slack_webhook import router as slack_router

app = FastAPI(title="Mailki Email Agent")


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(slack_router, prefix="/api")
