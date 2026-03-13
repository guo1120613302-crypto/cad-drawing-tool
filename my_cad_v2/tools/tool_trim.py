# tools/tool_trim.py
import math
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
import shapely.geometry as sg
from shapely.ops import split, snap

from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartCircleItem, 
    SmartPolylineItem, SmartArcItem
)

class CommandTrimGeom(QUndoCommand):
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


class TrimTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0

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
        text, color = "修剪: 请点击要剪掉的线段 (解析几何级绝对精度)", "#d9534f"
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:{color}; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>✂️ {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _get_item_geom(self, item):
        # 仅保留给直线的 Shapely 逻辑
        geom_type = getattr(item, 'geom_type', 'unknown')
        try:
            if geom_type in ('line', 'polyline'): 
                return sg.LineString(item.coords)
            elif geom_type == 'poly': 
                coords = list(item.coords)
                if coords[0] != coords[-1]: 
                    coords.append(coords[0]) 
                return sg.LineString(coords)
        except: 
            pass
        return None

    def _get_all_cutters(self, exclude_item):
        lines = []
        for item in self.canvas.scene().items():
            if getattr(item, 'is_smart_shape', False) and item != exclude_item and item.isVisible():
                geom = self._get_item_geom(item)
                if geom and not geom.is_empty: 
                    lines.append(geom)
        if not lines: 
            return None
        return sg.MultiLineString(lines) if len(lines) > 1 else lines[0]

    def _get_exact_math_intersections(self, target_item):
        """【核武器】：纯数学解析几何方程求解交点，彻底抛弃 Shapely 多边形模拟，实现零误差闭合！"""
        cx, cy = target_item.center
        r = target_item.radius
        angles = []
        
        for item in self.canvas.scene().items():
            if not getattr(item, 'is_smart_shape', False) or item == target_item or not item.isVisible():
                continue
                
            geom_type = getattr(item, 'geom_type', '')

            # 1. 直线、多段线切圆：解一元二次方程
            if geom_type in ('line', 'polyline', 'poly'):
                coords = list(item.coords)
                if geom_type == 'poly' and coords[0] != coords[-1]: 
                    coords.append(coords[0])
                    
                for i in range(len(coords)-1):
                    p1, p2 = coords[i], coords[i+1]
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    vx = p1[0] - cx
                    vy = p1[1] - cy
                    
                    a = dx*dx + dy*dy
                    if a < 1e-8: 
                        continue
                        
                    b = 2 * (vx*dx + vy*dy)
                    c_val = vx*vx + vy*vy - r*r
                    delta = b*b - 4*a*c_val
                    
                    if delta >= -1e-6: # 容忍极微小的相切误差
                        if delta < 0: 
                            delta = 0
                        sq = math.sqrt(delta)
                        for t in [(-b - sq)/(2*a), (-b + sq)/(2*a)]:
                            if -1e-5 <= t <= 1 + 1e-5: # 确保交点在线段内部
                                ix = p1[0] + t*dx
                                iy = p1[1] + t*dy
                                angle = math.degrees(math.atan2(-(iy - cy), ix - cx))
                                if angle < 0: 
                                    angle += 360
                                angles.append(round(angle, 5))

            # 2. 圆切圆：利用两圆心距离与弦长定理精准求解
            elif geom_type in ('circle', 'arc'):
                cx2, cy2 = item.center
                r2 = item.radius
                d = math.hypot(cx2 - cx, cy2 - cy)
                
                # 不相交、内含或同心圆
                if d > r + r2 + 1e-5 or d < abs(r - r2) - 1e-5 or d < 1e-5: 
                    continue
                    
                a_val = (r*r - r2*r2 + d*d) / (2*d)
                h2 = r*r - a_val*a_val
                if h2 < 0: 
                    h2 = 0
                h = math.sqrt(h2)
                
                px = cx + a_val * (cx2 - cx) / d
                py = cy + a_val * (cy2 - cy) / d
                ix1 = px + h * (cy2 - cy) / d
                iy1 = py - h * (cx2 - cx) / d
                ix2 = px - h * (cy2 - cy) / d
                iy2 = py + h * (cx2 - cx) / d
                
                for ix, iy in [(ix1, iy1), (ix2, iy2)]:
                    if geom_type == 'arc':
                        ang2 = math.degrees(math.atan2(-(iy - cy2), ix - cx2))
                        if ang2 < 0: 
                            ang2 += 360
                        sa2, ea2 = item.start_angle, item.end_angle
                        in_arc = sa2 - 1e-2 <= ang2 <= ea2 + 1e-2 if sa2 < ea2 else ang2 >= sa2 - 1e-2 or ang2 <= ea2 + 1e-2
                        if not in_arc: 
                            continue
                            
                    angle = math.degrees(math.atan2(-(iy - cy), ix - cx))
                    if angle < 0: 
                        angle += 360
                    angles.append(round(angle, 5))
                    
        return sorted(list(set(angles)))

    def _delete_segment(self, target_item, click_pt):
        geom_type = getattr(target_item, 'geom_type', '')
        if geom_type in ('line', 'circle', 'arc'):
            return [] 
            
        elif geom_type == 'polyline':
            coords = list(target_item.coords)
            min_dist = float('inf')
            target_idx = -1
            for i in range(len(coords)-1):
                seg = sg.LineString([coords[i], coords[i+1]])
                dist = seg.distance(click_pt)
                if dist < min_dist:
                    min_dist = dist
                    target_idx = i
                    
            new_items = []
            c1 = coords[:target_idx+1]
            c2 = coords[target_idx+1:]
            
            if len(c1) == 2: 
                new_items.append(SmartLineItem(c1[0], c1[1]))
            elif len(c1) > 2: 
                new_items.append(SmartPolylineItem(c1))
            
            if len(c2) == 2: 
                new_items.append(SmartLineItem(c2[0], c2[1]))
            elif len(c2) > 2: 
                new_items.append(SmartPolylineItem(c2))
            return new_items
            
        elif geom_type == 'poly':
            coords = list(target_item.coords)
            if coords[0] == coords[-1]: 
                coords.pop() 
                
            min_dist = float('inf')
            target_idx = -1
            n = len(coords)
            for i in range(n):
                seg = sg.LineString([coords[i], coords[(i+1)%n]])
                dist = seg.distance(click_pt)
                if dist < min_dist:
                    min_dist = dist
                    target_idx = i
                    
            new_c = []
            for i in range(n):
                new_c.append(coords[(target_idx + 1 + i) % n])
                
            new_items = []
            if len(new_c) == 2: 
                new_items.append(SmartLineItem(new_c[0], new_c[1]))
            elif len(new_c) > 2: 
                new_items.append(SmartPolylineItem(new_c))
            return new_items
            
        return []

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
                if getattr(it, 'is_smart_shape', False):
                    target_item = it
                    break
                    
            if target_item:
                self._perform_trim(target_item, final_point)
                
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

    def _perform_trim(self, target_item, click_pos):
        click_pt = sg.Point(click_pos.x(), click_pos.y())
        
        # 专项分流：圆和圆弧采用纯数学解法
        if getattr(target_item, 'geom_type', '') == 'circle':
            self._trim_circle_exact(target_item, click_pt)
            return
            
        if getattr(target_item, 'geom_type', '') == 'arc':
            self._trim_arc_exact(target_item, click_pt)
            return

        # 剩下的直线和矩形依然使用 Shapely
        cutters = self._get_all_cutters(target_item)
        if not cutters: 
            new_items = self._delete_segment(target_item, click_pt)
            cmd = CommandTrimGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)
            return 

        target_geom = self._get_item_geom(target_item)
        if not target_geom: 
            return

        try:
            intersections = target_geom.intersection(cutters)
            
            if intersections.is_empty:
                new_items = self._delete_segment(target_item, click_pt)
                cmd = CommandTrimGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
                self.canvas.undo_stack.push(cmd)
                return

            snapped_target = snap(target_geom, intersections, 1e-3)
            split_result = split(snapped_target, intersections)
            
            if len(split_result.geoms) <= 1: 
                new_items = self._delete_segment(target_item, click_pt)
                cmd = CommandTrimGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
                self.canvas.undo_stack.push(cmd)
                return

            min_dist = float('inf')
            target_segment_idx = -1
            for i, geom in enumerate(split_result.geoms):
                dist = geom.distance(click_pt)
                if dist < min_dist:
                    min_dist = dist
                    target_segment_idx = i

            new_items = []
            for i, geom in enumerate(split_result.geoms):
                if i == target_segment_idx: 
                    continue 
                coords = list(geom.coords)
                if len(coords) == 2: 
                    new_items.append(SmartLineItem(coords[0], coords[1]))
                elif len(coords) > 2: 
                    new_items.append(SmartPolylineItem(coords))

            cmd = CommandTrimGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)
                
        except Exception as e:
            print(f"Trim Engine Error: {e}")

    def _trim_circle_exact(self, circle_item, click_pt):
        cx, cy = circle_item.center
        r = circle_item.radius
        
        # 换用全新的数学矩阵求交点
        angles = self._get_exact_math_intersections(circle_item)
        
        if len(angles) < 2: 
            cmd = CommandTrimGeom(self.canvas.scene(), circle_item, [], self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)
            return 

        click_angle = math.degrees(math.atan2(-(click_pt.y - cy), click_pt.x - cx))
        if click_angle < 0: 
            click_angle += 360

        target_interval = None
        for i in range(len(angles)):
            a1 = angles[i]
            a2 = angles[(i+1) % len(angles)]
            if a1 < a2:
                if a1 <= click_angle <= a2: 
                    target_interval = (a1, a2)
                    break
            else: 
                if click_angle >= a1 or click_angle <= a2: 
                    target_interval = (a1, a2)
                    break
                    
        if not target_interval: 
            return
        
        start_a = target_interval[1]
        end_a = target_interval[0]
        
        new_items = [SmartArcItem(circle_item.center, circle_item.radius, start_a, end_a)]
        cmd = CommandTrimGeom(self.canvas.scene(), circle_item, new_items, self.canvas.layer_manager)
        self.canvas.undo_stack.push(cmd)

    def _trim_arc_exact(self, arc_item, click_pt):
        cx, cy = arc_item.center
        r = arc_item.radius
        
        # 获取所有绝对数学交点
        angles = self._get_exact_math_intersections(arc_item)
        
        valid_angles = [arc_item.start_angle, arc_item.end_angle]
        def in_arc_span(a, sa, ea):
            if sa < ea: 
                return sa - 1e-3 <= a <= ea + 1e-3
            else: 
                return a >= sa - 1e-3 or a <= ea + 1e-3
            
        for a in angles:
            if in_arc_span(a, arc_item.start_angle, arc_item.end_angle):
                valid_angles.append(a)
                
        valid_angles = sorted(list(set(valid_angles)))
        
        if len(valid_angles) <= 2:
            cmd = CommandTrimGeom(self.canvas.scene(), arc_item, [], self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)
            return
            
        span = arc_item.end_angle - arc_item.start_angle
        if span <= 0: 
            span += 360
        
        rel_angles = []
        for a in valid_angles:
            rel_a = a - arc_item.start_angle
            if rel_a < 0: 
                rel_a += 360
            if rel_a > span and abs(rel_a - 360) > 1e-4: 
                continue 
            if rel_a > span: 
                rel_a = 0
            rel_angles.append((rel_a, a))
            
        rel_angles.sort(key=lambda x: x[0])
        
        click_angle = math.degrees(math.atan2(-(click_pt.y - cy), click_pt.x - cx))
        if click_angle < 0: 
            click_angle += 360
        rel_click = click_angle - arc_item.start_angle
        if rel_click < 0: 
            rel_click += 360
        
        if rel_click > span: 
            return 
        
        new_items = []
        for i in range(len(rel_angles) - 1):
            rel_a1, a1 = rel_angles[i]
            rel_a2, a2 = rel_angles[i+1]
            
            if rel_a1 <= rel_click <= rel_a2:
                continue 
            else:
                if abs(a1 - a2) < 1e-4: 
                    continue
                new_items.append(SmartArcItem((cx, cy), r, a1, a2))
                
        cmd = CommandTrimGeom(self.canvas.scene(), arc_item, new_items, self.canvas.layer_manager)
        self.canvas.undo_stack.push(cmd)