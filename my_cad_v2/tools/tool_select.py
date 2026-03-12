# tools/tool_select.py
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QBrush, QUndoCommand, QPolygonF
import math
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

class SelectTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.start_point = None
        self.selection_box = None
        
        self.is_stretching = False
        self.stretch_items = [] 
        self.stretch_start_pos = None 
        
        # --- 修复：支持多物体并发拉伸的幽灵数组 ---
        self.ghost_items = [] 
        self.original_affected_items = []

        self.input_buffer = ""

    def _cleanup_temp_items(self):
        """安全清理所有幽灵组件 (彻底杜绝 C++ 内存崩溃)"""
        # --- 修复闪退：正确解析字典结构 ---
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
        return self.stretch_start_pos if self.is_stretching else None

    def get_input_buffer(self): return self.input_buffer

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.MiddleButton: return False

        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_stretching:
                # 修复：安全传递坐标，避免游标迷失
                self._finalize_stretch(final_point) 
                return True

            self.input_buffer = "" 
            raw_point = self.canvas.mapToScene(event.pos())
            
            selected_items = self.canvas.scene().selectedItems()
            if selected_items:
                hit_radius = 12.0 / self.canvas.transform().m11()
                found_grips = []
                
                for item in selected_items:
                    if isinstance(item, (SmartLineItem, SmartPolygonItem)):
                        for i, (gx, gy) in enumerate(item.get_grips()):
                            if math.hypot(raw_point.x() - gx, raw_point.y() - gy) < hit_radius:
                                found_grips.append({
                                    'item': item,
                                    'index': i,
                                    'type': 'line' if isinstance(item, SmartLineItem) else 'poly',
                                    'old_coords': list(item.coords),
                                    'grip_pos': (gx, gy)
                                })
                                item.hot_grip_index = i 

                if found_grips:
                    self.is_stretching = True
                    self.stretch_items = found_grips
                    
                    hit_gx, hit_gy = found_grips[0]['grip_pos']
                    self.stretch_start_pos = QPointF(hit_gx, hit_gy)
                    
                    pen = QPen(QColor(255, 0, 0, 150), 1)
                    pen.setCosmetic(True)
                    brush = QBrush(QColor(255, 0, 0, 50))
                    
                    self.original_affected_items = []
                    self.ghost_items = []
                    
                    # 动态生成独立的幽灵，完美支持多重节点拉伸
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
                        else:
                            ghost = QGraphicsPolygonItem(item.polygon())
                            ghost.setPen(pen)
                            ghost.setBrush(brush)
                            ghost.setZValue(10000)
                            self.canvas.scene().addItem(ghost)
                            self.ghost_items.append({'ghost': ghost, 'data': item_data})
                            
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
            if self.is_stretching:
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
            elif self.canvas.scene().selectedItems():
                self.canvas.scene().clearSelection()
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.is_stretching and self.stretch_items:
            dx = final_point.x() - self.stretch_start_pos.x()
            dy = final_point.y() - self.stretch_start_pos.y()
            
            for ghost_dict in self.ghost_items:
                ghost = ghost_dict['ghost']
                data = ghost_dict['data']
                
                g_type = data['type']
                old_coords = data['old_coords']
                idx = data['index']
                new_coords = list(old_coords)
                
                if g_type == 'line':
                    if idx == 0: new_coords[0] = (old_coords[0][0] + dx, old_coords[0][1] + dy)
                    elif idx == 2: new_coords[1] = (old_coords[1][0] + dx, old_coords[1][1] + dy)
                    elif idx == 1: 
                        new_coords[0] = (old_coords[0][0] + dx, old_coords[0][1] + dy)
                        new_coords[1] = (old_coords[1][0] + dx, old_coords[1][1] + dy)
                    (x1, y1), (x2, y2) = new_coords
                    ghost.setLine(QLineF(x1, y1, x2, y2))
                else:
                    count = len(old_coords)
                    if idx < count:
                        new_coords[idx] = (old_coords[idx][0] + dx, old_coords[idx][1] + dy)
                    else:
                        edge_idx = idx - count
                        p1_idx = edge_idx
                        p2_idx = (edge_idx + 1) % count
                        new_coords[p1_idx] = (old_coords[p1_idx][0] + dx, old_coords[p1_idx][1] + dy)
                        new_coords[p2_idx] = (old_coords[p2_idx][0] + dx, old_coords[p2_idx][1] + dy)
                    
                    poly = QPolygonF()
                    for x, y in new_coords: poly.append(QPointF(x, y))
                    ghost.setPolygon(poly)
            
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
        if event.button() == Qt.MouseButton.LeftButton and self.is_stretching:
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
        if self.is_stretching:
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
                        sx, sy = self.stretch_start_pos.x(), self.stretch_start_pos.y()
                        
                        hud_info = self.canvas.hud_polar_info.toPlainText() if self.canvas.hud_polar_info else ""
                        current_angle = 0.0
                        if "极轴" in hud_info:
                             try:
                                angle_str = hud_info.split("<")[1].split("°")[0].strip()
                                current_angle = float(angle_str)
                             except (IndexError, ValueError): pass
                        
                        rad = math.radians(current_angle)
                        new_x = sx + dist * math.cos(rad)
                        new_y = sy - dist * math.sin(rad)
                        
                        self._finalize_stretch(QPointF(new_x, new_y))
                    except (ValueError, EOFError): pass
                else: 
                    self._finalize_stretch()
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cleanup_temp_items()
                if hasattr(self.canvas, '_cleanup_tracking_huds'):
                    self.canvas._cleanup_tracking_huds()
                return True
        return False

    def _finalize_stretch(self, final_point=None):
        if not self.stretch_items: return
        
        if not final_point:
            return
            
        dx = final_point.x() - self.stretch_start_pos.x()
        dy = final_point.y() - self.stretch_start_pos.y()
        
        stretch_data = []
        is_all_valid = True
        
        for data in self.stretch_items:
            item = data['item']
            idx = data['index']
            g_type = data['type']
            old_coords = data['old_coords']
            new_coords = list(old_coords)
            
            if g_type == 'line':
                if idx == 0: new_coords[0] = (old_coords[0][0] + dx, old_coords[0][1] + dy)
                elif idx == 2: new_coords[1] = (old_coords[1][0] + dx, old_coords[1][1] + dy)
                elif idx == 1: 
                    new_coords[0] = (old_coords[0][0] + dx, old_coords[0][1] + dy)
                    new_coords[1] = (old_coords[1][0] + dx, old_coords[1][1] + dy)
            elif g_type == 'poly':
                count = len(old_coords)
                if idx < count:
                    new_coords[idx] = (old_coords[idx][0] + dx, old_coords[idx][1] + dy)
                else:
                    edge_idx = idx - count
                    p1_idx = edge_idx
                    p2_idx = (edge_idx + 1) % count
                    new_coords[p1_idx] = (old_coords[p1_idx][0] + dx, old_coords[p1_idx][1] + dy)
                    new_coords[p2_idx] = (old_coords[p2_idx][0] + dx, old_coords[p2_idx][1] + dy)
            
            # 核心拦截：不允许保存“自交”的不合法多边形
            if g_type == 'poly' and not GeometryEngine.is_valid_polygon(new_coords):
                is_all_valid = False
            
            stretch_data.append((item, old_coords, new_coords))

        if not is_all_valid:
            self._cleanup_temp_items()
            return 

        if stretch_data:
            current_color = self.canvas.color_manager.get_color()
            for item in self.original_affected_items:
                pen = QPen(current_color, 1)
                pen.setCosmetic(True)
                item.setPen(pen)

            self.canvas.undo_stack.push(CommandModifyMultipleGeom(stretch_data))
            
        self._cleanup_temp_items()
        
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()
        self.canvas.viewport().update()