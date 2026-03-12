# tools/tool_select.py
from tools.base_tool import BaseTool
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem
from PyQt6.QtCore import Qt, QRectF, QLineF, QPointF
from PyQt6.QtGui import QPen, QColor, QBrush, QUndoCommand, QPolygonF
import math

class CommandModifyMultipleGeom(QUndoCommand):
    def __init__(self, stretch_data):
        super().__init__()
        self.stretch_data = stretch_data 
    def redo(self):
        for item, g_type, _, new_geom in self.stretch_data:
            if item.scene(): 
                if g_type == 'line': item.setLine(new_geom)
                elif g_type == 'poly': item.setPolygon(new_geom)
    def undo(self):
        for item, g_type, old_geom, _ in self.stretch_data:
            if item.scene(): 
                if g_type == 'line': item.setLine(old_geom)
                elif g_type == 'poly': item.setPolygon(old_geom)

class SelectTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.start_point = None
        self.selection_box = None
        self.is_stretching = False
        self.stretch_items = [] 
        self.rubber_bands = [] 
        self.stretch_start_pos = None
        self.input_buffer = ""

    def get_reference_point(self):
        # 【核心修复】：无论拖拽什么对象，极轴追踪的参考点永远是“夹点的初始位置”
        if self.is_stretching and self.stretch_items:
            return self.stretch_start_pos
        return None
    

    def get_input_buffer(self):
        return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def deactivate(self):
        self._cleanup_all()

    def _cleanup_box(self):
        if self.selection_box:
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
        self.start_point = None

    def _cleanup_rubber_bands(self):
        for rb in self.rubber_bands:
            if rb.scene():
                self.canvas.scene().removeItem(rb)
        self.rubber_bands = []

    def _cleanup_all(self):
        self._cleanup_box()
        self._cleanup_rubber_bands()
        self.canvas.scene().clearSelection()

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_stretching:
                self._finalize_stretch()
                return True

            self.input_buffer = "" 
            raw_point = self.canvas.mapToScene(event.pos())
            
            selected_items = self.canvas.scene().selectedItems()
            if selected_items:
                hit_radius = 12.0 / self.canvas.transform().m11()
                found_grips = []
                
                for item in selected_items:
                    if hasattr(item, 'get_grips'):
                        for i, g_pos in enumerate(item.get_grips()):
                            if math.hypot(raw_point.x() - g_pos.x(), raw_point.y() - g_pos.y()) < hit_radius:
                                g_type = 'line' if isinstance(item, QGraphicsLineItem) else 'poly'
                                old_geom = item.line() if g_type == 'line' else item.polygon()
                                
                                found_grips.append({
                                    'item': item,
                                    'index': i,
                                    'type': g_type,
                                    'old_geom': old_geom
                                })
                                item.hot_grip_index = i 

                if found_grips:
                    self.is_stretching = True
                    self.stretch_items = found_grips
                    self.stretch_start_pos = raw_point
                    
                    self._cleanup_rubber_bands()
                    rb_pen = QPen(QColor(150, 150, 150, 150), 1, Qt.PenStyle.DashLine)
                    rb_pen.setCosmetic(True)
                    for data in found_grips:
                        if data['type'] == 'line': rb_geom = QGraphicsLineItem(data['old_geom'])
                        else: rb_geom = QGraphicsPolygonItem(data['old_geom'])
                        rb_geom.setPen(rb_pen)
                        rb_geom.setZValue(50) 
                        self.canvas.scene().addItem(rb_geom)
                        self.rubber_bands.append(rb_geom)
                        
                    self.canvas.viewport().update()
                    return True
            
            self.start_point = raw_point
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.canvas.scene().clearSelection()
            self.selection_box = QGraphicsRectItem()
            self.selection_box.setZValue(5000)
            self.canvas.scene().addItem(self.selection_box)
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self._cleanup_all()
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.is_stretching and self.stretch_items:
            if not self.input_buffer:
                for data in self.stretch_items:
                    item, idx, g_type, old = data['item'], data['index'], data['type'], data['old_geom']
                    
                    if g_type == 'line':
                        if idx == 0: item.setLine(QLineF(final_point, old.p2()))
                        elif idx == 2: item.setLine(QLineF(old.p1(), final_point))
                        elif idx == 1:
                            dx, dy = final_point.x() - self.stretch_start_pos.x(), final_point.y() - self.stretch_start_pos.y()
                            item.setLine(QLineF(QPointF(old.p1().x()+dx, old.p1().y()+dy), QPointF(old.p2().x()+dx, old.p2().y()+dy)))
                    
                    elif g_type == 'poly':
                        count = old.count()
                        points = [old.at(i) for i in range(count)]
                        
                        # 【核心算法】：完美支持 CAD 两种拖拽行为
                        if idx < count:
                            points[idx] = final_point # 1. 拉角点：单独变形
                        else:
                            # 2. 拉中点：整边平移
                            edge_idx = idx - count
                            p1_idx = edge_idx
                            p2_idx = (edge_idx + 1) % count
                            dx = final_point.x() - self.stretch_start_pos.x()
                            dy = final_point.y() - self.stretch_start_pos.y()
                            points[p1_idx] = QPointF(old.at(p1_idx).x() + dx, old.at(p1_idx).y() + dy)
                            points[p2_idx] = QPointF(old.at(p2_idx).x() + dx, old.at(p2_idx).y() + dy)
                            
                        item.setPolygon(QPolygonF(points))
                        
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
            self._cleanup_box()
            return True
        return False

    def keyPressEvent(self, event):
        if self.is_stretching:
            key = event.text()
            if key.isdigit() or key == '.':
                self.input_buffer += key
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    try:
                        dist = float(self.input_buffer)
                        self._apply_stretch_by_dist(dist)
                    except ValueError: pass
                else: self._finalize_stretch()
                return True
            elif event.key() == Qt.Key.Key_Escape:
                for data in self.stretch_items:
                    if data['type'] == 'line': data['item'].setLine(data['old_geom'])
                    elif data['type'] == 'poly': data['item'].setPolygon(data['old_geom'])
                    data['item'].hot_grip_index = -1
                self.is_stretching = False
                self.stretch_items = []
                self._cleanup_rubber_bands() 
                self.input_buffer = ""
                self.canvas._cleanup_tracking_huds()
                return True
        return False

    def get_reference_point(self):
        # 【核心修复】：无论拖拽什么对象，极轴追踪的参考点永远是“夹点的初始位置”
        if self.is_stretching and self.stretch_items:
            return self.stretch_start_pos
        return None

    def _apply_stretch_by_dist(self, distance):
        if not self.stretch_items: return
        
        # 【核心修复】：键盘键入的距离，直接以“夹点初始位置”为基准沿着鼠标方向延伸
        # 这完美还原了 CAD 中拖拽夹点输入数值的行为
        anchor = self.stretch_start_pos

        _, current_angle = self.canvas._calculate_global_snap(self.canvas.last_cursor_point)
        rad = math.radians(current_angle)
        new_point = QPointF(anchor.x() + distance * math.cos(rad), anchor.y() - distance * math.sin(rad))
        
        for data in self.stretch_items:
            item, idx, g_type, old = data['item'], data['index'], data['type'], data['old_geom']
            if g_type == 'line':
                if idx == 0: item.setLine(QLineF(new_point, old.p2()))
                elif idx == 2: item.setLine(QLineF(old.p1(), new_point))
                elif idx == 1: # 补充了线段中点的键盘平移支持
                    dx = new_point.x() - anchor.x()
                    dy = new_point.y() - anchor.y()
                    item.setLine(QLineF(QPointF(old.p1().x()+dx, old.p1().y()+dy), QPointF(old.p2().x()+dx, old.p2().y()+dy)))
                    
            elif g_type == 'poly':
                count = old.count()
                points = [old.at(i) for i in range(count)]
                if idx < count:
                    # 1. 拉角点
                    points[idx] = new_point
                else:
                    # 2. 拉中点 (整边平移)
                    edge_idx = idx - count
                    dx = new_point.x() - anchor.x()
                    dy = new_point.y() - anchor.y()
                    p1_idx = edge_idx
                    p2_idx = (edge_idx + 1) % count
                    points[p1_idx] = QPointF(old.at(p1_idx).x() + dx, old.at(p1_idx).y() + dy)
                    points[p2_idx] = QPointF(old.at(p2_idx).x() + dx, old.at(p2_idx).y() + dy)
                item.setPolygon(QPolygonF(points))
                
        self._finalize_stretch()

    def _finalize_stretch(self):
        if self.stretch_items:
            stretch_data = []
            for data in self.stretch_items:
                new_geom = data['item'].line() if data['type'] == 'line' else data['item'].polygon()
                stretch_data.append((data['item'], data['type'], data['old_geom'], new_geom))
                data['item'].hot_grip_index = -1
            self.canvas.undo_stack.push(CommandModifyMultipleGeom(stretch_data))
            
        self.is_stretching = False
        self.stretch_items = []
        self._cleanup_rubber_bands()
        self.input_buffer = ""
        self.canvas._cleanup_tracking_huds()
        self.canvas.viewport().update()