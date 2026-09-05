from bspwm_display_manager.backend.profile import OutputSpec, Profile


def _sample_profile():
    return Profile(
        name="work",
        fingerprint="abc123",
        scale_percent=150,
        outputs=[
            OutputSpec(edid_or_pattern="edid-dell", mode=(2560, 1440), rate=59.95,
                       x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, primary=False),
            OutputSpec(edid_or_pattern="eDP-*", mode=(1920, 1200), rate=60.03,
                       x=1600, y=1440, rotation="normal", scale_x=1.0, scale_y=1.0, primary=True),
        ],
        desktop_assignment={"eDP-*": ["term", "chat", "media"], "edid-dell": ["pm", "office", "settings"]},
        hooks=["setsid -f bspbar"],
    )


def test_profile_round_trips_through_dict():
    profile = _sample_profile()
    restored = Profile.from_dict(profile.to_dict())
    assert restored == profile


def test_output_spec_round_trips_mode_as_a_list_in_json_safe_dict():
    profile = _sample_profile()
    d = profile.to_dict()
    assert d["outputs"][0]["mode"] == [2560, 1440]
