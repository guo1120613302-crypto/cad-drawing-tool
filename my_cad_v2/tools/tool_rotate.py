# tools/tool_rotate.py
import math
from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartDimensionItem, 
    SmartCircleItem, SmartPolylineItem, SmartArcItem
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem, 
    QGraphicsPathItem, QGraphicsRectItem
)
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF, QPainterPath, QBrush

class CommandRotateGeom(QUndoCommand):
    def __init__(self, rotate_data):
        super().__init__()
        self.rotate_data = rotate_data 

    def redo(self):
        for item, _, new_data in self.rotate_data:
            if item.scene():
                item.set_coords(new_data)

    def undo(self):
        for item, old_data, _ in self.rotate_data:
            if item.scene():
                item.set_coords(old_data)


class RotateTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_items = []
        self.base_point = None
        self.ref_angle = 0.0
        self.ghost_items = []
        self.state = 0 
        self.input_buffer = ""
        self.selection_box = None
        self.start_point = None

    def get_reference_point(self):
        return self.base_point if self.state == 2 else None

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.base_point = None
        self.input_buffer = ""
        self._cleanup_ghosts()
        
        selected = self.canvas.scene().selectedItems() if self.canvas.scene() else []
        self.target_items = [item for item in selected if getattr(item, 'is_smart_shape', False)]
        if self.target_items:
            self.state = 1
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghosts()
        for item in self.target_items:
            item.setSelected(False)
        self.target_items.clear()
        
        if self.selection_box:
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
            
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghosts(self):
        for ghost_dict in self.ghost_items:
            if ghost_dict['ghost'].scene():
                self.canvas.scene().removeItem(ghost_dict['ghost'])
        self.ghost_items.clear()

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): 
            return
            
        self.canvas.hud_polar_info.show()
        if self.state == 0:
            text, color = "旋转: 框选或点击要旋转的对象 (选完按右键或回车确认)", "#5bc0de"
        elif self.state == 1:
            text, color = "旋转: 请指定旋转的【基点】", "#f0ad4e"
        elif self.state == 2:
            text, color = f"旋转: 指定旋转角度或第二点: {self.input_buffer}", "#5cb85c"
            
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:{color}; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>🔄 {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _update_preview(self, current_angle):
        if not self.target_items or not self.base_point: 
            return
            
        delta_angle = current_angle - self.ref_angle
        rad = math.radians(delta_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        bx, by = self.base_point.x(), self.base_point.y()

        if not self.ghost_items:
            pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            for item in self.target_items:
                ghost = QGraphicsPathItem()
                ghost.setPen(pen)
                self.canvas.scene().addItem(ghost)
                self.ghost_items.append({
                    'item': item, 
                    'ghost': ghost, 
                    'type': getattr(item, 'geom_type', 'unknown')
                })

        for data in self.ghost_items:
            item = data['item']
            ghost = data['ghost']
            g_type = data['type']
            path = QPainterPath()
            
            if g_type == 'arc':
                c = item.center
                r = item.radius
                sa = item.start_angle
                ea = item.end_angle
                
                nx = bx + (c[0] - bx) * cos_a - (c[1] - by) * sin_a
                ny = by + (c[0] - bx) * sin_a + (c[1] - by) * cos_a
                
                new_sa = (sa + delta_angle) % 360
                new_ea = (ea + delta_angle) % 360
                span = new_ea - new_sa
                if span <= 0: 
                    span += 360
                    
                rect = QRectF(nx - r, ny - r, 2 * r, 2 * r)
                path.arcMoveTo(rect, new_sa)
                path.arcTo(rect, new_sa, span)
            else:
                new_c = []
                for x, y in item.coords:
                    nx = bx + (x - bx) * cos_a - (y - by) * sin_a
                    ny = by + (x - bx) * sin_a + (y - by) * cos_a
                    new_c.append((nx, ny))
                    
                if g_type == 'line': 
                    path.moveTo(QPointF(*new_c[0]))
                    path.lineTo(QPointF(*new_c[1]))
                elif g_type == 'poly':
                    path.moveTo(QPointF(*new_c[0]))
                    for nx, ny in new_c[1:]: 
                        path.lineTo(QPointF(nx, ny))
                    path.closeSubpath()
                elif g_type == 'dim': 
                    path = item.get_lines_path(new_c)
                elif g_type == 'circle':
                    c = new_c[0]
                    e = new_c[1]
                    r = math.hypot(e[0] - c[0], e[1] - c[1])
                    path.addEllipse(QPointF(*c), r, r)
                elif g_type == 'polyline':
                    path.moveTo(QPointF(*new_c[0]))
                    for nx, ny in new_c[1:]: 
                        path.lineTo(QPointF(nx, ny))
                        
            ghost.setPath(path)

    def mousePressEvent(self, event, final_point, snapped_angle):
        raw_point = self.canvas.mapToScene(event.pos())
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
                if getattr(item, 'is_smart_shape', False):
                    # 点选
                    if item not in self.target_items: 
                        self.target_items.append(item)
                        item.setSelected(True)
                else:
                    # 空白处点击，开启框选
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
                self.base_point = final_point
                self.state = 2
                self.ref_angle = snapped_angle
                self._update_hud()
                return True
                
            elif self.state == 2:
                self._finalize_rotate(snapped_angle)
                return True
                
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state == 0 and self.target_items:
                self.state = 1
            elif self.state == 2:
                self._cleanup_ghosts()
                self.state = 1
            elif self.state == 1:
                self.state = 0
                for item in self.target_items: 
                    item.setSelected(False)
                self.target_items.clear()
            else:
                self.deactivate()
                self.canvas.switch_tool("选择")
            self._update_hud()
            return True
            
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        raw_point = self.canvas.mapToScene(event.pos())
        self._update_hud()
        
        # 处理框选动画
        if self.state == 0 and self.selection_box and self.start_point:
            x = min(self.start_point.x(), raw_point.x())
            y = min(self.start_point.y(), raw_point.y())
            w = abs(self.start_point.x() - raw_point.x())
            h = abs(self.start_point.y() - raw_point.y())
            
            self.selection_box.setRect(x, y, w, h)
            
            # 判断蓝框(全包围)还是绿框(交叉)
            is_blue = raw_point.x() > self.start_point.x()
            color = QColor(0, 120, 215) if is_blue else QColor(76, 175, 80)
            pen_style = Qt.PenStyle.SolidLine if is_blue else Qt.PenStyle.DashLine
            
            pen = QPen(color, 1, pen_style)
            pen.setCosmetic(True)
            self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
            return True
            
        if self.state == 2 and self.base_point:
            self._update_preview(snapped_angle)
            
        return True

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton and self.state == 0 and self.selection_box:
            rect = self.selection_box.rect()
            if rect.width() > 0 and rect.height() > 0:
                raw_point = self.canvas.mapToScene(event.pos())
                is_blue = raw_point.x() > self.start_point.x()
                mode = Qt.ItemSelectionMode.ContainsItemShape if is_blue else Qt.ItemSelectionMode.IntersectsItemShape
                
                for item in self.canvas.scene().items(rect, mode):
                    if getattr(item, 'is_smart_shape', False) and item not in self.target_items:
                        self.target_items.append(item)
                        item.setSelected(True)
                        
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
            self.start_point = None
            return True
        return False

    def keyPressEvent(self, event):
        key = event.text()
        if key.isdigit() or key in ['.', '-']: 
            self.input_buffer += key
            self._update_hud()
            return True
        elif event.key() == Qt.Key.Key_Backspace:
            self.input_buffer = self.input_buffer[:-1]
            self._update_hud()
            return True
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.state == 0 and self.target_items:
                self.state = 1
                self._update_hud()
            elif self.state == 2:
                if self.input_buffer:
                    try:
                        self._finalize_rotate(self.ref_angle + float(self.input_buffer))
                    except ValueError:
                        pass
                else:
                    self._finalize_rotate(getattr(self.canvas, 'last_snapped_angle', 0.0))
            return True
        elif event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
        return False

    def _finalize_rotate(self, target_angle):
        if not self.target_items or not self.base_point: 
            return
            
        delta_angle = target_angle - self.ref_angle
        rad = math.radians(delta_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        bx, by = self.base_point.x(), self.base_point.y()
        
        rotate_data = []
        for item in self.target_items:
            g_type = getattr(item, 'geom_type', '')
            if g_type == 'arc':
                c = item.center
                r = item.radius
                sa = item.start_angle
                ea = item.end_angle
                
                nx = bx + (c[0] - bx) * cos_a - (c[1] - by) * sin_a
                ny = by + (c[0] - bx) * sin_a + (c[1] - by) * cos_a
                
                new_sa = (sa + delta_angle) % 360
                new_ea = (ea + delta_angle) % 360
                
                old_data = {'center': c, 'radius': r, 'sa': sa, 'ea': ea}
                new_data = {'center': (nx, ny), 'radius': r, 'sa': new_sa, 'ea': new_ea}
                rotate_data.append((item, old_data, new_data))
            else:
                old_c = list(item.coords)
                new_c = []
                for x, y in old_c:
                    nx = bx + (x - bx) * cos_a - (y - by) * sin_a
                    ny = by + (x - bx) * sin_a + (y - by) * cos_a
                    new_c.append((nx, ny))
                rotate_data.append((item, old_c, new_c))
            
        if rotate_data:
            self.canvas.undo_stack.push(CommandRotateGeom(rotate_data))
            
        self.deactivate()
        self.canvas.switch_tool("选择")