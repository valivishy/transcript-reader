import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


class ChannelState(BaseModel):
    last_checked: str | None = None
    video_ids: list[str] = []


class ScrapeState(BaseModel):
    last_run: str | None = None
    channels: dict[str, ChannelState] = {}


def load_state(state_path: Path) -> ScrapeState:
    if not state_path.exists():
        return ScrapeState()
    try:
        data = json.loads(state_path.read_text())
        return ScrapeState.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return ScrapeState()


def save_state(state: ScrapeState, state_path: Path) -> None:
    state.last_run = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state.model_dump(), indent=2) + "\n")
