from app.enums import ApplicationStatus

# Which statuses a given status is allowed to move to directly.
# Real job searches aren't perfectly linear (e.g. a "screen" can be skipped,
# an "interview" can loop back into itself for multiple rounds), so this is
# intentionally permissive about forward/lateral movement while still
# blocking nonsensical jumps and locking terminal states.
ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.SAVED: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.SCREEN,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.SCREEN: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.INTERVIEW,  # additional interview rounds
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OFFER: {
        ApplicationStatus.REJECTED,  # offer rescinded
        ApplicationStatus.WITHDRAWN,  # candidate declines
    },
    # Terminal states: no outgoing transitions without force=True.
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}

TERMINAL_STATUSES: set[ApplicationStatus] = {
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}


class InvalidTransitionError(Exception):
    """Raised when a status change isn't allowed by the transition graph
    and the caller didn't pass force=True to override it."""

    def __init__(self, from_status: ApplicationStatus, to_status: ApplicationStatus):
        self.from_status = from_status
        self.to_status = to_status
        allowed = sorted(s.value for s in ALLOWED_TRANSITIONS.get(from_status, set()))
        super().__init__(
            f"Cannot move from '{from_status.value}' to '{to_status.value}'. "
            f"Allowed next statuses: {allowed or 'none (terminal state)'}. "
            f"Pass force=true to override."
        )


def validate_transition(
    from_status: ApplicationStatus, to_status: ApplicationStatus, force: bool = False
) -> None:
    if from_status == to_status:
        return  # no-op, handled separately by the caller
    if force:
        return
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise InvalidTransitionError(from_status, to_status)
