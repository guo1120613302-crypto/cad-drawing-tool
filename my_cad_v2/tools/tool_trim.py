# tools/tool_trim.py
import math
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
import shapely.geometry as sg
from shapely.ops import split, snap, unary_union

from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartCircleItem, 
    SmartPolylineItem, SmartArcItem, SmartEllipseItem, SmartSplineItem
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
        text, color = "修剪: 请点击要剪掉的线段 (支持全系数学图形)", "#d9534f"
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:{color}; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>✂️ {text}</div>"
        )
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
                
            if not coords or len(coords) < 2: 
                return None
            
            if geom_type in ('poly', 'circle', 'ellipse'):
                if math.hypot(coords[0][0] - coords[-1][0], coords[0][1] - coords[-1][1]) > 1e-5:
                    coords.append(coords[0])
            
            return sg.LineString(coords)
        except:
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
        return unary_union(lines)

    def _delete_segment(self, target_item, click_pt):
        geom_type = getattr(target_item, 'geom_type', '')
        if geom_type in ('line', 'circle', 'arc', 'ellipse', 'spline'):
            return [] 
            
        elif geom_type == 'polyline':
            coords = list(target_item.coords)
            if len(coords) < 2: return []
            
            # 【核心修复1】智能识别碎化曲线：如果点极多且平均线段极短，说明它是被降级的数学曲线
            total_len = sum(math.hypot(coords[i+1][0]-coords[i][0], coords[i+1][1]-coords[i][1]) for i in range(len(coords)-1))
            avg_len = total_len / (len(coords) - 1) if len(coords) > 1 else 0
            
            # 直接整条删除，解决“一像素一像素，剪不完根本”的 Bug
            if len(coords) > 10 and avg_len < 10.0:
                return []
                
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
            
            if len(c1) == 2: new_items.append(SmartLineItem(c1[0], c1[1]))
            elif len(c1) > 2: new_items.append(SmartPolylineItem(c1))
            
            if len(c2) == 2: new_items.append(SmartLineItem(c2[0], c2[1]))
            elif len(c2) > 2: new_items.append(SmartPolylineItem(c2))
            return new_items
            
        elif geom_type == 'poly':
            coords = list(target_item.coords)
            if coords[0] == coords[-1]: coords.pop() 
            if len(coords) < 3: return []
            
            total_len = sum(math.hypot(coords[(i+1)%len(coords)][0]-coords[i][0], coords[(i+1)%len(coords)][1]-coords[i][1]) for i in range(len(coords)))
            avg_len = total_len / len(coords)
            if len(coords) > 10 and avg_len < 10.0:
                return []
                
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
            if len(new_c) == 2: new_items.append(SmartLineItem(new_c[0], new_c[1]))
            elif len(new_c) > 2: new_items.append(SmartPolylineItem(new_c))
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
                if getattr(it, 'is_smart_shape', False) and getattr(it, 'geom_type', '') not in ('text', 'dim', 'ortho_dim', 'rad_dim', 'angle_dim', 'arclen_dim', 'leader'):
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
        target_geom = self._get_item_geom(target_item)
        if not target_geom: return

        cutters = self._get_all_cutters(target_item)
        if not cutters or cutters.is_empty: 
            new_items = self._delete_segment(target_item, click_pt)
            cmd = CommandTrimGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)
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
            geom_type = getattr(target_item, 'geom_type', '')
            
            for i, geom in enumerate(split_result.geoms):
                if i == target_segment_idx: continue 
                coords = list(geom.coords)
                if len(coords) < 2: continue
                
                if geom_type in ('circle', 'arc'):
                    cx, cy = target_item.center
                    r = target_item.radius
                    
                    p_start = coords[0]
                    p_end = coords[-1]
                    
                    sa = math.degrees(math.atan2(-(p_start[1] - cy), p_start[0] - cx))
                    ea = math.degrees(math.atan2(-(p_end[1] - cy), p_end[0] - cx))
                    if sa < 0: sa += 360
                    if ea < 0: ea += 360
                    
                    span = ea - sa
                    if span <= 0: span += 360
                    if span < 0.5: continue 
                    
                    new_items.append(SmartArcItem((cx, cy), r, sa, ea))
                else:
                    # 【核心修复2】样条曲线和椭圆修剪后，合并多余的坐标点
                    if len(coords) > 8:
                        try:
                            # 1.0像素容差，大幅剔除多余控制点，缓解满屏蓝点的问题
                            simplified_geom = sg.LineString(coords).simplify(1.0, preserve_topology=True)
                            coords = list(simplified_geom.coords)
                        except: pass
                        
                    if len(coords) == 2: 
                        new_items.append(SmartLineItem(coords[0], coords[1]))
                    else: 
                        new_items.append(SmartPolylineItem(coords))

            cmd = CommandTrimGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)
                
        except Exception as e:
            print(f"Trim Engine Error: {e}")