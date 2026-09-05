import pytest

from bspwm_display_manager.backend.profile import OutputSpec, Profile
from bspwm_display_manager.backend.profile_store import list_profiles, load, save


def _sample_profile(name="work"):
    return Profile(
        name=name, fingerprint="fp1", scale_percent=100,
        outputs=[OutputSpec(edid_or_pattern="eDP-*", mode=(1920, 1200), rate=60.03,
                             x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, primary=True)],
        desktop_assignment={"eDP-*": ["term"]},
        hooks=[],
    )


def test_save_then_load_round_trips(tmp_path):
    profile = _sample_profile()
    save(profile, tmp_path)
    loaded = load("work", tmp_path)
    assert loaded == profile


def test_load_missing_profile_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load("nonexistent", tmp_path)


def test_list_profiles_returns_names_sorted(tmp_path):
    save(_sample_profile("work"), tmp_path)
    save(_sample_profile("home"), tmp_path)
    assert list_profiles(tmp_path) == ["home", "work"]


def test_list_profiles_empty_dir_returns_empty_list(tmp_path):
    assert list_profiles(tmp_path) == []
