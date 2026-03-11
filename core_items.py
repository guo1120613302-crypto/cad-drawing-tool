# core_items.py
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsItem
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QPainterPathStroker, QPolygonF

class CADLineItem(QGraphicsLineItem):
    """CAD 标准直线实体"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setZValue(100) 
        self.setAcceptHoverEvents(True) 
        self._is_hovered = False
        self.hot_grip_index = -1 

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

    def boundingRect(self):
        rect = super().boundingRect()
        padding = 50.0  
        return rect.adjusted(-padding, -padding, padding, padding)

    def paint(self, painter, option, widget=None):
        pen = QPen(self.pen())
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215)) 
        elif self._is_hovered:
            pen.setWidth(2)
            pen.setColor(QColor(180, 220, 255)) 
            
        painter.setPen(pen)
        painter.drawLine(self.line())

    def get_grips(self):
        line = self.line()
        p1 = line.p1()
        p2 = line.p2()
        mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
        return [p1, mid, p2] 

class CADRectItem(QGraphicsPolygonItem):
    """CAD 多段线闭合矩形实体"""
    def __init__(self, rect, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        self.set_rect(rect)

    def set_rect(self, rect):
        poly = QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()])
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
        poly = self.polygon()
        count = poly.count()
        if count == 0: return []
        pts = [poly.at(i) for i in range(count)]
        
        # 【核心还原】：CAD矩形的8个夹点 (4个角点 + 4个边中点)
        grips = list(pts) # 索引 0,1,2,3 是四个角点
        for i in range(count):
            p1 = pts[i]
            p2 = pts[(i+1) % count]
            mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
            grips.append(mid) # 索引 4,5,6,7 是边中点
        return grips