# tools/tool_select.py
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem, SmartDimensionItem
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsPathItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QBrush, QUndoCommand, QPolygonF, QPainterPath
import math
import traceback
from utils.geom_engine import GeometryEngine

class CommandModifyMultipleGeom(QUndoCommand):
    def __init__(self, stretch_data):
        super().__init__()
        self.stretch_data = stretch_data 
    def redo(self):
        for item, _, new_coords in self.stretch_data:
            if item.scene(): 
                item.set_coords(new_coords)
    def undo(self):
        for item, old_coords, _ in self.stretch_data:
            if item.scene(): 
                item.set_coords(old_coords)

class CommandMoveGeom(QUndoCommand):
    def __init__(self, move_data):
        super().__init__()
        self.move_data = move_data
    def redo(self):
        for item, _, new_c in self.move_data:
            if item.scene(): item.set_coords(new_c)
    def undo(self):
        for item, old_c, _ in self.move_data:
            if item.scene(): item.set_coords(old_c)

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
        self.ghost_items = [] 
        self.original_affected_items = []
        self.input_buffer = ""

    def _cleanup_temp_items(self):
        for ghost_dict in self.ghost_items:
            ghost_item = ghost_dict['ghost']
            if ghost_item.scene():
                ghost_item.scene().removeItem(ghost_item)
        self.ghost_items.clear()
        
        for item in self.original_affected_items:
            item.show()
            item.hot_grip_index = -1
        self.original_affected_items = []
        
        self.is_stretching = False
        self.stretch_items = []
        self.stretch_start_pos = None
        self.is_moving = False
        self.move_items = []
        self.move_start_pos = None
        self.input_buffer = ""

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def deactivate(self):
        self._cleanup_temp_items()
        if self.selection_box:
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
        if self.canvas.scene():
            self.canvas.scene().clearSelection()

    def get_reference_point(self):
        if self.is_stretching: return self.stretch_start_pos
        elif self.is_moving: return self.move_start_pos
        return None

    def get_input_buffer(self): return self.input_buffer

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.MiddleButton: return False

        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_stretching:
                self._finalize_stretch(final_point) 
                return True
            if self.is_moving:
                self._finalize_move(final_point)
                return True

            self.input_buffer = "" 
            raw_point = self.canvas.mapToScene(event.pos())
            selected_items = self.canvas.scene().selectedItems()
            if selected_items:
                hit_radius = 15.0 / self.canvas.transform().m11()
                found_grips = []
                
                for item in selected_items:
                    # 【支持标注夹点拉伸】
                    if isinstance(item, (SmartLineItem, SmartPolygonItem, SmartDimensionItem)):
                        for i, (gx, gy) in enumerate(item.get_grips()):
                            if math.hypot(raw_point.x() - gx, raw_point.y() - gy) < hit_radius:
                                g_type = 'line' if isinstance(item, SmartLineItem) else ('poly' if isinstance(item, SmartPolygonItem) else 'dim')
                                found_grips.append({
                                    'item': item, 'index': i, 'type': g_type,
                                    'old_coords': list(item.coords), 'grip_pos': (gx, gy)
                                })
                                item.hot_grip_index = i 

                if found_grips:
                    self.is_stretching = True
                    self.stretch_items = found_grips
                    self.stretch_start_pos = QPointF(*found_grips[0]['grip_pos'])
                    pen = QPen(QColor(255, 0, 0, 150), 1)
                    pen.setCosmetic(True)
                    brush = QBrush(QColor(255, 0, 0, 50))
                    
                    self.original_affected_items = []
                    self.ghost_items = []
                    
                    for item_data in self.stretch_items:
                        item = item_data['item']
                        if item not in self.original_affected_items:
                            item.hide()
                            self.original_affected_items.append(item)
                            
                        if item_data['type'] == 'line':
                            ghost = QGraphicsLineItem(item.line())
                            ghost.setPen(pen)
                            ghost.setZValue(10000)
                            self.canvas.scene().addItem(ghost)
                            self.ghost_items.append({'ghost': ghost, 'data': item_data})
                        elif item_data['type'] == 'poly':
                            ghost = QGraphicsPolygonItem(item.polygon())
                            ghost.setPen(pen)
                            ghost.setBrush(brush)
                            ghost.setZValue(10000)
                            self.canvas.scene().addItem(ghost)
                            self.ghost_items.append({'ghost': ghost, 'data': item_data})
                        elif item_data['type'] == 'dim':
                            ghost = QGraphicsPathItem(item.get_lines_path())
                            ghost.setPen(pen)
                            ghost.setZValue(10000)
                            self.canvas.scene().addItem(ghost)
                            self.ghost_items.append({'ghost': ghost, 'data': item_data})
                    return True
                
                clicked_item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
                if isinstance(clicked_item, (SmartLineItem, SmartPolygonItem, SmartDimensionItem)) and clicked_item.isSelected():
                    self.is_moving = True
                    self.move_items = [item for item in selected_items if isinstance(item, (SmartLineItem, SmartPolygonItem, SmartDimensionItem))]
                    self.move_start_pos = final_point
                    
                    pen = QPen(QColor(0, 255, 255, 150), 1, Qt.PenStyle.DashLine)
                    pen.setCosmetic(True)
                    self.ghost_items = []
                    self.original_affected_items = []
                    
                    for item in self.move_items:
                        item.hide()
                        self.original_affected_items.append(item)
                        if isinstance(item, SmartLineItem):
                            ghost = QGraphicsLineItem(item.line())
                            ghost.setPen(pen)
                            ghost.setZValue(10000)
                            self.canvas.scene().addItem(ghost)
                            self.ghost_items.append({'ghost': ghost, 'item': item, 'type': 'line'})
                        elif isinstance(item, SmartPolygonItem):
                            ghost = QGraphicsPolygonItem(item.polygon())
                            ghost.setPen(pen)
                            ghost.setZValue(10000)
                            self.canvas.scene().addItem(ghost)
                            self.ghost_items.append({'ghost': ghost, 'item': item, 'type': 'poly'})
                        elif isinstance(item, SmartDimensionItem):
                            ghost = QGraphicsPathItem(item.get_lines_path())
                            ghost.setPen(pen)
                            ghost.setZValue(10000)
                            self.canvas.scene().addItem(ghost)
                            self.ghost_items.append({'ghost': ghost, 'item': item, 'type': 'dim'})
                    return True
            
            self.start_point = raw_point
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.canvas.scene().clearSelection()
            self.selection_box = QGraphicsRectItem()
            pen = QPen(QColor(0, 120, 215), 1)
            pen.setCosmetic(True)
            self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(0, 120, 215, 40)))
            self.selection_box.setZValue(5000)
            self.canvas.scene().addItem(self.selection_box)
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            if self.is_stretching or self.is_moving:
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
            elif self.canvas.scene().selectedItems():
                self.canvas.scene().clearSelection()
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.is_moving and self.move_items:
            dx = final_point.x() - self.move_start_pos.x()
            dy = final_point.y() - self.move_start_pos.y()
            for ghost_dict in self.ghost_items:
                ghost, item, g_type = ghost_dict['ghost'], ghost_dict['item'], ghost_dict['type']
                if g_type == 'line':
                    old_c = item.coords
                    ghost.setLine(QLineF(old_c[0][0]+dx, old_c[0][1]+dy, old_c[1][0]+dx, old_c[1][1]+dy))
                elif g_type == 'poly':
                    old_c = item.coords
                    poly_f = QPolygonF()
                    for x, y in old_c: poly_f.append(QPointF(x + dx, y + dy))
                    ghost.setPolygon(poly_f)
                elif g_type == 'dim':
                    old_c = item.coords
                    new_c = [(x + dx, y + dy) for x, y in old_c]
                    ghost.setPath(item.get_lines_path(new_c))
            self.canvas.viewport().update()
            return True
        
        if self.is_stretching and self.stretch_items:
            dx = final_point.x() - self.stretch_start_pos.x()
            dy = final_point.y() - self.stretch_start_pos.y()
            for ghost_dict in self.ghost_items:
                ghost, data = ghost_dict['ghost'], ghost_dict['data']
                g_type, old_coords, idx = data['type'], data['old_coords'], data['index']
                new_coords = list(old_coords)
                
                if g_type == 'line':
                    if idx == 0: new_coords[0] = (old_coords[0][0]+dx, old_coords[0][1]+dy)
                    elif idx == 2: new_coords[1] = (old_coords[1][0]+dx, old_coords[1][1]+dy)
                    elif idx == 1: 
                        new_coords[0] = (old_coords[0][0]+dx, old_coords[0][1]+dy)
                        new_coords[1] = (old_coords[1][0]+dx, old_coords[1][1]+dy)
                    ghost.setLine(QLineF(new_coords[0][0], new_coords[0][1], new_coords[1][0], new_coords[1][1]))
                elif g_type == 'poly':
                    count = len(old_coords)
                    if idx < count:
                        new_coords[idx] = (old_coords[idx][0]+dx, old_coords[idx][1]+dy)
                    else:
                        edge_idx = idx - count
                        p1_idx, p2_idx = edge_idx, (edge_idx + 1) % count
                        new_coords[p1_idx] = (old_coords[p1_idx][0]+dx, old_coords[p1_idx][1]+dy)
                        new_coords[p2_idx] = (old_coords[p2_idx][0]+dx, old_coords[p2_idx][1]+dy)
                    poly = QPolygonF()
                    for x, y in new_coords: poly.append(QPointF(x, y))
                    ghost.setPolygon(poly)
                elif g_type == 'dim':
                    new_coords[idx] = (old_coords[idx][0] + dx, old_coords[idx][1] + dy)
                    ghost.setPath(data['item'].get_lines_path(new_coords))
                    
            self.canvas.viewport().update()
            return True

        if self.start_point and self.selection_box:
            raw_point = self.canvas.mapToScene(event.pos())
            x, y = min(self.start_point.x(), raw_point.x()), min(self.start_point.y(), raw_point.y())
            w, h = abs(self.start_point.x() - raw_point.x()), abs(self.start_point.y() - raw_point.y())
            self.selection_box.setRect(x, y, w, h)
            color = QColor(0, 120, 215) if raw_point.x() > self.start_point.x() else QColor(76, 175, 80)
            pen = QPen(color, 1, Qt.PenStyle.SolidLine if raw_point.x() > self.start_point.x() else Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
            return True
        return False

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton and (self.is_stretching or self.is_moving):
            return True 
        
        if event.button() == Qt.MouseButton.LeftButton and self.start_point and self.selection_box:
            raw_point = self.canvas.mapToScene(event.pos())
            rect = self.selection_box.rect()
            if rect.width() > 0 and rect.height() > 0:
                mode = Qt.ItemSelectionMode.ContainsItemShape if raw_point.x() > self.start_point.x() else Qt.ItemSelectionMode.IntersectsItemShape
                for item in self.canvas.scene().items(rect, mode):
                    if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable:
                        item.setSelected(True)
            if self.selection_box: self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
            self.start_point = None
            return True
        return False

    def keyPressEvent(self, event):
        if self.is_stretching or self.is_moving:
            key = event.text()
            if key.isdigit() or key in ['.', '-']:
                self.input_buffer += key
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                return True
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
                        new_x = sx + dist * math.cos(rad)
                        new_y = sy - dist * math.sin(rad)
                        if self.is_stretching: self._finalize_stretch(QPointF(new_x, new_y))
                        elif self.is_moving: self._finalize_move(QPointF(new_x, new_y))
                    except ValueError: pass
                else:
                    if self.is_stretching: self._finalize_stretch()
                    elif self.is_moving: self._finalize_move(getattr(self.canvas, 'last_cursor_point', QPointF(0,0)))
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
                return True
        return False

    def _finalize_stretch(self, final_point=None):
        if not self.stretch_items or not final_point: return
        dx = final_point.x() - self.stretch_start_pos.x()
        dy = final_point.y() - self.stretch_start_pos.y()
        stretch_data = []
        is_all_valid = True
        
        for data in self.stretch_items:
            item, idx, g_type, old_coords = data['item'], data['index'], data['type'], data['old_coords']
            new_coords = list(old_coords)
            if g_type == 'line':
                if idx == 0: new_coords[0] = (old_coords[0][0]+dx, old_coords[0][1]+dy)
                elif idx == 2: new_coords[1] = (old_coords[1][0]+dx, old_coords[1][1]+dy)
                elif idx == 1: 
                    new_coords[0] = (old_coords[0][0]+dx, old_coords[0][1]+dy)
                    new_coords[1] = (old_coords[1][0]+dx, old_coords[1][1]+dy)
            elif g_type == 'poly':
                count = len(old_coords)
                if idx < count:
                    new_coords[idx] = (old_coords[idx][0]+dx, old_coords[idx][1]+dy)
                else:
                    edge_idx = idx - count
                    p1_idx, p2_idx = edge_idx, (edge_idx + 1) % count
                    new_coords[p1_idx] = (old_coords[p1_idx][0]+dx, old_coords[p1_idx][1]+dy)
                    new_coords[p2_idx] = (old_coords[p2_idx][0]+dx, old_coords[p2_idx][1]+dy)
            elif g_type == 'dim':
                new_coords[idx] = (old_coords[idx][0]+dx, old_coords[idx][1]+dy)
            
            if g_type == 'poly' and not GeometryEngine.is_valid_polygon(new_coords):
                is_all_valid = False
            stretch_data.append((item, old_coords, new_coords))

        if not is_all_valid:
            self._cleanup_temp_items()
            return 

        if stretch_data:
            # 【核心修复】：彻底移除了将原图形覆盖为当前白色画笔的 Bug 代码！拉伸后永远保持原色原图层！
            self.canvas.undo_stack.push(CommandModifyMultipleGeom(stretch_data))
            
        self._cleanup_temp_items()
        if hasattr(self.canvas, '_cleanup_tracking_huds'): self.canvas._cleanup_tracking_huds()
        self.canvas.viewport().update()

    def _finalize_move(self, final_point):
        if not self.move_items or not self.move_start_pos: return
        dx = final_point.x() - self.move_start_pos.x()
        dy = final_point.y() - self.move_start_pos.y()
        move_data = []
        for item in self.move_items:
            old_c = list(item.coords)
            new_c = [(x + dx, y + dy) for x, y in old_c]
            move_data.append((item, old_c, new_c))
        if move_data:
            self.canvas.undo_stack.push(CommandMoveGeom(move_data))
        self._cleanup_temp_items()
        if hasattr(self.canvas, '_cleanup_tracking_huds'): self.canvas._cleanup_tracking_huds()
        self.canvas.viewport().update()