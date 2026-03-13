# tools/tool_polyline.py
from tools.base_tool import BaseTool
from core.core_items import SmartPolylineItem
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand

class CommandCreatePolyline(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__()
        self.scene = scene
        self.item = item
    def redo(self):
        if self.item not in self.scene.items(): self.scene.addItem(self.item)
    def undo(self):
        if self.item in self.scene.items():
            self.item.setSelected(False)
            self.scene.removeItem(self.item)

class PolylineTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.points = []
        self.temp_lines = []
        self.preview_line = None

    def get_reference_point(self):
        return QPointF(*self.points[-1]) if self.points else None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._cleanup_temp_items()
        self._update_hud()

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        for line in self.temp_lines:
            if line.scene(): self.canvas.scene().removeItem(line)
        if self.preview_line and self.preview_line.scene():
            self.canvas.scene().removeItem(self.preview_line)
        self.temp_lines.clear()
        self.preview_line = None
        self.points.clear()

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if not self.points: text, color = "多段线: 请指定起点", "#5bc0de"
        else: text, color = "多段线: 请指定下一点 (回车 / 鼠标右键 结束绘制)", "#5cb85c"
        self.canvas.hud_polar_info.setHtml(f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>📈 {text}</div>")
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            pt = (final_point.x(), final_point.y())
            if not self.points:
                self.canvas.scene().clearSelection()
                self.points.append(pt)
                self.preview_line = QGraphicsLineItem()
                pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.preview_line.setPen(pen)
                self.canvas.scene().addItem(self.preview_line)
            else:
                self.points.append(pt)
                fixed_line = QGraphicsLineItem(QLineF(self.points[-2][0], self.points[-2][1], pt[0], pt[1]))
                pen = QPen(QColor(255, 255, 255, 150), 1)
                pen.setCosmetic(True)
                fixed_line.setPen(pen)
                self.canvas.scene().addItem(fixed_line)
                self.temp_lines.append(fixed_line)
            self._update_hud()
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            if len(self.points) > 1:
                final_item = SmartPolylineItem(list(self.points))
                final_item.setPen(QPen(self.canvas.color_manager.get_color(), 1, Qt.PenStyle.SolidLine))
                final_item.pen().setCosmetic(True)
                self.canvas.layer_manager.apply_current_layer_props(final_item)
                self.canvas.undo_stack.push(CommandCreatePolyline(self.canvas.scene(), final_item))
            self._cleanup_temp_items()
            self.canvas.switch_tool("选择")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        if self.points and self.preview_line:
            self.preview_line.setLine(QLineF(self.points[-1][0], self.points[-1][1], final_point.x(), final_point.y()))
        return True

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if len(self.points) > 1:
                final_item = SmartPolylineItem(list(self.points))
                final_item.setPen(QPen(self.canvas.color_manager.get_color(), 1, Qt.PenStyle.SolidLine))
                final_item.pen().setCosmetic(True)
                self.canvas.layer_manager.apply_current_layer_props(final_item)
                self.canvas.undo_stack.push(CommandCreatePolyline(self.canvas.scene(), final_item))
            self._cleanup_temp_items()
            self.canvas.switch_tool("选择")
            return True
        elif event.key() == Qt.Key.Key_Escape:
            self._cleanup_temp_items()
            if hasattr(self.canvas, '_cleanup_tracking_huds'): self.canvas._cleanup_tracking_huds()
            return True
        return False