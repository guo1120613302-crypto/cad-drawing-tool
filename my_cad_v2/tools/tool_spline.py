# tools/tool_spline.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartSplineItem
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPainterPath

class CommandDrawSpline(QUndoCommand):
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

class SplineTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.points = []
        self.preview_item = None
        self.input_mode = "length"
        self.length_buffer = ""
        self.angle_buffer = ""
        self.current_draw_angle = 0.0

    def get_reference_point(self):
        return QPointF(*self.points[-1]) if self.points else None

    def get_input_buffer(self):
        return self.length_buffer if self.input_mode == "length" else self.angle_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._cleanup_temp_items()

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        if self.preview_item and self.preview_item.scene():
            self.canvas.scene().removeItem(self.preview_item)
        self.preview_item = None
        self.points.clear()
        self.length_buffer = ""
        self.angle_buffer = ""
        self.input_mode = "length"

    def _build_spline_path(self, pts):
        path = QPainterPath()
        if not pts: return path
        path.moveTo(QPointF(*pts[0]))
        if len(pts) == 1: return path
        if len(pts) == 2:
            path.lineTo(QPointF(*pts[1]))
            return path
            
        # Catmull-Rom 转 三次贝塞尔曲线
        for i in range(len(pts) - 1):
            p0 = pts[i - 1] if i > 0 else pts[i]
            p1 = pts[i]
            p2 = pts[i + 1]
            p3 = pts[i + 2] if i < len(pts) - 2 else pts[i + 1]

            c1x = p1[0] + (p2[0] - p0[0]) / 6.0
            c1y = p1[1] + (p2[1] - p0[1]) / 6.0
            c2x = p2[0] - (p3[0] - p1[0]) / 6.0
            c2y = p2[1] - (p3[1] - p1[1]) / 6.0

            path.cubicTo(QPointF(c1x, c1y), QPointF(c2x, c2y), QPointF(*p2))
        return path

    def _update_preview(self, final_point):
        if not self.points: return
        
        pts = list(self.points)
        sx, sy = self.points[-1]
        
        # 融入输入缓冲区逻辑
        if self.length_buffer or self.angle_buffer:
            try:
                dist = float(self.length_buffer) if self.length_buffer else math.hypot(final_point.x() - sx, final_point.y() - sy)
                ang = float(self.angle_buffer) if self.angle_buffer else self.current_draw_angle
                # 假设是在下半区需要反转数学角度
                is_lower = final_point.y() > sy
                if self.angle_buffer and is_lower: ang = (360 - ang) % 360
                
                rad = math.radians(ang)
                nx = sx + dist * math.cos(rad)
                ny = sy - dist * math.sin(rad)
                pts.append((nx, ny))
            except ValueError:
                pts.append((final_point.x(), final_point.y()))
        else:
            pts.append((final_point.x(), final_point.y()))
            
        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            self.preview_item.setPen(pen)
            self.canvas.scene().addItem(self.preview_item)
            
        self.preview_item.setPath(self._build_spline_path(pts))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.points: self.canvas.scene().clearSelection()
            self.points.append((final_point.x(), final_point.y()))
            self.length_buffer = ""
            self.angle_buffer = ""
            self.input_mode = "length"
            self._update_preview(final_point)
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self._finalize_spline()
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.points:
            p1 = self.points[-1]
            is_lower = final_point.y() > p1[1]
            self.current_draw_angle = (360 - snapped_angle) % 360 if is_lower else snapped_angle
        else:
            self.current_draw_angle = snapped_angle
            
        self._update_preview(final_point)
        return True

    def keyPressEvent(self, event):
        if not self.points: return False
        
        if event.key() == Qt.Key.Key_Tab or event.key() == Qt.Key.Key_Backtab:
            event.accept()
            self.input_mode = "angle" if self.input_mode == "length" else "length"
            self._update_preview(self.canvas.last_cursor_point)
            return True
            
        key = event.text()
        if key.isdigit() or key == '.' or key == '-':
            if self.input_mode == "length": self.length_buffer += key
            else: self.angle_buffer += key
            self._update_preview(self.canvas.last_cursor_point)
            return True
            
        elif event.key() == Qt.Key.Key_Backspace:
            if self.input_mode == "length": self.length_buffer = self.length_buffer[:-1]
            else: self.angle_buffer = self.angle_buffer[:-1]
            self._update_preview(self.canvas.last_cursor_point)
            return True
            
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.length_buffer or self.angle_buffer:
                # 添加通过输入确定的点
                try:
                    sx, sy = self.points[-1]
                    fp = self.canvas.last_cursor_point
                    dist = float(self.length_buffer) if self.length_buffer else math.hypot(fp.x() - sx, fp.y() - sy)
                    ang = float(self.angle_buffer) if self.angle_buffer else self.current_draw_angle
                    is_lower = fp.y() > sy
                    if self.angle_buffer and is_lower: ang = (360 - ang) % 360
                    rad = math.radians(ang)
                    self.points.append((sx + dist * math.cos(rad), sy - dist * math.sin(rad)))
                    self.length_buffer = ""
                    self.angle_buffer = ""
                    self.input_mode = "length"
                    self._update_preview(self.canvas.last_cursor_point)
                except ValueError: pass
            else:
                self._finalize_spline()
            return True
            
        elif event.key() == Qt.Key.Key_Escape:
            self._cleanup_temp_items()
            if hasattr(self.canvas, '_cleanup_tracking_huds'):
                self.canvas._cleanup_tracking_huds()
            return True
        return False

    def _finalize_spline(self):
        if len(self.points) > 1:
            new_item = SmartSplineItem(list(self.points))
            pen = QPen(self.canvas.color_manager.get_color(), 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            new_item.setPen(pen)
            self.canvas.layer_manager.apply_current_layer_props(new_item)
            self.canvas.undo_stack.push(CommandDrawSpline(self.canvas.scene(), new_item))
            
        self._cleanup_temp_items()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()