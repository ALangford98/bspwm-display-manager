from bspwm_display_manager.ui.snap import Rect, compute_snap


def test_snaps_left_edge_to_others_right_edge_within_threshold():
    dragged = Rect(x=105, y=0, w=100, h=100)
    other = Rect(x=0, y=0, w=100, h=100)
    assert compute_snap(dragged, [other], threshold=10) == (100, 0)


def test_no_snap_when_outside_threshold():
    dragged = Rect(x=150, y=0, w=100, h=100)
    other = Rect(x=0, y=0, w=100, h=100)
    assert compute_snap(dragged, [other], threshold=10) == (150, 0)


def test_snaps_top_edge_to_others_bottom_edge():
    dragged = Rect(x=0, y=105, w=100, h=100)
    other = Rect(x=0, y=0, w=100, h=100)
    assert compute_snap(dragged, [other], threshold=10) == (0, 100)


def test_x_and_y_snap_independently():
    dragged = Rect(x=103, y=203, w=50, h=50)
    other = Rect(x=0, y=0, w=100, h=100)
    x, y = compute_snap(dragged, [other], threshold=10)
    assert x == 100
    assert y == 203


def test_picks_nearest_candidate_among_multiple_others():
    dragged = Rect(x=52, y=0, w=50, h=50)
    near = Rect(x=0, y=0, w=50, h=50)
    far = Rect(x=200, y=0, w=50, h=50)
    x, _ = compute_snap(dragged, [near, far], threshold=10)
    assert x == 50
