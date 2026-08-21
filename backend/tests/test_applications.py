from app.models import AuditLog


def create_sample_application(client, **overrides):
    payload = {
        "company": "Acme Corp",
        "role": "Software Engineer",
        "url": "https://acme.example.com/jobs/123",
        "location": "Remote",
        "status": "applied",
        "source": "manual",
    }
    payload.update(overrides)
    return client.post("/applications", json=payload)


def test_create_application(client):
    resp = create_sample_application(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["company"] == "Acme Corp"
    assert body["role"] == "Software Engineer"
    assert body["status"] == "applied"
    assert "id" in body


def test_create_application_writes_timeline_and_audit(client, db_session):
    resp = create_sample_application(client)
    app_id = resp.json()["id"]

    detail = client.get(f"/applications/{app_id}").json()
    assert len(detail["events"]) == 1
    assert detail["events"][0]["event_type"] == "created"

    audit_rows = db_session.query(AuditLog).filter_by(application_id=app_id).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "application_created"


def test_get_application_not_found(client):
    resp = client.get("/applications/does-not-exist")
    assert resp.status_code == 404


def test_list_applications_with_filters(client):
    create_sample_application(client, company="Acme Corp", role="Backend Engineer")
    create_sample_application(client, company="Globex", role="Frontend Engineer", status="saved")

    resp = client.get("/applications", params={"status": "saved"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["company"] == "Globex"

    resp = client.get("/applications", params={"q": "backend"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["role"] == "Backend Engineer"

    resp = client.get("/applications", params={"company": "acme"})
    body = resp.json()
    assert body["total"] == 1


def test_update_status_creates_timeline_event_and_audit(client, db_session):
    resp = create_sample_application(client, status="applied")
    app_id = resp.json()["id"]

    resp = client.patch(f"/applications/{app_id}", json={"status": "interview"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "interview"

    detail = client.get(f"/applications/{app_id}").json()
    event_types = [e["event_type"] for e in detail["events"]]
    assert "status_change" in event_types

    status_event = next(e for e in detail["events"] if e["event_type"] == "status_change")
    assert status_event["from_status"] == "applied"
    assert status_event["to_status"] == "interview"

    audit_rows = (
        db_session.query(AuditLog)
        .filter_by(application_id=app_id, action="status_changed")
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].details == {"from": "applied", "to": "interview"}


def test_update_status_noop_does_not_duplicate_events(client):
    resp = create_sample_application(client, status="applied")
    app_id = resp.json()["id"]

    # Setting the same status should not create a spurious status_change event.
    client.patch(f"/applications/{app_id}", json={"status": "applied"})

    detail = client.get(f"/applications/{app_id}").json()
    status_changes = [e for e in detail["events"] if e["event_type"] == "status_change"]
    assert len(status_changes) == 0


def test_update_field_only(client):
    resp = create_sample_application(client)
    app_id = resp.json()["id"]

    resp = client.patch(f"/applications/{app_id}", json={"notes": "Recruiter seemed excited"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Recruiter seemed excited"


def test_delete_application(client, db_session):
    resp = create_sample_application(client)
    app_id = resp.json()["id"]

    resp = client.delete(f"/applications/{app_id}")
    assert resp.status_code == 204

    resp = client.get(f"/applications/{app_id}")
    assert resp.status_code == 404

    # Audit row for the deletion should persist even though the application is gone.
    audit_rows = db_session.query(AuditLog).filter_by(action="application_deleted").all()
    assert len(audit_rows) == 1


def test_invalid_transition_rejected(client):
    resp = create_sample_application(client, status="saved")
    app_id = resp.json()["id"]

    # saved -> offer is not an allowed direct transition
    resp = client.patch(f"/applications/{app_id}", json={"status": "offer"})
    assert resp.status_code == 409
    assert "saved" in resp.json()["detail"]
    assert "offer" in resp.json()["detail"]

    # status should be unchanged
    detail = client.get(f"/applications/{app_id}").json()
    assert detail["status"] == "saved"


def test_invalid_transition_with_force_succeeds(client):
    resp = create_sample_application(client, status="saved")
    app_id = resp.json()["id"]

    resp = client.patch(f"/applications/{app_id}?force=true", json={"status": "offer"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "offer"


def test_terminal_state_locked(client):
    resp = create_sample_application(client, status="applied")
    app_id = resp.json()["id"]

    client.patch(f"/applications/{app_id}", json={"status": "rejected"})

    resp = client.patch(f"/applications/{app_id}", json={"status": "interview"})
    assert resp.status_code == 409

    detail = client.get(f"/applications/{app_id}").json()
    assert detail["status"] == "rejected"


def test_valid_transition_chain(client):
    resp = create_sample_application(client, status="saved")
    app_id = resp.json()["id"]

    for target in ["applied", "screen", "interview", "offer"]:
        resp = client.patch(f"/applications/{app_id}", json={"status": target})
        assert resp.status_code == 200, f"failed moving to {target}: {resp.json()}"
        assert resp.json()["status"] == target


def test_interview_can_loop_to_itself(client):
    resp = create_sample_application(client, status="interview")
    app_id = resp.json()["id"]

    resp = client.patch(f"/applications/{app_id}", json={"status": "interview"})
    assert resp.status_code == 200


def test_rejected_field_update_still_blocked_from_invalid_status(client, db_session):
    """An invalid status transition should roll back any other field changes
    sent in the same PATCH request, not partially apply them."""
    resp = create_sample_application(client, status="saved")
    app_id = resp.json()["id"]

    resp = client.patch(
        f"/applications/{app_id}",
        json={"status": "offer", "notes": "should not be saved"},
    )
    assert resp.status_code == 409

    detail = client.get(f"/applications/{app_id}").json()
    assert detail["notes"] is None


def test_multi_status_filter(client):
    create_sample_application(client, company="A", status="saved")
    create_sample_application(client, company="B", status="applied")
    create_sample_application(client, company="C", status="offer")

    resp = client.get("/applications", params=[("status", "saved"), ("status", "applied")])
    body = resp.json()
    assert body["total"] == 2
    companies = {item["company"] for item in body["items"]}
    assert companies == {"A", "B"}


def test_sorting(client):
    create_sample_application(client, company="Zeta", role="Engineer")
    create_sample_application(client, company="Alpha", role="Engineer")

    resp = client.get(
        "/applications", params={"sort_by": "company", "sort_dir": "asc"}
    )
    companies = [item["company"] for item in resp.json()["items"]]
    assert companies == ["Alpha", "Zeta"]

    resp = client.get(
        "/applications", params={"sort_by": "company", "sort_dir": "desc"}
    )
    companies = [item["company"] for item in resp.json()["items"]]
    assert companies == ["Zeta", "Alpha"]


def test_applied_date_range_filter(client):
    create_sample_application(client, company="Early", applied_date="2026-01-01")
    create_sample_application(client, company="Late", applied_date="2026-06-01")

    resp = client.get(
        "/applications",
        params={"applied_date_from": "2026-03-01", "applied_date_to": "2026-12-31"},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["company"] == "Late"


def test_pagination(client):
    for i in range(5):
        create_sample_application(client, role=f"Engineer {i}")

    resp = client.get("/applications", params={"limit": 2, "offset": 0})
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2

    resp = client.get("/applications", params={"limit": 2, "offset": 4})
    body = resp.json()
    assert len(body["items"]) == 1
