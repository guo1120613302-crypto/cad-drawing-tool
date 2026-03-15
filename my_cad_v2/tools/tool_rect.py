# tools/tool_rect.py
from tools.base_tool import BaseTool
from core.core_items import SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QColor, QUndoCommand

class CommandDrawRect(QUndoCommand):
    def __init__(self, scene, rect_item):
        super().__init__()
        self.scene = scene
        self.rect_item = rect_item
    def redo(self):
        if self.rect_item not in self.scene.items(): self.scene.addItem(self.rect_item)
    def undo(self):
        if self.rect_item in self.scene.items():
            self.rect_item.setSelected(False)
            self.scene.removeItem(self.rect_item)

class RectTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.start_tuple = None
        self.input_mode = "width"
        self.width_buffer = ""
        self.height_buffer = ""

    def get_reference_point(self):
        return QPointF(*self.start_tuple) if self.start_tuple else None

    def get_input_buffer(self):
        return self.width_buffer if self.input_mode == "width" else self.height_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        if self.temp_item:
            self.canvas.scene().removeItem(self.temp_item)
        self.temp_item = None
        self.start_tuple = None
        self.input_mode = "width"
        self.width_buffer = ""
        self.height_buffer = ""

    def _generate_rect_coords(self, start_tup, end_tup):
        sx, sy = start_tup
        ex, ey = end_tup
        return [(sx, sy), (ex, sy), (ex, ey), (sx, ey)]

    def _update_preview(self):
        if self.start_tuple and self.temp_item and hasattr(self.canvas, 'last_cursor_point'):
            class DummyEvent: pass
            self.mouseMoveEvent(DummyEvent(), self.canvas.last_cursor_point, getattr(self.canvas, 'last_snapped_angle', 0.0))

    def finalize_current_rect(self, end_point):
        if self.temp_item:
            end_tuple = (end_point.x(), end_point.y())
            coords = self._generate_rect_coords(self.start_tuple, end_tuple)
            self.temp_item.set_coords(coords)
            
            current_color = self.canvas.color_manager.get_color()
            final_pen = QPen(current_color, 1)
            final_pen.setCosmetic(True)
            self.temp_item.setPen(final_pen)
            
            self.temp_item.setFlags(
                QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            )
            
            self.canvas.layer_manager.apply_current_layer_props(self.temp_item)
            
            cmd = CommandDrawRect(self.canvas.scene(), self.temp_item)
            self.canvas.undo_stack.push(cmd)
            
            self.temp_item = None
            self.start_tuple = None
            self.input_mode = "width"
            self.width_buffer = ""
            self.height_buffer = ""
            self.canvas.acquired_point = None

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.start_tuple is None:
                self.canvas.scene().clearSelection()
                self.start_tuple = (final_point.x(), final_point.y())
                
                coords = self._generate_rect_coords(self.start_tuple, self.start_tuple)
                self.temp_item = SmartPolygonItem(coords)
                self.temp_item.setFlags(QGraphicsItem.GraphicsItemFlag(0))
                # 【修改】：虚线改为实线 SolidLine
                pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine)
                pen.setCosmetic(True)
                self.temp_item.setPen(pen)
                
                self.canvas.layer_manager.apply_current_layer_props(self.temp_item)
                self.canvas.scene().addItem(self.temp_item)
            else:
                self.finalize_current_rect(final_point)
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self._cleanup_temp_items()
            if hasattr(self.canvas, '_cleanup_tracking_huds'):
                self.canvas._cleanup_tracking_huds()
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.start_tuple and self.temp_item:
            sx, sy = self.start_tuple
            ex, ey = final_point.x(), final_point.y()
            
            if self.width_buffer:
                try:
                    w = float(self.width_buffer)
                    ex = sx + w if ex >= sx else sx - w
                except ValueError: pass
            
            if self.height_buffer:
                try:
                    h = float(self.height_buffer)
                    ey = sy + h if ey >= sy else sy - h
                except ValueError: pass
                
            end_tuple = (ex, ey)
            coords = self._generate_rect_coords(self.start_tuple, end_tuple)
            self.temp_item.set_coords(coords)
        return True

    def keyPressEvent(self, event):
        if self.start_tuple:
            # 支持 Tab 切换
            if event.key() == Qt.Key.Key_Tab or event.key() == Qt.Key.Key_Backtab:
                event.accept()
                self.input_mode = "height" if self.input_mode == "width" else "width"
                self._update_preview()
                return True
                
            key = event.text()
            # 兼容您的老习惯：如果输入了逗号，直接跳到高度输入框
            if key == ',':  
                event.accept()
                self.input_mode = "height"
                self._update_preview()
                return True

            if key.isdigit() or key == '.' or key == '-':
                if self.input_mode == "width":
                    self.width_buffer += key
                else:
                    self.height_buffer += key
                self._update_preview()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                if self.input_mode == "width":
                    self.width_buffer = self.width_buffer[:-1]
                else:
                    self.height_buffer = self.height_buffer[:-1]
                self._update_preview()
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.temp_item:
                    ex = self.temp_item.coords[2][0]
                    ey = self.temp_item.coords[2][1]
                    self.finalize_current_rect(QPointF(ex, ey))
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
                return True
        return False