# tools/tool_polygon.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPainterPath

class CommandDrawPolygon(QUndoCommand):
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

class PolygonTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.sides = 6 # 默认6边形
        self.center_point = None
        self.ghost_poly = None
        self.state = 0 # 0: 选中心(或改边数), 1: 拉半径
        self.input_buffer = ""

    def get_reference_point(self):
        return QPointF(*self.center_point) if self.state == 1 and self.center_point else None

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.center_point = None
        self.input_buffer = ""
        self._cleanup_ghost()
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghost()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghost(self):
        if self.ghost_poly and self.ghost_poly.scene():
            self.canvas.scene().removeItem(self.ghost_poly)
        self.ghost_poly = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if self.state == 0:
            text = f"多边形: 指定中心点 [或输入边数更改(当前={self.sides})]: {self.input_buffer}"
        else:
            text = f"多边形: 指定半径: {self.input_buffer}"
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:#5bc0de; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>⬡ {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _update_preview(self):
        if self.state == 1 and hasattr(self.canvas, 'last_cursor_point'):
            class DummyEvent: pass
            self.mouseMoveEvent(DummyEvent(), self.canvas.last_cursor_point, getattr(self.canvas, 'last_snapped_angle', 0.0))

    def _generate_poly_coords(self, radius, angle_offset_deg):
        cx, cy = self.center_point
        coords = []
        angle_step = 360.0 / self.sides
        for i in range(self.sides):
            a = math.radians(angle_offset_deg + i * angle_step)
            coords.append((cx + radius * math.cos(a), cy - radius * math.sin(a)))
        return coords

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                self.center_point = (final_point.x(), final_point.y())
                self.state = 1
                self.input_buffer = ""
                self.ghost_poly = QGraphicsPathItem()
                pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
                pen.setCosmetic(True)
                self.ghost_poly.setPen(pen)
                self.canvas.scene().addItem(self.ghost_poly)
                self._update_hud()
            elif self.state == 1:
                r = 0.0
                if self.input_buffer:
                    try: r = float(self.input_buffer)
                    except ValueError: pass
                
                cx, cy = self.center_point
                if r <= 0: r = math.hypot(final_point.x() - cx, final_point.y() - cy)
                angle_deg = math.degrees(math.atan2(-(final_point.y() - cy), final_point.x() - cx))
                if r > 0.01: self._finalize_polygon(r, angle_deg)
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state == 1:
                self.state = 0
                self.center_point = None
                self.input_buffer = ""
                self._cleanup_ghost()
                self._update_hud()
            else:
                self.deactivate()
                self.canvas.switch_tool("选择")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        if self.state == 1 and self.ghost_poly:
            cx, cy = self.center_point
            r = math.hypot(final_point.x() - cx, final_point.y() - cy)
            if self.input_buffer:
                try: r = float(self.input_buffer)
                except ValueError: pass
            
            angle_deg = math.degrees(math.atan2(-(final_point.y() - cy), final_point.x() - cx))
            coords = self._generate_poly_coords(r, angle_deg)
            
            path = QPainterPath()
            if coords:
                path.moveTo(QPointF(*coords[0]))
                for pt in coords[1:]: path.lineTo(QPointF(*pt))
                path.lineTo(QPointF(*coords[0]))
            self.ghost_poly.setPath(path)
        return True

    def keyPressEvent(self, event):
        key = event.text()
        if key.isdigit() or key == '.':
            self.input_buffer += key
            self._update_hud()
            self._update_preview()
            return True
        elif event.key() == Qt.Key.Key_Backspace:
            self.input_buffer = self.input_buffer[:-1]
            self._update_hud()
            self._update_preview()
            return True
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.input_buffer:
                try:
                    val = float(self.input_buffer)
                    if self.state == 0:
                        if int(val) >= 3: self.sides = int(val)
                        self.input_buffer = ""
                        self._update_hud()
                    elif self.state == 1 and val > 0:
                        fp = self.canvas.last_cursor_point
                        angle_deg = math.degrees(math.atan2(-(fp.y() - self.center_point[1]), fp.x() - self.center_point[0]))
                        self._finalize_polygon(val, angle_deg)
                except ValueError: pass
            return True
        elif event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def _finalize_polygon(self, radius, angle_deg):
        coords = self._generate_poly_coords(radius, angle_deg)
        new_item = SmartPolygonItem(coords)
        pen = QPen(self.canvas.color_manager.get_color(), 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        new_item.setPen(pen)
        self.canvas.layer_manager.apply_current_layer_props(new_item)
        self.canvas.undo_stack.push(CommandDrawPolygon(self.canvas.scene(), new_item))
        
        self.state = 0
        self.center_point = None
        self.input_buffer = ""
        self._cleanup_ghost()
        self._update_hud()