# tools/tool_circle.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartCircleItem
from PyQt6.QtWidgets import QGraphicsEllipseItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand

class CommandDrawCircle(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__()
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item not in self.scene.items():
            self.scene.addItem(self.item)

    def undo(self):
        if self.item in self.scene.items():
            self.item.setSelected(False)
            self.scene.removeItem(self.item)

class CircleTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.center_point = None
        self.ghost_circle = None
        self.state = 0
        self.input_buffer = ""

    def get_reference_point(self):
        # 核心：将圆心暴露给底层画板，用于绘制半径标注线
        return QPointF(*self.center_point) if self.state == 1 and self.center_point else None

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.center_point = None
        self.input_buffer = ""
        self._cleanup_ghost()

    def deactivate(self):
        self._cleanup_ghost()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghost(self):
        if self.ghost_circle and self.ghost_circle.scene():
            self.canvas.scene().removeItem(self.ghost_circle)
        self.ghost_circle = None

    def _update_preview(self):
        # 触发底层的鼠标移动事件，强制刷新画布上的动态 HUD 尺寸框
        if self.state == 1 and self.ghost_circle and hasattr(self.canvas, 'last_cursor_point'):
            class DummyEvent: pass
            self.mouseMoveEvent(DummyEvent(), self.canvas.last_cursor_point, getattr(self.canvas, 'last_snapped_angle', 0.0))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                # 第一步：确定圆心
                self.center_point = (final_point.x(), final_point.y())
                self.state = 1
                self.input_buffer = "" # 清空可能的残留输入
                
                self.ghost_circle = QGraphicsEllipseItem()
                # 【修改】：虚线改为实线 SolidLine，并稍微加深了透明度(200)使其更明显
                pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
                pen.setCosmetic(True)
                self.ghost_circle.setPen(pen)
                self.canvas.scene().addItem(self.ghost_circle)
                self._update_hud()
                return True
                
            elif self.state == 1:
                # 第二步：确定半径并提交
                r = 0.0
                if self.input_buffer:
                    try:
                        r = float(self.input_buffer)
                    except ValueError:
                        pass
                
                # 如果没输数值，则使用当前点击点计算半径
                if r <= 0:
                    cx, cy = self.center_point
                    r = math.hypot(final_point.x() - cx, final_point.y() - cy)
                
                if r > 0.01:
                    self._finalize_circle(r)
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
        if self.state == 1 and self.ghost_circle:
            cx, cy = self.center_point
            if not self.input_buffer:
                r = math.hypot(final_point.x() - cx, final_point.y() - cy)
                if r > 0:
                    self.ghost_circle.setRect(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            else:
                self._update_ghost_by_input() 
        return True

    def keyPressEvent(self, event):
        if self.state == 1:
            key = event.text()
            if key.isdigit() or key == '.':
                self.input_buffer += key
                self._update_ghost_by_input()
                self._update_preview()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                self._update_ghost_by_input()
                self._update_preview()
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    try:
                        r = float(self.input_buffer)
                        if r > 0:
                            self._finalize_circle(r)
                    except ValueError: pass
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self.state = 0
                self.center_point = None
                self.input_buffer = ""
                self._cleanup_ghost()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
                return True
        return False

    def _update_ghost_by_input(self):
        if self.state == 1 and self.ghost_circle and self.input_buffer:
            try:
                r = float(self.input_buffer)
                if r > 0:
                    cx, cy = self.center_point
                    self.ghost_circle.setRect(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            except ValueError:
                pass


    def _update_hud(self):
        if hasattr(self.canvas, 'hud_polar_info') and self.canvas.hud_polar_info:
            if len(self.points) == 1:
                # 获取鼠标当前坐标
                cursor_pt = getattr(self, 'last_mouse_point', getattr(self.canvas, 'last_cursor_point', None))
                if cursor_pt:
                    import math
                    dx = cursor_pt.x() - self.points[0][0]
                    dy = cursor_pt.y() - self.points[0][1]
                    radius = math.hypot(dx, dy)
                    self.canvas.hud_polar_info.setPlainText(f"半径: {radius:.2f}")
            else:
                self.canvas.hud_polar_info.setPlainText("")

                
    def _finalize_circle(self, radius):
        if radius <= 0: return
            
        new_item = SmartCircleItem(self.center_point, radius)
        
        current_color = self.canvas.color_manager.get_color()
        pen = QPen(current_color, 1)
        pen.setCosmetic(True)
        new_item.setPen(pen)
        self.canvas.layer_manager.apply_current_layer_props(new_item)
        
        cmd = CommandDrawCircle(self.canvas.scene(), new_item)
        self.canvas.undo_stack.push(cmd)
        
        self.state = 0
        self.center_point = None
        self.input_buffer = ""
        self._cleanup_ghost()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()