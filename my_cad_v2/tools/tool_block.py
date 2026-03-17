# tools/tool_block.py
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QGraphicsView, QLineEdit, QGraphicsItem
from core.core_items import BLOCK_REGISTRY, SmartBlockReference, clone_geometry_item

# =========================================================================
# 【核心架构修复】：拦截并重写 SmartBlockReference 的底层重建方法
# 彻底抹除所有子图元的独立人格，防止它们往画布上散发偏移的局部坐标夹点
# =========================================================================
_original_rebuild = SmartBlockReference.rebuild_from_registry

def _patched_rebuild(self):
    _original_rebuild(self)  # 先执行原版的克隆组装流程
    
    # 遍历所有被克隆到块内部的子图形
    for child in self.childItems():
        # 1. 剥夺独立被选权，让鼠标点击事件直接穿透给父级(块整体)
        child.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        child.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)
        # 2. 剥夺智能标记，底层画布就不会去提取它错误的局部坐标画夹点了
        child.is_smart_shape = False

SmartBlockReference.rebuild_from_registry = _patched_rebuild
# =========================================================================


class CommandCreateBlock(QUndoCommand):
    def __init__(self, scene, original_items, base_point, block_name):
        super().__init__()
        self.scene = scene
        
        self.original_items = []
        for it in original_items:
            if getattr(it, 'is_smart_shape', False) and not getattr(it, 'is_block', False):
                self.original_items.append(it)
                
        self.base_point = base_point
        self.block_name = block_name
        self.block_ref = None

    def redo(self):
        bx, by = self.base_point.x(), self.base_point.y()
        templates = []
        
        for item in self.original_items:
            # 【核心修复】：将图形被移动产生的偏移(scenePos)与基准点进行绝对数学合并
            abs_dx = item.scenePos().x() - bx
            abs_dy = item.scenePos().y() - by
            
            t_item = clone_geometry_item(item, abs_dx, abs_dy)
            if t_item:
                templates.append(t_item)
                
        BLOCK_REGISTRY[self.block_name] = templates

        if not self.block_ref:
            self.block_ref = SmartBlockReference(self.block_name)
        
        if self.block_ref.scene() != self.scene:
            self.scene.addItem(self.block_ref)
        
        self.block_ref.setPos(self.base_point)
        self.block_ref.rebuild_from_registry() 

        for item in self.original_items:
            item.setSelected(False)
            if item.scene() == self.scene:
                item.setVisible(False) 

        for it in self.scene.items():
            if getattr(it, 'is_block', False) and getattr(it, 'block_name', "") == self.block_name and it != self.block_ref:
                it.rebuild_from_registry()

        self.block_ref.setSelected(True)

    def undo(self):
        for item in self.original_items:
            item.setVisible(True)
            item.setSelected(True)
        if self.block_ref and self.block_ref.scene() == self.scene:
            self.block_ref.setSelected(False)
            self.scene.removeItem(self.block_ref)


class BlockTool(BaseTool):
    """V2.0 专业建块工具 (支持用户手动精确点击基准点，彻底解决偏移)"""
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0 # 0: 框选, 1: 输名字, 2: 等待鼠标点击基点
        self.selected_items = []
        self.block_name = "未命名块"
        
        self.input_box = QLineEdit(self.canvas.viewport())
        self.input_box.setStyleSheet("QLineEdit { background-color: #2b2b2b; color: #00ff00; border: 2px solid #0055ff; border-radius: 4px; padding: 4px; font-size: 14px; font-weight: bold; }")
        self.input_box.returnPressed.connect(self._on_input_enter)
        self.input_box.hide()

    def _show_input(self, placeholder_text):
        w = self.canvas.viewport().width()
        self.input_box.setGeometry(w - 240, 20, 220, 40)
        self.input_box.clear()
        self.input_box.setPlaceholderText(placeholder_text)
        self.input_box.show()
        self.input_box.setFocus()

    def activate(self):
        self.state = 0
        self.input_box.hide()
        self.block_name = "未命名块"
        self.selected_items = self.canvas.scene().selectedItems()
        if self.selected_items:
            self._goto_state_1()
        else:
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:4px;'>请用鼠标 <b>框选</b> 需要建块的图形 (松手自动确认)</div>")
            self.canvas.hud_polar_info.show()
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self): 
        self.canvas.hud_polar_info.hide()
        self.input_box.hide()
        self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _goto_state_1(self):
        self.state = 1
        self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.canvas.hud_polar_info.setHtml("<div style='background:#0055ff;color:white;padding:4px;'>✅ 图形已选中，请看右上角输入块名称</div>")
        self.canvas.hud_polar_info.show()
        self._show_input("输入块名称 (回车确认)")

    def _check_auto_advance(self):
        if self.state == 0:
            self.selected_items = self.canvas.scene().selectedItems()
            if self.selected_items:
                self._goto_state_1()

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            QTimer.singleShot(50, self._check_auto_advance)
            return False
        return False

    def _on_input_enter(self):
        if self.state == 1:
            text = self.input_box.text().strip()
            if text: 
                self.block_name = text
            self.input_box.hide()
            
            self.state = 2
            self.canvas.hud_polar_info.setHtml(f"<div style='background:#ffaa00;color:black;padding:4px;'>📌 命名完成！请在图形上 <b>点击一下鼠标</b> 指定基准点 (推荐点在图形中心)</div>")

    def mousePressEvent(self, event, final_point, snapped_angle):
        if self.state == 0: 
            return False 
        if self.state == 1:
            return True
        if self.state == 2:
            if event.button() == Qt.MouseButton.LeftButton:
                cmd = CommandCreateBlock(self.canvas.scene(), self.selected_items, final_point, self.block_name)
                self.canvas.undo_stack.push(cmd)
                
                self.canvas.hud_polar_info.setHtml(f"<div style='background:#00aa00;color:white;padding:4px;'>🎉 块 [{self.block_name}] 建立成功！</div>")
                
                self.state = 0
                self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            else:
                self.activate() 
            return True
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: 
            self.activate()
            return True
        return False