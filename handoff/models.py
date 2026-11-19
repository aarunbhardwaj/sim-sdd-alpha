"""Request and response shapes. Persistence behavior lands in later tasks."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "critical"]


class HandoffCreate(BaseModel):
    author_id: str = Field(min_length=1, max_length=80)
    severity: Severity
    summary: str = Field(min_length=1, max_length=500)


class Handoff(BaseModel):
    id: str
    author_id: str
    created_at: datetime
    severity: Severity
    summary: str
