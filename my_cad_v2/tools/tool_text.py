# tools/tool_text.py
from tools.base_tool import BaseTool
from core.core_items import SmartTextItem
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QTextCursor

class CommandAddText(QUndoCommand):
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

class TextTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)

    def get_reference_point(self):
        return None

    def get_input_buffer(self):
        return ""

    def activate(self):
        # 切换到典型的打字光标
        self.canvas.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def deactivate(self):
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            self.canvas.scene().clearSelection()
            
            pos = (final_point.x(), final_point.y())
            text_item = SmartTextItem("输入文字...", pos)
            
            # 【应用颜色与图层属性】
            pen = QPen(self.canvas.color_manager.get_color(), 1)
            text_item.setPen(pen)
            self.canvas.layer_manager.apply_current_layer_props(text_item)
            
            # 压入撤销栈
            cmd = CommandAddText(self.canvas.scene(), text_item)
            self.canvas.undo_stack.push(cmd)
            
            # 【细节】：生成后立刻全选文字，方便用户一敲键盘就覆盖掉 "输入文字..." 这四个字
            text_item.setFocus()
            cursor = text_item.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            text_item.setTextCursor(cursor)
            
            # 留在文字工具，用户想写下一段话可以直接点别的地方继续写
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False