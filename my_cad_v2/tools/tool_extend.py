# tools/tool_extend.py
import math
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPainterPath
import shapely.geometry as sg
from shapely.ops import unary_union

from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartCircleItem, 
    SmartPolylineItem, SmartArcItem, SmartEllipseItem, SmartSplineItem
)

class CommandExtendGeom(QUndoCommand):
    def __init__(self, scene, old_item, new_item, layer_manager):
        super().__init__()
        self.scene = scene
        self.old_item = old_item
        self.new_item = new_item
        self.layer_manager = layer_manager
        
        pen = QPen(self.old_item.pen().color(), 1, self.old_item.pen().style())
        pen.setCosmetic(True)
        self.new_item.setPen(pen)
        self.layer_manager.copy_layer_props(self.new_item, self.old_item)

    def redo(self):
        self.scene.clearSelection()
        if self.old_item in self.scene.items():
            self.scene.removeItem(self.old_item)
        if self.new_item not in self.scene.items():
            self.scene.addItem(self.new_item)

    def undo(self):
        if self.new_item in self.scene.items():
            self.scene.removeItem(self.new_item)
        if self.old_item not in self.scene.items():
            self.scene.addItem(self.old_item)


class ExtendTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.ghost_item = None
        self.current_extend_data = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self._cleanup_ghost()
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghost()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghost(self):
        if self.ghost_item and self.ghost_item.scene():
            self.canvas.scene().removeItem(self.ghost_item)
        self.ghost_item = None
        self.current_extend_data = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        text, color = "延伸: 移动鼠标预览，点击延伸至最近边界 (封闭图形不可延伸)", "#5cb85c"
        self.canvas.hud_polar_info.setHtml(f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>✏️ {text}</div>")
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _get_item_geom(self, item):
        geom_type = getattr(item, 'geom_type', 'unknown')
        if geom_type in ('text', 'dim', 'ortho_dim', 'rad_dim', 'angle_dim', 'arclen_dim', 'leader'):
            return None
        try:
            if hasattr(item, 'get_geom_coords'):
                coords = list(item.get_geom_coords())
            else:
                coords = list(item.coords)
            if not coords or len(coords) < 2: return None
            
            if geom_type in ('poly', 'circle', 'ellipse'):
                if math.hypot(coords[0][0] - coords[-1][0], coords[0][1] - coords[-1][1]) > 1e-5:
                    coords.append(coords[0])
            return sg.LineString(coords)
        except: pass
        return None

    def _get_boundaries(self, exclude_item):
        lines = []
        for item in self.canvas.scene().items():
            if getattr(item, 'is_smart_shape', False) and item != exclude_item and item.isVisible():
                geom = self._get_item_geom(item)
                if geom and not geom.is_empty: lines.append(geom)
        if not lines: return None
        return unary_union(lines)

    def _get_extend_data(self, target_item, click_pos):
        geom_type = getattr(target_item, 'geom_type', '')
        if geom_type in ('poly', 'circle', 'ellipse'): return None

        boundaries = self._get_boundaries(target_item)
        if not boundaries or boundaries.is_empty: return None

        px, py = click_pos.x(), click_pos.y()
        
        # ==========================================
        # 直线、多段线、样条曲线 的端点切线延伸逻辑
        # ==========================================
        if geom_type in ('line', 'polyline', 'spline'):
            coords = list(target_item.coords)
            if len(coords) < 2: return None
            
            segs = getattr(target_item, 'segments', []) if geom_type == 'polyline' else None
            
            p_start, p_end = coords[0], coords[-1]
            dist_to_start = math.hypot(px - p_start[0], py - p_start[1])
            dist_to_end = math.hypot(px - p_end[0], py - p_end[1])
            
            is_start = dist_to_start < dist_to_end
            idx_target = 0 if is_start else -1
            
            # 【修复点】：智能切线求导，如果末端是圆弧，顺着切线射出
            if geom_type == 'polyline' and segs:
                if is_start:
                    seg = segs[0] if len(segs) > 0 else {}
                    if seg.get('type') == 'arc' and 'bulge' in seg:
                        bulge = seg['bulge']
                        dx, dy = coords[1][0] - coords[0][0], coords[1][1] - coords[0][1]
                        chord_angle = math.atan2(dy, dx)
                        alpha = 2 * math.atan(bulge)
                        tangent_angle = chord_angle - alpha
                        nx, ny = -math.cos(tangent_angle), -math.sin(tangent_angle)
                    else:
                        vx, vy = coords[0][0] - coords[1][0], coords[0][1] - coords[1][1]
                        length = math.hypot(vx, vy)
                        if length < 1e-4: return None
                        nx, ny = vx / length, vy / length
                else:
                    seg = segs[-1] if len(segs) > 0 else {}
                    if seg.get('type') == 'arc' and 'bulge' in seg:
                        bulge = seg['bulge']
                        dx, dy = coords[-1][0] - coords[-2][0], coords[-1][1] - coords[-2][1]
                        chord_angle = math.atan2(dy, dx)
                        alpha = 2 * math.atan(bulge)
                        tangent_angle = chord_angle + alpha
                        nx, ny = math.cos(tangent_angle), math.sin(tangent_angle)
                    else:
                        vx, vy = coords[-1][0] - coords[-2][0], coords[-1][1] - coords[-2][1]
                        length = math.hypot(vx, vy)
                        if length < 1e-4: return None
                        nx, ny = vx / length, vy / length
            else:
                if is_start:
                    vx, vy = coords[0][0] - coords[1][0], coords[0][1] - coords[1][1]
                else:
                    vx, vy = coords[-1][0] - coords[-2][0], coords[-1][1] - coords[-2][1]
                length = math.hypot(vx, vy)
                if length < 1e-4: return None
                nx, ny = vx / length, vy / length
            
            ray_start = coords[idx_target]
            ray_end = (ray_start[0] + nx * 10000, ray_start[1] + ny * 10000)
            ray_line = sg.LineString([ray_start, ray_end])
            
            intersections = ray_line.intersection(boundaries)
            if intersections.is_empty: return None

            def extract_points(g):
                pts = []
                if g.is_empty: return pts
                if g.geom_type == 'Point': pts.append(g)
                elif g.geom_type == 'MultiPoint': pts.extend(list(g.geoms))
                elif g.geom_type == 'GeometryCollection':
                    for sub_g in g.geoms: pts.extend(extract_points(sub_g))
                elif g.geom_type in ('LineString', 'MultiLineString'):
                    if g.geom_type == 'LineString': pts.append(sg.Point(g.coords[0]))
                    else:
                        for line in g.geoms: pts.append(sg.Point(line.coords[0]))
                return pts

            pts = extract_points(intersections)
            if not pts: return None

            min_dist = float('inf')
            best_pt = None
            ray_start_pt = sg.Point(*ray_start)
            
            for pt in pts:
                dist = pt.distance(ray_start_pt)
                if 1e-3 < dist < min_dist:
                    dot_product = (pt.x - ray_start[0])*nx + (pt.y - ray_start[1])*ny
                    if dot_product > 0:
                        min_dist = dist
                        best_pt = (pt.x, pt.y)

            if not best_pt: return None

            new_coords = list(coords)
            
            # 【修复点】：完美保留和追加 segments 数据，不破坏原有弧形
            new_segs = None
            if geom_type == 'polyline':
                new_segs = list(segs) if segs else []
                if new_segs:
                    while len(new_segs) < len(coords) - 1:
                        new_segs.append({'type': 'line'})
                        
                if is_start:
                    new_coords.insert(0, best_pt)
                    new_segs.insert(0, {'type': 'line'})
                else:
                    new_coords.append(best_pt)
                    new_segs.append({'type': 'line'})
                    
            elif geom_type == 'spline':
                if is_start:
                    new_coords.insert(0, best_pt)
                else:
                    new_coords.append(best_pt)
            else:
                new_coords[idx_target] = best_pt
                
            return {'type': geom_type, 'coords': new_coords, 'segments': new_segs}

        # ==========================================
        # 圆弧的轨道生长延伸逻辑
        # ==========================================
        elif geom_type == 'arc':
            cx, cy = target_item.center
            r = target_item.radius
            sa, ea = target_item.start_angle, target_item.end_angle
            
            click_angle = math.degrees(math.atan2(-(py - cy), px - cx))
            if click_angle < 0: click_angle += 360
            
            def diff_ccw(a, b): return (a - b) % 360.0
            def diff_cw(a, b): return (b - a) % 360.0
            
            dist_to_sa = min(diff_ccw(click_angle, sa), diff_cw(click_angle, sa))
            dist_to_ea = min(diff_ccw(click_angle, ea), diff_cw(click_angle, ea))
            
            is_extend_ccw = (dist_to_ea < dist_to_sa)
            
            ring = sg.Point(cx, cy).buffer(r, resolution=128).exterior
            intersections = ring.intersection(boundaries)
            if intersections.is_empty: return None
            
            def extract_points(g):
                pts = []
                if g.is_empty: return pts
                if g.geom_type == 'Point': pts.append(g)
                elif g.geom_type == 'MultiPoint': pts.extend(list(g.geoms))
                elif g.geom_type == 'GeometryCollection':
                    for sub_g in g.geoms: pts.extend(extract_points(sub_g))
                return pts

            pts = extract_points(intersections)
            if not pts: return None

            best_angle = None
            min_diff = 360.0
            
            for pt in pts:
                pt_a = math.degrees(math.atan2(-(pt.y - cy), pt.x - cx))
                if pt_a < 0: pt_a += 360
                
                if is_extend_ccw:
                    diff = diff_ccw(pt_a, ea)
                    if 0.1 < diff < min_diff:
                        min_diff = diff
                        best_angle = pt_a
                else:
                    diff = diff_cw(pt_a, sa)
                    if 0.1 < diff < min_diff:
                        min_diff = diff
                        best_angle = pt_a

            if best_angle is None: return None
            
            if is_extend_ccw: return {'type': 'arc', 'center': (cx, cy), 'radius': r, 'sa': sa, 'ea': best_angle}
            else: return {'type': 'arc', 'center': (cx, cy), 'radius': r, 'sa': best_angle, 'ea': ea}

        return None

    def _update_preview(self, final_point):
        lod = self.canvas.transform().m11()
        hit_size = 10.0 / lod if lod > 0 else 10.0
        rect = QRectF(final_point.x() - hit_size/2, final_point.y() - hit_size/2, hit_size, hit_size)
        items = self.canvas.scene().items(rect, Qt.ItemSelectionMode.IntersectsItemShape, Qt.SortOrder.DescendingOrder, self.canvas.transform())
        
        target_item = None
        for it in items:
            if getattr(it, 'is_smart_shape', False) and getattr(it, 'geom_type', '') not in ('text', 'dim', 'ortho_dim', 'rad_dim', 'angle_dim', 'arclen_dim', 'leader'):
                target_item = it; break
                
        if not target_item:
            self._cleanup_ghost()
            return

        data = self._get_extend_data(target_item, final_point)
        self.current_extend_data = {'item': target_item, 'data': data} if data else None

        if not data:
            self._cleanup_ghost()
            return
            
        if not self.ghost_item:
            self.ghost_item = QGraphicsPathItem()
            pen = QPen(QColor(0, 255, 0, 200), 2, Qt.PenStyle.DashLine) 
            pen.setCosmetic(True)
            self.ghost_item.setPen(pen)
            self.ghost_item.setZValue(5000)
            self.canvas.scene().addItem(self.ghost_item)
            
        path = QPainterPath()
        if data['type'] in ('line', 'polyline', 'spline'):
            coords = data['coords']
            path.moveTo(QPointF(*coords[0]))
            for x, y in coords[1:]: path.lineTo(QPointF(x, y))
        elif data['type'] == 'arc':
            c, r = data['center'], data['radius']
            sa, ea = data['sa'], data['ea']
            rect = QRectF(c[0]-r, c[1]-r, 2*r, 2*r)
            span = ea - sa
            if span <= 0: span += 360
            path.arcMoveTo(rect, sa)
            path.arcTo(rect, sa, span)
            
        self.ghost_item.setPath(path)
        self.ghost_item.show()

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_extend_data and self.current_extend_data['data']:
                item = self.current_extend_data['item']
                data = self.current_extend_data['data']
                
                if data['type'] == 'line':
                    new_item = SmartLineItem(data['coords'][0], data['coords'][1])
                elif data['type'] == 'polyline':
                    # 【核心修复】：注入 segments，恢复多段线的原有弧度
                    new_item = SmartPolylineItem(data['coords'], segments=data.get('segments'))
                elif data['type'] == 'spline':
                    new_item = SmartSplineItem(data['coords'])
                elif data['type'] == 'arc':
                    new_item = SmartArcItem(data['center'], data['radius'], data['sa'], data['ea'])
                    
                cmd = CommandExtendGeom(self.canvas.scene(), item, new_item, self.canvas.layer_manager)
                self.canvas.undo_stack.push(cmd)
                self._cleanup_ghost()
                
            self.canvas.scene().clearSelection()
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        self._update_preview(final_point)
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.deactivate(); self.canvas.switch_tool("选择")
            return True
        return False