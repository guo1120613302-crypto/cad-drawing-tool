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
        
        # 开启悬停探测
        self.setAcceptHoverEvents(True) 
        self._is_hovered = False
        # 记录当前被捏住的夹点 (-1 代表静止状态)
        self.hot_grip_index = -1 

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update() # 触发重绘
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def shape(self):
        # 【神级优化】：给 1 像素的线条包上一层 10 像素厚的“隐形肉体”
        # 彻底解决线条太细导致鼠标点不中、悬停不灵敏的问题！
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0) 
        return stroker.createStroke(super().shape())

    def boundingRect(self):
        rect = super().boundingRect()
        padding = 50.0  
        return rect.adjusted(-padding, -padding, padding, padding)

    def paint(self, painter, option, widget=None):
        pen = self.pen()
        
        # 【悬停预选高亮】：没被选中 + 鼠标滑过 = 冰蓝色粗体发光
        if self._is_hovered and not self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(180, 220, 255)) 
            
        painter.setPen(pen)
        painter.drawLine(self.line())

    def get_grips(self):
        line = self.line()
        p1 = line.p1()
        p2 = line.p2()
        mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
        return [p1, mid, p2] # 索引: 0=起点, 1=中点, 2=终点