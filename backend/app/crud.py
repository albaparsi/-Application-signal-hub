from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.enums import ApplicationSource, ApplicationStatus, AuditAction, EventType
from app.models import Application, ApplicationEvent, AuditLog
from app.schemas import ApplicationCreate, ApplicationUpdate


def _log_audit(
    db: Session,
    application_id: str | None,
    action: AuditAction,
    details: dict | None = None,
    actor: str = "user",
) -> None:
    db.add(
        AuditLog(
            application_id=application_id,
            actor=actor,
            action=action.value,
            details=details or {},
        )
    )


def create_application(db: Session, data: ApplicationCreate) -> Application:
    application = Application(
        company=data.company.strip(),
        role=data.role.strip(),
        url=data.url,
        location=data.location,
        status=data.status.value,
        source=data.source.value,
        applied_date=data.applied_date,
        notes=data.notes,
    )
    db.add(application)
    db.flush()  # populate application.id before we reference it

    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type=EventType.CREATED.value,
            to_status=application.status,
            description=f"Application created ({data.source.value})",
            source=data.source.value,
        )
    )
    _log_audit(
        db,
        application.id,
        AuditAction.APPLICATION_CREATED,
        details={"company": application.company, "role": application.role},
    )

    db.commit()
    db.refresh(application)
    return application


def get_application(db: Session, application_id: str) -> Application | None:
    return db.get(Application, application_id)


def list_applications(
    db: Session,
    status: ApplicationStatus | None = None,
    company: str | None = None,
    source: ApplicationSource | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Application], int]:
    stmt = select(Application)

    if status is not None:
        stmt = stmt.where(Application.status == status.value)
    if source is not None:
        stmt = stmt.where(Application.source == source.value)
    if company is not None:
        stmt = stmt.where(Application.company.ilike(f"%{company}%"))
    if q is not None:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Application.company.ilike(like),
                Application.role.ilike(like),
                Application.notes.ilike(like),
            )
        )

    total = len(db.execute(stmt).scalars().all())

    stmt = stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
    items = db.execute(stmt).scalars().all()
    return list(items), total


def update_application(
    db: Session, application: Application, data: ApplicationUpdate
) -> Application:
    updates = data.model_dump(exclude_unset=True)
    changed_fields: dict[str, dict[str, object]] = {}

    new_status = updates.pop("status", None)

    for field, value in updates.items():
        current = getattr(application, field)
        if current != value:
            changed_fields[field] = {"from": current, "to": value}
            setattr(application, field, value)

    if new_status is not None:
        new_status_value = new_status.value if hasattr(new_status, "value") else new_status
        if new_status_value != application.status:
            old_status = application.status
            application.status = new_status_value
            db.add(
                ApplicationEvent(
                    application_id=application.id,
                    event_type=EventType.STATUS_CHANGE.value,
                    from_status=old_status,
                    to_status=new_status_value,
                    description=f"Status changed from {old_status} to {new_status_value}",
                    source=ApplicationSource.MANUAL.value,
                )
            )
            _log_audit(
                db,
                application.id,
                AuditAction.STATUS_CHANGED,
                details={"from": old_status, "to": new_status_value},
            )

    if changed_fields:
        db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type=EventType.FIELD_UPDATED.value,
                description=f"Updated fields: {', '.join(changed_fields.keys())}",
                source=ApplicationSource.MANUAL.value,
            )
        )
        _log_audit(
            db,
            application.id,
            AuditAction.APPLICATION_UPDATED,
            details=changed_fields,
        )

    db.commit()
    db.refresh(application)
    return application


def delete_application(db: Session, application: Application) -> None:
    _log_audit(
        db,
        application.id,
        AuditAction.APPLICATION_DELETED,
        details={"company": application.company, "role": application.role},
    )
    db.delete(application)
    db.commit()
