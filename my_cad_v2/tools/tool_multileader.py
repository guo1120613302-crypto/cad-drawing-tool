# tools/tool_multileader.py
from tools.base_tool import BaseTool
from core.core_items import SmartLeaderItem
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPen, QUndoCommand, QTextCursor
from PyQt6.QtWidgets import QGraphicsLineItem

class CommandAddLeader(QUndoCommand):
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

class MultileaderTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0 # 0: 箭头, 1: 转折点
        self.arrow_pt = None
        self.ghost_line = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.arrow_pt = None
        self._cleanup_ghost()

    def deactivate(self):
        self._cleanup_ghost()

    def _cleanup_ghost(self):
        if self.ghost_line and self.ghost_line.scene():
            self.canvas.scene().removeItem(self.ghost_line)
        self.ghost_line = None

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                self.canvas.scene().clearSelection()
                self.arrow_pt = (final_point.x(), final_point.y())
                self.state = 1
                
                self.ghost_line = QGraphicsLineItem()
                pen = QPen(Qt.GlobalColor.white, 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.ghost_line.setPen(pen)
                self.canvas.scene().addItem(self.ghost_line)
                
            elif self.state == 1:
                landing_pt = (final_point.x(), final_point.y())
                leader = SmartLeaderItem(self.arrow_pt, landing_pt)
                
                pen = QPen(self.canvas.color_manager.get_color(), 1)
                leader.setPen(pen)
                self.canvas.layer_manager.apply_current_layer_props(leader)
                
                cmd = CommandAddLeader(self.canvas.scene(), leader)
                self.canvas.undo_stack.push(cmd)
                
                # QTimer 劫持焦点给刚出生的文本框
                def grab_focus():
                    leader.text_item.setFocus()
                    cursor = leader.text_item.textCursor()
                    cursor.select(QTextCursor.SelectionType.Document)
                    leader.text_item.setTextCursor(cursor)
                QTimer.singleShot(50, grab_focus)
                
                self.deactivate()
                self.canvas.switch_tool("选择")
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.state == 1 and self.ghost_line:
            self.ghost_line.setLine(self.arrow_pt[0], self.arrow_pt[1], final_point.x(), final_point.y())
        return True