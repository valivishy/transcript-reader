from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class Channel(BaseModel):
    id: str
    name: str
    slug: str
    language: str = "en"
    max_duration: int | None = None

    @field_validator("id")
    @classmethod
    def validate_channel_id(cls, v: str) -> str:
        if not v.startswith("UC") or len(v) != 24:
            raise ValueError(f"Invalid channel ID format: {v} (must be UC + 22 chars)")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", v):
            raise ValueError(f"Invalid slug: {v} (must be lowercase alphanumeric + hyphens)")
        return v


class ChannelsConfig(BaseModel):
    channels: list[Channel]

    @field_validator("channels")
    @classmethod
    def validate_unique_slugs(cls, v: list[Channel]) -> list[Channel]:
        slugs = [c.slug for c in v]
        if len(slugs) != len(set(slugs)):
            duplicates = [s for s in slugs if slugs.count(s) > 1]
            raise ValueError(f"Duplicate channel slugs: {set(duplicates)}")
        return v


def load_config(config_path: Path) -> ChannelsConfig:
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return ChannelsConfig.model_validate(data)
