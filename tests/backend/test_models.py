from bspwm_display_manager.backend.models import Mode, Output, LayoutState

def test_output_current_mode_returns_the_starred_mode():
    m1 = Mode(width=1920, height=1200, rate=60.03, id="0x49", current=True, preferred=True)
    m2 = Mode(width=1920, height=1200, rate=59.88, id="0x4a", current=False, preferred=False)
    out = Output(name="eDP-1", connected=True, primary=True, edid="abc",
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0,
                 modes=[m1, m2])
    assert out.current_mode() is m1

def test_output_current_mode_none_when_no_mode_is_current():
    m1 = Mode(width=1920, height=1200, rate=60.03, id="0x49", current=False, preferred=True)
    out = Output(name="HDMI-1", connected=False, primary=False, edid=None,
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[m1])
    assert out.current_mode() is None

def test_output_preferred_mode_returns_the_plus_preferred_mode():
    m1 = Mode(width=1920, height=1200, rate=60.03, id="0x49", current=True, preferred=False)
    m2 = Mode(width=3840, height=2160, rate=59.98, id="0x4c", current=False, preferred=True)
    out = Output(name="DP-2", connected=True, primary=False, edid="xyz",
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0,
                 modes=[m1, m2])
    assert out.preferred_mode() is m2

def test_layout_state_connected_filters_disconnected_outputs():
    connected = Output(name="eDP-1", connected=True, primary=True, edid="a",
                        x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])
    disconnected = Output(name="HDMI-1", connected=False, primary=False, edid=None,
                           x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])
    state = LayoutState(outputs=[connected, disconnected])
    assert state.connected() == [connected]
