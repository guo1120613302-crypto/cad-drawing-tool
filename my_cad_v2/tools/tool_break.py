# tools/tool_break.py
import math
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
import shapely.geometry as sg
from shapely.ops import split, snap

from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartCircleItem, 
    SmartPolylineItem, SmartArcItem, SmartEllipseItem, SmartSplineItem
)

class CommandBreakGeom(QUndoCommand):
    def __init__(self, scene, old_item, new_items, layer_manager):
        super().__init__()
        self.scene = scene
        self.old_item = old_item
        self.new_items = new_items
        self.layer_manager = layer_manager
        
        for new_item in self.new_items:
            pen = QPen(self.old_item.pen().color(), 1, self.old_item.pen().style())
            pen.setCosmetic(True)
            new_item.setPen(pen)
            self.layer_manager.copy_layer_props(new_item, self.old_item)

    def redo(self):
        self.scene.clearSelection()
        if self.old_item in self.scene.items():
            self.scene.removeItem(self.old_item)
        for new_item in self.new_items:
            if new_item not in self.scene.items():
                self.scene.addItem(new_item)

    def undo(self):
        for new_item in self.new_items:
            if new_item in self.scene.items():
                self.scene.removeItem(new_item)
        if self.old_item not in self.scene.items():
            self.scene.addItem(self.old_item)


class BreakTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0

    def get_reference_point(self):
        return None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self._update_hud()

    def deactivate(self): 
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): 
            return
            
        self.canvas.hud_polar_info.show()
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:#d9534f; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>"
            f"🔨 打断于点: 请点击图形上的任意一点将其一分为二 (支持全系图形)</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            lod = self.canvas.transform().m11()
            hit_size = 10.0 / lod if lod > 0 else 10.0
            rect = QRectF(final_point.x() - hit_size/2, final_point.y() - hit_size/2, hit_size, hit_size)
            
            items = self.canvas.scene().items(
                rect, Qt.ItemSelectionMode.IntersectsItemShape, 
                Qt.SortOrder.DescendingOrder, self.canvas.transform()
            )
            
            target_item = None
            for it in items:
                if getattr(it, 'is_smart_shape', False) and getattr(it, 'geom_type', '') not in ('text', 'dim', 'ortho_dim', 'rad_dim', 'angle_dim', 'arclen_dim', 'leader'):
                    target_item = it
                    break
            
            if target_item:
                self._perform_break(target_item, final_point)
                
            self.canvas.scene().clearSelection()
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
            
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def _perform_break(self, target_item, click_pos):
        geom_type = getattr(target_item, 'geom_type', '')
        px, py = click_pos.x(), click_pos.y()
        new_items = []
        
        # ==========================================
        # 1. 纯直线打断逻辑
        # ==========================================
        if geom_type == 'line':
            p1, p2 = target_item.coords
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            length_sq = dx*dx + dy*dy
            if length_sq > 1e-6:
                t = max(0, min(1, ((px - p1[0])*dx + (py - p1[1])*dy) / length_sq))
                bx, by = p1[0] + t*dx, p1[1] + t*dy
            else:
                bx, by = px, py
                
            if math.hypot(bx - p1[0], by - p1[1]) > 1e-4 and math.hypot(bx - p2[0], by - p2[1]) > 1e-4:
                new_items.append(SmartLineItem(p1, (bx, by)))
                new_items.append(SmartLineItem((bx, by), p2))

        # ==========================================
        # 2. 纯数学圆 / 圆弧的无损打断逻辑
        # ==========================================
        elif geom_type in ('circle', 'arc'):
            cx, cy = target_item.center
            r = target_item.radius
            angle = math.degrees(math.atan2(-(py - cy), px - cx))
            angle = angle % 360.0
            
            if geom_type == 'circle':
                sa = (angle + 0.01) % 360.0
                new_items.append(SmartArcItem((cx, cy), r, sa, angle))
            else:
                sa, ea = target_item.start_angle, target_item.end_angle
                span = (ea - sa) % 360.0
                if span <= 0: span += 360.0
                if ((angle - sa) % 360.0) <= span:
                    if abs((angle - sa) % 360.0) > 0.5 and abs((ea - angle) % 360.0) > 0.5:
                        new_items.append(SmartArcItem((cx, cy), r, sa, angle))
                        new_items.append(SmartArcItem((cx, cy), r, angle, ea))

        # ==========================================
        # 3. 多段线 / 多边形 的无损凸度拆分逻辑 (核心修复)
        # ==========================================
        elif geom_type in ('polyline', 'poly'):
            coords = list(target_item.coords)
            is_poly = (geom_type == 'poly')
            if is_poly:
                if math.hypot(coords[0][0] - coords[-1][0], coords[0][1] - coords[-1][1]) > 1e-5:
                    coords.append(coords[0])

            segs = list(getattr(target_item, 'segments', []))
            while len(segs) < len(coords) - 1:
                segs.append({'type': 'line'})

            min_dist = float('inf')
            best_info = None
            click_pt = sg.Point(px, py)

            for i in range(len(coords) - 1):
                p1, p2 = coords[i], coords[i+1]
                seg = segs[i]

                if seg.get('type') == 'arc' and 'bulge' in seg and abs(seg['bulge']) > 1e-4:
                    bulge = seg['bulge']
                    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                    chord = math.hypot(dx, dy)
                    if chord < 1e-4: continue

                    d = -(chord / 2.0) * ((1.0 - bulge**2) / (2.0 * bulge))
                    mid_x, mid_y = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
                    cx, cy = mid_x - d * (dy / chord), mid_y - d * (-dx / chord)
                    R = math.hypot(p1[0] - cx, p1[1] - cy)

                    start_angle = math.atan2(-(p1[1] - cy), p1[0] - cx)
                    span_angle = 4 * math.atan(bulge)

                    steps = max(16, int(abs(math.degrees(span_angle)) / 5))
                    arc_pts = []
                    for j in range(steps + 1):
                        a = start_angle + span_angle * j / steps
                        arc_pts.append((cx + R * math.cos(a), cy - R * math.sin(a)))

                    arc_line = sg.LineString(arc_pts)
                    dist = arc_line.distance(click_pt)

                    if dist < min_dist:
                        min_dist = dist
                        proj_dist = arc_line.project(click_pt)
                        t = max(0.001, min(0.999, proj_dist / arc_line.length))
                        proj_pt = arc_line.interpolate(proj_dist)
                        
                        # 【核心公式】：完美计算打断后的新凸度，绝对保真
                        bulge1 = math.tan(t * math.atan(bulge))
                        bulge2 = math.tan((1.0 - t) * math.atan(bulge))

                        best_info = {'idx': i, 'type': 'arc', 'B': (proj_pt.x, proj_pt.y), 'bulge1': bulge1, 'bulge2': bulge2}
                else:
                    line = sg.LineString([p1, p2])
                    dist = line.distance(click_pt)
                    if dist < min_dist:
                        min_dist = dist
                        proj_dist = line.project(click_pt)
                        proj_pt = line.interpolate(proj_dist)
                        best_info = {'idx': i, 'type': 'line', 'B': (proj_pt.x, proj_pt.y)}

            if min_dist > 5.0 or best_info is None:
                return

            idx, B = best_info['idx'], best_info['B']

            if not is_poly:
                coords1, segs1 = coords[:idx+1] + [B], segs[:idx]
                coords2, segs2 = [B] + coords[idx+1:], segs[idx+1:]

                if best_info['type'] == 'arc':
                    segs1.append({'type': 'arc', 'bulge': best_info['bulge1']})
                    segs2.insert(0, {'type': 'arc', 'bulge': best_info['bulge2']})
                else:
                    segs1.append({'type': 'line'})
                    segs2.insert(0, {'type': 'line'})

                new_items.append(SmartPolylineItem(coords1, segments=segs1))
                new_items.append(SmartPolylineItem(coords2, segments=segs2))
            else:
                # 封闭多边形被打断后，自动展开成一条含有正确凸度的敞开多段线
                new_coords = [B] + coords[idx+1:-1] + coords[:idx+1] + [B]
                if best_info['type'] == 'arc':
                    new_segs = [{'type': 'arc', 'bulge': best_info['bulge2']}] + segs[idx+1:] + segs[:idx] + [{'type': 'arc', 'bulge': best_info['bulge1']}]
                else:
                    new_segs = [{'type': 'line'}] + segs[idx+1:] + segs[:idx] + [{'type': 'line'}]
                new_items.append(SmartPolylineItem(new_coords, segments=new_segs))

        # ==========================================
        # 4. 椭圆 / 样条曲线的完美还原逻辑
        # ==========================================
        elif geom_type in ('ellipse', 'spline'):
            coords = target_item.get_geom_coords()
            if geom_type == 'ellipse':
                if math.hypot(coords[0][0]-coords[-1][0], coords[0][1]-coords[-1][1]) > 1e-5:
                    coords.append(coords[0])

            if not coords or len(coords) < 2: return
            line = sg.LineString(coords)
            pt = sg.Point(px, py)
            if line.distance(pt) > 5.0: return

            pt_on_line = line.interpolate(line.project(pt))
            split_res = split(snap(line, pt_on_line, 1e-4), pt_on_line)

            # 【修复】：彻底移除了坑人的 simplify(1.0)，保留所有的 128 个拟合点，保证打断后绝对平滑如初！
            if len(split_res.geoms) > 1:
                for g in split_res.geoms:
                    c = list(g.coords)
                    if len(c) == 2: new_items.append(SmartLineItem(c[0], c[1]))
                    elif len(c) > 2: new_items.append(SmartPolylineItem(c))
            elif geom_type == 'ellipse':
                # 封闭椭圆打断展开
                ring = sg.LinearRing(coords)
                pt_on_ring = ring.interpolate(ring.project(pt))
                split_res2 = split(snap(line, pt_on_ring, 1e-4), pt_on_ring)
                if len(split_res2.geoms) == 2:
                     new_coords = list(split_res2.geoms[1].coords) + list(split_res2.geoms[0].coords)[1:]
                     new_items.append(SmartPolylineItem(new_coords))

        if new_items:
            cmd = CommandBreakGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)