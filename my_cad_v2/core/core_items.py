# core/core_items.py
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsItem
from PyQt6.QtCore import QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QPainterPathStroker, QPolygonF, QPainterPath
import math

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
        self.coords = [p1_tuple, p2_tuple]
        self._sync_visuals()

    def set_coords(self, coords):
        if len(coords) == 2:
            self.coords = coords
            self._sync_visuals()

    def _sync_visuals(self):
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
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0) 
        return stroker.createStroke(super().shape())

    def paint(self, painter, option, widget=None):
        pen = QPen(self.pen())
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215)) # 选中时的经典 CAD 蓝
        elif self._is_hovered:
            pen.setWidth(3) # 【修复】：悬停时仅加粗，绝不改变原本的图层颜色
            
        painter.setPen(pen)
        painter.drawLine(self.line())

    def get_grips(self):
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
        self.coords = coords
        self._sync_visuals()

    def set_coords(self, coords):
        self.coords = coords
        self._sync_visuals()

    def _sync_visuals(self):
        poly = QPolygonF()
        for x, y in self.coords: poly.append(QPointF(x, y))
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
        stroker.setWidth(20.0)
        return stroker.createStroke(super().shape())

    def paint(self, painter, option, widget=None):
        pen = QPen(self.pen())
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(3) # 【修复】：悬停时仅加粗，绝不改变原本的图层颜色
            
        painter.setPen(pen)
        painter.drawPolygon(self.polygon())

    def get_grips(self):
        grips = list(self.coords) 
        count = len(self.coords)
        for i in range(count):
            x1, y1 = self.coords[i]
            x2, y2 = self.coords[(i + 1) % count]
            mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            grips.append((mid_x, mid_y))
        return grips


class SmartDimensionItem(QGraphicsItem):
    """V2.0 智能线性标注实体 (纯正 CAD 风格)"""
    def __init__(self, p1, p2, offset_pt, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setZValue(110)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        self.coords = [p1, p2, offset_pt]
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def pen(self):
        return self._pen

    def set_coords(self, coords):
        self.coords = coords
        self.prepareGeometryChange()
        self.update()

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        p1, p2, offset_pt = self.coords
        xs = [p1[0], p2[0], offset_pt[0]]
        ys = [p1[1], p2[1], offset_pt[1]]
        margin = 100.0 
        return QRectF(min(xs) - margin, min(ys) - margin, max(xs) - min(xs) + 2*margin, max(ys) - min(ys) + 2*margin)

    def get_lines_path(self, coords=None):
        """【修复核心】：计算标注系统的精准数学路径（三根线），用于精确点击"""
        if coords is None: coords = self.coords
        path = QPainterPath()
        p1, p2, offset_pt = coords
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 1e-4: return path
        
        ux, uy = dx / dist, dy / dist
        nx, ny = -uy, ux
        vx, vy = offset_pt[0] - p1[0], offset_pt[1] - p1[1]
        proj = vx * nx + vy * ny
        
        dim_p1 = (p1[0] + proj * nx, p1[1] + proj * ny)
        dim_p2 = (p2[0] + proj * nx, p2[1] + proj * ny)
        
        path.moveTo(QPointF(*p1)); path.lineTo(QPointF(*dim_p1))
        path.moveTo(QPointF(*p2)); path.lineTo(QPointF(*dim_p2))
        path.moveTo(QPointF(*dim_p1)); path.lineTo(QPointF(*dim_p2))
        return path

    def shape(self):
        """【修复核心】：摒弃粗暴的矩形框，改为仅在标注线条上才可触发点击"""
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0) 
        return stroker.createStroke(self.get_lines_path())

    def paint(self, painter, option, widget=None):
        p1, p2, offset_pt = self.coords
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 1e-4: return

        ux, uy = dx / dist, dy / dist
        nx, ny = -uy, ux
        vx, vy = offset_pt[0] - p1[0], offset_pt[1] - p1[1]
        proj = vx * nx + vy * ny
        
        dim_p1 = (p1[0] + proj * nx, p1[1] + proj * ny)
        dim_p2 = (p2[0] + proj * nx, p2[1] + proj * ny)

        pen = QPen(self._pen)
        text_color = pen.color()
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
            text_color = QColor(0, 120, 215)
        elif self._is_hovered:
            pen.setWidth(3) # 【修复】：仅加粗，不改变标注本身的颜色
            
        painter.setPen(pen)
        
        lod = painter.worldTransform().m11()
        scale_f = 1.0 / lod if lod > 0 else 1.0
        gap = 4 * scale_f        
        ext = 3 * scale_f        
        arrow_size = 8 * scale_f 
        arrow_angle = 0.15       

        sign = 1 if proj >= 0 else -1
        l1_start = QPointF(p1[0] + sign * gap * nx, p1[1] + sign * gap * ny)
        l1_end = QPointF(dim_p1[0] + sign * ext * nx, dim_p1[1] + sign * ext * ny)
        l2_start = QPointF(p2[0] + sign * gap * nx, p2[1] + sign * gap * ny)
        l2_end = QPointF(dim_p2[0] + sign * ext * nx, dim_p2[1] + sign * ext * ny)

        painter.drawLine(l1_start, l1_end)
        painter.drawLine(l2_start, l2_end)
        painter.drawLine(QPointF(*dim_p1), QPointF(*dim_p2))

        painter.drawLine(QPointF(*dim_p1), QPointF(dim_p1[0] + arrow_size*ux + arrow_size*nx*arrow_angle, dim_p1[1] + arrow_size*uy + arrow_size*ny*arrow_angle))
        painter.drawLine(QPointF(*dim_p1), QPointF(dim_p1[0] + arrow_size*ux - arrow_size*nx*arrow_angle, dim_p1[1] + arrow_size*uy - arrow_size*ny*arrow_angle))
        painter.drawLine(QPointF(*dim_p2), QPointF(dim_p2[0] - arrow_size*ux + arrow_size*nx*arrow_angle, dim_p2[1] - arrow_size*uy + arrow_size*ny*arrow_angle))
        painter.drawLine(QPointF(*dim_p2), QPointF(dim_p2[0] - arrow_size*ux - arrow_size*nx*arrow_angle, dim_p2[1] - arrow_size*uy - arrow_size*ny*arrow_angle))

        mid_x, mid_y = (dim_p1[0] + dim_p2[0]) / 2.0, (dim_p1[1] + dim_p2[1]) / 2.0
        angle = math.degrees(math.atan2(dy, dx))
        if angle > 90 or angle <= -90: angle += 180

        painter.save()
        painter.translate(mid_x, mid_y)
        painter.rotate(angle)
        
        text_str = f"{dist:.2f}"
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QPen(text_color)) # 文字保持同色
        
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text_str)
        painter.drawText(int(-tw / 2.0), -int(4 * scale_f), text_str) 
        painter.restore()

    def get_grips(self):
        return [self.coords[0], self.coords[1], self.coords[2]]