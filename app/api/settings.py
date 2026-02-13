import json
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

SETTINGS_FILE = Path("/app/data/settings.json")

# Keys that can be edited via UI
EDITABLE_KEYS = [
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "POLL_INTERVAL_MINUTES",
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "SLACK_APPROVER_USER_ID",
    "SLACK_APPROVAL_CHANNEL",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
]

# Keys whose values should be partially masked in GET responses
SECRET_KEYS = {"OPENAI_API_KEY", "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "GOOGLE_CLIENT_SECRET"}


def _mask(value: str) -> str:
    if not value or len(value) < 8:
        return "***" if value else ""
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def _load_overrides():
    """Load saved settings overrides from disk and apply to settings object."""
    if SETTINGS_FILE.exists():
        try:
            overrides = json.loads(SETTINGS_FILE.read_text())
            for key, val in overrides.items():
                if key in EDITABLE_KEYS and hasattr(settings, key):
                    setattr(settings, key, val)
            logger.info(f"Loaded {len(overrides)} settings overrides from {SETTINGS_FILE}")
        except Exception as e:
            logger.error(f"Failed to load settings overrides: {e}")


# Load overrides on module import (app startup)
_load_overrides()


@router.get("/settings")
def get_settings():
    result = {}
    for key in EDITABLE_KEYS:
        val = getattr(settings, key, "")
        if key in SECRET_KEYS:
            result[key] = {"value": _mask(str(val)), "is_set": bool(val)}
        else:
            result[key] = {"value": str(val), "is_set": bool(val)}
    return result


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


@router.put("/settings")
def update_settings(data: SettingsUpdate):
    updated = []
    for key, val in data.settings.items():
        if key not in EDITABLE_KEYS:
            continue
        if key in SECRET_KEYS and val and set(val) == {"*"}:
            continue  # Skip masked-only values (user didn't change it)
        if hasattr(settings, key):
            # Convert types as needed
            if key == "POLL_INTERVAL_MINUTES":
                setattr(settings, key, int(val))
            else:
                setattr(settings, key, val)
            updated.append(key)

    # Persist to disk
    try:
        existing = {}
        if SETTINGS_FILE.exists():
            existing = json.loads(SETTINGS_FILE.read_text())
        for key in updated:
            existing[key] = getattr(settings, key)
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(existing, indent=2, default=str))
    except Exception as e:
        logger.error(f"Failed to persist settings: {e}")

    logger.info(f"Settings updated: {updated}")
    return {"status": "ok", "updated": updated}
