# tools/tool_offset.py
import math
from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartDimensionItem, 
    SmartCircleItem, SmartPolylineItem, SmartArcItem
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem, 
    QGraphicsPathItem, QGraphicsEllipseItem
)
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF, QPainterPath
import shapely.geometry as sg

class CommandOffsetGeom(QUndoCommand):
    def __init__(self, scene, original_item, new_item, layer_manager):
        super().__init__()
        self.scene = scene
        self.original_item = original_item
        self.new_item = new_item
        self.layer_manager = layer_manager
        
        pen = QPen(original_item.pen().color(), 1, original_item.pen().style())
        pen.setCosmetic(True)
        self.new_item.setPen(pen)
        self.layer_manager.copy_layer_props(self.new_item, self.original_item)

    def redo(self):
        self.scene.clearSelection()
        if self.new_item not in self.scene.items():
            self.scene.addItem(self.new_item)
        self.new_item.setSelected(True)

    def undo(self):
        if self.new_item in self.scene.items():
            self.new_item.setSelected(False)
            self.scene.removeItem(self.new_item)


class OffsetTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_item = None
        self.state = 0
        self.ghost_item = None
        self.input_buffer = ""
        self.current_preview_data = None

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.target_item = None
        self.input_buffer = ""
        self._cleanup_ghosts()
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghosts()
        if self.target_item:
            self.target_item.setSelected(False)
        self.target_item = None
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghosts(self):
        if self.ghost_item and self.ghost_item.scene():
            self.canvas.scene().removeItem(self.ghost_item)
        self.ghost_item = None
        self.current_preview_data = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'):
            return
            
        self.canvas.hud_polar_info.show()
        if self.state == 0:
            text, color = "偏移: 请选择要偏移的对象", "#5bc0de"
        else:
            text, color = f"偏移: 请指定偏移方向或输入距离: {self.input_buffer}", "#5cb85c"
            
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:{color}; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>🔲 {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _get_offset_data(self, target_point, fixed_distance=None):
        if not self.target_item:
            return None
            
        px = target_point.x()
        py = target_point.y()
        geom_type = getattr(self.target_item, 'geom_type', '')
        
        if geom_type in ('circle', 'arc'):
            cx, cy = self.target_item.center
            r = self.target_item.radius
            dist_to_center = math.hypot(px - cx, py - cy)
            
            if fixed_distance is not None:
                offset_dist = fixed_distance
            else:
                offset_dist = abs(dist_to_center - r)
                
            if dist_to_center > r:
                new_r = r + offset_dist
            else:
                new_r = r - offset_dist
                
            if new_r <= 0.1:
                new_r = 0.1
                
            if geom_type == 'circle':
                return {'type': 'circle', 'center': (cx, cy), 'radius': new_r}
            else:
                return {
                    'type': 'arc', 
                    'center': (cx, cy), 
                    'radius': new_r, 
                    'sa': self.target_item.start_angle, 
                    'ea': self.target_item.end_angle
                }

        elif geom_type == 'line':
            (x1, y1), (x2, y2) = self.target_item.coords
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)
            if length < 1e-4:
                return None
                
            nx = -dy / length
            ny = dx / length
            vx = px - x1
            vy = py - y1
            cross = vx * nx + vy * ny
            sign = 1 if cross > 0 else -1
            
            if fixed_distance is not None:
                dist = fixed_distance
            else:
                dist = abs(cross)
                
            nx_shift = nx * sign * dist
            ny_shift = ny * sign * dist
            new_coords = [(x1 + nx_shift, y1 + ny_shift), (x2 + nx_shift, y2 + ny_shift)]
            return {'type': 'line', 'coords': new_coords}

        elif geom_type in ('poly', 'polyline'):
            coords = self.target_item.coords
            if len(coords) < 2:
                return None
                
            if geom_type == 'poly':
                geom = sg.Polygon(coords)
                if not geom.is_valid:
                    geom = geom.buffer(0)
                    
                pt = sg.Point(px, py)
                is_inside = geom.contains(pt)
                
                if fixed_distance is not None:
                    dist = fixed_distance
                else:
                    dist = geom.exterior.distance(pt)
                    
                buffer_dist = dist if not is_inside else -dist
                offset_geom = geom.buffer(buffer_dist, join_style=2)
                
                if offset_geom.is_empty:
                    return None
                    
                if offset_geom.geom_type == 'Polygon':
                    ext = list(offset_geom.exterior.coords)
                    if ext:
                        ext.pop()
                    return {'type': 'poly', 'coords': ext}
            else:
                geom = sg.LineString(coords)
                pt = sg.Point(px, py)
                
                if fixed_distance is not None:
                    dist = fixed_distance
                else:
                    dist = geom.distance(pt)
                    
                off_left = geom.parallel_offset(dist, 'left', join_style=2)
                off_right = geom.parallel_offset(dist, 'right', join_style=2)
                
                dist_l = off_left.distance(pt) if not off_left.is_empty else float('inf')
                dist_r = off_right.distance(pt) if not off_right.is_empty else float('inf')
                
                best_off = off_left if dist_l < dist_r else off_right
                if best_off.is_empty:
                    return None
                    
                if best_off.geom_type == 'LineString':
                    return {'type': 'polyline', 'coords': list(best_off.coords)}
                    
        return None

    def _update_preview(self, final_point):
        if not self.target_item:
            return
            
        fixed_dist = None
        if self.input_buffer:
            try:
                fixed_dist = float(self.input_buffer)
            except ValueError:
                pass
            
        data = self._get_offset_data(final_point, fixed_dist)
        self.current_preview_data = data
        
        if not data:
            if self.ghost_item:
                self.ghost_item.hide()
            return
            
        if not self.ghost_item:
            pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            
            if data['type'] == 'circle':
                self.ghost_item = QGraphicsEllipseItem()
            else:
                self.ghost_item = QGraphicsPathItem()
                
            self.ghost_item.setPen(pen)
            self.canvas.scene().addItem(self.ghost_item)
            
        self.ghost_item.show()
        
        if data['type'] == 'circle':
            c = data['center']
            r = data['radius']
            if not isinstance(self.ghost_item, QGraphicsEllipseItem):
                self.canvas.scene().removeItem(self.ghost_item)
                self.ghost_item = QGraphicsEllipseItem()
                pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.ghost_item.setPen(pen)
                self.canvas.scene().addItem(self.ghost_item)
            self.ghost_item.setRect(QRectF(c[0]-r, c[1]-r, 2*r, 2*r))
        else:
            if not isinstance(self.ghost_item, QGraphicsPathItem):
                self.canvas.scene().removeItem(self.ghost_item)
                self.ghost_item = QGraphicsPathItem()
                pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.ghost_item.setPen(pen)
                self.canvas.scene().addItem(self.ghost_item)
                
            path = QPainterPath()
            if data['type'] == 'arc':
                c = data['center']
                r = data['radius']
                sa = data['sa']
                ea = data['ea']
                
                span = ea - sa
                if span <= 0:
                    span += 360
                
                rect = QRectF(c[0]-r, c[1]-r, 2*r, 2*r)
                path.arcMoveTo(rect, sa)
                path.arcTo(rect, sa, span)
            else:
                coords = data['coords']
                if coords:
                    path.moveTo(QPointF(*coords[0]))
                    for x, y in coords[1:]:
                        path.lineTo(QPointF(x, y))
                    if data['type'] == 'poly':
                        path.closeSubpath()
                        
            self.ghost_item.setPath(path)

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                raw_point = self.canvas.mapToScene(event.pos())
                item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
                if getattr(item, 'is_smart_shape', False):
                    self.target_item = item
                    self.canvas.scene().clearSelection()
                    item.setSelected(True)
                    self.state = 1
                self._update_hud()
                return True
            elif self.state == 1:
                self._finalize_offset()
                return True
                
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state == 1:
                self.state = 0
                if self.target_item:
                    self.target_item.setSelected(False)
                self.target_item = None
                self._cleanup_ghosts()
            else:
                self.deactivate()
                self.canvas.switch_tool("选择")
            self._update_hud()
            return True
            
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        if self.state == 1:
            self._update_preview(final_point)
        return True

    def keyPressEvent(self, event):
        if self.state == 1:
            key = event.text()
            if key.isdigit() or key == '.':
                self.input_buffer += key
                self._update_hud()
                # 输入数字后立即更新预览
                self._update_preview(self.canvas.last_cursor_point)
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud()
                # 删除数字后立即更新预览
                self._update_preview(self.canvas.last_cursor_point)
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # 回车前确保预览数据是最新的
                self._update_preview(self.canvas.last_cursor_point)
                self._finalize_offset()
                return True
                
        if event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
            
        return False

    def _finalize_offset(self):
        if not self.target_item or not self.current_preview_data:
            return
            
        data = self.current_preview_data
        
        if data['type'] == 'circle':
            new_item = SmartCircleItem(data['center'], data['radius'])
        elif data['type'] == 'arc':
            new_item = SmartArcItem(data['center'], data['radius'], data['sa'], data['ea'])
        elif data['type'] == 'line':
            new_item = SmartLineItem(data['coords'][0], data['coords'][1])
        elif data['type'] == 'poly':
            new_item = SmartPolygonItem(data['coords'])
        elif data['type'] == 'polyline':
            new_item = SmartPolylineItem(data['coords'])
            
        cmd = CommandOffsetGeom(self.canvas.scene(), self.target_item, new_item, self.canvas.layer_manager)
        self.canvas.undo_stack.push(cmd)
        
        self.target_item.setSelected(False)
        self.target_item = None
        self.state = 0
        self.input_buffer = ""
        self._cleanup_ghosts()
        self._update_hud()