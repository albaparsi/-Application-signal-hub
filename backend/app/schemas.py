from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ApplicationSource, ApplicationStatus


class ApplicationCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=255)
    status: ApplicationStatus = ApplicationStatus.SAVED
    source: ApplicationSource = ApplicationSource.MANUAL
    applied_date: date | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    """All fields optional — PATCH semantics. Any provided field is applied;
    status changes are diffed against current status to produce a timeline
    event + audit log entry in the CRUD layer."""

    company: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=255)
    status: ApplicationStatus | None = None
    applied_date: date | None = None
    notes: str | None = None


class ApplicationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    from_status: str | None
    to_status: str | None
    description: str | None
    source: str
    created_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company: str
    role: str
    url: str | None
    location: str | None
    status: str
    source: str
    applied_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetailRead(ApplicationRead):
    events: list[ApplicationEventRead] = []


class ApplicationListResponse(BaseModel):
    items: list[ApplicationRead]
    total: int
    limit: int
    offset: int
