# core/core_items.py
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsItem
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QPainterPathStroker, QPolygonF

class SmartLineItem(QGraphicsLineItem):
    """V2.0 数据驱动直线实体"""
    def __init__(self, p1_tuple, p2_tuple, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setZValue(100) 
        self.setAcceptHoverEvents(True) 
        self._is_hovered = False
        self.hot_grip_index = -1 
        
        # 【核心改变】：图形的本体不再是 QLineF，而是纯数学坐标列表
        self.coords = [p1_tuple, p2_tuple]
        self._sync_visuals()

    def set_coords(self, coords):
        """外部工具修改坐标的唯一入口"""
        if len(coords) == 2:
            self.coords = coords
            self._sync_visuals()

    def _sync_visuals(self):
        """将内部的数学坐标同步给 Qt 的显示层"""
        (x1, y1), (x2, y2) = self.coords
        self.setLine(QLineF(x1, y1, x2, y2))

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update() 
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def shape(self):
        # 增加鼠标点击的判定粗细，不用非得点中那 1 像素
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0) 
        return stroker.createStroke(super().shape())

    def paint(self, painter, option, widget=None):
        pen = QPen(self.pen())
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215)) # 选中时的经典 CAD 蓝
        elif self._is_hovered:
            pen.setWidth(2)
            pen.setColor(QColor(180, 220, 255)) # 悬停高亮
            
        painter.setPen(pen)
        painter.drawLine(self.line())

    def get_grips(self):
        """返回用于 UI 渲染和基础捕捉的夹点 (端点与中点)"""
        (x1, y1), (x2, y2) = self.coords
        mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        return [(x1, y1), (mid_x, mid_y), (x2, y2)] 


class SmartPolygonItem(QGraphicsPolygonItem):
    """V2.0 数据驱动多段线/矩形实体"""
    def __init__(self, coords, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        
        # 【核心改变】：本体是一组坐标点，顺逆时针直接决定面积正负
        self.coords = coords
        self._sync_visuals()

    def set_coords(self, coords):
        self.coords = coords
        self._sync_visuals()

    def _sync_visuals(self):
        poly = QPolygonF()
        for x, y in self.coords:
            poly.append(QPointF(x, y))
        self.setPolygon(poly)

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0)
        return stroker.createStroke(super().shape())

    def paint(self, painter, option, widget=None):
        pen = QPen(self.pen())
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(2)
            pen.setColor(QColor(180, 220, 255))
        painter.setPen(pen)
        painter.drawPolygon(self.polygon())

    def get_grips(self):
        """返回多段线的角点与边中点 (共 8 个夹点)"""
        grips = list(self.coords) 
        count = len(self.coords)
        for i in range(count):
            x1, y1 = self.coords[i]
            x2, y2 = self.coords[(i + 1) % count]
            mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            grips.append((mid_x, mid_y))
        return grips