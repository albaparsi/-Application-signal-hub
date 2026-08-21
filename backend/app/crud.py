from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.enums import (
    ApplicationSource,
    ApplicationStatus,
    AuditAction,
    EventType,
    SortDir,
    SortField,
)
from app.models import Application, ApplicationEvent, AuditLog
from app.schemas import ApplicationCreate, ApplicationUpdate
from app.transitions import InvalidTransitionError, validate_transition


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


_SORT_COLUMNS = {
    SortField.CREATED_AT: Application.created_at,
    SortField.UPDATED_AT: Application.updated_at,
    SortField.APPLIED_DATE: Application.applied_date,
    SortField.COMPANY: Application.company,
    SortField.ROLE: Application.role,
}


def list_applications(
    db: Session,
    status: list[ApplicationStatus] | None = None,
    company: str | None = None,
    source: ApplicationSource | None = None,
    q: str | None = None,
    applied_date_from: date | None = None,
    applied_date_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort_by: SortField = SortField.CREATED_AT,
    sort_dir: SortDir = SortDir.DESC,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Application], int]:
    stmt = select(Application)

    if status:
        stmt = stmt.where(Application.status.in_([s.value for s in status]))
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
    if applied_date_from is not None:
        stmt = stmt.where(Application.applied_date >= applied_date_from)
    if applied_date_to is not None:
        stmt = stmt.where(Application.applied_date <= applied_date_to)
    if created_from is not None:
        stmt = stmt.where(Application.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(Application.created_at <= created_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    sort_column = _SORT_COLUMNS[sort_by]
    sort_column = sort_column.asc() if sort_dir == SortDir.ASC else sort_column.desc()
    stmt = stmt.order_by(sort_column).limit(limit).offset(offset)

    items = db.execute(stmt).scalars().all()
    return list(items), total


def update_application(
    db: Session,
    application: Application,
    data: ApplicationUpdate,
    force: bool = False,
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
            try:
                validate_transition(
                    ApplicationStatus(old_status),
                    ApplicationStatus(new_status_value),
                    force=force,
                )
            except InvalidTransitionError:
                db.rollback()  # discard any other field changes staged above
                raise
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
