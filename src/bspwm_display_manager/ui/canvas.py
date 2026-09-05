from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
)

from bspwm_display_manager.backend.models import Output
from bspwm_display_manager.ui.snap import Rect, compute_snap

SCALE_DOWN = 10  # 1 scene unit == 10 real pixels, keeps a 4K desktop on-screen
SNAP_THRESHOLD = 15  # scene units


class MonitorItem(QGraphicsRectItem):
    def __init__(self, output_name: str, w: int, h: int):
        super().__init__(0, 0, w, h)
        self.output_name = output_name
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            others = [
                Rect(int(item.x()), int(item.y()), int(item.rect().width()), int(item.rect().height()))
                for item in self.scene().items()
                if isinstance(item, MonitorItem) and item is not self
            ]
            dragged = Rect(int(value.x()), int(value.y()),
                            int(self.rect().width()), int(self.rect().height()))
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
            item = MonitorItem(out.name, mode.width // SCALE_DOWN, mode.height // SCALE_DOWN)
            item.setPos(out.x // SCALE_DOWN, out.y // SCALE_DOWN)
            self._scene.addItem(item)

    def positions(self) -> dict[str, tuple[int, int]]:
        result = {}
        for item in self._scene.items():
            if isinstance(item, MonitorItem):
                result[item.output_name] = (int(item.x()) * SCALE_DOWN, int(item.y()) * SCALE_DOWN)
        return result
