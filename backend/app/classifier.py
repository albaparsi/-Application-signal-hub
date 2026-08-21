"""Deterministic classification of recruiting emails into signal types.

Design choice: this is intentionally rule-based (keyword/phrase matching),
not ML-based. For an MVP that proposes state changes to a user's job
applications, predictable and explainable behavior matters more than
recall — every classification comes with the exact phrase that triggered
it, so the user (and we, debugging) can see *why*.

Priority matters: some phrases could plausibly appear in more than one
category ("we will not be moving forward with your interview" contains
"interview" but is a rejection). Categories are checked in order of
specificity/reliability: OFFER and REJECTION signals are rarely ambiguous
and are checked first; INTERVIEW and CONFIRMATION are checked after and
are more permissive.
"""

from dataclasses import dataclass, field

from app.enums import EmailSignalType

# Order matters — first category with a match wins.
_RULES: list[tuple[EmailSignalType, list[str]]] = [
    (
        EmailSignalType.OFFER,
        [
            "pleased to offer you",
            "pleased to extend an offer",
            "job offer",
            "offer letter",
            "excited to offer you",
            "formal offer",
            "extend an offer of employment",
        ],
    ),
    (
        EmailSignalType.REJECTION,
        [
            "will not be moving forward",
            "decided not to move forward",
            "will not be moving on to the next",
            "not moving forward with your application",
            "other candidates whose",
            "pursue other candidates",
            "not be proceeding with your application",
            "unfortunately",
            "regret to inform",
            "we have decided to move forward with other candidates",
        ],
    ),
    (
        EmailSignalType.INTERVIEW,
        [
            "schedule an interview",
            "invite you to interview",
            "interview invitation",
            "would like to interview you",
            "next step is an interview",
            "phone screen",
            "schedule a call",
            "schedule some time to chat",
            "move you forward to the interview",
        ],
    ),
    (
        EmailSignalType.CONFIRMATION,
        [
            "application received",
            "thank you for applying",
            "we have received your application",
            "thanks for your application",
            "successfully submitted",
            "confirming your application",
        ],
    ),
]


@dataclass
class ClassificationResult:
    signal_type: EmailSignalType
    confidence: float
    matched_phrases: list[str] = field(default_factory=list)


def classify_email(subject: str, body: str) -> ClassificationResult:
    haystack = f"{subject}\n{body}".lower()

    for signal_type, phrases in _RULES:
        matched = [p for p in phrases if p in haystack]
        if matched:
            # Confidence scales modestly with number of corroborating phrases,
            # capped at 0.95 — deterministic rules should never claim certainty.
            confidence = min(0.6 + 0.1 * (len(matched) - 1), 0.95)
            return ClassificationResult(
                signal_type=signal_type, confidence=confidence, matched_phrases=matched
            )

    return ClassificationResult(signal_type=EmailSignalType.UNKNOWN, confidence=0.0)
