import math
import os
import pathlib
import posixpath
import re
import sys
from collections.abc import Callable, Generator
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from pathvalidate import sanitize_filename, sanitize_filepath
from pathvalidate.error import ValidationError
from tidalapi import Album, Mix, Playlist, Track, UserPlaylist, Video
from tidalapi.media import AudioExtensions

from tidal_dl_ng import __name_display__
from tidal_dl_ng.constants import UNIQUIFY_THRESHOLD, MediaType
from tidal_dl_ng.helper.tidal import name_builder_album_artist, name_builder_artist, name_builder_title


def path_home() -> str:
    if "XDG_CONFIG_HOME" in os.environ:
        return os.environ["XDG_CONFIG_HOME"]
    elif "HOME" in os.environ:
        return os.environ["HOME"]
    elif "HOMEDRIVE" in os.environ and "HOMEPATH" in os.environ:
        return os.path.join(os.environ["HOMEDRIVE"], os.environ["HOMEPATH"])
    else:
        return os.path.abspath("./")


def path_config_base() -> str:
    # https://wiki.archlinux.org/title/XDG_Base_Directory
    # X11 workaround: If user specified config path is set, do not point to "~/.config"
    path_user_custom: str = os.environ.get("XDG_CONFIG_HOME", "")
    path_config: str = ".config" if not path_user_custom else ""
    path_base: str = os.path.join(path_home(), path_config, __name_display__)

    return path_base


def path_file_log() -> str:
    return os.path.join(path_config_base(), "app.log")


def path_file_token() -> str:
    return os.path.join(path_config_base(), "token.json")


def path_file_settings() -> str:
    return os.path.join(path_config_base(), "settings.json")


def format_path_media(
    fmt_template: str, media: Track | Album | Playlist | UserPlaylist | Video | Mix, album_track_num_pad_min: int = 0
) -> str:
    result = fmt_template

    # Search track format template for placeholder.
    regex = r"\{(.+?)\}"
    matches = re.finditer(regex, fmt_template, re.MULTILINE)

    for _matchNum, match in enumerate(matches, start=1):
        template_str = match.group()
        result_fmt = format_str_media(match.group(1), media, album_track_num_pad_min)

        if result_fmt != match.group(1):
            value = sanitize_filename(result_fmt)
            result = result.replace(template_str, value)

    return result


MediaAny = Track | Album | Playlist | UserPlaylist | Video | Mix


def _duration_minutes(seconds: int) -> str:
    minutes, remainder = divmod(seconds, 60)

    return f"{minutes:01d}:{remainder:02d}"


def _explicit_suffix(media: MediaAny) -> str:
    return " (Explicit)" if media.explicit else ""


def _album_of(media: Track | Video) -> Album | None:
    return media.album if hasattr(media, "album") else None


def _num_volumes_of(media: Track | Video) -> int:
    album = _album_of(media)

    return album.num_volumes if album is not None else 1


def _num_tracks_of(media: Track | Video) -> int:
    album = _album_of(media)

    return album.num_tracks if album is not None else 1


def _fmt_artist_name(media: MediaAny, pad_min: int) -> str | None:
    if not isinstance(media, Track | Video):
        return None

    if hasattr(media, "artists"):
        return name_builder_artist(media)

    if hasattr(media, "artist"):
        return media.artist.name

    return None


def _fmt_track_title(media: MediaAny, pad_min: int) -> str | None:
    return name_builder_title(media) if isinstance(media, Track | Video) else None


def _fmt_mix_name(media: MediaAny, pad_min: int) -> str | None:
    return media.title if isinstance(media, Mix) else None


def _fmt_playlist_name(media: MediaAny, pad_min: int) -> str | None:
    return media.name if isinstance(media, Playlist | UserPlaylist) else None


def _fmt_album_title(media: MediaAny, pad_min: int) -> str | None:
    if isinstance(media, Album):
        return media.name

    if isinstance(media, Track):
        return media.album.name

    return None


def _fmt_album_track_num(media: MediaAny, pad_min: int) -> str | None:
    if not isinstance(media, Track | Video):
        return None

    count_digits: int = int(math.log10(_num_tracks_of(media))) + 1

    return str(media.track_num).zfill(max(count_digits, pad_min))


def _fmt_album_num_tracks(media: MediaAny, pad_min: int) -> str | None:
    return str(_num_tracks_of(media)) if isinstance(media, Track | Video) else None


def _fmt_track_id(media: MediaAny, pad_min: int) -> str | None:
    return str(media.id) if isinstance(media, Track | Video) else None


def _fmt_playlist_id(media: MediaAny, pad_min: int) -> str | None:
    return str(media.id) if isinstance(media, Playlist) else None


def _fmt_album_id(media: MediaAny, pad_min: int) -> str | None:
    if isinstance(media, Album):
        return str(media.id)

    if isinstance(media, Track):
        return str(media.album.id)

    return None


def _fmt_track_duration_seconds(media: MediaAny, pad_min: int) -> str | None:
    return str(media.duration) if isinstance(media, Track | Video) else None


def _fmt_track_duration_minutes(media: MediaAny, pad_min: int) -> str | None:
    return _duration_minutes(media.duration) if isinstance(media, Track | Video) else None


def _fmt_album_duration_seconds(media: MediaAny, pad_min: int) -> str | None:
    return str(media.duration) if isinstance(media, Album) else None


def _fmt_album_duration_minutes(media: MediaAny, pad_min: int) -> str | None:
    return _duration_minutes(media.duration) if isinstance(media, Album) else None


def _fmt_album_year(media: MediaAny, pad_min: int) -> str | None:
    if isinstance(media, Album):
        return str(media.year)

    if isinstance(media, Track):
        return str(media.album.year)

    return None


def _fmt_video_quality(media: MediaAny, pad_min: int) -> str | None:
    return media.video_quality if isinstance(media, Video) else None


def _fmt_track_quality(media: MediaAny, pad_min: int) -> str | None:
    return ", ".join(tag for tag in media.media_metadata_tags) if isinstance(media, Track) else None


def _fmt_track_explicit(media: MediaAny, pad_min: int) -> str | None:
    return _explicit_suffix(media) if isinstance(media, Track | Video) else None


def _fmt_album_explicit(media: MediaAny, pad_min: int) -> str | None:
    return _explicit_suffix(media) if isinstance(media, Album) else None


def _fmt_album_num_volumes(media: MediaAny, pad_min: int) -> str | None:
    return str(media.num_volumes) if isinstance(media, Album) else None


def _fmt_track_volume_num(media: MediaAny, pad_min: int) -> str | None:
    return str(media.volume_num) if isinstance(media, Track | Video) else None


def _fmt_track_volume_num_optional(media: MediaAny, pad_min: int) -> str | None:
    if not isinstance(media, Track | Video):
        return None

    return "" if _num_volumes_of(media) == 1 else str(media.volume_num)


def _fmt_track_volume_num_optional_cd(media: MediaAny, pad_min: int) -> str | None:
    if not isinstance(media, Track | Video):
        return None

    return "" if _num_volumes_of(media) == 1 else f"CD{media.volume_num!s}"


def _fmt_isrc(media: MediaAny, pad_min: int) -> str | None:
    return media.isrc if isinstance(media, Track) else None


# Playlist durations deliberately read from an Album, matching the placeholders' original behaviour.
_MEDIA_FORMATTERS: dict[str, Callable[[MediaAny, int], str | None]] = {
    "artist_name": _fmt_artist_name,
    "album_artist": lambda media, pad_min: name_builder_album_artist(media),
    "track_title": _fmt_track_title,
    "mix_name": _fmt_mix_name,
    "playlist_name": _fmt_playlist_name,
    "album_title": _fmt_album_title,
    "album_track_num": _fmt_album_track_num,
    "album_num_tracks": _fmt_album_num_tracks,
    "track_id": _fmt_track_id,
    "playlist_id": _fmt_playlist_id,
    "album_id": _fmt_album_id,
    "track_duration_seconds": _fmt_track_duration_seconds,
    "track_duration_minutes": _fmt_track_duration_minutes,
    "album_duration_seconds": _fmt_album_duration_seconds,
    "album_duration_minutes": _fmt_album_duration_minutes,
    "playlist_duration_seconds": _fmt_album_duration_seconds,
    "playlist_duration_minutes": _fmt_album_duration_minutes,
    "album_year": _fmt_album_year,
    "video_quality": _fmt_video_quality,
    "track_quality": _fmt_track_quality,
    "track_explicit": _fmt_track_explicit,
    "album_explicit": _fmt_album_explicit,
    "album_num_volumes": _fmt_album_num_volumes,
    "track_volume_num": _fmt_track_volume_num,
    "track_volume_num_optional": _fmt_track_volume_num_optional,
    "track_volume_num_optional_CD": _fmt_track_volume_num_optional_cd,
    "isrc": _fmt_isrc,
}


def format_str_media(name: str, media: MediaAny, album_track_num_pad_min: int = 0) -> str:
    """Resolve a filename placeholder against a media item.

    An unknown placeholder, one that does not apply to this media type, or a lookup that raises all
    yield the placeholder unchanged, so the caller can decide how to handle the gap.

    :param name: Placeholder to resolve.
    :param media: Media item to read the value from.
    :param album_track_num_pad_min: Minimum width to zero-pad the album track number to.
    :return: The resolved value, or `name` when it cannot be resolved.
    """
    formatter = _MEDIA_FORMATTERS.get(name)

    if formatter is None:
        return name

    try:
        result = formatter(media, album_track_num_pad_min)
    except Exception as e:
        # TODO: Implement better exception logging.
        print(e)

        return name

    return name if result is None else result


def get_format_template(
    media: Track | Album | Playlist | UserPlaylist | Video | Mix | MediaType, settings
) -> str | bool:
    result = False

    if isinstance(media, Track) or media == MediaType.TRACK:
        result = settings.data.format_track
    elif isinstance(media, Album) or media == MediaType.ALBUM or media == MediaType.ARTIST:
        result = settings.data.format_album
    elif isinstance(media, Playlist | UserPlaylist) or media == MediaType.PLAYLIST:
        result = settings.data.format_playlist
    elif isinstance(media, Mix) or media == MediaType.MIX:
        result = settings.data.format_mix
    elif isinstance(media, Video) or media == MediaType.VIDEO:
        result = settings.data.format_video

    return result


def path_file_sanitize(path_file: pathlib.Path, adapt: bool = False, uniquify: bool = True) -> pathlib.Path:
    path_parent = path_file.parent  # Keep the original directory structure
    file_stem = path_file.stem  # Filename without extension
    file_ext = path_file.suffix  # Keep the correct extension (.m4a, .flac)

    # Sanitize the filename (excluding the extension)
    sanitized_filename = sanitize_filename(
        file_stem, replacement_text=" ", validate_after_sanitize=True, platform="auto"
    )

    # Rebuild the sanitized path
    sanitized_path = path_parent / f"{sanitized_filename}{file_ext}"

    # Ensure full path sanitization
    try:
        sanitized_path = sanitize_filepath(
            sanitized_path, replacement_text=" ", validate_after_sanitize=True, platform="auto"
        )
    except ValidationError:
        if adapt:
            sanitized_path = pathlib.Path.home() / sanitized_path.name  # Fallback to home directory
        else:
            raise

    return sanitized_path


def file_unique_suffix(path_file: pathlib.Path, seperator: str = "_") -> str:
    threshold_zfill: int = len(str(UNIQUIFY_THRESHOLD))
    count: int = 0
    path_file_tmp: pathlib.Path = deepcopy(path_file)
    unique_suffix: str = ""

    while check_file_exists(path_file_tmp) and count < UNIQUIFY_THRESHOLD:
        count += 1
        unique_suffix = seperator + str(count).zfill(threshold_zfill)
        path_file_tmp = path_file.parent / (path_file.stem + unique_suffix + path_file.suffix)

    return unique_suffix


def check_file_exists(path_file: pathlib.Path, extension_ignore: bool = False) -> bool:
    if extension_ignore:
        path_file_stem: str = pathlib.Path(path_file).stem
        path_parent: pathlib.Path = pathlib.Path(path_file).parent
        path_files: [str] = []

        for extension in AudioExtensions:
            path_files.append(str(path_parent.joinpath(path_file_stem + extension)))
    else:
        path_files: [str] = [path_file]

    result = bool(sum([[True] if os.path.isfile(_file) else [] for _file in path_files], []))

    return result


def resource_path(relative_path: str) -> str:
    """Resolve a bundled resource path for source checkouts and compiled builds alike.

    PyInstaller extracts data files to ``sys._MEIPASS``. Nuitka standalone builds place them next to
    the executable, which is the only reliable anchor: a bundle launched from Finder inherits ``/``
    as its working directory, so a relative lookup would silently miss every resource.

    :param relative_path: Resource path relative to the project root.
    :return: Absolute path to the resource.
    """
    base_path: Path

    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    elif "__compiled__" in globals() or getattr(sys, "frozen", False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent.parent.parent

    return str(base_path / relative_path)


def url_to_filename(url: str) -> str:
    """Return basename corresponding to url.
    >>> print(url_to_filename('http://example.com/path/to/file%C3%80?opt=1'))
    fileÀ
    >>> print(url_to_filename('http://example.com/slash%2fname')) # '/' in name
    Taken from https://gist.github.com/zed/c2168b9c52b032b5fb7d
    Traceback (most recent call last):
    ...
    ValueError
    """
    urlpath: str = urlsplit(url).path
    basename: str = posixpath.basename(unquote(urlpath))

    if os.path.basename(basename) != basename or unquote(posixpath.basename(urlpath)) != basename:
        raise ValueError  # reject '%2f' or 'dir%5Cbasename.ext' on Windows

    return basename


def receding_path(p: pathlib.Path) -> Generator[Path | Any, Any, None]:
    while str(p) != p.root:
        yield p

        p = p.parent
