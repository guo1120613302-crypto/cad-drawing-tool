# tools/tool_dim_angle.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartAngleDimensionItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QUndoCommand, QColor

class CommandAddAngleDim(QUndoCommand):
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

class DimAngleTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0 # 0: 选线1, 1: 选线2, 2: 拖拽预览
        self.line1 = None
        self.line2 = None
        self.p1_pick = None
        self.p2_pick = None
        self.center = None
        self.dim_item = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.state = 0
        self.canvas.scene().clearSelection()
        self._cleanup()
        self._update_hud()

    def deactivate(self):
        self._cleanup()
        self.canvas.scene().clearSelection()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup(self):
        if self.dim_item and self.dim_item.scene():
            self.canvas.scene().removeItem(self.dim_item)
        self.dim_item = None
        self.line1 = None
        self.line2 = None
        self.center = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if self.state == 0: text = "角度标注: 选择第一条直线"
        elif self.state == 1: text = "角度标注: 选择第二条直线"
        elif self.state == 2: text = "角度标注: 移动鼠标指定标注位置"
        else: text = "角度标注"
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:#5bc0de; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>📐 {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _get_intersection(self, l1, l2):
        x1, y1 = l1.coords[0]; x2, y2 = l1.coords[1]
        x3, y3 = l2.coords[0]; x4, y4 = l2.coords[1]
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-6: return None # 平行线
        px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / denom
        py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / denom
        return (px, py)

    # 【新增功能】：将鼠标坐标绝对精确地数学投影到线条本身上
    def _project_point(self, line, pt):
        x1, y1 = line.coords[0]
        x2, y2 = line.coords[1]
        px, py = pt
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-10: return pt
        t = ((px - x1) * dx + (py - y1) * dy) / length_sq
        return (x1 + t * dx, y1 + t * dy)

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.state == 2 and self.dim_item:
            self.dim_item.set_coords([self.p1_pick, self.center, self.p2_pick, (final_point.x(), final_point.y())])
        return True

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            
            raw_point = self.canvas.mapToScene(event.pos())
            lod = self.canvas.transform().m11()
            r = 10.0 / lod if lod > 0 else 10.0
            hit_rect = QRectF(raw_point.x() - r, raw_point.y() - r, r * 2, r * 2)
            
            clicked_item = None
            for it in self.canvas.scene().items(hit_rect):
                if isinstance(it, SmartLineItem):
                    clicked_item = it
                    break
            
            if self.state == 0:
                if clicked_item:
                    self.line1 = clicked_item
                    self.line1.setSelected(True) 
                    # 【核心修复】：将鼠标位置完美吸附到线上，消除一切角度误差
                    self.p1_pick = self._project_point(self.line1, (raw_point.x(), raw_point.y())) 
                    self.state = 1
                    self._update_hud()
                    
            elif self.state == 1:
                if clicked_item and clicked_item != self.line1:
                    self.line2 = clicked_item
                    self.line2.setSelected(True) 
                    # 【核心修复】：将鼠标位置完美吸附到线上，消除一切角度误差
                    self.p2_pick = self._project_point(self.line2, (raw_point.x(), raw_point.y()))
                    self.center = self._get_intersection(self.line1, self.line2)
                    if self.center:
                        self.state = 2
                        self.dim_item = SmartAngleDimensionItem(self.p1_pick, self.center, self.p2_pick, (final_point.x(), final_point.y()))
                        pen = QPen(QColor(150, 200, 255, 180), 1)
                        pen.setCosmetic(True)
                        self.dim_item.setPen(pen)
                        self.canvas.scene().addItem(self.dim_item)
                        self._update_hud()
                        
            elif self.state == 2:
                pen = QPen(self.canvas.color_manager.get_color(), 1)
                pen.setCosmetic(True)
                self.dim_item.setPen(pen)
                self.canvas.layer_manager.apply_current_layer_props(self.dim_item)
                self.canvas.undo_stack.push(CommandAddAngleDim(self.canvas.scene(), self.dim_item))
                self.dim_item = None
                self.canvas.scene().clearSelection() 
                self.activate() 
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False