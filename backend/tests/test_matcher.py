from app.enums import MatchStatus
from app.matcher import extract_company_hint, match_application, normalize_company_name
from app.models import Application


def test_normalize_strips_suffixes_and_punctuation():
    assert normalize_company_name("Acme Corp.") == "acme"
    assert normalize_company_name("Acme, Inc.") == "acme"
    assert normalize_company_name("acme") == "acme"


def test_extract_hint_from_direct_company_domain():
    hint = extract_company_hint("no-reply@acme.com", "Your application")
    assert hint == "acme"


def test_extract_hint_from_shared_ats_domain_uses_subject():
    hint = extract_company_hint(
        "no-reply@greenhouse.io", "Thank you for your application to Acme Corp"
    )
    assert hint is not None
    assert "acme" in hint.lower()


def test_extract_hint_returns_none_when_ats_domain_and_subject_unparseable():
    hint = extract_company_hint("no-reply@greenhouse.io", "Update on your candidacy")
    assert hint is None


def test_match_application_single_confident_match(db_session):
    app = Application(company="Acme Corp", role="Software Engineer", status="applied")
    db_session.add(app)
    db_session.commit()

    result = match_application(db_session, "acme")
    assert result.status == MatchStatus.MATCHED
    assert result.application.id == app.id


def test_match_application_no_match(db_session):
    app = Application(company="Acme Corp", role="Software Engineer", status="applied")
    db_session.add(app)
    db_session.commit()

    result = match_application(db_session, "globex")
    assert result.status == MatchStatus.UNMATCHED


def test_match_application_ambiguous_when_multiple_same_company(db_session):
    db_session.add(Application(company="Acme Corp", role="Backend Engineer", status="applied"))
    db_session.add(Application(company="Acme Corp", role="Frontend Engineer", status="applied"))
    db_session.commit()

    result = match_application(db_session, "acme")
    assert result.status == MatchStatus.AMBIGUOUS
    assert len(result.candidate_ids) == 2


def test_match_application_no_hint_is_unmatched(db_session):
    result = match_application(db_session, None)
    assert result.status == MatchStatus.UNMATCHED
