# tools/tool_dim_angle.py
import math
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPainterPath
import shapely.geometry as sg

from tools.base_tool import BaseTool
from core.core_items import SmartAngleDimensionItem

class CommandDrawDimAngle(QUndoCommand):
    def __init__(self, scene, item, layer_manager):
        super().__init__()
        self.scene = scene
        self.item = item
        self.layer_manager = layer_manager
        
        # 兼容当前图层属性
        self.layer_manager.apply_current_layer_props(self.item)

    def redo(self):
        if self.item not in self.scene.items():
            self.scene.addItem(self.item)

    def undo(self):
        if self.item in self.scene.items():
            self.scene.removeItem(self.item)

class DimAngleTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.line1_pts = None
        self.line2_pts = None
        self.ghost_item = None
        self.highlight_line1 = None
        self.highlight_line2 = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.line1_pts = None
        self.line2_pts = None
        self._cleanup_ghosts()
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghosts()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghosts(self):
        if self.ghost_item and self.ghost_item.scene():
            self.canvas.scene().removeItem(self.ghost_item)
        self.ghost_item = None
        if self.highlight_line1 and self.highlight_line1.scene():
            self.canvas.scene().removeItem(self.highlight_line1)
        self.highlight_line1 = None
        if self.highlight_line2 and self.highlight_line2.scene():
            self.canvas.scene().removeItem(self.highlight_line2)
        self.highlight_line2 = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        if self.state == 0:
            text, color = "角度标注: 请选择第一条边 (支持直线、矩形、多边形)", "#5bc0de"
        elif self.state == 1:
            text, color = "角度标注: 请选择第二条边 (同一图形的不同边也可)", "#f0ad4e"
        else:
            text, color = "角度标注: 请拖动鼠标并点击，放置标注文本的位置", "#5cb85c"
        self.canvas.hud_polar_info.setHtml(f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>📐 {text}</div>")
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _get_clicked_segment(self, item, click_pos):
        """核心修复：将多边形、矩形、多段线剥离出最近的单条边，完美覆盖隐式闭合边"""
        geom_type = getattr(item, 'geom_type', '')
        
        # 1. 如果本来就是直线，直接返回
        if geom_type == 'line':
            return list(item.coords)
            
        # 2. 如果是多边形或多段线，遍历寻找鼠标点击的最近边
        elif geom_type in ('poly', 'polygon', 'polyline'):
            coords = list(getattr(item, 'coords', []))
            if not coords or len(coords) < 2: return None
            
            segments = []
            # 添加所有的常规边
            for i in range(len(coords)-1):
                segments.append((coords[i], coords[i+1]))
                
            # 【终极修复】：无论图形类型，只要首尾不重合，就把“最后一条回到起点的边”加进备选池
            # 这样多边形的最后一条边就不会变成“不可触碰的死角”了
            if math.hypot(coords[0][0]-coords[-1][0], coords[0][1]-coords[-1][1]) > 1e-5:
                segments.append((coords[-1], coords[0]))
                
            min_dist = float('inf')
            best_seg = None
            px, py = click_pos.x(), click_pos.y()
            pt = sg.Point(px, py)
            
            for p1, p2 in segments:
                line = sg.LineString([p1, p2])
                dist = line.distance(pt)
                if dist < min_dist:
                    min_dist = dist
                    best_seg = (p1, p2)
                    
            # 容差判断：确保真的点中了边
            lod = self.canvas.transform().m11()
            tolerance = 10.0 / lod if lod > 0 else 10.0
            if min_dist <= tolerance:
                return best_seg
                
        return None

    def _highlight_segment(self, pts):
        """将被选中的边高亮显示为蓝色，方便用户确认"""
        hl = QGraphicsLineItem(QLineF(pts[0][0], pts[0][1], pts[1][0], pts[1][1]))
        pen = QPen(QColor(0, 120, 215), 2)
        pen.setCosmetic(True)
        hl.setPen(pen)
        hl.setZValue(5000)
        self.canvas.scene().addItem(hl)
        return hl

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state in (0, 1):
                lod = self.canvas.transform().m11()
                hit_size = 10.0 / lod if lod > 0 else 10.0
                rect = QRectF(final_point.x() - hit_size/2, final_point.y() - hit_size/2, hit_size, hit_size)
                items = self.canvas.scene().items(rect, Qt.ItemSelectionMode.IntersectsItemShape, Qt.SortOrder.DescendingOrder, self.canvas.transform())
                
                target_seg = None
                for it in items:
                    if getattr(it, 'is_smart_shape', False) and getattr(it, 'geom_type', '') not in ('text', 'dim', 'ortho_dim', 'rad_dim', 'arclen_dim', 'leader'):
                        seg = self._get_clicked_segment(it, final_point)
                        if seg:
                            target_seg = seg
                            break
                            
                if target_seg:
                    if self.state == 0:
                        self.line1_pts = target_seg
                        self.highlight_line1 = self._highlight_segment(target_seg)
                        self.state = 1
                    elif self.state == 1:
                        # 确保第二条边不是刚刚选中的第一条边 (正反向均要判断)
                        if target_seg != self.line1_pts and target_seg != (self.line1_pts[1], self.line1_pts[0]):
                            self.line2_pts = target_seg
                            self.highlight_line2 = self._highlight_segment(target_seg)
                            self.state = 2
                self._update_hud()
                return True
                
            elif self.state == 2:
                self._finalize_dimension(final_point)
                return True
                
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state == 1:
                self.state = 0
                self.line1_pts = None
                if self.highlight_line1:
                    self.canvas.scene().removeItem(self.highlight_line1)
                    self.highlight_line1 = None
                self._update_hud()
            elif self.state == 2:
                self.state = 1
                self.line2_pts = None
                if self.highlight_line2:
                    self.canvas.scene().removeItem(self.highlight_line2)
                    self.highlight_line2 = None
                if self.ghost_item:
                    self.ghost_item.hide()
                self._update_hud()
            else:
                self.deactivate()
                self.canvas.switch_tool("选择")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        if self.state == 2:
            self._update_preview(final_point)
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def _calculate_intersection(self):
        (x1, y1), (x2, y2) = self.line1_pts
        (x3, y3), (x4, y4) = self.line2_pts
        
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-6: return None # 两条边完全平行
        
        px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / denom
        py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / denom
        return (px, py)

    def _update_preview(self, text_pos):
        if not self.ghost_item:
            self.ghost_item = QGraphicsPathItem()
            pen = QPen(QColor(150, 150, 150), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.ghost_item.setPen(pen)
            self.canvas.scene().addItem(self.ghost_item)
        
        intersect = self._calculate_intersection()
        if not intersect:
            self.ghost_item.hide()
            return
        
        cx, cy = intersect
        tx, ty = text_pos.x(), text_pos.y()
        radius = math.hypot(tx - cx, ty - cy)
        
        path = QPainterPath()
        # 简单画一个占位预览圆
        rect = QRectF(cx - radius, cy - radius, 2*radius, 2*radius)
        path.addEllipse(rect)
        self.ghost_item.setPath(path)
        self.ghost_item.show()

    def _finalize_dimension(self, text_pos):
        intersect = self._calculate_intersection()
        if intersect:
            try:
                def get_far_pt(pts, c):
                    d0 = math.hypot(pts[0][0]-c[0], pts[0][1]-c[1])
                    d1 = math.hypot(pts[1][0]-c[0], pts[1][1]-c[1])
                    return pts[0] if d0 > d1 else pts[1]
                    
                p1 = get_far_pt(self.line1_pts, intersect)
                p2 = get_far_pt(self.line2_pts, intersect)
                
                new_item = SmartAngleDimensionItem(p1, intersect, p2, (text_pos.x(), text_pos.y()))
                cmd = CommandDrawDimAngle(self.canvas.scene(), new_item, self.canvas.layer_manager)
                self.canvas.undo_stack.push(cmd)
            except Exception as e:
                try:
                    new_item = SmartAngleDimensionItem(self.line1_pts, self.line2_pts, (text_pos.x(), text_pos.y()))
                    cmd = CommandDrawDimAngle(self.canvas.scene(), new_item, self.canvas.layer_manager)
                    self.canvas.undo_stack.push(cmd)
                except Exception as e2:
                    print(f"Error creating angle dimension: {e2}")

        self.state = 0
        self.line1_pts = None
        self.line2_pts = None
        self._cleanup_ghosts()
        self._update_hud()