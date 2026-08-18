import enum


class ApplicationStatus(str, enum.Enum):
    SAVED = "saved"
    APPLIED = "applied"
    SCREEN = "screen"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationSource(str, enum.Enum):
    MANUAL = "manual"
    EXTENSION = "extension"
    EMAIL = "email"
    SEED = "seed"


class EventType(str, enum.Enum):
    CREATED = "created"
    STATUS_CHANGE = "status_change"
    NOTE_ADDED = "note_added"
    FIELD_UPDATED = "field_updated"


class AuditAction(str, enum.Enum):
    APPLICATION_CREATED = "application_created"
    APPLICATION_UPDATED = "application_updated"
    APPLICATION_DELETED = "application_deleted"
    STATUS_CHANGED = "status_changed"
