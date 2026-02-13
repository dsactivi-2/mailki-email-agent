from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Mailbox
from app.services.gmail import exchange_code, get_auth_url

router = APIRouter()


def _redirect_uri(request: Request) -> str:
    """Build callback URI using 127.0.0.1 instead of localhost for Google OAuth."""
    url = str(request.url_for("google_callback"))
    return url.replace("://localhost", "://127.0.0.1")


@router.get("/auth/google")
def google_login(request: Request, mailbox_id: str = Query(...)):
    redirect_uri = _redirect_uri(request)
    auth_url = get_auth_url(redirect_uri)
    return RedirectResponse(auth_url + f"&state={mailbox_id}")


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
