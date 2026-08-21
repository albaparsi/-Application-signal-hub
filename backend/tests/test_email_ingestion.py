def create_application(client, **overrides):
    payload = {
        "company": "Acme Corp",
        "role": "Software Engineer",
        "status": "applied",
        "source": "manual",
    }
    payload.update(overrides)
    return client.post("/applications", json=payload).json()


def ingest(client, **overrides):
    payload = {
        "message_id": "msg-1",
        "from_address": "no-reply@acme.com",
        "subject": "Your application to Acme",
        "body": "We have received your application and will be in touch soon.",
        "received_at": "2026-01-15T10:00:00Z",
    }
    payload.update(overrides)
    return client.post("/email-events/ingest", json=payload)


def test_confirmation_email_creates_proposal(client):
    application = create_application(client, status="saved")

    resp = ingest(
        client,
        subject="Thank you for applying to Acme Corp",
        body="We have received your application and will follow up soon.",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email_event"]["signal_type"] == "confirmation"
    assert body["email_event"]["match_status"] == "matched"
    assert body["proposal"] is not None
    assert body["proposal"]["proposed_status"] == "applied"
    assert body["proposal"]["application_id"] == application["id"]
    assert body["proposal"]["status"] == "pending"


def test_rejection_email_creates_proposal(client):
    create_application(client, status="interview")

    resp = ingest(
        client,
        message_id="msg-rejection",
        subject="Update on your application at Acme",
        body="Unfortunately, we have decided to move forward with other candidates.",
    )
    body = resp.json()
    assert body["email_event"]["signal_type"] == "rejection"
    assert body["proposal"]["proposed_status"] == "rejected"


def test_unrelated_email_creates_no_proposal(client):
    create_application(client)

    resp = ingest(
        client,
        message_id="msg-newsletter",
        subject="Your weekly newsletter",
        body="Check out this week's top tech articles.",
    )
    body = resp.json()
    assert body["email_event"]["signal_type"] == "unknown"
    assert body["proposal"] is None
    assert "no proposal" in body["message"].lower()


def test_unmatched_company_creates_no_proposal(client):
    create_application(client, company="Acme Corp")

    resp = ingest(
        client,
        message_id="msg-unmatched",
        from_address="no-reply@globex.com",
        subject="Your application to Globex",
        body="We have received your application.",
    )
    body = resp.json()
    assert body["email_event"]["match_status"] == "unmatched"
    assert body["proposal"] is None


def test_ambiguous_company_creates_no_proposal(client):
    create_application(client, company="Acme Corp", role="Backend Engineer")
    create_application(client, company="Acme Corp", role="Frontend Engineer")

    resp = ingest(
        client,
        message_id="msg-ambiguous",
        subject="Your application to Acme",
        body="We have received your application.",
    )
    body = resp.json()
    assert body["email_event"]["match_status"] == "ambiguous"
    assert body["proposal"] is None


def test_duplicate_message_id_is_idempotent(client):
    create_application(client, status="saved")

    first = ingest(client, message_id="msg-dup")
    second = ingest(client, message_id="msg-dup")

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["message"].lower().startswith("duplicate")

    # Only one proposal should exist for this email, no duplicates created.
    proposals = client.get("/proposals").json()
    matching = [p for p in proposals if p["email_event_id"] == first.json()["email_event"]["id"]]
    assert len(matching) == 1


def test_approve_proposal_applies_status_change(client):
    application = create_application(client, status="saved")

    # saved -> applied is a valid transition, so this proposal should approve cleanly.
    resp = ingest(client, message_id="msg-confirm-approve")
    proposal_id = resp.json()["proposal"]["id"]

    approve_resp = client.post(f"/proposals/{proposal_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    updated = client.get(f"/applications/{application['id']}").json()
    assert updated["status"] == "applied"

    events = [e["event_type"] for e in updated["events"]]
    assert "status_change" in events


def test_approve_proposal_respects_transition_rules(client):
    create_application(client, status="saved")

    resp = ingest(
        client,
        message_id="msg-offer-invalid",
        subject="Congratulations from Acme",
        body="We are pleased to offer you the position.",
    )
    proposal_id = resp.json()["proposal"]["id"]

    # saved -> offer directly is not an allowed transition.
    approve_resp = client.post(f"/proposals/{proposal_id}/approve")
    assert approve_resp.status_code == 409

    proposal = client.get(f"/proposals/{proposal_id}").json()
    assert proposal["status"] == "pending"  # left pending, not silently applied


def test_approve_proposal_with_force_overrides_transition_rules(client):
    create_application(client, status="saved")

    resp = ingest(
        client,
        message_id="msg-offer-force",
        subject="Congratulations from Acme",
        body="We are pleased to offer you the position.",
    )
    proposal_id = resp.json()["proposal"]["id"]

    approve_resp = client.post(f"/proposals/{proposal_id}/approve?force=true")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"


def test_reject_proposal_leaves_application_unchanged(client):
    application = create_application(client, status="saved")

    resp = ingest(client, message_id="msg-reject-flow")
    proposal_id = resp.json()["proposal"]["id"]

    reject_resp = client.post(f"/proposals/{proposal_id}/reject", params={"note": "false positive"})
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"
    assert reject_resp.json()["decision_note"] == "false positive"

    unchanged = client.get(f"/applications/{application['id']}").json()
    assert unchanged["status"] == "saved"


def test_cannot_approve_already_decided_proposal(client):
    create_application(client, status="saved")
    resp = ingest(client, message_id="msg-double-approve")
    proposal_id = resp.json()["proposal"]["id"]

    client.post(f"/proposals/{proposal_id}/approve")
    second_attempt = client.post(f"/proposals/{proposal_id}/approve")
    assert second_attempt.status_code == 400


def test_email_event_does_not_store_full_body(client):
    long_body = "word " * 500  # 2500 chars
    resp = ingest(client, message_id="msg-long-body", body=long_body)
    stored_excerpt = resp.json()["email_event"]["body_excerpt"]
    assert len(stored_excerpt) <= 300
    assert len(stored_excerpt) < len(long_body)


def test_list_and_get_email_events(client):
    create_application(client, status="saved")
    resp = ingest(client, message_id="msg-listable")
    event_id = resp.json()["email_event"]["id"]

    listed = client.get("/email-events").json()
    assert any(e["id"] == event_id for e in listed)

    single = client.get(f"/email-events/{event_id}")
    assert single.status_code == 200
    assert single.json()["id"] == event_id


def test_list_proposals_filter_by_status(client):
    create_application(client, status="saved")
    resp = ingest(client, message_id="msg-filter-test")
    proposal_id = resp.json()["proposal"]["id"]

    pending = client.get("/proposals", params={"status": "pending"}).json()
    assert any(p["id"] == proposal_id for p in pending)

    client.post(f"/proposals/{proposal_id}/approve")

    pending_after = client.get("/proposals", params={"status": "pending"}).json()
    assert not any(p["id"] == proposal_id for p in pending_after)

    approved = client.get("/proposals", params={"status": "approved"}).json()
    assert any(p["id"] == proposal_id for p in approved)
