"""The remaining go-live blockers are organisational, so the documentation is
the control. These tests keep it from drifting or quietly disappearing.

Closing the eleven code blockers did not make the system lawful to use. Four
things still have to happen before real data is entered, none of them code
changes. If someone deletes or renames the checklist, this suite fails rather
than the omission going unnoticed.
"""

import pathlib
import re

import pytest

CHECKLIST = pathlib.Path("docs/operations/go-live-checklist.md")

# The four things that block live data, and a phrase that must appear for each.
BLOCKERS = {
    "DPIA": "Data Protection Impact Assessment",
    "retention": "Retention periods agreed",
    "sign-off": "team-wide case visibility",
    "restore drill": "restore that has actually been run",
}

# Every document that must point a reader at the checklist.
MUST_LINK = [
    pathlib.Path("README.md"),
    pathlib.Path("docs/status.md"),
    pathlib.Path("docs/operations/deployment.md"),
    pathlib.Path("docs/operations/backups.md"),
    pathlib.Path("docs/operations/data-retention.md"),
    pathlib.Path("docs/operations/security-controls.md"),
    pathlib.Path("docs/adrs/007-team-wide-case-visibility.md"),
    pathlib.Path("docs/adrs/008-security-controls-for-production.md"),
    pathlib.Path("docs/user-guides/admin.md"),
]


def test_the_checklist_exists():
    assert CHECKLIST.is_file()


def test_the_checklist_says_the_app_is_not_ready():
    assert "NOT READY FOR LIVE DATA" in CHECKLIST.read_text()


@pytest.mark.parametrize("name,phrase", BLOCKERS.items())
def test_each_blocker_is_named_in_the_checklist(name, phrase):
    assert phrase in CHECKLIST.read_text(), name


def test_the_checklist_says_none_are_code_changes():
    """The point is that no further development closes these."""
    assert "none of them are code changes" in CHECKLIST.read_text().lower()


def test_each_blocker_names_an_owner_and_evidence():
    text = CHECKLIST.read_text()

    assert text.count("**Owner:**") >= 4
    assert text.count("**Evidence:**") >= 4


@pytest.mark.parametrize("path", MUST_LINK, ids=lambda p: str(p))
def test_the_checklist_is_linked_from(path):
    assert "go-live-checklist.md" in path.read_text()


def test_the_readme_warns_before_anything_else():
    """A warning below the fold is a warning nobody reads."""
    opening = pathlib.Path("README.md").read_text()[:900]

    assert "Not ready for live data" in opening
    assert "go-live-checklist.md" in opening


def test_the_user_guides_warn_in_plain_language():
    for path in (
        pathlib.Path("docs/user-guides/admin.md"),
        pathlib.Path("docs/user-guides/frontline-worker.md"),
    ):
        opening = path.read_text()[:700]
        assert "Do not" in opening and "real" in opening, path


def test_every_relative_link_in_the_operations_docs_resolves():
    """A broken link to the checklist is the same as no checklist."""
    broken = []

    for path in pathlib.Path("docs").rglob("*.md"):
        for target in re.findall(r"\]\((?!https?://|#)([^)#]+)", path.read_text()):
            if not (path.parent / target).resolve().exists():
                broken.append(f"{path} -> {target}")

    assert broken == []


def test_the_readme_links_resolve():
    broken = [
        target
        for target in re.findall(
            r"\]\((?!https?://|#)([^)#]+)", pathlib.Path("README.md").read_text()
        )
        if not pathlib.Path(target).exists()
    ]

    assert broken == []
