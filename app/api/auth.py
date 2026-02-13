from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Mailbox
from app.services.gmail import exchange_code, get_auth_url

router = APIRouter()


def _redirect_uri(request: Request) -> str:
    """Build callback URI, respecting X-Forwarded-Proto from reverse proxy."""
    url = str(request.url_for("google_callback"))
    url = url.replace("://localhost", "://127.0.0.1")
    # Behind Traefik/reverse proxy: force https if X-Forwarded-Proto says so
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto == "https" and url.startswith("http://"):
        url = "https://" + url[7:]
    return url


@router.get("/auth/google")
def google_login(request: Request, mailbox_id: str = Query(...)):
    redirect_uri = _redirect_uri(request)
    auth_url = get_auth_url(redirect_uri, state=mailbox_id)
    return RedirectResponse(auth_url)


@router.get("/auth/google/callback")
def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    redirect_uri = _redirect_uri(request)
    mailbox_id = state
    exchange_code(code, redirect_uri, mailbox_id)

    mailbox = db.query(Mailbox).filter_by(id=mailbox_id).first()
    if mailbox:
        mailbox.credentials_ref = f"token://{mailbox_id}"
        db.commit()

    return RedirectResponse("/?connected=1")
