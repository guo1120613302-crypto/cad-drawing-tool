# tools/tool_offset.py
from tools.base_tool import BaseTool
from core_items import CADRectItem, CADLineItem
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
from utils.geom_engine import GeometryEngine
import math

class CommandOffsetItem(QUndoCommand):
    def __init__(self, scene, new_item):
        super().__init__()
        self.scene = scene
        self.new_item = new_item
    def redo(self):
        if self.new_item not in self.scene.items(): self.scene.addItem(self.new_item)
    def undo(self):
        if self.new_item in self.scene.items():
            self.new_item.setSelected(False)
            self.scene.removeItem(self.new_item)

class OffsetTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.input_buffer = ""
        self.offset_distance = None  # 存储确定的偏移距离
        self.selected_target = None  # 准备偏移的实体
        
        self.state = "WAIT_DISTANCE" # 状态机：WAIT_DISTANCE, WAIT_SELECT, WAIT_SIDE

    def get_input_buffer(self):
        if self.state == "WAIT_DISTANCE":
            return f"输入偏移距离: {self.input_buffer}"
        elif self.state == "WAIT_SELECT":
            return f"请点击要偏移的对象 (距离:{self.offset_distance})"
        elif self.state == "WAIT_SIDE":
            return "请在要偏移的一侧点击鼠标"
        return ""

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.state = "WAIT_DISTANCE"
        self.input_buffer = ""
        self.offset_distance = None
        self.selected_target = None
        self.canvas.scene().clearSelection()

    def deactivate(self):
        self._reset_tool()

    def _reset_tool(self):
        self.state = "WAIT_DISTANCE"
        self.input_buffer = ""
        self.offset_distance = None
        self.selected_target = None
        if self.canvas: self.canvas.scene().clearSelection()

    def _create_offset_item(self, target_item, side_point):
        """核心计算逻辑"""
        new_item = None
        
        if isinstance(target_item, CADRectItem):
            poly = target_item.polygon()
            # 简单判断点击点在矩形内还是外，决定正负
            is_inside = poly.containsPoint(side_point, Qt.FillRule.OddEvenFill)
            # 向内偏移为负，向外偏移为正
            dist = -self.offset_distance if is_inside else self.offset_distance
            
            # 【调用底层 C++ 几何内核】
            new_poly = GeometryEngine.offset_polygon(poly, dist)
            if new_poly:
                new_item = CADRectItem(new_poly.boundingRect()) 
                new_item.setPolygon(new_poly) # 精确赋予偏移后的多边形
                
        elif isinstance(target_item, CADLineItem):
            # 直线的平行偏移计算
            line = target_item.line()
            p1, p2 = line.p1(), line.p2()
            dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
            length = math.hypot(dx, dy)
            if length == 0: return None
            
            # 计算法向量
            nx, ny = -dy / length, dx / length
            
            # 判断点击点在直线的哪一侧 (利用叉乘)
            cross_product = (side_point.x() - p1.x()) * dy - (side_point.y() - p1.y()) * dx
            if cross_product > 0:
                nx, ny = -nx, -ny
                
            off_p1 = QPointF(p1.x() + nx * self.offset_distance, p1.y() + ny * self.offset_distance)
            off_p2 = QPointF(p2.x() + nx * self.offset_distance, p2.y() + ny * self.offset_distance)
            
            new_item = CADLineItem(QLineF(off_p1, off_p2))

        if new_item:
            # 继承当前颜色
            current_color = self.canvas.color_manager.get_color()
            pen = QPen(current_color, 1)
            pen.setCosmetic(True)
            new_item.setPen(pen)
            
            cmd = CommandOffsetItem(self.canvas.scene(), new_item)
            self.canvas.undo_stack.push(cmd)

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == "WAIT_SELECT":
                # 获取点击位置的实体
                item = self.canvas.itemAt(event.pos())
                if isinstance(item, (CADRectItem, CADLineItem)):
                    self.selected_target = item
                    item.setSelected(True)
                    self.state = "WAIT_SIDE"
                return True
                
            elif self.state == "WAIT_SIDE":
                if self.selected_target:
                    self._create_offset_item(self.selected_target, final_point)
                    # 连续偏移支持
                    self.canvas.scene().clearSelection()
                    self.state = "WAIT_SELECT"
                    self.selected_target = None
                return True
                
        elif event.button() == Qt.MouseButton.RightButton:
            self._reset_tool()
            return True
        return False

    def keyPressEvent(self, event):
        if self.state == "WAIT_DISTANCE":
            key = event.text()
            if key.isdigit() or key == '.':
                self.input_buffer += key
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    try:
                        self.offset_distance = float(self.input_buffer)
                        self.state = "WAIT_SELECT"
                    except ValueError: pass
                return True
        elif event.key() == Qt.Key.Key_Escape:
            self._reset_tool()
            return True
        return False