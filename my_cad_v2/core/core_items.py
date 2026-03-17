# core/core_items.py
import math
from PyQt6.QtWidgets import (QGraphicsLineItem, QGraphicsPolygonItem, 
                             QGraphicsItem, QGraphicsTextItem, QStyle)
from PyQt6.QtCore import QPointF, QLineF, QRectF, Qt
from PyQt6.QtGui import (QPen, QColor, QPainterPathStroker, QPolygonF, 
                         QPainterPath, QBrush, QFont, QTextCursor)

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
        pts = []
        for i in range(720):
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
        path = QPainterPath()
        path.addEllipse(QPointF(*self.center), self.radius, self.radius)
        painter.drawPath(path)

    def get_grips(self):
        cx, cy = self.center
        r = self.radius
        return [(cx, cy), (cx+r, cy), (cx, cy-r), (cx-r, cy), (cx, cy+r)]


class SmartOrthogonalDimensionItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 专用CAD标准智能线性标注实体 (支持正交投影与实心箭头)"""
    geom_type = "ortho_dim"
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
        dist_aligned = math.hypot(dx, dy)
        if dist_aligned < 1e-4: 
            return path

        cx, cy = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
        off_x = offset_pt[0] - cx
        off_y = offset_pt[1] - cy

        mode = 'aligned'
        if abs(dx) > 1e-4 and abs(dy) > 1e-4:
            if abs(off_y) > abs(off_x) * 1.5:
                mode = 'horizontal'
            elif abs(off_x) > abs(off_y) * 1.5:
                mode = 'vertical'

        if mode == 'horizontal':
            dim_p1 = (p1[0], offset_pt[1])
            dim_p2 = (p2[0], offset_pt[1])
        elif mode == 'vertical':
            dim_p1 = (offset_pt[0], p1[1])
            dim_p2 = (offset_pt[0], p2[1])
        else:
            ux, uy = dx / dist_aligned, dy / dist_aligned
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
        dist_aligned = math.hypot(dx, dy)
        if dist_aligned < 1e-4: 
            return

        cx, cy = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
        off_x = offset_pt[0] - cx
        off_y = offset_pt[1] - cy

        mode = 'aligned'
        if abs(dx) > 1e-4 and abs(dy) > 1e-4:
            if abs(off_y) > abs(off_x) * 1.5:
                mode = 'horizontal'
            elif abs(off_x) > abs(off_y) * 1.5:
                mode = 'vertical'

        if mode == 'horizontal':
            dim_p1 = (p1[0], offset_pt[1])
            dim_p2 = (p2[0], offset_pt[1])
            measure_dist = abs(dx)
            angle = 0
            ext_dir_x, ext_dir_y = 0, (1 if offset_pt[1] > p1[1] else -1)
        elif mode == 'vertical':
            dim_p1 = (offset_pt[0], p1[1])
            dim_p2 = (offset_pt[0], p2[1])
            measure_dist = abs(dy)
            angle = -90 if dim_p1[1] < dim_p2[1] else 90 
            ext_dir_x, ext_dir_y = (1 if offset_pt[0] > p1[0] else -1), 0
        else:
            ux, uy = dx / dist_aligned, dy / dist_aligned
            nx, ny = -uy, ux
            vx, vy = offset_pt[0] - p1[0], offset_pt[1] - p1[1]
            proj = vx * nx + vy * ny
            dim_p1 = (p1[0] + proj * nx, p1[1] + proj * ny)
            dim_p2 = (p2[0] + proj * nx, p2[1] + proj * ny)
            measure_dist = dist_aligned
            angle = math.degrees(math.atan2(dim_p2[1] - dim_p1[1], dim_p2[0] - dim_p1[0]))
            if proj < 0: nx, ny = -nx, -ny
            ext_dir_x, ext_dir_y = nx, ny
            
        if angle > 90 or angle <= -90: 
            angle += 180

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
        
        exo = 2 * scale_f
        exe = 2 * scale_f
        arrow_size = 6 * scale_f

        for pt_orig, pt_dim in [(p1, dim_p1), (p2, dim_p2)]:
            dist_to_dim = math.hypot(pt_dim[0] - pt_orig[0], pt_dim[1] - pt_orig[1])
            if dist_to_dim > exo:
                start_pt = QPointF(pt_orig[0] + ext_dir_x * exo, pt_orig[1] + ext_dir_y * exo)
                painter.drawLine(start_pt, QPointF(*pt_dim))
            end_pt = QPointF(pt_dim[0] + ext_dir_x * exe, pt_dim[1] + ext_dir_y * exe)
            painter.drawLine(QPointF(*pt_dim), end_pt)

        painter.drawLine(QPointF(*dim_p1), QPointF(*dim_p2))

        painter.setBrush(QBrush(text_color)) 
        line_dx, line_dy = dim_p2[0] - dim_p1[0], dim_p2[1] - dim_p1[1]
        line_len = math.hypot(line_dx, line_dy)
        
        def draw_arrow(tip_x, tip_y, dir_x, dir_y):
            arrow_w = arrow_size * 0.2
            px, py = -dir_y, dir_x
            base_x = tip_x + dir_x * arrow_size
            base_y = tip_y + dir_y * arrow_size
            poly = QPolygonF([
                QPointF(tip_x, tip_y),
                QPointF(base_x + px * arrow_w, base_y + py * arrow_w),
                QPointF(base_x - px * arrow_w, base_y - py * arrow_w)
            ])
            painter.drawPolygon(poly)

        if line_len > 1e-4:
            lx, ly = line_dx / line_len, line_dy / line_len
            draw_arrow(dim_p1[0], dim_p1[1], lx, ly)
            draw_arrow(dim_p2[0], dim_p2[1], -lx, -ly)

        mid_x, mid_y = (dim_p1[0] + dim_p2[0]) / 2.0, (dim_p1[1] + dim_p2[1]) / 2.0

        painter.save()
        painter.translate(mid_x, mid_y)
        painter.rotate(angle)
        
        text_str = f"{measure_dist:.2f}"
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QPen(text_color)) 
        
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text_str)
        painter.drawText(int(-tw / 2.0), -int(3 * scale_f), text_str) 
        painter.restore()

    def get_grips(self):
        return [self.coords[0], self.coords[1], self.coords[2]]


class SmartPolylineItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能多段线实体"""
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
        pts = []
        span = self.end_angle - self.start_angle
        if span <= 0: 
            span += 360
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


class SmartEllipseItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能椭圆实体"""
    geom_type = "ellipse"
    def __init__(self, center, rx, ry, rotation_angle=0.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        
        self.center = center
        self.rx = abs(rx)
        self.ry = abs(ry)
        self.rotation_angle = rotation_angle 
        
        self.coords = [
            center, 
            (center[0] + rx * math.cos(math.radians(rotation_angle)), center[1] - rx * math.sin(math.radians(rotation_angle))),
            (center[0] - ry * math.sin(math.radians(rotation_angle)), center[1] - ry * math.cos(math.radians(rotation_angle)))
        ]
        
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
        max_r = max(self.rx, self.ry)
        margin = 10.0
        return QRectF(self.center[0] - max_r - margin, self.center[1] - max_r - margin, 2*max_r + 2*margin, 2*max_r + 2*margin)

    def get_geom_coords(self):
        pts = []
        rad_rot = math.radians(self.rotation_angle)
        cos_rot = math.cos(rad_rot)
        sin_rot = math.sin(rad_rot)
        for i in range(360):
            t = math.radians(i)
            px = self.rx * math.cos(t)
            py = self.ry * math.sin(t)
            rot_x = px * cos_rot - py * sin_rot
            rot_y = px * sin_rot + py * cos_rot
            pts.append((self.center[0] + rot_x, self.center[1] - rot_y))
        pts.append(pts[0])
        return pts

    def shape(self):
        path = QPainterPath()
        path.addEllipse(QRectF(-self.rx, -self.ry, 2*self.rx, 2*self.ry))
        
        trans_path = QPainterPath()
        cx, cy = self.center
        for i in range(path.elementCount()):
            el = path.elementAt(i)
            rad = math.radians(self.rotation_angle)
            nx = cx + el.x * math.cos(rad) + el.y * math.sin(rad)
            ny = cy - el.x * math.sin(rad) + el.y * math.cos(rad)
            if el.isMoveTo(): trans_path.moveTo(nx, ny)
            elif el.isLineTo(): trans_path.lineTo(nx, ny)
            else: trans_path.lineTo(nx, ny)
            
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0)
        return stroker.createStroke(trans_path)

    def paint(self, painter, option, widget=None):
        if self.rx < 1e-4 or self.ry < 1e-4: return
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(3)
        painter.setPen(pen)
        
        painter.save()
        painter.translate(*self.center)
        painter.rotate(-self.rotation_angle)
        path = QPainterPath()
        path.addEllipse(QRectF(-self.rx, -self.ry, 2*self.rx, 2*self.ry))
        painter.drawPath(path)
        painter.restore()

    def get_grips(self):
        cx, cy = self.center
        rad = math.radians(self.rotation_angle)
        return [
            (cx, cy),
            (cx + self.rx * math.cos(rad), cy - self.rx * math.sin(rad)),
            (cx - self.rx * math.cos(rad), cy + self.rx * math.sin(rad)),
            (cx + self.ry * math.sin(rad), cy + self.ry * math.cos(rad)),
            (cx - self.ry * math.sin(rad), cy - self.ry * math.cos(rad))
        ]


class SmartSplineItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能样条曲线实体 (基于Catmull-Rom平滑插值)"""
    geom_type = "spline"
    def __init__(self, coords, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.hot_grip_index = -1
        self.coords = coords
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

    def _build_spline_path(self):
        path = QPainterPath()
        if not self.coords: return path
        path.moveTo(QPointF(*self.coords[0]))
        if len(self.coords) == 1: return path
        if len(self.coords) == 2:
            path.lineTo(QPointF(*self.coords[1]))
            return path
            
        for i in range(len(self.coords) - 1):
            p0 = self.coords[i - 1] if i > 0 else self.coords[i]
            p1 = self.coords[i]
            p2 = self.coords[i + 1]
            p3 = self.coords[i + 2] if i < len(self.coords) - 2 else self.coords[i + 1]

            c1x = p1[0] + (p2[0] - p0[0]) / 6.0
            c1y = p1[1] + (p2[1] - p0[1]) / 6.0
            c2x = p2[0] - (p3[0] - p1[0]) / 6.0
            c2y = p2[1] - (p3[1] - p1[1]) / 6.0

            path.cubicTo(QPointF(c1x, c1y), QPointF(c2x, c2y), QPointF(*p2))
        return path

    def get_geom_coords(self):
        path = self._build_spline_path()
        pts = []
        for i in range(101):
            percent = i / 100.0
            p = path.pointAtPercent(percent)
            pts.append((p.x(), p.y()))
        return pts

    def boundingRect(self):
        return self.shape().boundingRect()

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(20.0)
        return stroker.createStroke(self._build_spline_path())

    def paint(self, painter, option, widget=None):
        if len(self.coords) < 2: return
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        elif self._is_hovered:
            pen.setWidth(3)
        painter.setPen(pen)
        painter.drawPath(self._build_spline_path())

    def get_grips(self):
        return list(self.coords)


class SmartTextItem(QGraphicsTextItem, SmartShapeMixin):
    """V2.0 智能文字实体 (支持双击编辑、多行输入、图层颜色同步)"""
    geom_type = "text"
    def __init__(self, text, position, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(120) 
        self.setPos(*position)
        self.coords = [position]
        self.hot_grip_index = -1
        
        font = QFont("Arial", 20)
        self.setFont(font)
        self._pen = QPen(QColor(255, 255, 255), 1)
        self.setDefaultTextColor(QColor(255, 255, 255))
        
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

    def setPen(self, pen):
        self._pen = pen
        self.setDefaultTextColor(pen.color())
        self.update()

    def pen(self): 
        return self._pen

    def set_coords(self, coords):
        if coords:
            self.setPos(*coords[0])
            self.coords = coords

    def get_geom_coords(self):
        return [] 

    def get_grips(self):
        rect = self.boundingRect()
        return [(self.x(), self.y()), (self.x() + rect.width(), self.y() + rect.height())]

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)


    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clearFocus()  # 主动失去焦点，触发 focusOutEvent 停止光标闪烁
            event.ignore()     # 忽略事件让其冒泡给画布，从而触发工具切换为“选择”
        else:
            super().keyPressEvent(event)

            
    def mouseDoubleClickEvent(self, event):
        if self.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus()
        super().mouseDoubleClickEvent(event)
        
    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())


class SmartLeaderItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能多重引线实体 (含原位文本框)"""
    geom_type = "leader"
    def __init__(self, arrow_pt, landing_pt, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(125)
        self.coords = [arrow_pt, landing_pt]
        
        self.text_item = QGraphicsTextItem(self)
        self.text_item.setFont(QFont("Arial", 14))
        self.text_item.setDefaultTextColor(QColor(255, 255, 255))
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_item.setPlainText("输入引线注释...")
        self.text_item.document().contentsChanged.connect(self._update_layout)
        
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)
        self._update_layout()

    def setPen(self, pen):
        self._pen = pen
        self.text_item.setDefaultTextColor(pen.color())
        self.update()

    def pen(self): return self._pen

    def set_coords(self, coords):
        self.coords = coords
        self._update_layout()

    def _update_layout(self):
        arrow_pt, landing_pt = self.coords
        is_right = landing_pt[0] >= arrow_pt[0]
        landing_len = 20.0
        end_x = landing_pt[0] + (landing_len if is_right else -landing_len)
        
        br = self.text_item.boundingRect()
        if is_right:
            self.text_item.setPos(end_x + 5, landing_pt[1] - br.height() / 2)
        else:
            self.text_item.setPos(end_x - br.width() - 5, landing_pt[1] - br.height() / 2)
        self.prepareGeometryChange()
        self.update()

    def get_geom_coords(self): return []
    def get_grips(self): return self.coords

    def boundingRect(self):
        return self.childrenBoundingRect().united(QRectF(self.coords[0][0]-10, self.coords[0][1]-10, 20, 20))

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.StateFlag.State_Selected
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        painter.setPen(pen)
        
        arrow_pt, landing_pt = self.coords
        is_right = landing_pt[0] >= arrow_pt[0]
        
        lod = painter.worldTransform().m11()
        scale_f = 1.0 / lod if lod > 0 else 1.0
        landing_len = 20.0 * scale_f
        end_x = landing_pt[0] + (landing_len if is_right else -landing_len)
        
        painter.drawLine(QPointF(*arrow_pt), QPointF(*landing_pt))
        painter.drawLine(QPointF(*landing_pt), QPointF(end_x, landing_pt[1]))
        
        dx, dy = landing_pt[0] - arrow_pt[0], landing_pt[1] - arrow_pt[1]
        dist = math.hypot(dx, dy)
        if dist > 1e-4:
            ux, uy = dx/dist, dy/dist
            arrow_size = 8 * scale_f
            nx, ny = -uy, ux
            p1 = QPointF(arrow_pt[0] + arrow_size*ux + arrow_size*nx*0.25, arrow_pt[1] + arrow_size*uy + arrow_size*ny*0.25)
            p2 = QPointF(arrow_pt[0] + arrow_size*ux - arrow_size*nx*0.25, arrow_pt[1] + arrow_size*uy - arrow_size*ny*0.25)
            painter.setBrush(pen.color())
            painter.drawPolygon(QPointF(*arrow_pt), p1, p2)


class SmartRadiusDimensionItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能半径/直径标注实体 (标准CAD水平着陆线样式)"""
    geom_type = "rad_dim"
    def __init__(self, center, edge_pt, prefix="R", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(110)
        self.coords = [center, edge_pt]
        self.prefix = prefix
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def pen(self): return self._pen

    def set_coords(self, coords):
        self.coords = coords
        self.prepareGeometryChange()
        self.update()

    def get_geom_coords(self): return []
    def get_grips(self): return self.coords

    def boundingRect(self):
        c, e = self.coords
        margin = 100.0
        return QRectF(min(c[0], e[0]) - margin, min(c[1], e[1]) - margin, 
                      abs(e[0]-c[0]) + 2*margin, abs(e[1]-c[1]) + 2*margin)

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.StateFlag.State_Selected
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        painter.setPen(pen)

        c, e = self.coords
        dx, dy = e[0] - c[0], e[1] - c[1]
        dist = math.hypot(dx, dy)
        if dist < 1e-4: return

        # 1. 画中心到边缘的连线
        painter.drawLine(QPointF(*c), QPointF(*e))

        lod = painter.worldTransform().m11()
        scale_f = 1.0 / lod if lod > 0 else 1.0
        arrow_size = 8 * scale_f
        
        # 2. 绘制边缘处的箭头
        ux, uy = dx/dist, dy/dist
        nx, ny = -uy, ux
        p1 = QPointF(e[0] - arrow_size*ux + arrow_size*nx*0.25, e[1] - arrow_size*uy + arrow_size*ny*0.25)
        p2 = QPointF(e[0] - arrow_size*ux - arrow_size*nx*0.25, e[1] - arrow_size*uy - arrow_size*ny*0.25)
        painter.setBrush(pen.color())
        painter.drawPolygon(QPointF(*e), p1, p2)

        # 3. 绘制 CAD 标准的水平着陆线
        landing_len = 15 * scale_f
        is_right = dx >= 0
        end_x = e[0] + (landing_len if is_right else -landing_len)
        painter.drawLine(QPointF(*e), QPointF(end_x, e[1]))

        # 4. 在水平线上方渲染文字
        text_str = f"{self.prefix} {dist:.2f}"
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text_str)
        
        text_x = e[0] + (2*scale_f if is_right else -tw - 2*scale_f)
        text_y = e[1] - 3*scale_f
        painter.drawText(int(text_x), int(text_y), text_str)


class SmartAngleDimensionItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能角度标注实体"""
    geom_type = "angle_dim"
    def __init__(self, p1, center, p2, offset_pt, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(110)
        self.coords = [p1, center, p2, offset_pt]
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def pen(self): return self._pen

    def set_coords(self, coords):
        self.coords = coords
        self.prepareGeometryChange()
        self.update()

    def get_geom_coords(self): return []
    def get_grips(self): return self.coords

    def boundingRect(self):
        c = self.coords[1]
        margin = 300.0
        return QRectF(c[0] - margin, c[1] - margin, 2*margin, 2*margin)

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.StateFlag.State_Selected
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        painter.setPen(pen)

        p1, c, p2, offset_pt = self.coords
        radius = math.hypot(offset_pt[0] - c[0], offset_pt[1] - c[1])
        if radius < 1e-4: return

        a1 = math.degrees(math.atan2(-(p1[1] - c[1]), p1[0] - c[0]))
        a2 = math.degrees(math.atan2(-(p2[1] - c[1]), p2[0] - c[0]))
        
        diff = (a2 - a1) % 360
        if diff > 180:
            a1, a2 = a2, a1
            diff = 360 - diff

        path = QPainterPath()
        rect = QRectF(c[0] - radius, c[1] - radius, 2*radius, 2*radius)
        path.arcMoveTo(rect, a1)
        path.arcTo(rect, a1, diff)
        painter.drawPath(path)

        # 【核心修复】：将箭头方向改为沿圆弧的“切线方向”，使其顺着弧线贴合
        def draw_arrow(angle_deg, is_start):
            lod = painter.worldTransform().m11()
            scale_f = 1.0 / lod if lod > 0 else 1.0
            arrow_size = 10 * scale_f
            arrow_width = 2.5 * scale_f  # 箭头半宽
            
            rad = math.radians(angle_deg)
            
            # 箭头顶点贴在边上
            tip_x = c[0] + radius * math.cos(rad)
            tip_y = c[1] - radius * math.sin(rad)
            tip = QPointF(tip_x, tip_y)
            
            # 计算圆弧在该点的切线向量 (逆时针方向)
            tx = -math.sin(rad)
            ty = -math.cos(rad)
            
            if is_start:
                # 起点处的箭头：指向顺时针方向 (顺着弧线往回指，顶到边上)
                dir_x, dir_y = -tx, -ty
            else:
                # 终点处的箭头：指向逆时针方向 (顺着弧线往前指，顶到边上)
                dir_x, dir_y = tx, ty
                
            norm_x, norm_y = -dir_y, dir_x
            
            base_x = tip_x - arrow_size * dir_x
            base_y = tip_y - arrow_size * dir_y
            
            p1 = QPointF(base_x + arrow_width * norm_x, base_y + arrow_width * norm_y)
            p2 = QPointF(base_x - arrow_width * norm_x, base_y - arrow_width * norm_y)
            
            painter.setBrush(pen.color())
            painter.drawPolygon(tip, p1, p2)

        # 绘制首尾两个箭头
        draw_arrow(a1, True)
        draw_arrow(a1 + diff, False)

        mid_a = a1 + diff / 2.0
        mid_rad = math.radians(mid_a)
        text_str = f"{diff:.1f}°"
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text_str)
        
        tx = c[0] + (radius + 15)*math.cos(mid_rad) - tw/2
        ty = c[1] - (radius + 15)*math.sin(mid_rad) + 5
        painter.drawText(int(tx), int(ty), text_str)
class SmartArcLengthDimensionItem(QGraphicsItem, SmartShapeMixin):
    """V2.0 智能弧长标注实体"""
    geom_type = "arclen_dim"
    def __init__(self, center, radius, start_angle, end_angle, offset_pt, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setZValue(110)
        self.coords = [center, offset_pt]
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle
        self._pen = QPen(QColor(255, 255, 255), 1)
        self._pen.setCosmetic(True)

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def pen(self): return self._pen

    def set_coords(self, coords):
        self.coords = coords
        self.prepareGeometryChange()
        self.update()

    def get_geom_coords(self): return []
    def get_grips(self): return self.coords

    def boundingRect(self):
        c = self.coords[0]
        margin = 300.0
        return QRectF(c[0] - margin, c[1] - margin, 2*margin, 2*margin)

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.StateFlag.State_Selected
        pen = QPen(self._pen)
        if self.isSelected():
            pen.setWidth(2)
            pen.setColor(QColor(0, 120, 215))
        painter.setPen(pen)

        c, offset_pt = self.coords
        dim_radius = math.hypot(offset_pt[0] - c[0], offset_pt[1] - c[1])
        if dim_radius < 1e-4: return

        span = self.end_angle - self.start_angle
        if span <= 0: span += 360

        rad1, rad2 = math.radians(self.start_angle), math.radians(self.end_angle)
        p1 = QPointF(c[0] + self.radius*math.cos(rad1), c[1] - self.radius*math.sin(rad1))
        e1 = QPointF(c[0] + (dim_radius + 10)*math.cos(rad1), c[1] - (dim_radius + 10)*math.sin(rad1))
        p2 = QPointF(c[0] + self.radius*math.cos(rad2), c[1] - self.radius*math.sin(rad2))
        e2 = QPointF(c[0] + (dim_radius + 10)*math.cos(rad2), c[1] - (dim_radius + 10)*math.sin(rad2))
        painter.drawLine(p1, e1)
        painter.drawLine(p2, e2)

        path = QPainterPath()
        rect = QRectF(c[0] - dim_radius, c[1] - dim_radius, 2*dim_radius, 2*dim_radius)
        path.arcMoveTo(rect, self.start_angle)
        path.arcTo(rect, self.start_angle, span)
        painter.drawPath(path)

        arc_length = 2 * math.pi * self.radius * (span / 360.0)
        text_str = f"⌒ {arc_length:.2f}"
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text_str)
        
        mid_a = self.start_angle + span / 2.0
        mid_rad = math.radians(mid_a)
        tx = c[0] + (dim_radius + 15)*math.cos(mid_rad) - tw/2
        ty = c[1] - (dim_radius + 15)*math.sin(mid_rad) + 5
        painter.drawText(int(tx), int(ty), text_str)
# =========================================================
# 真正的块管理器 (Block Manager) 与实例组件 [终极防弹版]
# =========================================================
from PyQt6.QtWidgets import QGraphicsItemGroup, QGraphicsItem
from PyQt6.QtGui import QPen, QBrush

BLOCK_REGISTRY = {}  # 全局块定义仓库：{ "块名称": [相对原点(0,0)的图元对象列表] }

def clone_geometry_item(item, dx=0, dy=0):
    """深度克隆引擎：增加严密的类型容错与深拷贝，绝不引发异常"""
    try:
        if not item or not hasattr(item, 'geom_type'):
            return None
        new_item = None
        if isinstance(item, SmartLineItem):
            new_item = SmartLineItem((item.coords[0][0]+dx, item.coords[0][1]+dy), 
                                     (item.coords[1][0]+dx, item.coords[1][1]+dy))
        elif isinstance(item, SmartPolygonItem):
            new_item = SmartPolygonItem([(x+dx, y+dy) for x, y in item.coords])
        elif isinstance(item, SmartPolylineItem):
            new_item = SmartPolylineItem([(x+dx, y+dy) for x, y in item.coords])
            if hasattr(item, 'segments'): new_item.segments = list(item.segments)
        elif isinstance(item, SmartArcItem):
            cx, cy = item.center
            new_item = SmartArcItem((cx+dx, cy+dy), item.radius, item.start_angle, item.end_angle)
        elif isinstance(item, SmartCircleItem):
            cx, cy = item.center
            new_item = SmartCircleItem((cx+dx, cy+dy), item.radius)
        elif isinstance(item, SmartEllipseItem):
            cx, cy = item.center
            try: new_item = SmartEllipseItem((cx+dx, cy+dy), item.rx, item.ry, getattr(item, 'rotation_angle', 0))
            except TypeError: new_item = SmartEllipseItem((cx+dx, cy+dy), item.rx, item.ry)
        elif isinstance(item, SmartSplineItem):
            new_item = SmartSplineItem([(x+dx, y+dy) for x, y in item.coords])

        if new_item:
            # 必须使用 QPen 和 QBrush 的构造函数进行深拷贝
            if hasattr(item, 'pen'):
                new_item.setPen(QPen(item.pen()))
            if hasattr(item, 'brush') and hasattr(new_item, 'setBrush'):
                new_item.setBrush(QBrush(item.brush()))
            
            # 确保 ID 标识同步
            new_item.is_smart_shape = True
            return new_item
    except Exception as e:
        print(f"Clone error: {e}")
        
    return None  


class SmartBlockReference(QGraphicsItem): # 抛弃 ItemGroup，用最基础的 Item
    def __init__(self, block_name):
        super().__init__()
        self.is_smart_shape = True  
        self.is_block = True        
        self.block_name = block_name
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.hot_grip_index = -1 

    def boundingRect(self):
        # 手动算出里面所有线条的范围，否则系统不知道在哪画框
        return self.childrenBoundingRect()

    def paint(self, painter, option, widget=None):
        # 绘制选中时的蓝色虚线框
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())

    def get_grips(self):
        return [(self.x(), self.y())]

    def get_geom_coords(self):
        return []

    def rebuild_from_registry(self):
        self.prepareGeometryChange() 
        
        # 1. 彻底切断旧子项的联系
        for child in list(self.childItems()):
            child.setParentItem(None)
            if child.scene():
                child.scene().removeItem(child)

        # 2. 从注册表克隆新成员
        if self.block_name in BLOCK_REGISTRY:
            for template_item in BLOCK_REGISTRY[self.block_name]:
                new_child = clone_geometry_item(template_item, 0, 0)
                if new_child:
                    new_child.setParentItem(self)
        self.update()