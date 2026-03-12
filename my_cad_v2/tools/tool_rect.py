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
        self.input_buffer = ""

    def get_reference_point(self):
        return QPointF(*self.start_tuple) if self.start_tuple else None

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        if self.temp_item:
            self.canvas.scene().removeItem(self.temp_item)
        self.temp_item = None
        self.start_tuple = None
        self.input_buffer = ""

    def _generate_rect_coords(self, start_tup, end_tup):
        """【V2.0 核心】：根据两点生成标准的矩形 4 顶点序列"""
        sx, sy = start_tup
        ex, ey = end_tup
        return [(sx, sy), (ex, sy), (ex, ey), (sx, ey)]

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
            
            cmd = CommandDrawRect(self.canvas.scene(), self.temp_item)
            self.canvas.undo_stack.push(cmd)
            
            self.temp_item = None
            self.start_tuple = None
            self.input_buffer = ""
            self.canvas.acquired_point = None

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.start_tuple is None:
                self.canvas.scene().clearSelection()
                self.start_tuple = (final_point.x(), final_point.y())
                
                coords = self._generate_rect_coords(self.start_tuple, self.start_tuple)
                self.temp_item = SmartPolygonItem(coords)
                self.temp_item.setFlags(QGraphicsItem.GraphicsItemFlag(0))
                pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.temp_item.setPen(pen)
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
            end_tuple = (final_point.x(), final_point.y())
            coords = self._generate_rect_coords(self.start_tuple, end_tuple)
            self.temp_item.set_coords(coords)
        return True

    def keyPressEvent(self, event):
        if self.start_tuple:
            key = event.text()
            if key.isdigit() or key in ['.', ',', '-']:
                self.input_buffer += key
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    try:
                        if ',' in self.input_buffer:
                            w, h = map(float, self.input_buffer.split(','))
                            sx, sy = self.start_tuple
                            self.finalize_current_rect(QPointF(sx + w, sy - h))
                        else:
                            side = float(self.input_buffer)
                            sx, sy = self.start_tuple
                            self.finalize_current_rect(QPointF(sx + side, sy - side))
                    except ValueError:
                        pass
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
                return True
        return False