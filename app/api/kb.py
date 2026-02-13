from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import KBCompliance, KBSignature, KBTone, KBVip

router = APIRouter(prefix="/kb")


# --- Signatures ---

class SignatureCreate(BaseModel):
    name: str
    content_html: str
    content_text: str
    language: str = "de"
    is_default: bool = False


@router.post("/signatures")
def create_signature(data: SignatureCreate, db: Session = Depends(get_db)):
    sig = KBSignature(**data.model_dump())
    if data.is_default:
        db.query(KBSignature).filter_by(language=data.language, is_default=True).update(
            {"is_default": False}
        )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return {"id": str(sig.id), "name": sig.name, "is_default": sig.is_default}


@router.get("/signatures")
def list_signatures(db: Session = Depends(get_db)):
    sigs = db.query(KBSignature).all()
    return [
        {"id": str(s.id), "name": s.name, "language": s.language, "is_default": s.is_default}
        for s in sigs
    ]


# --- Tones ---

class ToneCreate(BaseModel):
    name: str
    description: str = ""
    prompt_template: str
    is_default: bool = False


@router.post("/tones")
def create_tone(data: ToneCreate, db: Session = Depends(get_db)):
    tone = KBTone(**data.model_dump())
    if data.is_default:
        db.query(KBTone).filter_by(is_default=True).update({"is_default": False})
    db.add(tone)
    db.commit()
    db.refresh(tone)
    return {"id": str(tone.id), "name": tone.name, "is_default": tone.is_default}


@router.get("/tones")
def list_tones(db: Session = Depends(get_db)):
    tones = db.query(KBTone).all()
    return [
        {"id": str(t.id), "name": t.name, "description": t.description, "is_default": t.is_default}
        for t in tones
    ]


# --- VIPs ---

class VipCreate(BaseModel):
    email_pattern: str
    name: str = ""
    priority: str = "high"
    special_instructions: str = ""


@router.post("/vips")
def create_vip(data: VipCreate, db: Session = Depends(get_db)):
    vip = KBVip(**data.model_dump())
    db.add(vip)
    db.commit()
    db.refresh(vip)
    return {"id": str(vip.id), "email_pattern": vip.email_pattern, "name": vip.name}


@router.get("/vips")
def list_vips(db: Session = Depends(get_db)):
    vips = db.query(KBVip).all()
    return [
        {
            "id": str(v.id),
            "email_pattern": v.email_pattern,
            "name": v.name,
            "priority": v.priority,
            "special_instructions": v.special_instructions,
        }
        for v in vips
    ]


# --- Compliance ---

class ComplianceCreate(BaseModel):
    rule_name: str
    description: str = ""
    pattern: str = ""
    action: str = "flag"
    is_active: bool = True


@router.post("/compliance")
def create_compliance(data: ComplianceCreate, db: Session = Depends(get_db)):
    rule = KBCompliance(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": str(rule.id), "rule_name": rule.rule_name, "action": rule.action}


@router.get("/compliance")
def list_compliance(db: Session = Depends(get_db)):
    rules = db.query(KBCompliance).filter_by(is_active=True).all()
    return [
        {
            "id": str(r.id),
            "rule_name": r.rule_name,
            "description": r.description,
            "pattern": r.pattern,
            "action": r.action,
        }
        for r in rules
    ]
