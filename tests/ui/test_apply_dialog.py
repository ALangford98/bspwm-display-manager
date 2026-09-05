from bspwm_display_manager.ui.apply_dialog import ApplyConfirmDialog, remaining_seconds


def test_remaining_seconds_counts_down_to_zero():
    assert remaining_seconds(0, 15) == 15
    assert remaining_seconds(5, 15) == 10
    assert remaining_seconds(20, 15) == 0


def test_label_reflects_elapsed_time(qapp):
    dialog = ApplyConfirmDialog(timeout_seconds=15)
    dialog._elapsed = 5
    dialog._update_label()
    assert "10s" in dialog.label.text()


def test_confirm_marks_confirmed_and_accepts(qapp):
    dialog = ApplyConfirmDialog(timeout_seconds=15)
    dialog._confirm()
    assert dialog.was_confirmed() is True
    assert dialog.result() == dialog.DialogCode.Accepted


def test_ticking_past_the_timeout_rejects_without_confirming(qapp):
    dialog = ApplyConfirmDialog(timeout_seconds=2)
    dialog._tick()
    dialog._tick()
    assert dialog.was_confirmed() is False
    assert dialog.result() == dialog.DialogCode.Rejected
