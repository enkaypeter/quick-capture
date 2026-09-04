"""Blocker 6: no third-party scripts, and a CSP that pins scripts to this origin."""

import pathlib
import re

from conftest import register

TEMPLATE_DIR = pathlib.Path("app/templates")


def csp(response):
    return response.headers.get("Content-Security-Policy", "")


def test_no_template_loads_a_third_party_script():
    """A CDN script has full DOM access to pages showing case data."""
    offenders = [
        path.name
        for path in TEMPLATE_DIR.rglob("*.html")
        if re.search(r'<script[^>]+src="https?://', path.read_text())
    ]

    assert offenders == []


def test_tailwind_is_served_from_this_origin():
    assert pathlib.Path("app/static/vendor/tailwind.min.js").is_file()
    base = (TEMPLATE_DIR / "base.html").read_text()
    assert "vendor/tailwind.min.js" in base
    assert "cdn.tailwindcss.com" not in base


def test_no_template_uses_an_inline_event_handler():
    """Inline handlers would force 'unsafe-inline' back into the policy."""
    offenders = [
        path.name
        for path in TEMPLATE_DIR.rglob("*.html")
        if re.search(r"\son(click|submit|change|input|load)=", path.read_text())
    ]

    assert offenders == []


def test_every_inline_script_block_carries_the_nonce():
    offenders = [
        path.name
        for path in TEMPLATE_DIR.rglob("*.html")
        if "<script>" in path.read_text()
    ]

    assert offenders == []


def test_script_src_allows_only_this_origin_and_a_nonce(client):
    policy = csp(client.get("/login"))

    match = re.search(r"script-src ([^;]+)", policy)
    assert match
    directive = match.group(1)
    assert "'self'" in directive
    assert "'nonce-" in directive
    assert "http" not in directive
    assert "'unsafe-inline'" not in directive
    assert "'unsafe-eval'" not in directive


def test_the_nonce_changes_on_every_request(client):
    first = re.search(r"'nonce-([^']+)'", csp(client.get("/login"))).group(1)
    second = re.search(r"'nonce-([^']+)'", csp(client.get("/login"))).group(1)

    assert first != second


def test_the_rendered_page_nonce_matches_the_header(client):
    response = client.get("/login")

    header_nonce = re.search(r"'nonce-([^']+)'", csp(response)).group(1)
    body = response.get_data(as_text=True)
    if "<script nonce=" in body:
        assert f'nonce="{header_nonce}"' in body


def test_the_policy_blocks_framing_and_plugins(client):
    policy = csp(client.get("/login"))

    assert "frame-ancestors 'none'" in policy
    assert "object-src 'none'" in policy
    assert "base-uri 'self'" in policy
    assert "form-action 'self'" in policy


def test_the_standard_hardening_headers_are_present(client):
    headers = client.get("/login").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["Permissions-Policy"]


def test_case_pages_are_not_stored_by_shared_caches(client):
    register(client, "worker@example.org")

    assert client.get("/dashboard").headers["Cache-Control"] == "no-store"


def test_hsts_is_only_sent_over_https(client, app):
    app.config["HSTS_ENABLED"] = True

    plain = client.get("/login")
    secure = client.get("/login", base_url="https://localhost")

    assert "Strict-Transport-Security" not in plain.headers
    assert "max-age=" in secure.headers["Strict-Transport-Security"]


def test_hsts_is_on_by_default_in_the_production_config():
    from config import ProductionConfig

    assert ProductionConfig.HSTS_ENABLED is True
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
