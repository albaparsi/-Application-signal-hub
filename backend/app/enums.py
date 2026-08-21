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


class SortField(str, enum.Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    APPLIED_DATE = "applied_date"
    COMPANY = "company"
    ROLE = "role"


class SortDir(str, enum.Enum):
    ASC = "asc"
    DESC = "desc"


class EmailSignalType(str, enum.Enum):
    CONFIRMATION = "confirmation"
    INTERVIEW = "interview"
    REJECTION = "rejection"
    OFFER = "offer"
    UNKNOWN = "unknown"


# What status a given email signal proposes, when it can be matched to an application.
SIGNAL_TO_STATUS: dict[EmailSignalType, ApplicationStatus] = {
    EmailSignalType.CONFIRMATION: ApplicationStatus.APPLIED,
    EmailSignalType.INTERVIEW: ApplicationStatus.INTERVIEW,
    EmailSignalType.REJECTION: ApplicationStatus.REJECTED,
    EmailSignalType.OFFER: ApplicationStatus.OFFER,
}


class MatchStatus(str, enum.Enum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"  # no confident company match found
    AMBIGUOUS = "ambiguous"  # multiple equally-plausible applications


class ProposalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
