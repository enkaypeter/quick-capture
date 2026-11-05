

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
