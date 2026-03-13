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
    SmartPolylineItem, SmartArcItem
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
        """返回 None 表示不需要极轴追踪，但仍然启用捕捉系统"""
        return None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self._update_hud()

    def deactivate(self): 
        pass

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): 
            return
            
        self.canvas.hud_polar_info.show()
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:#d9534f; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>"
            f"🔨 打断: 请点击图形上的任意一点进行打断 (单点打断)</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            # 【核心修复 1】：装备 10x10 隐形捕捉框，告别“点不中中间”的问题
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
        """
        【重要】click_pos 已经是经过全局捕捉系统处理的点
        对于圆形，如果用户吸附到象限点，click_pos 就是精确的象限点坐标
        """
        geom_type = getattr(target_item, 'geom_type', '')
        px = click_pos.x()
        py = click_pos.y()
        new_items = []
        
        if geom_type == 'line':
            p1, p2 = target_item.coords
            
            # 【核心修复 2】：绝对数学投影，防止直线打断后变弯
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length_sq = dx*dx + dy*dy
            if length_sq > 1e-6:
                t = max(0, min(1, ((px - p1[0])*dx + (py - p1[1])*dy) / length_sq))
                px = p1[0] + t*dx
                py = p1[1] + t*dy
                
            # 防呆机制：防止在两端点产生长度为 0 的废线
            if math.hypot(px - p1[0], py - p1[1]) > 1e-4 and math.hypot(px - p2[0], py - p2[1]) > 1e-4:
                new_items.append(SmartLineItem(p1, (px, py)))
                new_items.append(SmartLineItem((px, py), p2))
            
        elif geom_type == 'polyline':
            coords = target_item.coords
            line = sg.LineString(coords)
            pt = sg.Point(px, py)
            pt_on_line = line.interpolate(line.project(pt))
            split_res = split(snap(line, pt_on_line, 1e-4), pt_on_line)
            
            if len(split_res.geoms) > 1:
                for g in split_res.geoms:
                    if len(g.coords) == 2: 
                        new_items.append(SmartLineItem(g.coords[0], g.coords[1]))
                    elif len(g.coords) > 2: 
                        new_items.append(SmartPolylineItem(list(g.coords)))
                    
        elif geom_type == 'poly':
            coords = list(target_item.coords)
            ring = sg.LinearRing(coords)
            pt = sg.Point(px, py)
            pt_on_ring = ring.interpolate(ring.project(pt))
            line = sg.LineString(coords + [coords[0]])
            split_res = split(snap(line, pt_on_ring, 1e-4), pt_on_ring)
            
            if len(split_res.geoms) == 2:
                new_coords = list(split_res.geoms[1].coords) + list(split_res.geoms[0].coords)[1:]
                new_items.append(SmartPolylineItem(new_coords))
                
        elif geom_type == 'circle':
            cx, cy = target_item.center
            r = target_item.radius
            
            # 【终极修复】找到最近的象限点或吸附点
            # 圆的象限点：右(0°), 上(90°), 左(180°), 下(270°)
            quadrant_angles = [0, 90, 180, 270]
            
            # 计算点击点的粗略角度
            rough_angle = math.degrees(math.atan2(cy - py, px - cx))
            if rough_angle < 0:
                rough_angle += 360
            
            # 找到最近的象限点
            snap_threshold_deg = 5.0  # 5度以内吸附到象限
            closest_angle = rough_angle
            min_diff = 360
            
            for qa in quadrant_angles:
                diff = abs(rough_angle - qa)
                if diff > 180:
                    diff = 360 - diff
                if diff < min_diff and diff < snap_threshold_deg:
                    min_diff = diff
                    closest_angle = qa
            
            angle = closest_angle
            # 打断圆形：创建一个几乎完整的圆弧（缺少0.01度）
            new_items.append(SmartArcItem((cx, cy), r, angle, angle - 0.01))
            
        elif geom_type == 'arc':
            cx, cy = target_item.center
            r = target_item.radius
            
            # 【终极修复】找到最近的象限点或吸附点
            quadrant_angles = [0, 90, 180, 270]
            
            # 计算点击点的粗略角度
            rough_angle = math.degrees(math.atan2(cy - py, px - cx))
            if rough_angle < 0:
                rough_angle += 360
            
            # 找到最近的象限点
            snap_threshold_deg = 5.0
            click_angle = rough_angle
            min_diff = 360
            
            for qa in quadrant_angles:
                diff = abs(rough_angle - qa)
                if diff > 180:
                    diff = 360 - diff
                if diff < min_diff and diff < snap_threshold_deg:
                    min_diff = diff
                    click_angle = qa
                
            new_items.append(SmartArcItem((cx, cy), r, target_item.start_angle, click_angle))
            new_items.append(SmartArcItem((cx, cy), r, click_angle, target_item.end_angle))

        if new_items:
            cmd = CommandBreakGeom(self.canvas.scene(), target_item, new_items, self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)