from bspwm_display_manager.ui.desktop_panel import DesktopAssignmentPanel


def test_load_assignment_populates_list_for_selected_monitor(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1", "DP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat", "media"], "DP-1": ["pm"]})
    panel.monitor_combo.setCurrentText("eDP-1")
    names = [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]
    assert names == ["term", "chat", "media"]


def test_add_desktop_appends_to_current_monitor(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term"]})
    panel.name_input.setText("chat")
    panel._add_desktop()
    assert panel.assignment()["eDP-1"] == ["term", "chat"]


def test_remove_selected_deletes_the_current_row(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat"]})
    panel.list_widget.setCurrentRow(0)
    panel._remove_selected()
    assert panel.assignment()["eDP-1"] == ["chat"]


def test_move_selected_swaps_order_and_keeps_selection_on_the_moved_item(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat", "media"]})
    panel.list_widget.setCurrentRow(0)
    panel._move_selected(1)
    assert panel.assignment()["eDP-1"] == ["chat", "term", "media"]
    assert panel.list_widget.currentRow() == 1


def test_move_selected_at_the_boundary_is_a_no_op(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat"]})
    panel.list_widget.setCurrentRow(0)
    panel._move_selected(-1)
    assert panel.assignment()["eDP-1"] == ["term", "chat"]


def test_switching_monitor_shows_that_monitors_own_list(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1", "DP-1"])
    panel.load_assignment({"eDP-1": ["term"], "DP-1": ["pm", "office"]})
    panel.monitor_combo.setCurrentText("DP-1")
    names = [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]
    assert names == ["pm", "office"]
