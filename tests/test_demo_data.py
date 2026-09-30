"""The seeded demo cases must match the current case model and load cleanly."""

import pytest

from app.models.case import (
    ETHNICITY_CHOICES,
    Case,
    ConsentStatus,
    Project,
    RiskRating,
)
from app.models.case_attachment import AttachmentKind, CaseAttachment
from app.models.case_note import CaseNote
from app.models.user import User
from app.services.demo_service import reset_demo_data
from app.services.seed_service import seed_demo_cases

from conftest import login_admin


@pytest.fixture()
def demo_cases(app):
    app.config["DEMO_CASES_ENABLED"] = True
    demo_user = User.query.filter_by(email="demo@quickcapture.local").one()
    seed_demo_cases(demo_user)
    return Case.query.filter(Case.identifier.like("DEMO-%")).all()


def test_demo_cases_use_only_current_choices(demo_cases):
    for case in demo_cases:
        assert case.project in Project.CHOICES, case.identifier
        assert case.consent_status in ConsentStatus.CHOICES, case.identifier
        assert case.risk_rating in RiskRating.CHOICES, case.identifier
        if case.ethnicity:
            assert case.ethnicity in ETHNICITY_CHOICES, case.identifier


def test_demo_cases_cover_every_project_and_have_a_key_worker(demo_cases):
    assert {case.project for case in demo_cases} == set(Project.CHOICES)
    assert all(case.assigned_worker is not None for case in demo_cases)


def test_demo_cases_exercise_the_new_fields(demo_cases):
    assert any(case.ethnicity for case in demo_cases)
    assert any(case.location_address for case in demo_cases)
    assert any(case.ni_number for case in demo_cases)
    assert any(
        a.kind == AttachmentKind.CONSENT_RISK for a in CaseAttachment.query.all()
    )
    assert CaseNote.query.filter_by(needs_review=True).count() >= 1


def test_no_demo_case_carries_mental_health_notes(demo_cases):
    assert all(not case.mental_health_notes for case in demo_cases)


def test_every_demo_case_page_and_list_loads(client, demo_cases):
    login_admin(client)

    for path in ("/dashboard", "/cases", "/cases/review", "/follow-ups", "/reports"):
        assert client.get(path).status_code == 200, path

    for case in demo_cases:
        response = client.get(f"/cases/{case.id}")
        assert response.status_code == 200, case.identifier
        assert b"Personal details" in response.data

    home = client.get("/dashboard").get_data(as_text=True)
    assert "Upcoming follow-ups" in home


def test_demo_consent_images_can_be_downloaded(client, demo_cases):
    login_admin(client)
    image = CaseAttachment.query.filter_by(kind=AttachmentKind.CONSENT_RISK).first()

    response = client.get(f"/attachments/{image.id}")

    assert response.status_code == 200
    assert response.data.startswith(b"\x89PNG")


def test_reset_reseeds_demo_data_in_the_new_shape(app, demo_cases):
    reset_demo_data(app.config)

    reseeded = Case.query.filter(Case.identifier.like("DEMO-%")).all()
    assert len(reseeded) == 10
    assert {case.project for case in reseeded} == set(Project.CHOICES)
