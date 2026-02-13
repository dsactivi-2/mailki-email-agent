from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Mailbox, User

router = APIRouter()


class UserCreate(BaseModel):
    email: str
    name: str
    role: str = "agent"


class MailboxCreate(BaseModel):
    email_address: str
    provider: str = "gmail"


@router.post("/users")
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(email=data.email, name=data.name, role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).filter_by(is_active=True).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.get("/users/{user_id}")
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "mailboxes": [
            {
                "id": str(m.id),
                "email_address": m.email_address,
                "provider": m.provider,
                "is_active": m.is_active,
                "last_sync_at": m.last_sync_at.isoformat() if m.last_sync_at else None,
            }
            for m in user.mailboxes
        ],
    }


@router.post("/users/{user_id}/mailboxes")
def create_mailbox(user_id: str, data: MailboxCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(Mailbox).filter_by(email_address=data.email_address).first()
    if existing:
        raise HTTPException(status_code=409, detail="Mailbox already exists")
    mailbox = Mailbox(
        user_id=user.id,
        email_address=data.email_address,
        provider=data.provider,
    )
    db.add(mailbox)
    db.commit()
    db.refresh(mailbox)
    return {
        "id": str(mailbox.id),
        "user_id": str(mailbox.user_id),
        "email_address": mailbox.email_address,
        "provider": mailbox.provider,
        "is_active": mailbox.is_active,
        "message": "Now connect Gmail via /api/auth/google?mailbox_id=" + str(mailbox.id),
    }


@router.get("/mailboxes")
def list_mailboxes(db: Session = Depends(get_db)):
    mailboxes = db.query(Mailbox).filter_by(is_active=True).all()
    return [
        {
            "id": str(m.id),
            "user_id": str(m.user_id),
            "email_address": m.email_address,
            "provider": m.provider,
            "is_active": m.is_active,
            "has_credentials": m.credentials_ref is not None,
            "last_sync_at": m.last_sync_at.isoformat() if m.last_sync_at else None,
        }
        for m in mailboxes
    ]
