# tools/tool_select.py
from tools.base_tool import BaseTool
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QRectF, QLineF, QPointF
from PyQt6.QtGui import QPen, QColor, QBrush, QUndoCommand
import math

class CommandModifyMultipleLines(QUndoCommand):
    def __init__(self, stretch_data):
        super().__init__()
        self.stretch_data = stretch_data 
    def redo(self):
        for item, _, new_line in self.stretch_data:
            if item.scene(): item.setLine(new_line)
    def undo(self):
        for item, old_line, _ in self.stretch_data:
            if item.scene(): item.setLine(old_line)

class SelectTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.start_point = None
        self.selection_box = None
        
        self.is_stretching = False
        self.stretch_items = [] 
        self.rubber_bands = [] # 【新增】：存储橡皮筋参考线
        self.stretch_start_pos = None
        self.input_buffer = ""

    def get_reference_point(self):
        if self.is_stretching and self.stretch_items:
            data = self.stretch_items[0]
            line = data['old_line']
            idx = data['index']
            if idx == 0: return line.p2()
            elif idx == 2: return line.p1()
            elif idx == 1: return self.stretch_start_pos
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
        """【新增】：清理残留的橡皮筋参考线"""
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
                                found_grips.append({
                                    'item': item,
                                    'index': i,
                                    'old_line': item.line()
                                })
                                item.hot_grip_index = i 

                if found_grips:
                    self.is_stretching = True
                    self.stretch_items = found_grips
                    self.stretch_start_pos = raw_point
                    
                    # 【核心新增】：创建橡皮筋引导线
                    self._cleanup_rubber_bands()
                    rb_pen = QPen(QColor(150, 150, 150, 150), 1, Qt.PenStyle.DashLine)
                    rb_pen.setCosmetic(True)
                    for data in found_grips:
                        rb_line = QGraphicsLineItem(data['old_line'])
                        rb_line.setPen(rb_pen)
                        rb_line.setZValue(50) # 置于底层
                        self.canvas.scene().addItem(rb_line)
                        self.rubber_bands.append(rb_line)
                        
                    self.canvas.viewport().update()
                    return True
            
            self.start_point = raw_point
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.canvas.scene().clearSelection()
            self.selection_box = QGraphicsRectItem()
            self.selection_box.setZValue(5000)
            self.canvas.scene().addItem(self.selection_box)
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.is_stretching and self.stretch_items:
            if not self.input_buffer:
                for data in self.stretch_items:
                    item, idx, old = data['item'], data['index'], data['old_line']
                    if idx == 0: item.setLine(QLineF(final_point, old.p2()))
                    elif idx == 2: item.setLine(QLineF(old.p1(), final_point))
                    elif idx == 1:
                        dx, dy = final_point.x() - self.stretch_start_pos.x(), final_point.y() - self.stretch_start_pos.y()
                        item.setLine(QLineF(QPointF(old.p1().x()+dx, old.p1().y()+dy), QPointF(old.p2().x()+dx, old.p2().y()+dy)))
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
                    data['item'].setLine(data['old_line'])
                    data['item'].hot_grip_index = -1
                self.is_stretching = False
                self.stretch_items = []
                self._cleanup_rubber_bands() # 取消时也清理
                self.input_buffer = ""
                self.canvas._cleanup_tracking_huds()
                return True
        return False

    def _apply_stretch_by_dist(self, distance):
        if not self.stretch_items: return
        ref_data = self.stretch_items[0]
        anchor = ref_data['old_line'].p2() if ref_data['index'] == 0 else ref_data['old_line'].p1()
        _, current_angle = self.canvas._calculate_global_snap(self.canvas.last_cursor_point)
        rad = math.radians(current_angle)
        
        new_point = QPointF(anchor.x() + distance * math.cos(rad), anchor.y() - distance * math.sin(rad))
        
        for data in self.stretch_items:
            item, idx, old = data['item'], data['index'], data['old_line']
            if idx == 0: item.setLine(QLineF(new_point, old.p2()))
            elif idx == 2: item.setLine(QLineF(old.p1(), new_point))
        self._finalize_stretch()

    def _finalize_stretch(self):
        if self.stretch_items:
            stretch_data = []
            for data in self.stretch_items:
                stretch_data.append((data['item'], data['old_line'], data['item'].line()))
                data['item'].hot_grip_index = -1
            self.canvas.undo_stack.push(CommandModifyMultipleLines(stretch_data))
        self.is_stretching = False
        self.stretch_items = []
        self._cleanup_rubber_bands() # 结算后清理
        self.input_buffer = ""
        self.canvas._cleanup_tracking_huds()
        self.canvas.viewport().update()