# tools/tool_rect.py
from tools.base_tool import BaseTool
from core_items import CADRectItem
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QRectF, QPointF
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
        self.start_point = None
        self.temp_rect = None
        self.input_buffer = ""

    def get_reference_point(self):
        return self.start_point

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        # 只有在按 ESC 或 右键取消时，才需要把未画完的预览框删掉
        if self.temp_rect:
            self.canvas.scene().removeItem(self.temp_rect)
        self.temp_rect = None
        self.start_point = None
        self.input_buffer = ""

    def finalize_current_rect(self, end_point):
        if self.temp_rect:
            rect = QRectF(self.start_point, end_point).normalized()
            self.temp_rect.set_rect(rect)
            
            # 读取全局颜色
            current_color = self.canvas.color_manager.get_color()
            final_pen = QPen(current_color, 1)
            final_pen.setCosmetic(True)
            self.temp_rect.setPen(final_pen)
            
            # 开启选中权限
            self.temp_rect.setFlags(
                QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            )
            
            cmd = CommandDrawRect(self.canvas.scene(), self.temp_rect)
            self.canvas.undo_stack.push(cmd)
            
            # 【核心修复】：不能调用 _cleanup_temp_items()！
            # 直接断开引用，将其留在场景中，并重置起点的状态用于画下一个矩形
            self.temp_rect = None
            self.start_point = None
            self.input_buffer = ""
            self.canvas.acquired_point = None

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.start_point is None:
                self.canvas.scene().clearSelection()
                self.start_point = final_point
                
                # 创建虚线预览框，禁止被选中拦截鼠标
                self.temp_rect = CADRectItem(QRectF(self.start_point, self.start_point))
                self.temp_rect.setFlags(QGraphicsItem.GraphicsItemFlag(0))
                pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.temp_rect.setPen(pen)
                self.canvas.scene().addItem(self.temp_rect)
            else:
                self.finalize_current_rect(final_point)
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self._cleanup_temp_items()
            self.canvas._cleanup_tracking_huds()
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.start_point and self.temp_rect:
            # 动态更新矩形对角点
            self.temp_rect.set_rect(QRectF(self.start_point, final_point).normalized())
        return True

    def keyPressEvent(self, event):
        if self.start_point:
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
                            new_x = self.start_point.x() + w
                            new_y = self.start_point.y() - h # Qt 的 Y 轴向下，CAD 向上
                            self.finalize_current_rect(QPointF(new_x, new_y))
                        else:
                            side = float(self.input_buffer)
                            new_x = self.start_point.x() + side
                            new_y = self.start_point.y() - side
                            self.finalize_current_rect(QPointF(new_x, new_y))
                    except ValueError:
                        pass
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cleanup_temp_items()
                self.canvas._cleanup_tracking_huds()
                return True
        return False