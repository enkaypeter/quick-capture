"""Client feedback round: naming, home screen, project, key worker, personal
details, consent and risk options, addresses and follow-ups."""

import io

from app.extensions import db
from app.models.case import Case
from app.models.case_attachment import CaseAttachment
from app.models.case_note import CaseNote
from app.models.follow_up_task import FollowUpTask
from app.models.user import User

from conftest import csrf_token, register


def post_new_case(client, **overrides):
    token = csrf_token(client, "/cases/new")
    data = {"csrf_token": token, "full_name": "Jo Bloggs"}
    data.update(overrides)
    return client.post("/cases/new", data=data, follow_redirects=False)


# --- naming ----------------------------------------------------------------


def test_landing_page_headline_is_outreach_case_management(client):
    page = client.get("/").get_data(as_text=True)

    assert "Outreach Case Management" in page
    assert "QuickCapture" not in page


# --- home screen -----------------------------------------------------------


def test_home_screen_shows_summary_boxes_and_follow_up_feed_but_no_case_list(client):
    register(client, "worker@example.org")
    post_new_case(client, full_name="Listed Person")
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")
    client.post(
        f"/cases/{case.id}/follow-ups",
        data={"csrf_token": token, "title": "Ring the GP", "due_date": "2030-01-02"},
    )

    page = client.get("/dashboard").get_data(as_text=True)

    assert "Active cases" in page
    assert "Follow-up actions" in page
    assert "Cases to review" in page
    assert "Upcoming follow-ups" in page
    assert "Ring the GP" in page
    assert 'name="q"' in page
    assert "New Case" in page
    # The full case list has moved to its own page; only the feed names a case.
    assert "risk: green" not in page
    assert page.count("Listed Person") == 1


def test_search_results_appear_on_the_home_screen(client):
    register(client, "worker@example.org")
    post_new_case(client, full_name="Findable Person")

    page = client.get("/dashboard?q=Findable").get_data(as_text=True)

    assert "Findable Person" in page


def test_active_cases_page_lists_every_case(client):
    register(client, "worker@example.org")
    post_new_case(client, full_name="Listed Person")

    assert b"Listed Person" in client.get("/cases").data


def test_follow_up_actions_page_lists_open_follow_ups(client):
    register(client, "worker@example.org")
    post_new_case(client)
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")
    client.post(
        f"/cases/{case.id}/follow-ups",
        data={"csrf_token": token, "title": "Chase housing", "due_date": "2030-05-06"},
    )

    page = client.get("/follow-ups").get_data(as_text=True)

    assert "Chase housing" in page
    assert "2030-05-06" in page


def test_cases_to_review_lists_cases_with_unchecked_transcripts(client):
    register(client, "worker@example.org")
    post_new_case(client, full_name="Needs Checking", voice_transcript="spoke about housing")
    post_new_case(client, full_name="All Fine")
    assert CaseNote.query.filter_by(needs_review=True).count() == 1

    page = client.get("/cases/review").get_data(as_text=True)

    assert "Needs Checking" in page
    assert "All Fine" not in page


# --- create form -----------------------------------------------------------


def test_create_form_offers_the_new_fields(client):
    register(client, "worker@example.org")

    page = client.get("/cases/new").get_data(as_text=True)

    assert "Personal details" in page
    assert "Identity" not in page
    assert "Consent &amp; risk" in page
    assert "reporting" not in page.lower().replace("reporting fields", "")
    assert "Mental health" not in page
    assert 'name="ethnicity"' in page
    assert 'name="ni_number"' in page
    assert "family member" in page
    assert 'name="location_address"' in page
    assert 'name="consent_image"' in page
    assert ">Core<" in page and ">Settled<" in page and ">EU<" in page
    assert "Case status" not in page


def test_consent_and_risk_no_longer_offer_unknown(client):
    register(client, "worker@example.org")

    page = client.get("/cases/new").get_data(as_text=True)
    consent = page.split('id="consent_status"')[1].split("</select>")[0]
    risk = page.split('id="risk_rating"')[1].split("</select>")[0]

    assert "Unknown" not in consent and "Unknown" not in risk
    assert consent.count("<option") == 3
    assert risk.count("<option") == 3


def test_case_notes_are_an_optional_dropdown(client):
    register(client, "worker@example.org")

    page = client.get("/cases/new").get_data(as_text=True)

    assert '<details id="notes-details"' in page
    assert "Case notes" in page


def test_new_case_defaults_key_worker_to_creator_and_saves_new_fields(client):
    register(client, "worker@example.org")
    worker = User.query.filter_by(email="worker@example.org").one()

    response = post_new_case(
        client,
        project="eu",
        ethnicity="White",
        ni_number="qq123456c",
        location_address="1 High Street, Leeds",
        other_contact="sister 07000 000000",
    )
    case = Case.query.one()

    assert response.status_code == 302
    assert case.assigned_user_id == worker.id
    assert case.project == "eu"
    assert case.ethnicity == "White"
    assert case.ni_number == "QQ123456C"
    assert case.location_address == "1 High Street, Leeds"
    assert case.consent_status == "not_required"
    assert case.risk_rating == "green"


def test_key_worker_can_be_chosen_from_the_list(client):
    register(client, "one@example.org", first_name="One")
    client.get("/logout")
    register(client, "two@example.org", first_name="Two")
    other = User.query.filter_by(email="one@example.org").one()

    post_new_case(client, key_worker_id=str(other.id))

    assert Case.query.one().assigned_user_id == other.id


def test_invalid_project_and_unknown_choices_are_rejected(client):
    register(client, "worker@example.org")

    for field, value in [
        ("project", "nonsense"),
        ("consent_status", "unknown"),
        ("risk_rating", "unknown"),
    ]:
        post_new_case(client, **{field: value})

    assert Case.query.count() == 0


def test_a_case_can_be_created_from_an_address_alone(client):
    register(client, "worker@example.org")

    response = post_new_case(client, full_name="", location_address="Under the railway arch")

    assert response.status_code == 302
    assert Case.query.one().location_address == "Under the railway arch"


def test_consent_image_is_stored_on_create(app, client):
    register(client, "worker@example.org")

    response = post_new_case(
        client,
        consent_image=(io.BytesIO(b"\x89PNG fake"), "consent.png"),
    )
    attachment = CaseAttachment.query.one()

    assert response.status_code == 302
    assert attachment.kind == "consent_risk"
    assert attachment.case_id == Case.query.one().id


def test_non_image_consent_upload_is_rejected(client):
    register(client, "worker@example.org")

    post_new_case(client, consent_image=(io.BytesIO(b"%PDF"), "consent.pdf"))

    assert Case.query.count() == 0
    assert CaseAttachment.query.count() == 0


# --- case detail -----------------------------------------------------------


def test_case_detail_leads_with_personal_details_then_support_provided(client):
    register(client, "worker@example.org")
    post_new_case(client, ethnicity="White", ni_number="QQ123456C")
    case = Case.query.one()

    page = client.get(f"/cases/{case.id}").get_data(as_text=True)

    assert page.index("Personal details") < page.index("Support Provided")
    assert "Quick Capture" not in page
    assert "QQ123456C" in page
    assert 'name="ethnicity"' in page
    assert "Mental health" not in page
    assert "Follow-ups" in page
    assert "Follow up on" in page
    assert "Case status" not in page


def test_personal_details_can_be_updated_after_creation(client):
    register(client, "worker@example.org")
    post_new_case(client)
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")

    response = client.post(
        f"/cases/{case.id}/edit",
        json={
            "ethnicity": "Other ethnic group",
            "ni_number": "ab 12 34 56 c",
            "location_address": "Flat 2, Park Road",
            "project": "settled",
        },
        headers={"X-CSRFToken": token},
    )
    db.session.refresh(case)

    assert response.status_code == 200
    assert case.ethnicity == "Other ethnic group"
    assert case.ni_number == "AB 12 34 56 C"
    assert case.location_address == "Flat 2, Park Road"
    assert case.project == "settled"


def test_key_worker_can_be_reallocated_and_is_audited(client):
    register(client, "one@example.org", first_name="One")
    post_new_case(client)
    case = Case.query.one()
    client.get("/logout")
    register(client, "two@example.org", first_name="Two")
    new_worker = User.query.filter_by(email="two@example.org").one()
    token = csrf_token(client, f"/cases/{case.id}")

    response = client.post(
        f"/cases/{case.id}/edit",
        json={"key_worker_id": str(new_worker.id)},
        headers={"X-CSRFToken": token},
    )
    db.session.refresh(case)

    assert response.status_code == 200
    assert case.assigned_user_id == new_worker.id
    audit = client.get(f"/cases/{case.id}/audit").get_json()["entries"]
    assert any(entry["field_name"] == "key_worker" for entry in audit)


def test_edit_rejects_unknown_consent_and_risk(client):
    register(client, "worker@example.org")
    post_new_case(client)
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")

    for payload in ({"consent_status": "unknown"}, {"risk_rating": "unknown"}, {"project": "x"}):
        response = client.post(
            f"/cases/{case.id}/edit", json=payload, headers={"X-CSRFToken": token}
        )
        assert response.status_code == 400


def test_legacy_unknown_values_render_without_being_offered(client):
    register(client, "worker@example.org")
    post_new_case(client)
    case = Case.query.one()
    case.consent_status = "unknown"
    case.risk_rating = "unknown"
    db.session.commit()

    page = client.get(f"/cases/{case.id}").get_data(as_text=True)

    assert "not set" in page.lower()
    consent = page.split('name="consent_status"')[1].split("</select>")[0]
    risk = page.split('name="risk_rating"')[1].split("</select>")[0]
    assert 'value="unknown"' not in consent
    assert 'value="unknown"' not in risk


def test_consent_image_can_be_uploaded_on_an_existing_case(client):
    register(client, "worker@example.org")
    post_new_case(client)
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")

    client.post(
        f"/cases/{case.id}/consent-image",
        data={"csrf_token": token, "consent_image": (io.BytesIO(b"\xff\xd8 jpeg"), "form.jpg")},
        content_type="multipart/form-data",
    )

    attachment = CaseAttachment.query.one()
    assert attachment.kind == "consent_risk"
    page = client.get(f"/cases/{case.id}").get_data(as_text=True)
    assert "form.jpg" in page


def test_reports_count_by_project(client):
    register(client, "worker@example.org")
    post_new_case(client, project="core")

    page = client.get("/reports").get_data(as_text=True)

    assert "Project" in page
    assert "Case status" not in page
