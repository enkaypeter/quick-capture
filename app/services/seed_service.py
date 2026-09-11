import os
from datetime import UTC, date, datetime, timedelta
from typing import Optional

import pyotp
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.audit_log import AuditAction, AuditLog
from app.models.case import Case
from app.models.case_attachment import CaseAttachment
from app.models.case_interaction import CaseInteraction, InteractionTag, InteractionTagType
from app.models.case_note import CaseNote, NoteSource
from app.models.follow_up_task import FollowUpStatus, FollowUpTask
from app.models.user import User


DEMO_CASE_DEFINITIONS = [
    {
        "identifier": "DEMO-OUTREACH-001",
        "full_name": "Demo Alex Reed",
        "phone_number": "07700 900001",
        "age": 38,
        "gender": "Man",
        "physical_description": "Blue coat, dark rucksack, usually near the market entrance.",
        "location_w3w": "market.safe.demo",
        "category": "caseload",
        "consent_status": "given",
        "consent_days_ago": 21,
        "risk_rating": "amber",
        "risk_notes": "Rough sleeping reported. No immediate safeguarding disclosure.",
        "mental_health_notes": "Anxiety mentioned during evening outreach.",
        "current_situation": "rough_sleeping",
        "created_days_ago": 28,
        "notes": [
            {
                "days_ago": 28,
                "content": "<p>Demo record created after first outreach conversation.</p>",
                "source": NoteSource.MANUAL,
            },
            {
                "days_ago": 13,
                "content": "<p>Voice note transcript: agreed to speak again near the drop-in.</p>",
                "source": NoteSource.TRANSCRIPTION,
                "needs_review": True,
            },
        ],
        "interactions": [
            {
                "days_ago": 28,
                "note": "<p>Introduced service and completed welfare check.</p>",
                "outcome": "Accepted information about breakfast provision.",
                "tags": [InteractionTagType.WELFARE_CHECK, InteractionTagType.SIGNPOSTED],
            },
            {
                "days_ago": 10,
                "note": "<p>Bought coffee and discussed temporary accommodation options.</p>",
                "outcome": "Open to housing conversation.",
                "tags": [InteractionTagType.FOOD_DRINK, InteractionTagType.HOUSING_SUPPORT],
            },
        ],
        "follow_ups": [
            {"title": "Check accommodation conversation", "due_offset": 1, "status": FollowUpStatus.OPEN},
            {"title": "Confirm drop-in attendance", "due_offset": -7, "status": FollowUpStatus.DONE},
        ],
        "attachments": [
            {
                "filename": "demo-alex-outreach-summary.txt",
                "content": "Demo outreach summary for Alex Reed. Not a real person.",
            }
        ],
    },
    {
        "identifier": "DEMO-CLIENT-002",
        "full_name": "Demo Sam Patel",
        "phone_number": "07700 900002",
        "age": 46,
        "gender": "Woman",
        "physical_description": "Often meets at the community cafe.",
        "other_contact": "Prefers phone contact after 10:00.",
        "location_w3w": "cafe.support.demo",
        "category": "client",
        "ni_number": "QQ123456C",
        "consent_status": "given",
        "consent_days_ago": 40,
        "risk_rating": "green",
        "risk_notes": "Stable engagement and known temporary accommodation.",
        "current_situation": "temporary_accommodation",
        "created_days_ago": 62,
        "notes": [
            {"days_ago": 62, "content": "<p>Formal client record created after referral.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 31,
                "note": "<p>Supported with GP registration paperwork.</p>",
                "outcome": "GP registration submitted.",
                "tags": [InteractionTagType.GP_SUPPORT],
            },
            {
                "days_ago": 5,
                "note": "<p>Reviewed benefit correspondence and next appointment.</p>",
                "outcome": "Benefit evidence list agreed.",
                "tags": [InteractionTagType.BENEFITS_SUPPORT],
            },
        ],
        "follow_ups": [
            {"title": "Upload benefit evidence", "due_offset": 4, "status": FollowUpStatus.OPEN},
        ],
        "attachments": [
            {
                "filename": "demo-sam-referral-form.txt",
                "content": "Demo referral form placeholder for Sam Patel. Not a real person.",
            }
        ],
    },
    {
        "identifier": "DEMO-UNKNOWN-003",
        "full_name": None,
        "phone_number": None,
        "age": None,
        "gender": "",
        "physical_description": "Grey sleeping bag, green hat, declined to give a name.",
        "location_w3w": "station.north.demo",
        "category": "non-caseload",
        "consent_status": "not_required",
        "risk_rating": "red",
        "risk_notes": "Seen late evening in cold weather. Welfare concern logged.",
        "current_situation": "rough_sleeping",
        "created_days_ago": 3,
        "notes": [
            {"days_ago": 3, "content": "<p>No name shared. Created record using location and description.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 3,
                "note": "<p>Welfare check completed. Person declined further support.</p>",
                "outcome": "Information left, no further details shared.",
                "tags": [InteractionTagType.WELFARE_CHECK, InteractionTagType.SLEEPING_BAG],
            },
        ],
        "follow_ups": [
            {"title": "Revisit location on evening outreach", "due_offset": 0, "status": FollowUpStatus.OPEN},
        ],
        "attachments": [],
    },
    {
        "identifier": "DEMO-GP-004",
        "full_name": "Demo Jordan Ellis",
        "phone_number": "07700 900004",
        "age": 52,
        "gender": "Man",
        "physical_description": "Usually carrying a black holdall.",
        "location_w3w": "clinic.path.demo",
        "category": "caseload",
        "consent_status": "given",
        "consent_days_ago": 12,
        "risk_rating": "amber",
        "risk_notes": "Medication routine inconsistent.",
        "mental_health_notes": "Reports low mood and poor sleep.",
        "current_situation": "hotel",
        "created_days_ago": 18,
        "notes": [
            {"days_ago": 18, "content": "<p>Added after GP referral conversation.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 14,
                "note": "<p>Discussed prescription collection and appointment reminder.</p>",
                "outcome": "Agreed appointment time.",
                "tags": [InteractionTagType.GP_SUPPORT, InteractionTagType.MEDICATION_CHECK],
            },
            {
                "days_ago": 2,
                "note": "<p>Taxi booked for clinic appointment.</p>",
                "outcome": "Transport arranged.",
                "tags": [InteractionTagType.TAXI_BOOKED],
            },
        ],
        "follow_ups": [
            {"title": "Confirm clinic appointment outcome", "due_offset": 2, "status": FollowUpStatus.OPEN},
        ],
        "attachments": [],
    },
    {
        "identifier": "DEMO-HOUSING-005",
        "full_name": "Demo Morgan Shaw",
        "phone_number": "07700 900005",
        "age": 29,
        "gender": "Non-binary",
        "physical_description": "Often meets near the library steps.",
        "location_w3w": "library.steps.demo",
        "category": "client",
        "ni_number": "QQ234567C",
        "consent_status": "given",
        "consent_days_ago": 33,
        "risk_rating": "amber",
        "risk_notes": "Temporary accommodation at risk if paperwork is missed.",
        "current_situation": "temporary_accommodation",
        "created_days_ago": 45,
        "notes": [
            {"days_ago": 45, "content": "<p>Client record created for housing support.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 20,
                "note": "<p>Reviewed housing application evidence.</p>",
                "outcome": "Two missing documents identified.",
                "tags": [InteractionTagType.HOUSING_SUPPORT],
            },
            {
                "days_ago": 8,
                "note": "<p>Completed follow-up call with housing contact.</p>",
                "outcome": "Application moved to review.",
                "tags": [InteractionTagType.HOUSING_SUPPORT, InteractionTagType.OTHER],
            },
        ],
        "follow_ups": [
            {"title": "Check housing review decision", "due_offset": 6, "status": FollowUpStatus.OPEN},
        ],
        "attachments": [
            {
                "filename": "demo-morgan-housing-checklist.txt",
                "content": "Demo housing checklist placeholder for Morgan Shaw. Not a real person.",
            }
        ],
    },
    {
        "identifier": "DEMO-DROPIN-006",
        "full_name": "Demo Casey Brooks",
        "phone_number": "",
        "age": 34,
        "gender": "Woman",
        "physical_description": "Red coat, attends day shelter intermittently.",
        "location_w3w": "shelter.entry.demo",
        "category": "non-caseload",
        "consent_status": "unknown",
        "risk_rating": "unknown",
        "current_situation": "unknown",
        "created_days_ago": 7,
        "notes": [
            {"days_ago": 7, "content": "<p>Brief drop-in conversation. No ongoing support agreed yet.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 7,
                "note": "<p>Provided signposting and food information.</p>",
                "outcome": "May return next week.",
                "tags": [InteractionTagType.SIGNPOSTED, InteractionTagType.FOOD_DRINK],
            },
        ],
        "follow_ups": [],
        "attachments": [],
    },
    {
        "identifier": "DEMO-SAFEGUARD-007",
        "full_name": "Demo Taylor Green",
        "phone_number": "07700 900007",
        "age": 41,
        "gender": "Man",
        "physical_description": "Usually seen with a small suitcase.",
        "location_w3w": "bridge.care.demo",
        "category": "caseload",
        "consent_status": "given",
        "consent_days_ago": 9,
        "risk_rating": "red",
        "risk_notes": "Safeguarding concern raised after disclosure during outreach.",
        "mental_health_notes": "Crisis support discussed. Worker to avoid repeated questioning.",
        "current_situation": "rough_sleeping",
        "created_days_ago": 15,
        "notes": [
            {"days_ago": 15, "content": "<p>Case opened due to escalating risk and repeated contact.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 9,
                "note": "<p>Completed welfare check and escalated safeguarding note.</p>",
                "outcome": "Team lead informed.",
                "tags": [InteractionTagType.WELFARE_CHECK, InteractionTagType.OTHER],
            },
            {
                "days_ago": 1,
                "note": "<p>Medication check and food provided.</p>",
                "outcome": "Accepted follow-up tomorrow.",
                "tags": [InteractionTagType.MEDICATION_CHECK, InteractionTagType.FOOD_DRINK],
            },
        ],
        "follow_ups": [
            {"title": "Team lead safeguarding review", "due_offset": 1, "status": FollowUpStatus.OPEN},
        ],
        "attachments": [
            {
                "filename": "demo-taylor-risk-note.txt",
                "content": "Demo risk note placeholder for Taylor Green. Not a real person.",
            }
        ],
    },
    {
        "identifier": "DEMO-TEMPACC-008",
        "full_name": "Demo Riley Chen",
        "phone_number": "07700 900008",
        "age": 58,
        "gender": "Man",
        "physical_description": "Meets at temporary accommodation reception.",
        "location_w3w": "reception.temp.demo",
        "category": "client",
        "ni_number": "QQ345678C",
        "consent_status": "given",
        "consent_days_ago": 70,
        "risk_rating": "green",
        "current_situation": "housed",
        "created_days_ago": 84,
        "notes": [
            {"days_ago": 84, "content": "<p>Transferred from active support to client record after accommodation stabilised.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 30,
                "note": "<p>Checked tenancy paperwork and benefit status.</p>",
                "outcome": "No urgent actions.",
                "tags": [InteractionTagType.BENEFITS_SUPPORT, InteractionTagType.HOUSING_SUPPORT],
            },
        ],
        "follow_ups": [
            {"title": "Monthly tenancy check-in", "due_offset": 12, "status": FollowUpStatus.OPEN},
        ],
        "attachments": [],
    },
    {
        "identifier": "DEMO-FOOD-009",
        "full_name": "Demo Jamie Stone",
        "phone_number": "",
        "age": None,
        "gender": "",
        "physical_description": "Black hoodie, sleeping near bus station steps.",
        "location_w3w": "bus.steps.demo",
        "category": "non-caseload",
        "consent_status": "not_required",
        "risk_rating": "amber",
        "current_situation": "rough_sleeping",
        "created_days_ago": 5,
        "notes": [
            {"days_ago": 5, "content": "<p>Short contact only. Person accepted food but declined further discussion.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 5,
                "note": "<p>Provided sandwich and sleeping bag.</p>",
                "outcome": "No contact details shared.",
                "tags": [InteractionTagType.FOOD_DRINK, InteractionTagType.SLEEPING_BAG],
            },
        ],
        "follow_ups": [
            {"title": "Check same location during morning outreach", "due_offset": 3, "status": FollowUpStatus.OPEN},
        ],
        "attachments": [],
    },
    {
        "identifier": "DEMO-SUPPORT-010",
        "full_name": "Demo Priya Khan",
        "phone_number": "07700 900010",
        "age": 36,
        "gender": "Woman",
        "physical_description": "Usually attends appointments at the day centre.",
        "other_contact": "Email preferred via support contact on file.",
        "location_w3w": "centre.appointment.demo",
        "category": "caseload",
        "consent_status": "declined",
        "risk_rating": "amber",
        "risk_notes": "Consent discussion to be revisited gently next appointment.",
        "current_situation": "hotel",
        "created_days_ago": 22,
        "notes": [
            {"days_ago": 22, "content": "<p>Ongoing support started after day centre appointment.</p>", "source": NoteSource.MANUAL},
        ],
        "interactions": [
            {
                "days_ago": 12,
                "note": "<p>Discussed support plan and next practical steps.</p>",
                "outcome": "Agreed to bring letters next time.",
                "tags": [InteractionTagType.SIGNPOSTED, InteractionTagType.BENEFITS_SUPPORT],
            },
            {
                "days_ago": 4,
                "note": "<p>Taxi booked to attend accommodation meeting.</p>",
                "outcome": "Meeting attended.",
                "tags": [InteractionTagType.TAXI_BOOKED, InteractionTagType.HOUSING_SUPPORT],
            },
        ],
        "follow_ups": [
            {"title": "Review letters at next appointment", "due_offset": 5, "status": FollowUpStatus.OPEN},
            {"title": "Accommodation meeting transport", "due_offset": -4, "status": FollowUpStatus.DONE},
        ],
        "attachments": [
            {
                "filename": "demo-priya-appointment-notes.txt",
                "content": "Demo appointment notes placeholder for Priya Khan. Not a real person.",
            }
        ],
    },
]


def seed_demo_account() -> Optional[User]:
    if not current_app.config.get("DEMO_ACCOUNT_ENABLED"):
        return None

    email = current_app.config["DEMO_ACCOUNT_EMAIL"]
    password = current_app.config["DEMO_ACCOUNT_PASSWORD"]
    user = User.query.filter_by(email=email).first()
    if user:
        changed = False
        if user.role != "admin":
            user.role = "admin"
            changed = True
        if user.first_name != current_app.config["DEMO_ACCOUNT_FIRST_NAME"]:
            user.first_name = current_app.config["DEMO_ACCOUNT_FIRST_NAME"]
            changed = True
        if not check_password_hash(user.password, password):
            user.password = generate_password_hash(password, method="pbkdf2:sha256")
            changed = True
        if _enrol_shared_demo_mfa(user):
            changed = True
        if changed:
            db.session.commit()
        return user

    user = User(
        email=email,
        first_name=current_app.config["DEMO_ACCOUNT_FIRST_NAME"],
        password=generate_password_hash(
            current_app.config["DEMO_ACCOUNT_PASSWORD"],
            method="pbkdf2:sha256",
        ),
        role="admin",
    )
    _enrol_shared_demo_mfa(user)
    db.session.add(user)
    db.session.commit()
    return user


def _enrol_shared_demo_mfa(user: User) -> bool:
    """Keep the shared demo account enrolled, so the code prompt is shown
    but nobody is sent to set up an authenticator. Returns True if changed.

    The secret is never shown to anyone; with DEMO_ACCOUNT_SHARED_MFA on,
    login accepts any 6-digit code instead (see MfaService.verify).
    """
    if not current_app.config.get("DEMO_ACCOUNT_SHARED_MFA"):
        return False
    if user.mfa_enabled and user.totp_secret:
        return False

    user.totp_secret = pyotp.random_base32()
    user.mfa_enabled = True
    user.mfa_confirmed_at = datetime.now(UTC)
    return True


def seed_demo_cases(user: Optional[User]) -> None:
    if not user or not current_app.config.get("DEMO_CASES_ENABLED"):
        return

    identifiers = [case_data["identifier"] for case_data in DEMO_CASE_DEFINITIONS]
    existing = {
        case.identifier
        for case in Case.query.filter(Case.identifier.in_(identifiers)).all()
    }

    for case_data in DEMO_CASE_DEFINITIONS:
        if case_data["identifier"] in existing:
            continue
        _create_demo_case(user, case_data)

    db.session.commit()


def _create_demo_case(user: User, case_data: dict) -> None:
    now = datetime.now(UTC)
    created_at = now - timedelta(days=case_data["created_days_ago"])
    dob = _dob_for_age(case_data.get("age"))

    case = Case(
        identifier=case_data["identifier"],
        full_name=case_data.get("full_name"),
        phone_number=case_data.get("phone_number") or None,
        date_of_birth=dob,
        age=case_data.get("age"),
        gender=case_data.get("gender") or None,
        physical_description=case_data.get("physical_description"),
        other_contact=case_data.get("other_contact"),
        location_w3w=case_data.get("location_w3w"),
        category=case_data["category"],
        ni_number=case_data.get("ni_number"),
        consent_status=case_data.get("consent_status", "unknown"),
        consent_date=_date_days_ago(case_data.get("consent_days_ago")),
        risk_rating=case_data.get("risk_rating", "unknown"),
        risk_notes=case_data.get("risk_notes"),
        mental_health_notes=case_data.get("mental_health_notes"),
        current_situation=case_data.get("current_situation"),
        created_at=created_at,
        updated_at=now - timedelta(days=case_data.get("updated_days_ago", 0)),
        user_id=user.id,
        assigned_user_id=user.id,
    )
    db.session.add(case)
    db.session.flush()

    db.session.add(
        AuditLog(
            case_id=case.id,
            user_id=user.id,
            action=AuditAction.CREATED,
            field_name="case",
            new_value=f"Seeded demo case {case.identifier}",
            timestamp=created_at,
        )
    )

    for note_data in case_data.get("notes", []):
        db.session.add(
            CaseNote(
                case_id=case.id,
                content=note_data["content"],
                source=note_data.get("source", NoteSource.MANUAL),
                needs_review=note_data.get("needs_review", False),
                created_at=now - timedelta(days=note_data["days_ago"]),
                updated_at=now - timedelta(days=note_data["days_ago"]),
            )
        )

    for interaction_data in case_data.get("interactions", []):
        occurred_at = now - timedelta(days=interaction_data["days_ago"])
        interaction = CaseInteraction(
            case_id=case.id,
            user_id=user.id,
            occurred_at=occurred_at,
            note_content=interaction_data.get("note"),
            outcome=interaction_data.get("outcome"),
            location_w3w=interaction_data.get("location_w3w") or case.location_w3w,
            created_at=occurred_at,
        )
        db.session.add(interaction)
        db.session.flush()

        for tag_type in interaction_data.get("tags", []):
            db.session.add(
                InteractionTag(
                    interaction_id=interaction.id,
                    tag_type=tag_type,
                    label=InteractionTagType.LABELS[tag_type],
                    created_at=occurred_at,
                )
            )

        db.session.add(
            AuditLog(
                case_id=case.id,
                user_id=user.id,
                action=AuditAction.CREATED,
                field_name=f"interaction:{interaction.id}",
                new_value=f"Seeded interaction with {len(interaction_data.get('tags', []))} tags",
                timestamp=occurred_at,
            )
        )

    for follow_up_data in case_data.get("follow_ups", []):
        due_date = _date_offset(follow_up_data["due_offset"])
        status = follow_up_data.get("status", FollowUpStatus.OPEN)
        completed_at = None
        if status == FollowUpStatus.DONE:
            completed_at = now - timedelta(days=abs(follow_up_data["due_offset"]))

        db.session.add(
            FollowUpTask(
                case_id=case.id,
                created_by_user_id=user.id,
                assigned_user_id=user.id,
                title=follow_up_data["title"],
                due_date=due_date,
                status=status,
                completed_at=completed_at,
                created_at=created_at,
            )
        )

    for attachment_data in case_data.get("attachments", []):
        stored_path, size_bytes = _write_demo_attachment(
            case.identifier,
            attachment_data["filename"],
            attachment_data["content"],
        )
        db.session.add(
            CaseAttachment(
                case_id=case.id,
                user_id=user.id,
                original_filename=attachment_data["filename"],
                stored_path=stored_path,
                content_type="text/plain",
                size_bytes=size_bytes,
                created_at=created_at,
            )
        )


def _dob_for_age(age: Optional[int]) -> Optional[str]:
    if age is None:
        return None
    today = date.today()
    try:
        return today.replace(year=today.year - age).isoformat()
    except ValueError:
        return date(today.year - age, 2, 28).isoformat()


def _date_days_ago(days_ago: Optional[int]) -> Optional[str]:
    if days_ago is None:
        return None
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _date_offset(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _write_demo_attachment(identifier: str, filename: str, content: str) -> tuple[str, int]:
    directory = os.path.join(current_app.config["UPLOAD_FOLDER"], "demo")
    os.makedirs(directory, exist_ok=True)

    stored_name = f"{identifier.lower()}-{filename}"
    absolute_path = os.path.join(directory, stored_name)
    with open(absolute_path, "w", encoding="utf-8") as file:
        file.write(content)

    return os.path.join("demo", stored_name), os.path.getsize(absolute_path)
