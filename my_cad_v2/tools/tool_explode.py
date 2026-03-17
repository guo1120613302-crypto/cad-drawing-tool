# tools/tool_explode.py
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QGraphicsView, QLineEdit
from core.core_items import SmartLineItem, SmartPolylineItem, SmartPolygonItem, SmartBlockReference, BLOCK_REGISTRY, clone_geometry_item

class CommandExplodeItems(QUndoCommand):
    def __init__(self, scene, selected_items):
        super().__init__()
        self.scene = scene
        self.selected_items = selected_items
        self.items_to_remove = []
        self.items_to_add = []
        self._process_explode()

    def _process_explode(self):
        for item in self.selected_items:
            # 1. 炸开专业块！
            if isinstance(item, SmartBlockReference):
                self.items_to_remove.append(item)
                bx, by = item.scenePos().x(), item.scenePos().y()
                # 核心：直接从仓库模版里提取，并叠加上当前块在画布上的绝对位置！
                for template_item in BLOCK_REGISTRY.get(item.block_name, []):
                    new_real_item = clone_geometry_item(template_item, bx, by)
                    if new_real_item:
                        self.items_to_add.append(new_real_item)
                        
            # 2. 炸开多段线或多边形
            elif isinstance(item, (SmartPolylineItem, SmartPolygonItem)):
                self.items_to_remove.append(item)
                coords = item.coords
                pen = item.pen()
                is_closed = isinstance(item, SmartPolygonItem) or getattr(item, 'is_closed', False)
                for i in range(len(coords) - 1):
                    line = SmartLineItem(coords[i], coords[i+1])
                    line.setPen(pen)
                    self.items_to_add.append(line)
                if is_closed and len(coords) > 2:
                    line = SmartLineItem(coords[-1], coords[0])
                    line.setPen(pen)
                    self.items_to_add.append(line)

    def redo(self):
        for item in self.items_to_remove:
            if item.scene() == self.scene:
                item.setSelected(False)
                self.scene.removeItem(item)
        for new_item in self.items_to_add:
            if new_item not in self.scene.items():
                self.scene.addItem(new_item)
                new_item.setSelected(True)

    def undo(self):
        for new_item in self.items_to_add:
            if new_item.scene() == self.scene:
                self.scene.removeItem(new_item)
        for item in self.items_to_remove:
            if item not in self.scene.items():
                self.scene.addItem(item)
                item.setSelected(True)

class ExplodeTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.selected_items = []
        
        self.input_box = QLineEdit(self.canvas.viewport())
        self.input_box.setStyleSheet("QLineEdit { background-color: #2b2b2b; color: #ff5555; border: 2px solid #ff0000; border-radius: 4px; padding: 4px; font-size: 14px; font-weight: bold; }")
        self.input_box.returnPressed.connect(self._on_input_enter)
        self.input_box.hide()

    def _show_input(self, placeholder_text):
        w = self.canvas.viewport().width()
        self.input_box.setGeometry(w - 240, 20, 220, 40)
        self.input_box.clear()
        self.input_box.setPlaceholderText(placeholder_text)
        self.input_box.setReadOnly(True) 
        self.input_box.show(); self.input_box.setFocus()

    def activate(self):
        self.state = 0; self.input_box.hide()
        self.selected_items = self.canvas.scene().selectedItems()
        if self.selected_items:
            self.state = 1; self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.canvas.hud_polar_info.setHtml("<div style='background:#ff5555;color:white;padding:4px;'>✅ 图形已选中，请看右上角</div>"); self.canvas.hud_polar_info.show()
            self._show_input("按【回车键】炸开块或多段线")
        else:
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:4px;'>请用鼠标 <b>框选</b> 需要打散的块或线 (松手自动确认)</div>"); self.canvas.hud_polar_info.show()
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self): 
        self.canvas.hud_polar_info.hide(); self.input_box.hide(); self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _check_auto_advance(self):
        if self.state == 0:
            self.selected_items = self.canvas.scene().selectedItems()
            if self.selected_items:
                self.state = 1; self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.canvas.hud_polar_info.setHtml("<div style='background:#ff5555;color:white;padding:4px;'>✅ 选取成功！请看右上角</div>"); self.canvas.hud_polar_info.show()
                self._show_input("按【回车键】炸开块或多段线")

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            QTimer.singleShot(50, self._check_auto_advance); return False
        return False

    def mousePressEvent(self, event, final_point, snapped_angle):
        if self.state == 0: return False 
        if event.button() != Qt.MouseButton.LeftButton: self.activate(); return True
        return False

    def _on_input_enter(self):
        if self.state == 1:
            cmd = CommandExplodeItems(self.canvas.scene(), self.selected_items)
            self.canvas.undo_stack.push(cmd)
            self.canvas.hud_polar_info.setHtml("<div style='background:#00aa00;color:white;padding:4px;'>💥 <b>打散成功！</b>实体已炸成散件</div>")
            self.input_box.hide(); self.state = 0; self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.activate(); return True
        return False