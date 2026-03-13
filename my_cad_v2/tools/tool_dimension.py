# tools/tool_dimension.py
from tools.base_tool import BaseTool
from core.core_items import SmartDimensionItem
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
import math

class CommandCreateDimension(QUndoCommand):
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

class DimensionTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.p1 = None
        self.p2 = None
        self.state = 0 # 0=起点, 1=终点, 2=放置点
        self.preview_line = None # 寻找第二点时的虚线指引

    def get_reference_point(self):
        if self.state == 1: return QPointF(*self.p1)
        elif self.state == 2: return QPointF(*self.p2)
        return None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self._cleanup_temp_items()
        self._update_hud()

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        if self.temp_item and self.temp_item.scene():
            self.canvas.scene().removeItem(self.temp_item)
        if self.preview_line and self.preview_line.scene():
            self.canvas.scene().removeItem(self.preview_line)
        self.temp_item = None
        self.preview_line = None
        self.p1 = None
        self.p2 = None
        self.state = 0

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if self.state == 0:
            text = "标注: 请点击指定第一条尺寸界线原点"
            color = "#5bc0de"
        elif self.state == 1:
            text = "标注: 请点击指定第二条尺寸界线原点"
            color = "#f0ad4e"
        else:
            text = "标注: 移动鼠标指定尺寸线位置，点击左键放置"
            color = "#5cb85c"
        
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>📏 {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            pt = (final_point.x(), final_point.y())
            
            if self.state == 0:
                self.canvas.scene().clearSelection()
                self.p1 = pt
                self.state = 1
                
                # 创建皮筋线，给用户明确的操作反馈
                self.preview_line = QGraphicsLineItem()
                pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.preview_line.setPen(pen)
                self.canvas.scene().addItem(self.preview_line)
                self.preview_line.setLine(QLineF(self.p1[0], self.p1[1], pt[0], pt[1]))
                
            elif self.state == 1:
                # 防止原地双击
                if math.hypot(pt[0]-self.p1[0], pt[1]-self.p1[1]) < 1e-4: return True
                
                self.p2 = pt
                self.state = 2
                
                if self.preview_line and self.preview_line.scene():
                    self.canvas.scene().removeItem(self.preview_line)
                self.preview_line = None
                
                # 生成真实的跟随标注模型
                self.temp_item = SmartDimensionItem(self.p1, self.p2, pt)
                pen = QPen(QColor(255, 255, 255), 1)
                pen.setCosmetic(True)
                self.temp_item.setPen(pen)
                self.canvas.layer_manager.apply_current_layer_props(self.temp_item)
                self.canvas.scene().addItem(self.temp_item)
                
            elif self.state == 2:
                # 第三次点击：定稿！
                if self.temp_item:
                    self.temp_item.set_coords([self.p1, self.p2, pt])
                    current_color = self.canvas.color_manager.get_color()
                    final_pen = QPen(current_color, 1)
                    final_pen.setCosmetic(True)
                    self.temp_item.setPen(final_pen)
                    self.canvas.layer_manager.apply_current_layer_props(self.temp_item)
                    
                    cmd = CommandCreateDimension(self.canvas.scene(), self.temp_item)
                    self.canvas.undo_stack.push(cmd)
                    
                    self.temp_item = None
                
                self.p1 = None
                self.p2 = None
                self.state = 0
                
            self._update_hud()
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state > 0:
                self._cleanup_temp_items()
                self._update_hud()
            else:
                self.canvas.switch_tool("选择")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        pt = (final_point.x(), final_point.y())
        
        # 实时更新皮筋线或尺寸线
        if self.state == 1 and self.preview_line:
            self.preview_line.setLine(QLineF(self.p1[0], self.p1[1], pt[0], pt[1]))
        elif self.state == 2 and self.temp_item:
            self.temp_item.set_coords([self.p1, self.p2, pt])
            
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cleanup_temp_items()
            if hasattr(self.canvas, '_cleanup_tracking_huds'):
                self.canvas._cleanup_tracking_huds()
            return True
        return False