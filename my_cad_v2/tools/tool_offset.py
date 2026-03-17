# tools/tool_offset.py
import math
from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartDimensionItem, 
    SmartCircleItem, SmartPolylineItem, SmartArcItem,
    SmartEllipseItem, SmartSplineItem
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem, 
    QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsRectItem
)
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF, QPainterPath, QTransform, QBrush
import shapely.geometry as sg

class CommandOffsetGeom(QUndoCommand):
    def __init__(self, scene, original_item, new_items, layer_manager):
        super().__init__()
        self.scene = scene
        self.original_item = original_item
        self.new_items = new_items if isinstance(new_items, list) else [new_items]
        self.layer_manager = layer_manager
        
        pen = QPen(original_item.pen().color(), 1, original_item.pen().style())
        pen.setCosmetic(True)
        for item in self.new_items:
            item.setPen(pen)
            self.layer_manager.copy_layer_props(item, self.original_item)

    def redo(self):
        self.scene.clearSelection()
        for item in self.new_items:
            if item not in self.scene.items():
                self.scene.addItem(item)
            item.setSelected(True)

    def undo(self):
        for item in self.new_items:
            if item in self.scene.items():
                item.setSelected(False)
                self.scene.removeItem(item)

class OffsetTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_item = None
        self.state = 0
        self.ghost_items = []  
        self.input_buffer = ""
        self.current_preview_data = []
        self.selection_box = None
        self.start_point = None

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
        if self.selection_box:
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
        self.start_point = None
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghosts(self):
        for ghost in self.ghost_items:
            if ghost.scene():
                self.canvas.scene().removeItem(ghost)
        self.ghost_items.clear()
        self.current_preview_data = []

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'):
            return
        self.canvas.hud_polar_info.show()
        if self.state == 0:
            text, color = "偏移: 请【框选或点击】要偏移的对象", "#5bc0de"
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
            
        px, py = target_point.x(), target_point.y()
        geom_type = getattr(self.target_item, 'geom_type', '')
        
        if geom_type in ('text', 'dim', 'ortho_dim', 'rad_dim', 'angle_dim', 'arclen_dim', 'leader'):
            return None
        
        results = []
        
        if geom_type in ('circle', 'arc'):
            cx, cy = self.target_item.center
            r = self.target_item.radius
            dist_to_center = math.hypot(px - cx, py - cy)
            
            offset_dist = fixed_distance if fixed_distance is not None else abs(dist_to_center - r)
            new_r = r + offset_dist if dist_to_center > r else r - offset_dist
            if new_r <= 0.1: new_r = 0.1
                
            if geom_type == 'circle':
                results.append({'type': 'circle', 'center': (cx, cy), 'radius': new_r})
            else:
                results.append({'type': 'arc', 'center': (cx, cy), 'radius': new_r, 
                                'sa': self.target_item.start_angle, 'ea': self.target_item.end_angle})
                
        elif geom_type == 'ellipse':
            cx, cy = self.target_item.center
            rx, ry = self.target_item.rx, self.target_item.ry
            rot = self.target_item.rotation_angle
            
            pts = self.target_item.get_geom_coords()
            geom = sg.Polygon(pts)
            if not geom.is_valid: geom = geom.buffer(0)
            pt = sg.Point(px, py)
            
            offset_dist = fixed_distance if fixed_distance is not None else geom.exterior.distance(pt)
            if geom.contains(pt):
                new_rx, new_ry = rx - offset_dist, ry - offset_dist
            else:
                new_rx, new_ry = rx + offset_dist, ry + offset_dist
                
            if new_rx <= 0.1: new_rx = 0.1
            if new_ry <= 0.1: new_ry = 0.1
            results.append({'type': 'ellipse', 'center': (cx, cy), 'rx': new_rx, 'ry': new_ry, 'rotation_angle': rot})

        elif geom_type == 'line':
            (x1, y1), (x2, y2) = self.target_item.coords
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length < 1e-4: return None
                
            nx, ny = -dy / length, dx / length
            cross = (px - x1) * nx + (py - y1) * ny
            sign = 1 if cross > 0 else -1
            
            dist = fixed_distance if fixed_distance is not None else abs(cross)
            nx_shift, ny_shift = nx * sign * dist, ny * sign * dist
            results.append({'type': 'line', 'coords': [(x1 + nx_shift, y1 + ny_shift), (x2 + nx_shift, y2 + ny_shift)]})

        elif geom_type in ('poly', 'polyline', 'spline'):
            raw_coords = []
            if geom_type == 'polyline':
                orig_coords = self.target_item.coords
                segs = getattr(self.target_item, 'segments', [])
                if orig_coords:
                    raw_coords.append(orig_coords[0])
                    for i in range(len(orig_coords)-1):
                        p1, p2 = orig_coords[i], orig_coords[i+1]
                        seg = segs[i] if i < len(segs) else {}
                        if seg.get("type") == "arc" and "bulge" in seg:
                            bulge = seg["bulge"]
                            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                            chord = math.hypot(dx, dy)
                            if chord > 1e-4 and abs(bulge) > 1e-4:
                                d = -(chord / 2.0) * ((1.0 - bulge**2) / (2.0 * bulge))
                                mid_x, mid_y = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
                                cx, cy = mid_x - d * (dy / chord), mid_y - d * (-dx / chord)
                                radius = math.hypot(p1[0] - cx, p1[1] - cy)
                                start_angle = math.degrees(math.atan2(-(p1[1] - cy), p1[0] - cx))
                                span_angle = math.degrees(4 * math.atan(bulge))
                                steps = max(16, int(abs(span_angle) / 5)) # 提高细分精度
                                for j in range(1, steps+1):
                                    a = math.radians(start_angle + span_angle * j / steps)
                                    raw_coords.append((cx + radius * math.cos(a), cy - radius * math.sin(a)))
                                continue
                        raw_coords.append(p2)
            elif geom_type == 'spline':
                raw_coords = self.target_item.get_geom_coords()
            else:
                raw_coords = self.target_item.coords
                
            clean_coords = []
            if raw_coords:
                clean_coords.append(raw_coords[0])
                for p in raw_coords[1:]:
                    if math.hypot(p[0] - clean_coords[-1][0], p[1] - clean_coords[-1][1]) > 1e-3:
                        clean_coords.append(p)
            if len(clean_coords) < 2: return None
            
            # 智能检测是否为闭合图形
            is_closed = False
            if len(clean_coords) >= 3 and math.hypot(clean_coords[0][0] - clean_coords[-1][0], clean_coords[0][1] - clean_coords[-1][1]) < 1e-3:
                is_closed = True

            # 【核心修复1】Join Style 控制：Spline 用平滑圆角(1)，Polyline/Poly 用锐角斜接(2)保证直线能自动延长相交
            js = 1 if geom_type == 'spline' else 2

            if geom_type == 'poly' or is_closed:
                geom = sg.Polygon(clean_coords)
                if not geom.is_valid: geom = geom.buffer(0)
                pt = sg.Point(px, py)
                
                dist = fixed_distance if fixed_distance is not None else geom.exterior.distance(pt)
                if dist < 1e-3: return None
                buffer_dist = dist if not geom.contains(pt) else -dist
                
                offset_geom = geom.buffer(buffer_dist, join_style=js, quad_segs=8)
                if offset_geom.is_empty: return None

                # 【核心修复2】完美提取多重闭合图案（包括内部所有的孔洞）
                def extract_poly_parts(polygon_geom):
                    extracted = []
                    # 提取外轮廓
                    ext = list(polygon_geom.exterior.coords)
                    if ext: ext.pop()
                    extracted.append({'type': 'poly', 'coords': ext})
                    # 提取由于重叠或自交产生的内部孔洞
                    for interior in polygon_geom.interiors:
                        int_coords = list(interior.coords)
                        if int_coords: int_coords.pop()
                        extracted.append({'type': 'poly', 'coords': int_coords})
                    return extracted

                if offset_geom.geom_type == 'Polygon':
                    results.extend(extract_poly_parts(offset_geom))
                elif offset_geom.geom_type == 'MultiPolygon':
                    for poly in offset_geom.geoms:
                        results.extend(extract_poly_parts(poly))
            else:
                geom = sg.LineString(clean_coords)
                pt = sg.Point(px, py)
                dist = fixed_distance if fixed_distance is not None else geom.distance(pt)
                if dist < 1e-3: return None
                    
                try:
                    if hasattr(geom, 'offset_curve'):
                        off_left = geom.offset_curve(dist, join_style=js, quad_segs=8)
                        off_right = geom.offset_curve(-dist, join_style=js, quad_segs=8)
                    else:
                        off_left = geom.parallel_offset(dist, 'left', join_style=js, quad_segs=8)
                        off_right = geom.parallel_offset(dist, 'right', join_style=js, quad_segs=8)
                    
                    dist_l = off_left.distance(pt) if not off_left.is_empty else float('inf')
                    dist_r = off_right.distance(pt) if not off_right.is_empty else float('inf')
                    
                    best_off = off_left if dist_l < dist_r else off_right
                    if best_off.is_empty: return None
                    
                    if best_off.geom_type == 'LineString':
                        results.append({'type': 'polyline', 'coords': list(best_off.coords)})
                    elif best_off.geom_type == 'MultiLineString':
                        for line in best_off.geoms:
                            results.append({'type': 'polyline', 'coords': list(line.coords)})
                except Exception as e:
                    return None
                    
        return results if results else None

    def _update_preview(self, final_point):
        if not self.target_item: return
            
        fixed_dist = None
        if self.input_buffer:
            try: fixed_dist = float(self.input_buffer)
            except ValueError: pass
            
        data_list = self._get_offset_data(final_point, fixed_dist)
        self.current_preview_data = data_list or []
        
        if not data_list:
            for ghost in self.ghost_items: ghost.hide()
            return
            
        while len(self.ghost_items) < len(data_list):
            ghost = QGraphicsPathItem()
            pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            ghost.setPen(pen)
            self.canvas.scene().addItem(ghost)
            self.ghost_items.append(ghost)
            
        for i in range(len(data_list), len(self.ghost_items)):
            self.ghost_items[i].hide()
            
        for i, data in enumerate(data_list):
            ghost = self.ghost_items[i]
            ghost.show()
            path = QPainterPath()
            
            if data['type'] == 'circle':
                c, r = data['center'], data['radius']
                path.addEllipse(QPointF(*c), r, r)
            elif data['type'] == 'ellipse':
                c, rx, ry, rot = data['center'], data['rx'], data['ry'], data['rotation_angle']
                temp_path = QPainterPath()
                temp_path.addEllipse(QRectF(-rx, -ry, 2*rx, 2*ry))
                trans = QTransform()
                trans.translate(c[0], c[1])
                trans.rotate(-rot)
                path = trans.map(temp_path)
            elif data['type'] == 'arc':
                c, r, sa, ea = data['center'], data['radius'], data['sa'], data['ea']
                span = ea - sa
                if span <= 0: span += 360
                path.arcMoveTo(QRectF(c[0]-r, c[1]-r, 2*r, 2*r), sa)
                path.arcTo(QRectF(c[0]-r, c[1]-r, 2*r, 2*r), sa, span)
            else:
                coords = data['coords']
                if coords:
                    path.moveTo(QPointF(*coords[0]))
                    for x, y in coords[1:]:
                        path.lineTo(QPointF(x, y))
                    if data['type'] == 'poly':
                        path.closeSubpath()
                        
            ghost.setPath(path)

    def mousePressEvent(self, event, final_point, snapped_angle):
        raw_point = self.canvas.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                self.start_point = raw_point
                self.selection_box = QGraphicsRectItem()
                pen = QPen(QColor(0, 120, 215), 1)
                pen.setCosmetic(True)
                self.selection_box.setPen(pen)
                self.selection_box.setBrush(QColor(0, 120, 215, 40))
                self.selection_box.setZValue(5000)
                self.canvas.scene().addItem(self.selection_box)
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
        raw_point = self.canvas.mapToScene(event.pos())
        self._update_hud()
        if self.state == 0 and self.selection_box and self.start_point:
            x, y = min(self.start_point.x(), raw_point.x()), min(self.start_point.y(), raw_point.y())
            w, h = abs(self.start_point.x() - raw_point.x()), abs(self.start_point.y() - raw_point.y())
            self.selection_box.setRect(x, y, w, h)
            is_blue = raw_point.x() > self.start_point.x()
            color = QColor(0, 120, 215) if is_blue else QColor(76, 175, 80)
            pen = QPen(color, 1, Qt.PenStyle.SolidLine if is_blue else Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
            return True
        if self.state == 1:
            self._update_preview(final_point)
        return True

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton and self.state == 0 and self.selection_box:
            rect = self.selection_box.rect()
            raw_point = self.canvas.mapToScene(event.pos())
            is_blue = raw_point.x() > self.start_point.x()
            mode = Qt.ItemSelectionMode.ContainsItemShape if is_blue else Qt.ItemSelectionMode.IntersectsItemShape
            
            if rect.width() < 1 or rect.height() < 1:
                rect = QRectF(raw_point.x() - 5, raw_point.y() - 5, 10, 10)
                mode = Qt.ItemSelectionMode.IntersectsItemShape
                
            for item in self.canvas.scene().items(rect, mode):
                if getattr(item, 'is_smart_shape', False) and getattr(item, 'geom_type', '') not in ('text', 'dim', 'ortho_dim', 'rad_dim', 'angle_dim', 'arclen_dim', 'leader'):
                    self.target_item = item
                    self.canvas.scene().clearSelection()
                    item.setSelected(True)
                    self.state = 1
                    break
                    
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
            self.start_point = None
            self._update_hud()
            if self.state == 1:
                self._update_preview(self.canvas.last_cursor_point)
            return True
        return False

    def keyPressEvent(self, event):
        if self.state == 1:
            key = event.text()
            if key.isdigit() or key == '.':
                self.input_buffer += key
                self._update_hud()
                self._update_preview(self.canvas.last_cursor_point)
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud()
                self._update_preview(self.canvas.last_cursor_point)
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
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
            
        new_items = []
        for data in self.current_preview_data:
            if data['type'] == 'circle':
                new_items.append(SmartCircleItem(data['center'], data['radius']))
            elif data['type'] == 'arc':
                new_items.append(SmartArcItem(data['center'], data['radius'], data['sa'], data['ea']))
            elif data['type'] == 'ellipse':
                new_items.append(SmartEllipseItem(data['center'], data['rx'], data['ry'], data['rotation_angle']))
            elif data['type'] == 'line':
                new_items.append(SmartLineItem(data['coords'][0], data['coords'][1]))
            elif data['type'] == 'poly':
                new_items.append(SmartPolygonItem(data['coords']))
            elif data['type'] == 'polyline':
                new_items.append(SmartPolylineItem(data['coords']))
                
        if new_items:
            cmd = CommandOffsetGeom(self.canvas.scene(), self.target_item, new_items, self.canvas.layer_manager)
            self.canvas.undo_stack.push(cmd)
        
        self.target_item.setSelected(False)
        self.target_item = None
        self.state = 0
        self.input_buffer = ""
        self._cleanup_ghosts()
        self._update_hud()