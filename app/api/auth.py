from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Mailbox
from app.services.gmail import exchange_code, get_auth_url

router = APIRouter()


def _redirect_uri(request: Request) -> str:
    return str(request.url_for("google_callback"))


@router.get("/auth/google")
def google_login(request: Request, mailbox_id: str = Query(...)):
    redirect_uri = _redirect_uri(request)
    auth_url = get_auth_url(redirect_uri)
    return {"auth_url": auth_url + f"&state={mailbox_id}"}


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

    return {"status": "ok", "message": "Gmail connected", "mailbox_id": mailbox_id}
