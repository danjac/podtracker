from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from radiofeed.feedparser import validators


class Item(BaseModel):
    """Individual item or episode in RSS or Atom podcast feed."""

    guid: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)

    categories: list[str] = Field(default_factory=list)

    description: str = ""
    keywords: str = ""

    pub_date: datetime

    media_url: str
    media_type: str

    cover_url: str | None = None
    website: str | None = None

    explicit: bool = False

    length: int | None = None
    duration: str | None = None

    season: int | None = None
    episode: int | None = None

    episode_type: str = "full"

    @field_validator("media_url", mode="before")
    @classmethod
    def validate_media_url(cls, value: Any) -> str:
        """Validates media url."""
        return validators.required_url(value)

    @field_validator("media_type", mode="after")
    @classmethod
    def validate_media_type(cls, value: Any) -> str:
        """Validates media type."""
        return validators.audio_mimetype(value)

    @field_validator("pub_date", mode="before")
    @classmethod
    def validate_pub_date(cls, value: Any) -> datetime:
        """Validates pub date."""
        return validators.pub_date(value)

    @field_validator("cover_url", mode="after")
    @classmethod
    def validate_cover_url(cls, value: Any) -> str | None:
        """Validates cover url."""
        return validators.url(value)

    @field_validator("website", mode="after")
    @classmethod
    def validate_website(cls, value: Any) -> str | None:
        """Validates website."""
        return validators.url(value)

    @field_validator("explicit", mode="before")
    @classmethod
    def validate_explicit(cls, value: Any) -> bool:
        """Validates explicit."""
        return validators.explicit(value)

    @field_validator("duration", mode="after")
    @classmethod
    def validate_duration(cls, value: Any) -> str | None:
        """Validates duration."""
        return validators.duration(value)

    @field_validator("length", mode="after")
    @classmethod
    def validate_length(cls, value: Any) -> int | None:
        """Validates length."""
        return validators.pg_integer(value)

    @field_validator("season", mode="after")
    @classmethod
    def validate_season(cls, value: Any) -> int | None:
        """Validates season."""
        return validators.pg_integer(value)

    @field_validator("episode", mode="after")
    @classmethod
    def validate_episode(cls, value: Any) -> int | None:
        """Validates episode."""
        return validators.pg_integer(value)

    @model_validator(mode="after")
    def validate_keywords(self) -> Item:
        """Set default keywords."""
        self.keywords = " ".join(filter(None, self.categories))
        return self


class Feed(BaseModel):
    """RSS/Atom Feed model."""

    title: str = Field(..., min_length=1)
    owner: str = ""
    description: str = ""

    pub_date: datetime | None = None

    language: str = "en"
    website: str | None = None
    cover_url: str | None = None

    funding_text: str = ""
    funding_url: str | None = None

    explicit: bool = False
    complete: bool = False

    items: list[Item]

    categories: list[str] = Field(default_factory=list)

    @field_validator("explicit", mode="before")
    @classmethod
    def validate_explicit(cls, value: Any) -> bool:
        """Validates explicit."""
        return validators.explicit(value)

    @field_validator("complete", mode="before")
    @classmethod
    def validate_complete(cls, value: Any) -> bool:
        """Validates complete."""
        return validators.complete(value)

    @field_validator("language", mode="after")
    @classmethod
    def validate_language(cls, value: Any) -> str:
        """Validates language."""
        return validators.language(value)

    @field_validator("cover_url", mode="after")
    @classmethod
    def validate_cover_url(cls, value: Any) -> str | None:
        """Validates cover url."""
        return validators.url(value)

    @field_validator("website", mode="after")
    @classmethod
    def validate_website(cls, value: Any) -> str | None:
        """Validates website."""
        return validators.url(value)

    @field_validator("funding_url", mode="after")
    @classmethod
    def validate_funding_url(cls, value: Any) -> str | None:
        """Validates funding url."""
        return validators.url(value)

    @model_validator(mode="after")
    def validate_pub_date(self) -> Feed:
        """Set default pub date based on max items pub date."""
        self.pub_date = max(item.pub_date for item in self.items)
        return self
