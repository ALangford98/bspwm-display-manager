from __future__ import annotations

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
)

from bspwm_display_manager.backend.models import Output
from bspwm_display_manager.ui.snap import Rect, compute_snap

SCALE_DOWN = 10  # 1 scene unit == 10 real pixels, keeps a 4K desktop on-screen
SNAP_THRESHOLD = 15  # scene units


class MonitorItem(QGraphicsRectItem):
    def __init__(self, output_name: str, w: float, h: float):
        super().__init__(0, 0, w, h)
        self.output_name = output_name
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            # Rounded to int here for the snap-candidate arithmetic only
            # (snapping is threshold-based, not exact); real-pixel
            # positions stay float scene coordinates everywhere else so
            # positions() can round-trip a value that isn't a multiple
            # of SCALE_DOWN.
            others = [
                Rect(round(item.x()), round(item.y()), round(item.rect().width()), round(item.rect().height()))
                for item in self.scene().items()
                if isinstance(item, MonitorItem) and item is not self
            ]
            dragged = Rect(round(value.x()), round(value.y()),
                            round(self.rect().width()), round(self.rect().height()))
            snapped_x, snapped_y = compute_snap(dragged, others, SNAP_THRESHOLD)
            value.setX(snapped_x)
            value.setY(snapped_y)
        return super().itemChange(change, value)


class DisplayCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

    def set_outputs(self, outputs: list[Output]) -> None:
        self._scene.clear()
        for out in outputs:
            mode = out.current_mode() or out.preferred_mode()
            if mode is None:
                continue
            # True (float) division, not floor division: a position or
            # size that isn't a multiple of SCALE_DOWN must still
            # round-trip exactly through positions() below. Floor
            # division would discard the remainder permanently.
            item = MonitorItem(out.name, mode.width / SCALE_DOWN, mode.height / SCALE_DOWN)
            item.setPos(out.x / SCALE_DOWN, out.y / SCALE_DOWN)
            self._scene.addItem(item)

    def positions(self) -> dict[str, tuple[int, int]]:
        result = {}
        for item in self._scene.items():
            if isinstance(item, MonitorItem):
                # round(), not int(): item.x()/y() are floats and binary
                # floating point can't represent every decimal exactly
                # (e.g. 10.7), but the error is many orders of magnitude
                # smaller than 0.5, so round() always recovers the exact
                # original integer pixel value.
                result[item.output_name] = (round(item.x() * SCALE_DOWN), round(item.y() * SCALE_DOWN))
        return result
