# tools/tool_smart_dim.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartCircleItem, SmartArcItem, SmartOrthogonalDimensionItem, SmartRadiusDimensionItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QUndoCommand, QColor

class CommandAddDim(QUndoCommand):
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

class SmartDimensionTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0 # 0: 拾取, 1: 拖拽预览(对齐/线性), 2: 等待第二点
        self.dim_item = None
        self.p1 = None
        self.p2 = None
        self.mode = "linear" 
        self.hovered_item = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.state = 0
        self._cleanup()
        self._update_hud()

    def deactivate(self):
        self._cleanup()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup(self):
        if self.dim_item and self.dim_item.scene():
            self.canvas.scene().removeItem(self.dim_item)
        self.dim_item = None
        self.p1 = None
        self.p2 = None
        self.hovered_item = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if self.state == 0: text = "智能标注: 单击选取直线/圆/弧，或指定第一个端点"
        elif self.state == 2: text = "智能标注: 请单击指定第二个端点"
        elif self.state == 1: text = "智能标注: 移动鼠标确定放置位置，单击确认"
        else: text = "智能标注"
        
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:#5bc0de; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>📏 {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            item = self.canvas.scene().itemAt(final_point, self.canvas.transform())
            if item != self.hovered_item:
                self.hovered_item = item
        elif self.state == 1 and self.dim_item:
            if self.mode == "linear":
                self.dim_item.set_coords([self.p1, self.p2, (final_point.x(), final_point.y())])
            elif self.mode == "radius":
                self.dim_item.set_coords([self.p1, (final_point.x(), final_point.y())])
        return True

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                item = self.canvas.scene().itemAt(final_point, self.canvas.transform())
                # 智能分支 A: 拾取直线
                if isinstance(item, SmartLineItem):
                    self.p1, self.p2 = item.coords[0], item.coords[1]
                    self.mode = "linear"
                    self.dim_item = SmartOrthogonalDimensionItem(self.p1, self.p2, (final_point.x(), final_point.y()))
                    self._start_preview()
                # 智能分支 B & C: 拾取圆或圆弧
                elif isinstance(item, SmartCircleItem) or isinstance(item, SmartArcItem):
                    self.p1 = item.center
                    self.mode = "radius"
                    self.dim_item = SmartRadiusDimensionItem(self.p1, (final_point.x(), final_point.y()), "R")
                    self._start_preview()
                else:
                    # 降级分支 D: 点击空白，进入两点拾取模式
                    self.p1 = (final_point.x(), final_point.y())
                    self.state = 2
                    self._update_hud()
            elif self.state == 2:
                self.p2 = (final_point.x(), final_point.y())
                self.mode = "linear"
                self.dim_item = SmartOrthogonalDimensionItem(self.p1, self.p2, (final_point.x(), final_point.y()))
                self._start_preview()
            elif self.state == 1:
                # 放置标注定稿
                pen = QPen(self.canvas.color_manager.get_color(), 1)
                pen.setCosmetic(True)
                self.dim_item.setPen(pen)
                self.canvas.layer_manager.apply_current_layer_props(self.dim_item)
                self.canvas.undo_stack.push(CommandAddDim(self.canvas.scene(), self.dim_item))
                self.dim_item = None
                self.activate() # 回到初始状态，允许连续标注
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def _start_preview(self):
        self.state = 1
        pen = QPen(QColor(150, 200, 255, 180), 1)
        pen.setCosmetic(True)
        self.dim_item.setPen(pen)
        self.canvas.scene().addItem(self.dim_item)
        self._update_hud()