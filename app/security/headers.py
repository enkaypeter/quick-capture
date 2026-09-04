"""HTTP security headers and Content Security Policy.

Blocker 6. Every page in this app renders National Insurance numbers, mental
health notes and risk assessments into the DOM. A CSP that pins scripts to
this origin is what stops a third-party or injected script from reading them.

Tailwind is served from `static/vendor/` rather than cdn.tailwindcss.com so
that no third party gets script access to those pages.
"""

import secrets

from flask import current_app, g, request


def _csp(nonce: str) -> str:
    directives = [
        "default-src 'self'",
        # 'self' plus a per-request nonce for the small inline blocks in the
        # templates. No CDN host is allowed.
        f"script-src 'self' 'nonce-{nonce}'",
        # The vendored Tailwind build compiles classes in the browser and
        # injects <style> elements, which requires 'unsafe-inline' for styles.
        # Removing this needs a build-time Tailwind step — see
        # docs/operations/security-controls.md.
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "media-src 'self' blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(directives)


def init_security_headers(app):
    """Attach CSP nonce generation and response security headers."""

    @app.before_request
    def _generate_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def _inject_csp_nonce():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def _apply_security_headers(response):
        if not app.config.get("SECURITY_HEADERS_ENABLED", True):
            return response

        nonce = getattr(g, "csp_nonce", "")
        response.headers.setdefault("Content-Security-Policy", _csp(nonce))
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(self), geolocation=(self), payment=()",
        )
        # Case data must never be held by a shared cache or a proxy.
        response.headers.setdefault("Cache-Control", "no-store")

        if app.config.get("HSTS_ENABLED") and request.is_secure:
            max_age = app.config.get("HSTS_MAX_AGE", 31536000)
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={max_age}; includeSubDomains",
            )

        return response
