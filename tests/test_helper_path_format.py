"""Characterisation tests for `format_str_media`.

Each case pins the value the formatter returns today, including the fallbacks: an unknown
placeholder, a placeholder that does not apply to the given media type, and a media object that
raises while being read. Together they cover every branch of the placeholder table.
"""

import pytest
from tidalapi import Album, Mix, Playlist, Track, UserPlaylist, Video
from tidalapi.artist import Role

from tidal_dl_ng.helper.path import format_str_media


class _Artist:
    def __init__(self, name: str, main: bool = True) -> None:
        self.name = name
        self.roles = [Role.main] if main else []


def _make(cls, **attributes):
    """Build a media instance without running its initialiser, so `isinstance` still matches.

    Several tidalapi attributes are read-only properties. Each instance therefore gets its own
    throwaway subclass, where a class attribute can shadow such a property.
    """
    subclass = type("Fake" + cls.__name__, (cls,), {})
    instance = object.__new__(subclass)

    for key, value in attributes.items():
        try:
            setattr(instance, key, value)
        except AttributeError:
            setattr(subclass, key, value)

    return instance


def _album(**overrides):
    attributes = {
        "name": "Album Name",
        "id": 42,
        "num_tracks": 12,
        "num_volumes": 1,
        "duration": 3725,
        "year": 1999,
        "explicit": True,
        "artists": [_Artist("Album Artist")],
    }
    attributes.update(overrides)

    return _make(Album, **attributes)


def _track(**overrides):
    attributes = {
        "name": "Track Name",
        "full_name": "Track Name (Live)",
        "id": 7,
        "track_num": 3,
        "volume_num": 1,
        "duration": 185,
        "explicit": False,
        "isrc": "ABCDE1234567",
        "media_metadata_tags": ["LOSSLESS", "HIRES_LOSSLESS"],
        "artists": [_Artist("First"), _Artist("Second")],
        "album": _album(),
    }
    attributes.update(overrides)

    return _make(Track, **attributes)


def _video(**overrides):
    attributes = {
        "name": "Video Name",
        "id": 9,
        "track_num": 2,
        "volume_num": 1,
        "duration": 245,
        "explicit": True,
        "video_quality": "MP4_1080P",
        "artists": [_Artist("Video Artist")],
        "album": _album(num_tracks=5, num_volumes=2),
    }
    attributes.update(overrides)

    return _make(Video, **attributes)


@pytest.mark.parametrize(
    ("placeholder", "media", "expected"),
    [
        ("artist_name", _track(), "First, Second"),
        ("album_artist", _track(), "Album Artist"),
        ("album_artist", _album(), "Album Artist"),
        ("track_title", _track(), "Track Name (Live)"),
        ("mix_name", _make(Mix, title="Mix Title"), "Mix Title"),
        ("playlist_name", _make(Playlist, name="Playlist Name"), "Playlist Name"),
        ("playlist_name", _make(UserPlaylist, name="User Playlist"), "User Playlist"),
        ("album_title", _album(), "Album Name"),
        ("album_title", _track(), "Album Name"),
        ("album_track_num", _track(), "03"),
        ("album_num_tracks", _track(), "12"),
        ("track_id", _track(), "7"),
        ("playlist_id", _make(Playlist, id="pl-1"), "pl-1"),
        ("album_id", _album(), "42"),
        ("album_id", _track(), "42"),
        ("track_duration_seconds", _track(), "185"),
        ("track_duration_minutes", _track(), "3:05"),
        ("album_duration_seconds", _album(), "3725"),
        ("album_duration_minutes", _album(), "62:05"),
        ("playlist_duration_seconds", _album(), "3725"),
        ("playlist_duration_minutes", _album(), "62:05"),
        ("album_year", _album(), "1999"),
        ("album_year", _track(), "1999"),
        ("video_quality", _video(), "MP4_1080P"),
        ("track_quality", _track(), "LOSSLESS, HIRES_LOSSLESS"),
        ("track_explicit", _track(), ""),
        ("track_explicit", _video(), " (Explicit)"),
        ("album_explicit", _album(), " (Explicit)"),
        ("album_explicit", _album(explicit=False), ""),
        ("album_num_volumes", _album(), "1"),
        ("track_volume_num", _track(), "1"),
        ("track_volume_num_optional", _track(), ""),
        ("track_volume_num_optional", _video(), "1"),
        ("track_volume_num_optional_CD", _track(), ""),
        ("track_volume_num_optional_CD", _video(), "CD1"),
        ("isrc", _track(), "ABCDE1234567"),
    ],
)
def test_placeholder_is_replaced(placeholder, media, expected):
    assert format_str_media(placeholder, media) == expected


def test_album_track_num_pads_to_the_requested_minimum():
    assert format_str_media("album_track_num", _track(), album_track_num_pad_min=4) == "0003"


def test_album_track_num_keeps_the_computed_width_when_wider_than_the_minimum():
    track = _track(track_num=7, album=_album(num_tracks=150))

    assert format_str_media("album_track_num", track, album_track_num_pad_min=2) == "007"


def test_unknown_placeholder_is_returned_unchanged():
    assert format_str_media("not_a_placeholder", _track()) == "not_a_placeholder"


def test_placeholder_that_does_not_apply_is_returned_unchanged():
    assert format_str_media("mix_name", _track()) == "mix_name"
    assert format_str_media("video_quality", _track()) == "video_quality"
    assert format_str_media("isrc", _album()) == "isrc"


def test_a_raising_attribute_falls_back_to_the_placeholder():
    class _Exploding(Track):
        @property
        def duration(self):
            raise RuntimeError("boom")

    exploding = _make(_Exploding)

    assert format_str_media("track_duration_minutes", exploding) == "track_duration_minutes"


def test_artist_name_without_a_populated_artists_list_returns_the_placeholder():
    """Track declares `artists` at class level, so the `artist` fallback branch is unreachable.

    With nothing assigned, the join raises and the placeholder is handed back untouched.
    """
    track = _make(Track, artist=_Artist("Solo Artist"))

    assert format_str_media("artist_name", track) == "artist_name"
