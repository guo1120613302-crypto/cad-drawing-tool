# core_items.py
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsItem
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QPainterPathStroker

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
        # 【核心修复】：pen() 始终保存着用户的真实颜色
        pen = QPen(self.pen())
        
        # 视觉优先级的覆盖渲染（绝不污染真实的 self.pen()）
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215)) # 选中时的 CAD 蓝
        elif self._is_hovered:
            pen.setWidth(2)
            pen.setColor(QColor(180, 220, 255)) # 悬停高亮
            
        painter.setPen(pen)
        painter.drawLine(self.line())

    def get_grips(self):
        line = self.line()
        p1 = line.p1()
        p2 = line.p2()
        mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
        return [p1, mid, p2]