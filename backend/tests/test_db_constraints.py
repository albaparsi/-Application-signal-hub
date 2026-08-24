from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import DataError, IntegrityError

from app.models import Application, ApplicationEvent, EmailEvent, Proposal


def _make_application(**overrides):
    defaults = {"company": "Acme", "role": "SWE", "status": "applied", "source": "manual"}
    defaults.update(overrides)
    return Application(**defaults)


def test_application_status_check_constraint(db_session):
    db_session.add(_make_application(status="not_a_real_status"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_application_source_check_constraint(db_session):
    db_session.add(_make_application(source="not_a_real_source"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_application_event_to_status_check_constraint(db_session):
    app = _make_application()
    db_session.add(app)
    db_session.commit()

    db_session.add(
        ApplicationEvent(
            application_id=app.id,
            event_type="status_change",
            to_status="not_a_real_status",
            source="manual",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_application_event_allows_null_from_status(db_session):
    """NULL is valid for from_status (e.g. the initial 'created' event) —
    the constraint should only reject non-null invalid values."""
    app = _make_application()
    db_session.add(app)
    db_session.commit()

    db_session.add(
        ApplicationEvent(
            application_id=app.id,
            event_type="created",
            from_status=None,
            to_status="applied",
            source="manual",
        )
    )
    db_session.commit()  # should not raise


def test_email_event_confidence_range_constraint(db_session):
    db_session.add(
        EmailEvent(
            message_id="m1",
            from_address="a@b.com",
            subject="s",
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            signal_type="confirmation",
            classification_confidence=1.5,  # out of range
            match_status="unmatched",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_email_event_signal_type_constraint(db_session):
    db_session.add(
        EmailEvent(
            message_id="m2",
            from_address="a@b.com",
            subject="s",
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            signal_type="not_a_real_signal",
            match_status="unmatched",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_email_event_match_status_constraint(db_session):
    db_session.add(
        EmailEvent(
            message_id="m3",
            from_address="a@b.com",
            subject="s",
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            signal_type="confirmation",
            match_status="not_a_real_match_status",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_email_event_body_excerpt_length_constraint(db_session):
    db_session.add(
        EmailEvent(
            message_id="m4",
            from_address="a@b.com",
            subject="s",
            body_excerpt="x" * 301,  # exceeds the 300-char cap
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            signal_type="confirmation",
            match_status="unmatched",
        )
    )
    # Postgres enforces this two ways depending on which check trips first:
    # the VARCHAR(300) column type itself (raises DataError) or, if that
    # weren't there, our explicit CHECK constraint (IntegrityError). Both
    # are "the database rejected this" — either is a correct outcome here.
    with pytest.raises((IntegrityError, DataError)):
        db_session.commit()


def test_email_event_duplicate_message_id_constraint(db_session):
    db_session.add(
        EmailEvent(
            message_id="dup",
            from_address="a@b.com",
            subject="s",
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            signal_type="confirmation",
            match_status="unmatched",
        )
    )
    db_session.commit()

    db_session.add(
        EmailEvent(
            message_id="dup",
            from_address="c@d.com",
            subject="s2",
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            signal_type="confirmation",
            match_status="unmatched",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def _make_email_event(db_session, message_id="m-proposal"):
    event = EmailEvent(
        message_id=message_id,
        from_address="a@b.com",
        subject="s",
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        signal_type="confirmation",
        match_status="matched",
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_proposal_status_check_constraint(db_session):
    app = _make_application()
    db_session.add(app)
    db_session.commit()
    event = _make_email_event(db_session)

    db_session.add(
        Proposal(
            application_id=app.id,
            email_event_id=event.id,
            proposed_status="applied",
            status_at_proposal="saved",
            confidence=0.8,
            status="not_a_real_proposal_status",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_proposal_confidence_range_constraint(db_session):
    app = _make_application()
    db_session.add(app)
    db_session.commit()
    event = _make_email_event(db_session)

    db_session.add(
        Proposal(
            application_id=app.id,
            email_event_id=event.id,
            proposed_status="applied",
            status_at_proposal="saved",
            confidence=-0.1,
            status="pending",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_proposal_proposed_status_check_constraint(db_session):
    app = _make_application()
    db_session.add(app)
    db_session.commit()
    event = _make_email_event(db_session)

    db_session.add(
        Proposal(
            application_id=app.id,
            email_event_id=event.id,
            proposed_status="not_a_real_status",
            status_at_proposal="saved",
            confidence=0.8,
            status="pending",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_proposal_duplicate_email_event_constraint(db_session):
    app = _make_application()
    db_session.add(app)
    db_session.commit()
    event = _make_email_event(db_session)

    db_session.add(
        Proposal(
            application_id=app.id,
            email_event_id=event.id,
            proposed_status="applied",
            status_at_proposal="saved",
            confidence=0.8,
            status="pending",
        )
    )
    db_session.commit()

    db_session.add(
        Proposal(
            application_id=app.id,
            email_event_id=event.id,  # same email event again
            proposed_status="interview",
            status_at_proposal="applied",
            confidence=0.8,
            status="pending",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
