#!/usr/bin/env python
import importlib.metadata
from itertools import takewhile
from pathlib import Path
from urllib.parse import urlparse

import requests
import toml

from tidal_dl_ng.constants import REQUESTS_TIMEOUT_SEC
from tidal_dl_ng.model.meta import ProjectInformation, ReleaseLatest

# Stands in for a version that could not be determined, on either side of an update check.
VERSION_UNKNOWN: str = "v0.0.0"


def metadata_project() -> ProjectInformation:
    result: ProjectInformation
    file_path: Path = Path(__file__)
    tmp_result: dict = {}

    paths: [Path] = [
        file_path.parent,
        file_path.parent.parent,
        file_path.parent.parent.parent,
    ]

    for pyproject_toml_dir in paths:
        pyproject_toml_file: Path = pyproject_toml_dir / "pyproject.toml"

        if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
            tmp_result = toml.load(pyproject_toml_file)

            break

    if tmp_result:
        result = ProjectInformation(
            version=tmp_result["project"]["version"], repository_url=tmp_result["project"]["repository"]
        )
    else:
        try:
            meta_info = importlib.metadata.metadata(name_package())
            result = ProjectInformation(version=meta_info["Version"], repository_url=meta_info["Home-page"])
        except:
            result = ProjectInformation(
                version=VERSION_UNKNOWN.lstrip("v"), repository_url="https://anerroroccur.ed/sorry/for/that"
            )

    return result


def version_app() -> str:
    metadata: ProjectInformation = metadata_project()
    version: str = metadata.version

    return version


def repository_url() -> str:
    metadata: ProjectInformation = metadata_project()
    url_repo: str = metadata.repository_url

    return url_repo


def repository_path() -> str:
    url_repo: str = repository_url()
    url_path: str = urlparse(url_repo).path

    return url_path


def latest_version_information() -> ReleaseLatest:
    release_info: ReleaseLatest
    repo_path: str = repository_path()
    url: str = f"https://api.github.com/repos{repo_path}/releases/latest"

    try:
        response = requests.get(url, timeout=REQUESTS_TIMEOUT_SEC)

        # A missing or renamed repository answers 404 with a body that carries no tag, which would
        # otherwise surface as an unexplained KeyError.
        response.raise_for_status()

        payload: dict = response.json()
        release_info = ReleaseLatest(version=payload["tag_name"], url=payload["html_url"], release_info=payload["body"])
    except Exception:
        release_info = ReleaseLatest(
            version=VERSION_UNKNOWN,
            url=url,
            release_info=f"Something went wrong calling {url}. Check your internet connection.",
        )

    return release_info


def name_package() -> str:
    package_name: str = __package__ or __name__

    return package_name


def is_dev_env() -> bool:
    package_name: str = name_package()
    result: bool = False

    # Check if package is running from source code == dev mode
    # If package is not running in Nuitka environment, try to import it from pip libraries.
    # If this also fails, it is dev mode.
    if "__compiled__" not in globals():
        try:
            importlib.metadata.version(package_name)
        except:
            # If package is not installed
            result = True

    return result


def name_app() -> str:
    app_name: str = name_package()
    is_dev: bool = is_dev_env()

    if is_dev:
        app_name = app_name + "-dev"

    return app_name


__name_display__ = name_app()
__version__ = version_app()


def version_parts(version: str) -> tuple[int, ...]:
    """Split a version tag into the numeric components that order it.

    Leading "v" and any pre-release or build suffix are discarded, so "v1.2.3-rc1" and "1.2.3" order
    alike. Parsing stops at the first component that does not start with a digit.

    :param version: Version tag to split.
    :return: The numeric components, empty if none could be read.
    """
    core: str = version.lstrip("vV").split("+", 1)[0].split("-", 1)[0]
    parts: list[int] = []

    for chunk in core.split("."):
        digits: str = "".join(takewhile(str.isdigit, chunk))

        if not digits:
            break

        parts.append(int(digits))

    return tuple(parts)


def version_is_newer(candidate: str, current: str) -> bool:
    """Whether `candidate` names a later version than `current`.

    An unreadable version on either side orders nowhere, so it never reports an update. That covers
    the placeholder a failed release lookup returns.

    :param candidate: Version offered as an update.
    :param current: Version currently running.
    :return: True only if `candidate` is strictly later than `current`.
    """
    parts_candidate: tuple[int, ...] = version_parts(candidate)
    parts_current: tuple[int, ...] = version_parts(current)

    if not parts_candidate or not parts_current:
        return False

    width: int = max(len(parts_candidate), len(parts_current))
    padded_candidate: tuple[int, ...] = parts_candidate + (0,) * (width - len(parts_candidate))
    padded_current: tuple[int, ...] = parts_current + (0,) * (width - len(parts_current))

    return padded_candidate > padded_current


def update_available() -> (bool, ReleaseLatest):
    """Check whether a later release than the running version is published.

    :return: Whether an update is available, and the latest release information.
    """
    latest_info: ReleaseLatest = latest_version_information()
    version_current: str = "v" + __version__

    # Without a known local version there is nothing meaningful to compare against.
    if version_current == VERSION_UNKNOWN:
        return False, latest_info

    return version_is_newer(latest_info.version, version_current), latest_info
