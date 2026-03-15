# tools/tool_dim_arclen.py
from tools.base_tool import BaseTool
from core.core_items import SmartArcItem, SmartArcLengthDimensionItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QUndoCommand, QColor

class CommandAddArcLenDim(QUndoCommand):
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

class DimArcLenTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0 # 0: 选弧, 1: 拖拽预览
        self.arc_item = None
        self.dim_item = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.state = 0
        self.canvas.scene().clearSelection() # 激活工具时清理残留高亮
        self._cleanup()
        self._update_hud()

    def deactivate(self):
        self._cleanup()
        self.canvas.scene().clearSelection() # 退出工具时清理高亮
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup(self):
        if self.dim_item and self.dim_item.scene():
            self.canvas.scene().removeItem(self.dim_item)
        self.dim_item = None
        self.arc_item = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if self.state == 0: text = "弧长标注: 选择要标注的圆弧"
        elif self.state == 1: text = "弧长标注: 移动鼠标指定标注位置"
        else: text = "弧长标注"
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:#5bc0de; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>⌒ {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.state == 1 and self.dim_item:
            self.dim_item.set_coords([self.arc_item.center, (final_point.x(), final_point.y())])
        return True

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                # 【核心修复】：使用 10 像素容差的拾取框来找圆弧
                raw_point = self.canvas.mapToScene(event.pos())
                lod = self.canvas.transform().m11()
                r = 10.0 / lod if lod > 0 else 10.0
                hit_rect = QRectF(raw_point.x() - r, raw_point.y() - r, r * 2, r * 2)
                
                clicked_item = None
                for it in self.canvas.scene().items(hit_rect):
                    if isinstance(it, SmartArcItem):
                        clicked_item = it
                        break

                if clicked_item:
                    self.arc_item = clicked_item
                    self.arc_item.setSelected(True) # 【核心修复】：选中后立刻高亮圆弧
                    self.state = 1
                    self.dim_item = SmartArcLengthDimensionItem(
                        self.arc_item.center, self.arc_item.radius, 
                        self.arc_item.start_angle, self.arc_item.end_angle, 
                        (final_point.x(), final_point.y())
                    )
                    pen = QPen(QColor(150, 200, 255, 180), 1)
                    pen.setCosmetic(True)
                    self.dim_item.setPen(pen)
                    self.canvas.scene().addItem(self.dim_item)
                    self._update_hud()
                    
            elif self.state == 1:
                pen = QPen(self.canvas.color_manager.get_color(), 1)
                pen.setCosmetic(True)
                self.dim_item.setPen(pen)
                self.canvas.layer_manager.apply_current_layer_props(self.dim_item)
                self.canvas.undo_stack.push(CommandAddArcLenDim(self.canvas.scene(), self.dim_item))
                self.dim_item = None
                self.canvas.scene().clearSelection() # 【核心修复】：标注放置完毕后，自动取消圆弧高亮
                self.activate() 
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False