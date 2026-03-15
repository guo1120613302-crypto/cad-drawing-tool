# tools/tool_ellipse.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartEllipseItem
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPainterPath

class CommandDrawEllipse(QUndoCommand):
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

class EllipseTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.center = None
        self.axis1_pt = None
        self.ghost_item = None
        self.state = 0 # 0: 选中心, 1: 轴1端点, 2: 轴2距离
        self.input_buffer = ""

    def get_reference_point(self):
        return QPointF(*self.center) if self.state > 0 and self.center else None

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.center = None
        self.axis1_pt = None
        self.input_buffer = ""
        self._cleanup_ghost()
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghost()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghost(self):
        if self.ghost_item and self.ghost_item.scene():
            self.canvas.scene().removeItem(self.ghost_item)
        self.ghost_item = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if self.state == 0: text = f"椭圆: 指定中心点"
        elif self.state == 1: text = f"椭圆: 指定轴端点: {self.input_buffer}"
        else: text = f"椭圆: 指定另一条半轴长度: {self.input_buffer}"
        
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:#5bc0de; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>⬭ {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _update_preview(self):
        if self.state > 0 and hasattr(self.canvas, 'last_cursor_point'):
            class DummyEvent: pass
            self.mouseMoveEvent(DummyEvent(), self.canvas.last_cursor_point, getattr(self.canvas, 'last_snapped_angle', 0.0))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                self.center = (final_point.x(), final_point.y())
                self.state = 1
                self.input_buffer = ""
                self.ghost_item = QGraphicsPathItem()
                pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
                pen.setCosmetic(True)
                self.ghost_item.setPen(pen)
                self.canvas.scene().addItem(self.ghost_item)
                
            elif self.state == 1:
                if self.input_buffer:
                    try:
                        r1 = float(self.input_buffer)
                        a_rad = math.radians(snapped_angle)
                        self.axis1_pt = (self.center[0] + r1*math.cos(a_rad), self.center[1] - r1*math.sin(a_rad))
                    except ValueError: pass
                
                if not self.axis1_pt: self.axis1_pt = (final_point.x(), final_point.y())
                self.state = 2
                self.input_buffer = ""
                
            elif self.state == 2:
                r2 = 0.0
                if self.input_buffer:
                    try: r2 = float(self.input_buffer)
                    except ValueError: pass
                if r2 <= 0: r2 = math.hypot(final_point.x() - self.center[0], final_point.y() - self.center[1])
                if r2 > 0.01: self._finalize_ellipse(r2)
            
            self._update_hud()
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state > 0:
                self.state = 0
                self.center = None
                self.axis1_pt = None
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
        if not self.ghost_item: return
        
        cx, cy = self.center
        path = QPainterPath()
        
        if self.state == 1:
            # 只画第一根轴线
            r1 = math.hypot(final_point.x() - cx, final_point.y() - cy)
            if self.input_buffer:
                try: r1 = float(self.input_buffer)
                except ValueError: pass
            a_rad = math.radians(snapped_angle)
            nx = cx + r1 * math.cos(a_rad)
            ny = cy - r1 * math.sin(a_rad)
            path.moveTo(cx, cy); path.lineTo(nx, ny)
            self.ghost_item.setPath(path)
            
        elif self.state == 2:
            r1 = math.hypot(self.axis1_pt[0] - cx, self.axis1_pt[1] - cy)
            a_deg = math.degrees(math.atan2(-(self.axis1_pt[1] - cy), self.axis1_pt[0] - cx))
            
            r2 = math.hypot(final_point.x() - cx, final_point.y() - cy)
            if self.input_buffer:
                try: r2 = float(self.input_buffer)
                except ValueError: pass
                
            path.addEllipse(QRectF(-r1, -r2, 2*r1, 2*r2))
            
            # 使用 QTransform 原地旋转再写入 path，保证渲染完美
            from PyQt6.QtGui import QTransform
            trans = QTransform()
            trans.translate(cx, cy)
            trans.rotate(-a_deg)
            self.ghost_item.setPath(trans.map(path))
            
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
                    if self.state == 1 and val > 0:
                        a_rad = math.radians(self.canvas.last_snapped_angle if hasattr(self.canvas, 'last_snapped_angle') else 0)
                        self.axis1_pt = (self.center[0] + val*math.cos(a_rad), self.center[1] - val*math.sin(a_rad))
                        self.state = 2
                        self.input_buffer = ""
                        self._update_hud()
                    elif self.state == 2 and val > 0:
                        self._finalize_ellipse(val)
                except ValueError: pass
            return True
        elif event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def _finalize_ellipse(self, r2):
        r1 = math.hypot(self.axis1_pt[0] - self.center[0], self.axis1_pt[1] - self.center[1])
        angle_deg = math.degrees(math.atan2(-(self.axis1_pt[1] - self.center[1]), self.axis1_pt[0] - self.center[0]))
        
        new_item = SmartEllipseItem(self.center, r1, r2, angle_deg)
        pen = QPen(self.canvas.color_manager.get_color(), 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        new_item.setPen(pen)
        self.canvas.layer_manager.apply_current_layer_props(new_item)
        self.canvas.undo_stack.push(CommandDrawEllipse(self.canvas.scene(), new_item))
        
        self.state = 0
        self.center = None
        self.axis1_pt = None
        self.input_buffer = ""
        self._cleanup_ghost()
        self._update_hud()