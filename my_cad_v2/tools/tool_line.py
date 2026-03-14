# tools/tool_line.py
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
import math

class CommandDrawLine(QUndoCommand):
    def __init__(self, scene, line_item):
        super().__init__()
        self.scene = scene
        self.line_item = line_item
    def redo(self):
        if self.line_item not in self.scene.items(): self.scene.addItem(self.line_item)
    def undo(self):
        if self.line_item in self.scene.items():
            self.line_item.setSelected(False)
            self.scene.removeItem(self.line_item)

class LineTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.start_tuple = None
        self.input_mode = "length"  # "length" 或 "angle"
        self.length_buffer = ""
        self.angle_buffer = ""
        self.current_draw_angle = 0.0 

    def get_reference_point(self):
        return QPointF(*self.start_tuple) if self.start_tuple else None

    def get_input_buffer(self):
        """返回当前输入模式对应的缓冲区内容"""
        if self.input_mode == "length":
            return self.length_buffer
        else:
            return self.angle_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        if self.temp_item:
            self.canvas.scene().removeItem(self.temp_item)
        self.temp_item = None
        self.start_tuple = None
        self.input_mode = "length"
        self.length_buffer = ""
        self.angle_buffer = ""

    def finalize_current_line(self, end_point):
        if self.temp_item:
            end_tuple = (end_point.x(), end_point.y())
            self.temp_item.set_coords([self.start_tuple, end_tuple])
            
            # 兼容颜色覆盖面板
            current_color = self.canvas.color_manager.get_color()
            final_pen = QPen(current_color, 1)
            final_pen.setCosmetic(True)
            self.temp_item.setPen(final_pen)
            
            self.temp_item.setFlags(
                QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            )
            # 【Bug修复点1】：让定稿的线继承图层属性
            self.canvas.layer_manager.apply_current_layer_props(self.temp_item)
            
            cmd = CommandDrawLine(self.canvas.scene(), self.temp_item)
            self.canvas.undo_stack.push(cmd)
            
            self.start_tuple = end_tuple
            self.temp_item = SmartLineItem(self.start_tuple, self.start_tuple)
            self.temp_item.setFlags(QGraphicsItem.GraphicsItemFlag(0)) 
            pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine) 
            pen.setCosmetic(True)
            self.temp_item.setPen(pen)
            
            # 【Bug修复点2】：让下一根虚线也继承可见性
            self.canvas.layer_manager.apply_current_layer_props(self.temp_item)
            self.canvas.scene().addItem(self.temp_item)
            
            self.input_mode = "length"
            self.length_buffer = ""
            self.angle_buffer = ""
            self.canvas.acquired_point = None

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.start_tuple is None:
                self.canvas.scene().clearSelection()
                self.start_tuple = (final_point.x(), final_point.y())
                
                self.temp_item = SmartLineItem(self.start_tuple, self.start_tuple)
                self.temp_item.setFlags(QGraphicsItem.GraphicsItemFlag(0)) 
                pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine) 
                pen.setCosmetic(True)
                self.temp_item.setPen(pen)
                
                # 【Bug修复点3】：让画的第一根虚线就继承图层属性（如果图层关了，画的时候就是隐形的）
                self.canvas.layer_manager.apply_current_layer_props(self.temp_item)
                self.canvas.scene().addItem(self.temp_item)
            else:
                self.finalize_current_line(final_point)
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
            
            # 如果有角度输入，使用输入的角度；否则使用捕捉角度
            if self.angle_buffer:
                try:
                    cad_angle = float(self.angle_buffer)
                    # 判断当前在上半部分还是下半部分
                    if hasattr(self, 'last_mouse_point'):
                        is_lower = self.last_mouse_point.y() > sy
                    else:
                        is_lower = True  # 默认下半部分
                    
                    # 将CAD角度（0-180°）转换为数学角度（0-360°）
                    if is_lower:
                        # 下半部分：顺时针，CAD 90° = 数学 270°
                        self.current_draw_angle = (360 - cad_angle) % 360
                    else:
                        # 上半部分：逆时针，CAD 90° = 数学 90°
                        self.current_draw_angle = cad_angle
                except ValueError:
                    # snapped_angle已经是CAD角度，需要转换为数学角度
                    is_lower = final_point.y() > sy
                    if is_lower:
                        self.current_draw_angle = (360 - snapped_angle) % 360
                    else:
                        self.current_draw_angle = snapped_angle
            else:
                # snapped_angle已经是CAD角度，需要转换为数学角度
                is_lower = final_point.y() > sy
                if is_lower:
                    self.current_draw_angle = (360 - snapped_angle) % 360
                else:
                    self.current_draw_angle = snapped_angle
            
            # 计算预览线的终点
            if self.length_buffer:
                # 有长度输入：按输入的长度和当前角度绘制
                try:
                    exact_length = float(self.length_buffer)
                    rad = math.radians(self.current_draw_angle)
                    new_x = sx + exact_length * math.cos(rad)
                    new_y = sy - exact_length * math.sin(rad)
                    end_tuple = (new_x, new_y)
                except ValueError:
                    end_tuple = (final_point.x(), final_point.y())
            elif self.angle_buffer:
                # 只有角度输入：按输入的角度方向延伸到鼠标距离
                mouse_dist = math.hypot(final_point.x() - sx, final_point.y() - sy)
                rad = math.radians(self.current_draw_angle)
                new_x = sx + mouse_dist * math.cos(rad)
                new_y = sy - mouse_dist * math.sin(rad)
                end_tuple = (new_x, new_y)
            else:
                # 没有输入：跟随鼠标
                end_tuple = (final_point.x(), final_point.y())
                end_tuple = (final_point.x(), final_point.y())
            
            self.temp_item.set_coords([self.start_tuple, end_tuple])
        return True

    def keyPressEvent(self, event):
        if self.start_tuple:
            # Tab 键切换输入模式
            if event.key() == Qt.Key.Key_Tab or event.key() == Qt.Key.Key_Backtab:
                event.accept()
                self.input_mode = "angle" if self.input_mode == "length" else "length"
                return True
            
            key = event.text()
            if key.isdigit() or key == '.' or key == '-':
                if self.input_mode == "length":
                    self.length_buffer += key
                else:
                    self.angle_buffer += key
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                if self.input_mode == "length":
                    self.length_buffer = self.length_buffer[:-1]
                else:
                    self.angle_buffer = self.angle_buffer[:-1]
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.length_buffer or self.angle_buffer:
                    try:
                        # 获取长度和角度
                        exact_length = float(self.length_buffer) if self.length_buffer else math.hypot(
                            self.temp_item.coords[1][0] - self.start_tuple[0],
                            self.temp_item.coords[1][1] - self.start_tuple[1]
                        )
                        # 如果有角度输入，转换CAD角度为数学角度
                        if self.angle_buffer:
                            cad_angle = float(self.angle_buffer)
                            # 判断当前在上半部分还是下半部分
                            is_lower = self.temp_item.coords[1][1] > self.start_tuple[1]
                            if is_lower:
                                exact_angle = (360 - cad_angle) % 360
                            else:
                                exact_angle = cad_angle
                        else:
                            exact_angle = self.current_draw_angle
                        
                        sx, sy = self.start_tuple
                        rad = math.radians(exact_angle)
                        new_x = sx + exact_length * math.cos(rad)
                        new_y = sy - exact_length * math.sin(rad)
                        self.finalize_current_line(QPointF(new_x, new_y))
                    except ValueError: 
                        pass
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
                return True
        return False