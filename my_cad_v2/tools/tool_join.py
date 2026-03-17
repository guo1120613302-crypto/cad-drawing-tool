# tools/tool_join.py
import math
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QGraphicsView, QLineEdit
from core.core_items import SmartLineItem, SmartPolylineItem

class CommandJoinItems(QUndoCommand):
    """撤销/重做栈支持的图形合并命令"""
    def __init__(self, scene, selected_items):
        super().__init__()
        self.scene = scene
        self.selected_items = selected_items
        self.items_to_remove = []
        self.items_to_add = []
        self._process_join()

    def _dist(self, p1, p2):
        return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

    def _process_join(self):
        """核心算法：打碎所有线段，寻找共享端点并重新组装多段线"""
        edges = []
        # 1. 提取所有参与合并的直线和多段线的线段
        for item in self.selected_items:
            if isinstance(item, SmartLineItem):
                edges.append((item.coords[0], item.coords[1], item.pen()))
                self.items_to_remove.append(item)
            elif isinstance(item, SmartPolylineItem):
                for i in range(len(item.coords) - 1):
                    edges.append((item.coords[i], item.coords[i+1], item.pen()))
                self.items_to_remove.append(item)
        
        chains = []
        pens = []
        
        # 2. 拓扑连接算法：寻找首尾相连的端点 (容差 1e-4)
        while edges:
            e1, e2, pen = edges.pop(0)
            current_chain = [e1, e2]
            current_pen = pen
            progress = True
            
            while progress:
                progress = False
                for i, edge in enumerate(edges):
                    ce1, ce2, cpen = edge
                    # 检查是否与当前链条的头部相连
                    if self._dist(ce1, current_chain[0]) < 1e-4:
                        current_chain.insert(0, ce2)
                        edges.pop(i); progress = True; break
                    elif self._dist(ce2, current_chain[0]) < 1e-4:
                        current_chain.insert(0, ce1)
                        edges.pop(i); progress = True; break
                    # 检查是否与当前链条的尾部相连
                    elif self._dist(ce1, current_chain[-1]) < 1e-4:
                        current_chain.append(ce2)
                        edges.pop(i); progress = True; break
                    elif self._dist(ce2, current_chain[-1]) < 1e-4:
                        current_chain.append(ce1)
                        edges.pop(i); progress = True; break
                        
            chains.append(current_chain)
            pens.append(current_pen)

        # 3. 将组装好的点云链条生成新的图元
        for chain, pen in zip(chains, pens):
            # 如果只剩两个点，说明没连上别的东西，还原为直线
            if len(chain) == 2:
                new_item = SmartLineItem(chain[0], chain[1])
            else:
                new_item = SmartPolylineItem(chain)
            
            if pen: 
                new_item.setPen(pen)
            self.items_to_add.append(new_item)

    def redo(self):
        for item in self.items_to_remove:
            if item.scene() == self.scene:
                item.setSelected(False)
                self.scene.removeItem(item)
        for item in self.items_to_add:
            if item not in self.scene.items():
                self.scene.addItem(item)
                item.setSelected(True) # 合并后的新多段线保持选中状态

    def undo(self):
        for item in self.items_to_add:
            if item.scene() == self.scene:
                item.setSelected(False)
                self.scene.removeItem(item)
        for item in self.items_to_remove:
            if item not in self.scene.items():
                self.scene.addItem(item)
                item.setSelected(True)


class JoinTool(BaseTool):
    """V2.0 智能合并工具 (原生输入框确认，无缝交互)"""
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.selected_items = []
        
        # 挂载右侧原生输入框
        self.input_box = QLineEdit(self.canvas.viewport())
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b; color: #00ff00; 
                border: 2px solid #0055ff; border-radius: 4px; 
                padding: 4px; font-size: 14px; font-weight: bold;
            }
        """)
        self.input_box.returnPressed.connect(self._on_input_enter)
        self.input_box.hide()

    def _show_input(self, placeholder_text):
        w = self.canvas.viewport().width()
        self.input_box.setGeometry(w - 240, 20, 220, 40)
        self.input_box.clear()
        self.input_box.setPlaceholderText(placeholder_text)
        # 合并操作不需要打字，设置为只读，但能接收回车事件
        self.input_box.setReadOnly(True) 
        self.input_box.show()
        self.input_box.setFocus()

    def activate(self):
        self.state = 0
        self.input_box.hide()
        
        self.selected_items = self.canvas.scene().selectedItems()
        if self.selected_items:
            self.state = 1  
            self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.canvas.hud_polar_info.setHtml("<div style='background:#0055ff;color:white;padding:4px;'>✅ 线段已选中，请看右上角</div>")
            self.canvas.hud_polar_info.show()
            self._show_input("请按【回车键】执行合并")
        else:
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:4px;'>请用鼠标 <b>框选</b> 需要合并的散线 (松开鼠标自动确认)</div>")
            self.canvas.hud_polar_info.show()
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self): 
        self.canvas.hud_polar_info.hide()
        self.input_box.hide()
        self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _check_auto_advance(self):
        """松开鼠标自动检测框选"""
        if self.state == 0:
            self.selected_items = self.canvas.scene().selectedItems()
            if self.selected_items:
                self.state = 1
                self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.canvas.hud_polar_info.setHtml("<div style='background:#0055ff;color:white;padding:4px;'>✅ 选取成功！请看右上角</div>")
                self.canvas.hud_polar_info.show()
                self._show_input("请按【回车键】执行合并")

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            QTimer.singleShot(50, self._check_auto_advance)
            return False
        return False

    def mousePressEvent(self, event, final_point, snapped_angle):
        if self.state == 0: 
            return False 
        if event.button() != Qt.MouseButton.LeftButton: 
            self.activate(); return True
        return False

    def _on_input_enter(self):
        """按下回车，立即执行合并算法"""
        if self.state == 1:
            cmd = CommandJoinItems(self.canvas.scene(), self.selected_items)
            self.canvas.undo_stack.push(cmd)
            
            # 合并完成后给出成功提示，并重置工具
            self.canvas.hud_polar_info.setHtml("<div style='background:#00aa00;color:white;padding:4px;'>🎉 <b>合并成功！</b>散线已转为多段线</div>")
            self.input_box.hide()
            self.state = 0
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.activate()
            return True
        return False