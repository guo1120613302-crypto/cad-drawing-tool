# tools/tool_select.py
from tools.base_tool import BaseTool
from core.core_items import (SmartLineItem, SmartPolygonItem, SmartDimensionItem, 
                             SmartCircleItem, SmartPolylineItem, SmartArcItem,
                             SmartEllipseItem, SmartSplineItem, SmartTextItem, 
                             SmartLeaderItem, SmartOrthogonalDimensionItem, 
                             SmartRadiusDimensionItem, SmartAngleDimensionItem, SmartArcLengthDimensionItem)
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QBrush, QUndoCommand
import math
from utils.geom_engine import GeometryEngine

def apply_geom_data(item, data):
    """【万能刷新引擎】直接应用底层数据，触发图形实时重绘"""
    if isinstance(data, dict):
        for k, v in data.items():
            if k not in ('coords', 'pos'): setattr(item, k, v)
        if 'coords' in data: 
            item.set_coords(data['coords'])
        else:
            item.prepareGeometryChange()
            item.update()
    else:
        item.set_coords(data)

class CommandModifyMultipleGeom(QUndoCommand):
    def __init__(self, stretch_data):
        super().__init__()
        self.stretch_data = stretch_data 
    def redo(self):
        for item, _, new_data in self.stretch_data:
            if item.scene(): apply_geom_data(item, new_data)
    def undo(self):
        for item, old_data, _ in self.stretch_data:
            if item.scene(): apply_geom_data(item, old_data)

class CommandMoveGeom(QUndoCommand):
    def __init__(self, move_data):
        super().__init__()
        self.move_data = move_data
    def redo(self):
        for item, _, new_data in self.move_data:
            if item.scene(): 
                apply_geom_data(item, new_data)
                if getattr(item, 'geom_type', '') == 'text' and 'pos' in new_data:
                    item.setPos(new_data['pos'])
    def undo(self):
        for item, old_data, _ in self.move_data:
            if item.scene(): 
                apply_geom_data(item, old_data)
                if getattr(item, 'geom_type', '') == 'text' and 'pos' in old_data:
                    item.setPos(old_data['pos'])

class SelectTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.start_point = None
        self.selection_box = None
        self.is_stretching = False
        self.stretch_items = [] 
        self.stretch_start_pos = None 
        self.is_moving = False
        self.move_items = []
        self.move_start_pos = None
        self.input_buffer = ""

    def _cleanup_temp_items(self):
        for data in getattr(self, 'stretch_items', []):
            if 'item' in data: data['item'].hot_grip_index = -1
        self.is_stretching = False; self.stretch_items = []; self.stretch_start_pos = None
        self.is_moving = False; self.move_items = []; self.move_start_pos = None
        self.input_buffer = ""

    def activate(self): self.canvas.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def deactivate(self):
        self._cleanup_temp_items()
        if self.selection_box:
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
        if self.canvas.scene(): self.canvas.scene().clearSelection()

    def get_reference_point(self):
        if self.is_stretching: return self.stretch_start_pos
        elif self.is_moving: return self.move_start_pos
        return None

    def get_input_buffer(self): return self.input_buffer

    def _capture_old_data(self, item):
        """完整捕获对象的所有几何属性，用于实时预览的回退和撤销"""
        data = {'coords': list(item.coords)}
        if hasattr(item, 'center'): data['center'] = item.center
        if hasattr(item, 'radius'): data['radius'] = item.radius
        if hasattr(item, 'rx'): data['rx'] = item.rx
        if hasattr(item, 'ry'): data['ry'] = item.ry
        if hasattr(item, 'start_angle'): data['start_angle'] = item.start_angle
        if hasattr(item, 'end_angle'): data['end_angle'] = item.end_angle
        if hasattr(item, 'rotation_angle'): data['rotation_angle'] = item.rotation_angle
        if hasattr(item, 'pos'): data['pos'] = item.pos()
        return data

    def _calculate_moved_data(self, old_data, g_type, dx, dy):
        """计算整体平移后的新数据"""
        new_data = dict(old_data)
        old_c = old_data.get('coords', [])
        new_data['coords'] = [(x + dx, y + dy) for x, y in old_c]
        
        if 'center' in old_data:
            c = old_data['center']
            new_data['center'] = (c[0] + dx, c[1] + dy)
        if 'pos' in old_data and g_type == 'text':
            p = old_data['pos']
            new_data['pos'] = QPointF(p.x() + dx, p.y() + dy)
            
        return new_data

    def _calculate_stretched_data(self, data, dx, dy):
        """计算夹点被拉伸后的新数据"""
        idx = data['index']
        g_type = data['type']
        old_data = data['old_data']
        old_coords = old_data['coords']
        gx, gy = data['grip_pos']
        
        new_data = dict(old_data)
        new_coords = list(old_coords)
        
        if g_type == 'line':
            if idx == 0: new_coords[0] = (old_coords[0][0]+dx, old_coords[0][1]+dy)
            elif idx == 2: new_coords[1] = (old_coords[1][0]+dx, old_coords[1][1]+dy)
            elif idx == 1: 
                new_coords[0] = (old_coords[0][0]+dx, old_coords[0][1]+dy)
                new_coords[1] = (old_coords[1][0]+dx, old_coords[1][1]+dy)
                
        elif g_type in ('poly', 'polyline', 'spline'):
            count = len(old_coords)
            if idx < count: new_coords[idx] = (old_coords[idx][0]+dx, old_coords[idx][1]+dy)
            else:
                edge_idx = idx - count
                p1_idx, p2_idx = edge_idx, (edge_idx + 1) % count
                new_coords[p1_idx] = (old_coords[p1_idx][0]+dx, old_coords[p1_idx][1]+dy)
                new_coords[p2_idx] = (old_coords[p2_idx][0]+dx, old_coords[p2_idx][1]+dy)
                
        elif g_type in ('dim', 'ortho_dim', 'rad_dim', 'angle_dim', 'arclen_dim', 'leader'):
            if idx < len(new_coords):
                new_coords[idx] = (old_coords[idx][0]+dx, old_coords[idx][1]+dy)
                
        elif g_type == 'circle':
            if idx == 0: 
                c = (old_coords[0][0]+dx, old_coords[0][1]+dy)
                new_data['center'] = c
                new_coords = [c, (c[0]+old_data['radius'], c[1])]
            else: 
                c = old_data['center']
                r = math.hypot(gx+dx - c[0], gy+dy - c[1])
                new_data['radius'] = r
                new_coords = [c, (c[0]+r, c[1])]
                
        elif g_type == 'ellipse':
            c = old_data['center']
            if idx == 0:
                c = (c[0]+dx, c[1]+dy)
                new_data['center'] = c
            elif idx in (1, 2):
                new_data['rx'] = math.hypot(gx+dx - c[0], gy+dy - c[1])
            elif idx in (3, 4):
                new_data['ry'] = math.hypot(gx+dx - c[0], gy+dy - c[1])
                
        elif g_type == 'arc':
            if idx == 3: 
                c = (old_coords[0][0]+dx, old_coords[0][1]+dy)
                new_data['center'] = c
                new_coords = [c, (c[0]+old_data['radius'], c[1])]
            else:
                c = old_data['center']
                r = math.hypot(gx+dx - c[0], gy+dy - c[1])
                new_data['radius'] = r
                new_coords = [c, (c[0]+r, c[1])]
                
        elif g_type == 'text':
            if 'pos' in old_data:
                p = old_data['pos']
                new_data['pos'] = QPointF(p.x() + dx, p.y() + dy)
                
        new_data['coords'] = new_coords
        return new_data

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.MiddleButton: return False
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_stretching: self._finalize_stretch(final_point); return True
            if self.is_moving: self._finalize_move(final_point); return True

            self.input_buffer = "" 
            raw_point = self.canvas.mapToScene(event.pos())
            selected_items = self.canvas.scene().selectedItems()
            
            if selected_items:
                # 1. 检测夹点拉伸
                hit_radius = 15.0 / self.canvas.transform().m11()
                found_grips = []
                for item in selected_items:
                    if getattr(item, 'is_smart_shape', False):
                        for i, (gx, gy) in enumerate(item.get_grips()):
                            if math.hypot(raw_point.x() - gx, raw_point.y() - gy) < hit_radius:
                                found_grips.append({
                                    'item': item, 'index': i, 'type': getattr(item, 'geom_type', 'unknown'),
                                    'old_data': self._capture_old_data(item),
                                    'grip_pos': (gx, gy)
                                })
                                item.hot_grip_index = i 

                if found_grips:
                    self.is_stretching = True
                    self.stretch_items = found_grips
                    self.stretch_start_pos = QPointF(*found_grips[0]['grip_pos'])
                    return True
                
                # 2. 检测整体平移 (含大容差，解决圆/椭圆难点中的问题)
                clicked_item = None
                hit_radius_move = 10.0 / self.canvas.transform().m11()
                hit_rect = QRectF(raw_point.x() - hit_radius_move, raw_point.y() - hit_radius_move, hit_radius_move * 2, hit_radius_move * 2)
                
                for item in self.canvas.scene().items(hit_rect):
                    if getattr(item, 'is_smart_shape', False) and item.isSelected():
                        clicked_item = item
                        break

                if clicked_item:
                    self.is_moving = True
                    self.move_items = []
                    for item in selected_items:
                        if getattr(item, 'is_smart_shape', False):
                            self.move_items.append({
                                'item': item, 'type': getattr(item, 'geom_type', 'unknown'),
                                'old_data': self._capture_old_data(item)
                            })
                    self.move_start_pos = final_point
                    return True
            
            # 3. 空白处框选
            self.start_point = raw_point
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.canvas.scene().clearSelection()
            self.selection_box = QGraphicsRectItem()
            pen = QPen(QColor(0, 120, 215), 1); pen.setCosmetic(True)
            self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(0, 120, 215, 40)))
            self.selection_box.setZValue(5000)
            self.canvas.scene().addItem(self.selection_box)
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            # 鼠标右键：取消拖动并瞬间还原所有图形
            if self.is_stretching or self.is_moving:
                if self.is_stretching:
                    for data in self.stretch_items: apply_geom_data(data['item'], data['old_data'])
                if self.is_moving:
                    for data in self.move_items: 
                        apply_geom_data(data['item'], data['old_data'])
                        if data['type'] == 'text': data['item'].setPos(data['old_data']['pos'])
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'): self.canvas._cleanup_tracking_huds()
            elif self.canvas.scene().selectedItems():
                self.canvas.scene().clearSelection()
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        # === 核心魔法：抛弃幽灵线，直接让真实图形在拖拽时实时变幻！ ===
        if self.is_moving and self.move_items:
            dx = final_point.x() - self.move_start_pos.x()
            dy = final_point.y() - self.move_start_pos.y()
            for data in self.move_items:
                item = data['item']
                new_data = self._calculate_moved_data(data['old_data'], data['type'], dx, dy)
                apply_geom_data(item, new_data)
                if data['type'] == 'text' and 'pos' in new_data: item.setPos(new_data['pos'])
            self.canvas.viewport().update()
            return True

        if self.is_stretching and self.stretch_items:
            dx = final_point.x() - self.stretch_start_pos.x()
            dy = final_point.y() - self.stretch_start_pos.y()
            for data in self.stretch_items:
                item = data['item']
                new_data = self._calculate_stretched_data(data, dx, dy)
                apply_geom_data(item, new_data)
            self.canvas.viewport().update()
            return True

        # 框选
        if self.start_point and self.selection_box:
            raw_point = self.canvas.mapToScene(event.pos())
            x, y = min(self.start_point.x(), raw_point.x()), min(self.start_point.y(), raw_point.y())
            w, h = abs(self.start_point.x() - raw_point.x()), abs(self.start_point.y() - raw_point.y())
            self.selection_box.setRect(x, y, w, h)
            color = QColor(0, 120, 215) if raw_point.x() > self.start_point.x() else QColor(76, 175, 80)
            pen = QPen(color, 1, Qt.PenStyle.SolidLine if raw_point.x() > self.start_point.x() else Qt.PenStyle.DashLine)
            pen.setCosmetic(True); self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
            return True
        return False

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton and (self.is_stretching or self.is_moving): return True 
        if event.button() == Qt.MouseButton.LeftButton and self.start_point and self.selection_box:
            raw_point = self.canvas.mapToScene(event.pos())
            rect = self.selection_box.rect()
            if rect.width() > 0 and rect.height() > 0:
                mode = Qt.ItemSelectionMode.ContainsItemShape if raw_point.x() > self.start_point.x() else Qt.ItemSelectionMode.IntersectsItemShape
                for item in self.canvas.scene().items(rect, mode):
                    if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable:
                        item.setSelected(True)
            if self.selection_box: self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None; self.start_point = None
            return True
        return False

    def keyPressEvent(self, event):
        if self.is_stretching or self.is_moving:
            key = event.text()
            if key.isdigit() or key in ['.', '-']: self.input_buffer += key; return True
            elif event.key() == Qt.Key.Key_Backspace: self.input_buffer = self.input_buffer[:-1]; return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    try:
                        dist = float(self.input_buffer)
                        ref_pos = self.stretch_start_pos if self.is_stretching else self.move_start_pos
                        sx, sy = ref_pos.x(), ref_pos.y()
                        hud_info = self.canvas.hud_polar_info.toPlainText() if self.canvas.hud_polar_info else ""
                        current_angle = 0.0
                        if "极轴" in hud_info:
                             try: current_angle = float(hud_info.split("<")[1].split("°")[0].strip())
                             except: pass
                        rad = math.radians(current_angle)
                        new_x = sx + dist * math.cos(rad); new_y = sy - dist * math.sin(rad)
                        if self.is_stretching: self._finalize_stretch(QPointF(new_x, new_y))
                        elif self.is_moving: self._finalize_move(QPointF(new_x, new_y))
                    except ValueError: pass
                else:
                    if self.is_stretching: self._finalize_stretch()
                    elif self.is_moving: self._finalize_move(getattr(self.canvas, 'last_cursor_point', QPointF(0,0)))
                return True
            elif event.key() == Qt.Key.Key_Escape:
                if self.is_stretching:
                    for data in self.stretch_items: apply_geom_data(data['item'], data['old_data'])
                if self.is_moving:
                    for data in self.move_items: 
                        apply_geom_data(data['item'], data['old_data'])
                        if data['type'] == 'text': data['item'].setPos(data['old_data']['pos'])
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'): self.canvas._cleanup_tracking_huds()
                return True
        return False

    def _finalize_stretch(self, final_point=None):
        if not self.stretch_items or not final_point: return
        dx = final_point.x() - self.stretch_start_pos.x()
        dy = final_point.y() - self.stretch_start_pos.y()
        
        stretch_data_cmd = []
        is_all_valid = True
        
        for data in self.stretch_items:
            item = data['item']
            old_data = data['old_data']
            new_data = self._calculate_stretched_data(data, dx, dy)
            
            if data['type'] == 'poly' and not GeometryEngine.is_valid_polygon(new_data['coords']): 
                is_all_valid = False
            
            # 为了让撤销栈 UndoStack 能识别前后的状态变化，先把图形还原一次
            apply_geom_data(item, old_data)
            stretch_data_cmd.append((item, old_data, new_data))

        if not is_all_valid: 
            self._cleanup_temp_items(); return 
            
        if stretch_data_cmd: 
            self.canvas.undo_stack.push(CommandModifyMultipleGeom(stretch_data_cmd))
            
        self._cleanup_temp_items()
        if hasattr(self.canvas, '_cleanup_tracking_huds'): self.canvas._cleanup_tracking_huds()
        self.canvas.viewport().update()

    def _finalize_move(self, final_point):
        if not self.move_items or not self.move_start_pos: return
        dx = final_point.x() - self.move_start_pos.x()
        dy = final_point.y() - self.move_start_pos.y()
        
        move_data_cmd = []
        for data in self.move_items:
            item = data['item']
            old_data = data['old_data']
            new_data = self._calculate_moved_data(old_data, data['type'], dx, dy)
            
            # 先恢复原状
            apply_geom_data(item, old_data)
            if data['type'] == 'text' and 'pos' in old_data:
                item.setPos(old_data['pos'])
            
            move_data_cmd.append((item, old_data, new_data))
            
        if move_data_cmd: 
            self.canvas.undo_stack.push(CommandMoveGeom(move_data_cmd))
            
        self._cleanup_temp_items()
        if hasattr(self.canvas, '_cleanup_tracking_huds'): self.canvas._cleanup_tracking_huds()
        self.canvas.viewport().update()