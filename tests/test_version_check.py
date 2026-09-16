"""Tests for the update check.

The regression these guard against: a failed release lookup yields the `v0.0.0` placeholder, and
comparing versions for inequality reported that placeholder as an available update, so the app
offered to "upgrade" from 0.24.7 to 0.0.0 on every start.
"""

import pytest

import tidal_dl_ng
from tidal_dl_ng import VERSION_UNKNOWN, update_available, version_is_newer, version_parts
from tidal_dl_ng.model.meta import ReleaseLatest


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("v0.24.7", (0, 24, 7)),
        ("0.24.7", (0, 24, 7)),
        ("V1.0", (1, 0)),
        ("v2", (2,)),
        ("v1.2.3-rc1", (1, 2, 3)),
        ("v1.2.3+build5", (1, 2, 3)),
        ("v1.2.3rc1", (1, 2, 3)),
        ("v0.0.0", (0, 0, 0)),
        ("", ()),
        ("nightly", ()),
        ("v", ()),
    ],
)
def test_version_parts(version, expected):
    assert version_parts(version) == expected


@pytest.mark.parametrize(
    ("candidate", "current"),
    [
        ("v0.24.8", "v0.24.7"),
        ("v0.25.0", "v0.24.7"),
        ("v1.0.0", "v0.99.99"),
        ("v0.24.7.1", "v0.24.7"),
        ("v1.0.1", "v1.0"),
    ],
)
def test_a_later_version_is_an_update(candidate, current):
    assert version_is_newer(candidate, current) is True


@pytest.mark.parametrize(
    ("candidate", "current"),
    [
        ("v0.24.7", "v0.24.7"),
        ("0.24.7", "v0.24.7"),
        ("v0.24.6", "v0.24.7"),
        ("v0.23.99", "v0.24.0"),
        ("v1.0", "v1.0.0"),
        (VERSION_UNKNOWN, "v0.24.7"),
        ("nightly", "v0.24.7"),
        ("v0.24.8", "not-a-version"),
    ],
)
def test_same_earlier_or_unreadable_is_not_an_update(candidate, current):
    assert version_is_newer(candidate, current) is False


def test_a_failed_lookup_never_reports_an_update(monkeypatch):
    """The placeholder a failed lookup returns must not be offered as a newer release."""
    monkeypatch.setattr(
        tidal_dl_ng,
        "latest_version_information",
        lambda: ReleaseLatest(version=VERSION_UNKNOWN, url="https://example.invalid", release_info="failed"),
    )

    is_available, info = update_available()

    assert is_available is False
    assert info.version == VERSION_UNKNOWN


def test_a_published_later_release_reports_an_update(monkeypatch):
    monkeypatch.setattr(
        tidal_dl_ng,
        "latest_version_information",
        lambda: ReleaseLatest(version="v99.0.0", url="https://example.invalid", release_info="notes"),
    )

    is_available, info = update_available()

    assert is_available is True
    assert info.version == "v99.0.0"


def test_an_unknown_local_version_reports_no_update(monkeypatch):
    monkeypatch.setattr(tidal_dl_ng, "__version__", VERSION_UNKNOWN.lstrip("v"))
    monkeypatch.setattr(
        tidal_dl_ng,
        "latest_version_information",
        lambda: ReleaseLatest(version="v99.0.0", url="https://example.invalid", release_info="notes"),
    )

    is_available, _ = update_available()

    assert is_available is False
