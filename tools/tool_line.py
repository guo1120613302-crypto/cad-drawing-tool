# tools/tool_line.py
from tools.base_tool import BaseTool
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsItem
from PyQt6.QtCore import Qt, QLineF, QPointF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
import math

class CommandDrawLine(QUndoCommand):
    def __init__(self, scene, line_item):
        super().__init__()
        self.scene = scene
        self.line_item = line_item

    def redo(self):
        if self.line_item not in self.scene.items():
            self.scene.addItem(self.line_item)

    def undo(self):
        if self.line_item in self.scene.items():
            self.line_item.setSelected(False)
            self.scene.removeItem(self.line_item)

class LineTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.start_point = None
        self.temp_line = None
        self.input_buffer = ""
        self.current_draw_angle = 0.0 

    def get_reference_point(self):
        # 告诉画布：我现在的画图起点在哪里，请帮我算极轴追踪
        return self.start_point

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        if self.temp_line:
            self.canvas.scene().removeItem(self.temp_line)
        self.temp_line = None
        self.start_point = None
        self.input_buffer = ""

    def finalize_current_line(self, end_point):
        if self.temp_line:
            self.temp_line.setLine(QLineF(self.start_point, end_point))
            final_pen = QPen(QColor(255, 255, 255), 1)
            final_pen.setCosmetic(True)
            self.temp_line.setPen(final_pen)
            
            self.temp_line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            
            cmd = CommandDrawLine(self.canvas.scene(), self.temp_line)
            self.canvas.undo_stack.push(cmd)
            
            self.start_point = end_point
            
            self.temp_line = QGraphicsLineItem(QLineF(self.start_point, self.start_point))
            pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine) 
            pen.setCosmetic(True)
            self.temp_line.setPen(pen)
            self.canvas.scene().addItem(self.temp_line)
            
            self.input_buffer = ""
            self.canvas.acquired_point = None # 画完清空全局参考点

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.start_point is None:
                self.canvas.scene().clearSelection()
                self.start_point = final_point
                self.temp_line = QGraphicsLineItem(QLineF(self.start_point, self.start_point))
                pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine) 
                pen.setCosmetic(True)
                self.temp_line.setPen(pen)
                self.canvas.scene().addItem(self.temp_line)
            else:
                self.finalize_current_line(final_point)
            return True
                
        elif event.button() == Qt.MouseButton.RightButton:
            self._cleanup_temp_items()
            self.canvas._cleanup_tracking_huds() # 让画布清理辅助线
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.start_point and self.temp_line:
            self.temp_line.setLine(QLineF(self.start_point, final_point))
            self.current_draw_angle = snapped_angle
        return True

    def keyPressEvent(self, event):
        if self.start_point:
            key = event.text()
            if key.isdigit() or key == '.':
                self.input_buffer += key
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    try:
                        exact_length = float(self.input_buffer)
                        snapped_angle = self.current_draw_angle
                        new_x = self.start_point.x()
                        new_y = self.start_point.y()
                        
                        if snapped_angle in (0, 360): new_x += exact_length
                        elif snapped_angle == 180: new_x -= exact_length
                        elif snapped_angle == 90: new_y -= exact_length
                        elif snapped_angle == 270: new_y += exact_length
                        else:
                            rad = math.radians(snapped_angle)
                            new_x += exact_length * math.cos(rad)
                            new_y -= exact_length * math.sin(rad)
                        
                        exact_point = QPointF(new_x, new_y) 
                        self.finalize_current_line(exact_point)
                    except ValueError:
                        pass
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cleanup_temp_items()
                self.canvas._cleanup_tracking_huds()
                return True
        return False