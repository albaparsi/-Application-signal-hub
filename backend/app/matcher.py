"""Match a recruiting email to an existing application — conservatively.

Two-step process:
1. Infer a company name "hint" from the email (sender domain, or subject
   line if the domain belongs to a shared ATS provider like Greenhouse).
2. Look for existing applications whose company name corresponds to that
   hint. If exactly one matches, that's a match. Zero or more-than-one
   means we do NOT guess — the email is stored as unmatched/ambiguous for
   manual review instead of silently updating the wrong application.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MatchStatus
from app.models import Application

# Domains shared across many companies' hiring pipelines — the domain
# itself tells us nothing about which company sent the email, so we fall
# back to parsing the subject line instead.
_SHARED_ATS_DOMAINS = {
    "greenhouse.io",
    "lever.co",
    "myworkday.com",
    "icims.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "jobvite.com",
    "bamboohr.com",
    "workable.com",
}

# Subject-line patterns like "Your application to Acme Corp" or
# "Update from Acme Corp Careers". Kept intentionally simple/explicit.
_SUBJECT_PATTERNS = [
    re.compile(r"application (?:to|with|at) ([A-Z][\w&.,' -]{1,60})", re.IGNORECASE),
    re.compile(r"\bat ([A-Z][\w&.,' -]{1,60})$", re.IGNORECASE),
    re.compile(r"^([A-Z][\w&.,' -]{1,60}) (?:careers|recruiting|talent team)", re.IGNORECASE),
    re.compile(r"from the ([A-Z][\w&.,' -]{1,60}) team", re.IGNORECASE),
]

_COMPANY_SUFFIXES = {"inc", "llc", "corp", "corporation", "co", "ltd", "gmbh", "plc"}


def normalize_company_name(name: str) -> str:
    """Lowercase, strip punctuation and common legal suffixes, collapse
    whitespace — so 'Acme Corp.' and 'acme' compare equal."""
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t for t in cleaned.split() if t not in _COMPANY_SUFFIXES]
    return " ".join(tokens).strip()


def extract_company_hint(from_address: str, subject: str) -> str | None:
    domain = from_address.split("@")[-1].lower().strip()
    # Strip a leading mail subdomain like "jobs." or "careers.".
    domain_parts = domain.split(".")
    registrable = ".".join(domain_parts[-2:]) if len(domain_parts) >= 2 else domain

    if registrable not in _SHARED_ATS_DOMAINS:
        # e.g. "no-reply@acme.com" -> "acme"
        base = domain_parts[-2] if len(domain_parts) >= 2 else domain_parts[0]
        return base

    for pattern in _SUBJECT_PATTERNS:
        match = pattern.search(subject)
        if match:
            return match.group(1).strip()

    return None


@dataclass
class MatchResult:
    status: MatchStatus
    application: Application | None = None
    candidate_ids: list[str] = field(default_factory=list)
    company_hint: str | None = None


def match_application(db: Session, company_hint: str | None) -> MatchResult:
    if not company_hint:
        return MatchResult(status=MatchStatus.UNMATCHED, company_hint=company_hint)

    normalized_hint = normalize_company_name(company_hint)
    if not normalized_hint:
        return MatchResult(status=MatchStatus.UNMATCHED, company_hint=company_hint)

    candidates = db.execute(select(Application)).scalars().all()
    matches = [
        app
        for app in candidates
        if normalize_company_name(app.company) == normalized_hint
    ]

    if len(matches) == 1:
        return MatchResult(
            status=MatchStatus.MATCHED, application=matches[0], company_hint=company_hint
        )
    if len(matches) == 0:
        return MatchResult(status=MatchStatus.UNMATCHED, company_hint=company_hint)

    return MatchResult(
        status=MatchStatus.AMBIGUOUS,
        candidate_ids=[a.id for a in matches],
        company_hint=company_hint,
    )
