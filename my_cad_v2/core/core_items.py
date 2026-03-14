# core/core_items.py
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsItem
from PyQt6.QtCore import QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QPainterPathStroker, QPolygonF, QPainterPath
import math

class SmartShapeMixin:
    """【架构升级】V2.0 几何图元统一直系血统 (ID卡)"""
    is_smart_shape = True
    geom_type = "base"


class SmartLineItem(QGraphicsLineItem, SmartShapeMixin):
    """V2.0 数据驱动直线实体"""
    geom_type = "line"
    def __init__(self, p1_tuple, p2_tuple, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
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
            pen.setColor(QColor(0, 120, 215)) 
        elif self._is_hovered:
            pen.setWidth(3) 
        painter.setPen(pen)
        painter.drawLine(self.line())

    def get_grips(self):
        (x1, y1), (x2, y2) = self.coords
        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0
        return [(x1, y1), (mid_x, mid_y), (x2, y2)] 


class SmartPolygonItem(QGraphicsPolygonItem, SmartShapeMixin):
    """V2.0 数据驱动多段线/矩形实体"""
    geom_type = "poly"
    def __init__(self, coords, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
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
        stroker.setWidth(20.0)
        return stroker.createStroke(super().shape())

    def paint(self, painter, option, widget=None):
        pen = QPen(self.pen())
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(3) 
        painter.setPen(pen)
        painter.drawPolygon(self.polygon())

    def get_grips(self):
        grips = list(self.coords) 
        count = len(self.coords)
        for i in range(count):
            x1, y1 = self.coords[i]
            x2, y2 = self.coords[(i + 1) % count]
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0
            grips.append((mid_x, mid_y))
        return grips


class SmartDimensionItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能线性标注实体"""
    geom_type = "dim"
    def __init__(self, p1, p2, offset_pt, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
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
        if coords is None: 
            coords = self.coords
        path = QPainterPath()
        p1, p2, offset_pt = coords
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 1e-4: 
            return path
        
        ux, uy = dx / dist, dy / dist
        nx, ny = -uy, ux
        vx, vy = offset_pt[0] - p1[0], offset_pt[1] - p1[1]
        proj = vx * nx + vy * ny
        
        dim_p1 = (p1[0] + proj * nx, p1[1] + proj * ny)
        dim_p2 = (p2[0] + proj * nx, p2[1] + proj * ny)
        
        path.moveTo(QPointF(*p1))
        path.lineTo(QPointF(*dim_p1))
        path.moveTo(QPointF(*p2))
        path.lineTo(QPointF(*dim_p2))
        path.moveTo(QPointF(*dim_p1))
        path.lineTo(QPointF(*dim_p2))
        return path

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0) 
        return stroker.createStroke(self.get_lines_path())

    def paint(self, painter, option, widget=None):
        p1, p2, offset_pt = self.coords
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 1e-4: 
            return

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
            pen.setWidth(3) 
        painter.setPen(pen)
        
        lod = painter.worldTransform().m11()
        scale_f = 1.0 / lod if lod > 0 else 1.0
        ext = 3 * scale_f        
        arrow_size = 8 * scale_f 
        arrow_angle = 0.15       

        sign = 1 if proj >= 0 else -1
        l1_start = QPointF(p1[0], p1[1])
        l1_end = QPointF(dim_p1[0] + sign * ext * nx, dim_p1[1] + sign * ext * ny)
        l2_start = QPointF(p2[0], p2[1])
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
        if angle > 90 or angle <= -90: 
            angle += 180

        painter.save()
        painter.translate(mid_x, mid_y)
        painter.rotate(angle)
        
        text_str = f"{dist:.2f}"
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QPen(text_color)) 
        
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text_str)
        painter.drawText(int(-tw / 2.0), -int(4 * scale_f), text_str) 
        painter.restore()

    def get_grips(self):
        return [self.coords[0], self.coords[1], self.coords[2]]


class SmartCircleItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能圆实体"""
    geom_type = "circle"
    def __init__(self, center, radius, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        self.coords = [center, (center[0] + radius, center[1])]
        self._sync_data()
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)

    def _sync_data(self):
        self.center = self.coords[0]
        self.radius = math.hypot(self.coords[1][0] - self.coords[0][0], self.coords[1][1] - self.coords[0][1])

    def set_coords(self, coords):
        old_center = self.center
        old_edge = self.coords[1]
        new_center = coords[0]
        new_edge = coords[1]
        
        if new_center != old_center and new_edge == old_edge:
            dx = new_center[0] - old_center[0]
            dy = new_center[1] - old_center[1]
            self.coords = [new_center, (old_edge[0] + dx, old_edge[1] + dy)]
        else:
            self.coords = coords
            
        self._sync_data()
        self.prepareGeometryChange()
        self.update()

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def pen(self): 
        return self._pen

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        r = self.radius
        margin = 10.0
        return QRectF(self.center[0] - r - margin, self.center[1] - r - margin, 2*r + 2*margin, 2*r + 2*margin)

    def get_geom_coords(self):
        """【精度升级】：提供高精度物理轮廓供 Shapely 截断直线时使用"""
        pts = []
        for i in range(720): # 每0.5度一个点，消除折线误差
            angle = math.radians(i * 0.5)
            pts.append((self.center[0] + self.radius * math.cos(angle), self.center[1] - self.radius * math.sin(angle)))
        pts.append(pts[0])
        return pts

    def shape(self):
        path = QPainterPath()
        path.addEllipse(QPointF(*self.center), self.radius, self.radius)
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0)
        return stroker.createStroke(path)

    def paint(self, painter, option, widget=None):
        if self.radius < 1e-4: 
            return
            
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(3)
            
        painter.setPen(pen)
        
        # 启用全精度浮点路径渲染圆
        path = QPainterPath()
        path.addEllipse(QPointF(*self.center), self.radius, self.radius)
        painter.drawPath(path)

    def get_grips(self):
        cx, cy = self.center
        r = self.radius
        return [(cx, cy), (cx+r, cy), (cx, cy-r), (cx-r, cy), (cx, cy+r)]


class SmartPolylineItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能多段线实体，支持直线段和圆弧段（终极修复版）"""
    geom_type = "polyline"
    def __init__(self, coords, segments=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        self.coords = coords
        self.segments = segments if segments else [{"type": "line"} for _ in range(len(coords)-1)]
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)

    def set_coords(self, coords):
        self.coords = coords
        self.prepareGeometryChange()
        self.update()

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def pen(self): 
        return self._pen

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def get_geom_coords(self):
        return self.coords

    def _get_arc_path(self, p1, p2, bulge):
        path = QPainterPath()
        path.moveTo(QPointF(*p1))
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        chord = math.hypot(dx, dy)
        if chord < 1e-4 or abs(bulge) < 1e-4:
            path.lineTo(QPointF(*p2))
            return path

        # 完全贴合标准凸度圆心推导
        d = -(chord / 2.0) * ((1.0 - bulge**2) / (2.0 * bulge))
        mid_x, mid_y = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
        
        cx = mid_x - d * (dy / chord)
        cy = mid_y - d * (-dx / chord)
        radius = math.hypot(p1[0] - cx, p1[1] - cy)

        start_angle = math.degrees(math.atan2(-(p1[1] - cy), p1[0] - cx))
        span_angle = math.degrees(4 * math.atan(bulge))

        rect = QRectF(cx - radius, cy - radius, 2*radius, 2*radius)
        path.arcTo(rect, start_angle, span_angle)
        return path

    def shape(self):
        path = QPainterPath()
        if not self.coords: 
            return path
        path.moveTo(QPointF(*self.coords[0]))
        for i in range(len(self.coords) - 1):
            p1 = self.coords[i]
            p2 = self.coords[i + 1]
            seg = self.segments[i] if i < len(self.segments) else {"type": "line"}
            if seg.get("type") == "arc" and "bulge" in seg:
                arc_p = self._get_arc_path(p1, p2, seg["bulge"])
                path.addPath(arc_p)
            else:
                path.lineTo(QPointF(*p2))
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0)
        return stroker.createStroke(path)

    def boundingRect(self):
        return self.shape().boundingRect()

    def paint(self, painter, option, widget=None):
        if len(self.coords) < 2: 
            return
            
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(3)
        painter.setPen(pen)
        
        for i in range(len(self.coords) - 1):
            p1 = self.coords[i]
            p2 = self.coords[i + 1]
            seg_info = self.segments[i] if i < len(self.segments) else {"type": "line"}
            
            if seg_info.get("type") == "arc" and "bulge" in seg_info:
                path = self._get_arc_path(p1, p2, seg_info["bulge"])
                painter.drawPath(path)
            else:
                painter.drawLine(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1]))

    def get_grips(self):
        grips = list(self.coords)
        for i in range(len(self.coords) - 1):
            x1, y1 = self.coords[i]
            x2, y2 = self.coords[i+1]
            grips.append(((x1+x2)/2.0, (y1+y2)/2.0))
        return grips


class SmartArcItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能圆弧实体"""
    geom_type = "arc"
    def __init__(self, center, radius, start_angle, end_angle, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        
        self.center = center
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.coords = [center, (center[0] + radius, center[1])] 
        
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)

    def set_coords(self, coords):
        if isinstance(coords, dict):
            self.center = coords['center']
            self.radius = coords['radius']
            self.start_angle = coords['sa']
            self.end_angle = coords['ea']
            self.coords = [self.center, (self.center[0] + self.radius, self.center[1])]
        else:
            old_center = self.center
            new_center = coords[0]
            dx = new_center[0] - old_center[0]
            dy = new_center[1] - old_center[1]
            self.center = new_center
            self.coords = [new_center, (coords[1][0] + dx, coords[1][1] + dy)]
            
        self.prepareGeometryChange()
        self.update()

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def pen(self): 
        return self._pen

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        r = self.radius
        margin = 10.0
        return QRectF(self.center[0] - r - margin, self.center[1] - r - margin, 2*r + 2*margin, 2*r + 2*margin)

    def get_geom_coords(self):
        """【物理碰撞提升】：将多边形拟合精度拉满，确保 Shapely 完美切割其他线条"""
        pts = []
        span = self.end_angle - self.start_angle
        if span <= 0: 
            span += 360
        # 每 0.5 度一个点，消除折线误差
        steps = max(72, int(span * 2)) 
        for i in range(steps + 1):
            angle = math.radians(self.start_angle + (span * i / steps))
            pts.append((self.center[0] + self.radius * math.cos(angle), self.center[1] - self.radius * math.sin(angle)))
        return pts

    def shape(self):
        path = QPainterPath()
        rect = QRectF(self.center[0] - self.radius, self.center[1] - self.radius, 2*self.radius, 2*self.radius)
        span = self.end_angle - self.start_angle
        if span <= 0: 
            span += 360
        path.arcMoveTo(rect, self.start_angle)
        path.arcTo(rect, self.start_angle, span)
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0)
        return stroker.createStroke(path)

    def paint(self, painter, option, widget=None):
        if self.radius < 1e-4: 
            return
            
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(3)
        painter.setPen(pen)
        
        # 【终极渲染修复】：抛弃有精度丢失的 drawArc，启用浮点级 QPainterPath
        path = QPainterPath()
        rect = QRectF(self.center[0] - self.radius, self.center[1] - self.radius, 2*self.radius, 2*self.radius)
        span = self.end_angle - self.start_angle
        if span <= 0: 
            span += 360
            
        path.arcMoveTo(rect, self.start_angle)
        path.arcTo(rect, self.start_angle, span)
        painter.drawPath(path)

    def get_grips(self):
        pts = self.get_geom_coords()
        if not pts: 
            return []
        p_start = pts[0]
        p_end = pts[-1]
        p_mid = pts[len(pts)//2]
        return [p_start, p_mid, p_end, self.center]