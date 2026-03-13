# tools/tool_rotate.py
import traceback, math
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF, QBrush

class CommandRotateGeom(QUndoCommand):
    def __init__(self, rotate_data):
        super().__init__()
        self.rotate_data = rotate_data 
    def redo(self):
        for item, _, new_c in self.rotate_data:
            if item.scene(): item.set_coords(new_c)
    def undo(self):
        for item, old_c, _ in self.rotate_data:
            if item.scene(): item.set_coords(old_c)

class RotateTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_items = []
        self.base_point = None
        self.input_buffer = ""
        self.ghost_items = []
        self.state = 0
        # 框选相关
        self.start_point = None
        self.selection_box = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.input_buffer = ""
        self.base_point = None
        self._cleanup_ghosts()
        
        # 【核心逻辑】：智能继承选中状态 (完美支持先框选，后旋转)
        selected = self.canvas.scene().selectedItems() if self.canvas.scene() else []
        self.target_items = [i for i in selected if isinstance(i, (SmartLineItem, SmartPolygonItem))]
        
        if self.target_items:
            # 如果进来前就已经选了东西，直接跳过选人阶段，进入 state 1 (定基点)
            self.state = 1
        else:
            self.state = 0
            
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghosts()
        if self.selection_box:
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
        for i in self.target_items: i.setSelected(False)
        self.target_items.clear()

    def _cleanup_ghosts(self):
        for g in self.ghost_items:
            if g['ghost'].scene(): self.canvas.scene().removeItem(g['ghost'])
        self.ghost_items.clear()

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        # 提示语优化
        text = "选择要旋转的对象 (框选/点选，回车确认)" if self.state==0 else "指定旋转基点" if self.state==1 else f"指定旋转角度: {self.input_buffer}"
        color = "#5bc0de" if self.state==0 else "#f0ad4e" if self.state==1 else "#d9534f"
        self.canvas.hud_polar_info.setHtml(f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>{text}</div>")
        pos = self.canvas.mapToScene(20, 20)
        self.canvas.hud_polar_info.setPos(pos)

    def _rotate_point(self, px, py, cx, cy, angle_deg):
        rad = math.radians(angle_deg)
        nx = cx + (px - cx) * math.cos(rad) - (py - cy) * math.sin(rad)
        ny = cy + (px - cx) * math.sin(rad) + (py - cy) * math.cos(rad)
        return nx, ny

    def _update_preview(self, final_point):
        if not self.target_items or not self.base_point: return
        cx, cy = self.base_point.x(), self.base_point.y()
        angle = math.degrees(math.atan2(final_point.y() - cy, final_point.x() - cx))
        
        if not self.ghost_items:
            pen = QPen(QColor(255, 165, 0, 150), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            for item in self.target_items:
                ghost = QGraphicsLineItem() if isinstance(item, SmartLineItem) else QGraphicsPolygonItem()
                ghost.setPen(pen)
                self.canvas.scene().addItem(ghost)
                self.ghost_items.append({'item': item, 'ghost': ghost})
                
        for data in self.ghost_items:
            item, ghost = data['item'], data['ghost']
            new_c = [self._rotate_point(x, y, cx, cy, angle) for x, y in item.coords]
            if isinstance(item, SmartLineItem):
                ghost.setLine(QLineF(new_c[0][0], new_c[0][1], new_c[1][0], new_c[1][1]))
            else:
                ghost.setPolygon(QPolygonF([QPointF(x, y) for x, y in new_c]))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                # 点击选择对象
                raw_point = self.canvas.mapToScene(event.pos())
                item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
                
                if isinstance(item, (SmartLineItem, SmartPolygonItem)):
                    # 点选单个对象
                    if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        # 不按 Shift，清空之前的选择
                        for old_item in self.target_items:
                            old_item.setSelected(False)
                        self.target_items.clear()
                    
                    if item not in self.target_items:
                        self.target_items.append(item)
                        item.setSelected(True)
                    self.canvas.viewport().update()
                else:
                    # 开始框选
                    self.start_point = raw_point
                    if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        # 不按 Shift，清空之前的选择
                        for old_item in self.target_items:
                            old_item.setSelected(False)
                        self.target_items.clear()
                    
                    self.selection_box = QGraphicsRectItem()
                    pen = QPen(QColor(0, 120, 215), 1)
                    pen.setCosmetic(True)
                    self.selection_box.setPen(pen)
                    self.selection_box.setBrush(QBrush(QColor(0, 120, 215, 40)))
                    self.selection_box.setZValue(5000)
                    self.canvas.scene().addItem(self.selection_box)
                    
            elif self.state == 1:
                self.base_point = final_point
                self.state = 2
            elif self.state == 2:
                angle = math.degrees(math.atan2(final_point.y() - self.base_point.y(), final_point.x() - self.base_point.x()))
                self._execute_rotate(angle)
                
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state == 2: 
                self.deactivate()
                self.canvas.switch_tool("选择")
            elif self.state == 1:
                self.state = 0
                for item in self.target_items:
                    item.setSelected(False)
                self.target_items.clear()
                
        self._update_hud()
        return True

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self._update_hud()
        
        # 框选预览
        if self.start_point and self.selection_box:
            raw_point = self.canvas.mapToScene(event.pos())
            x = min(self.start_point.x(), raw_point.x())
            y = min(self.start_point.y(), raw_point.y())
            w = abs(self.start_point.x() - raw_point.x())
            h = abs(self.start_point.y() - raw_point.y())
            self.selection_box.setRect(x, y, w, h)
            
            # 窗选/交叉选择样式
            color = QColor(0, 120, 215) if raw_point.x() > self.start_point.x() else QColor(76, 175, 80)
            pen = QPen(color, 1, Qt.PenStyle.SolidLine if raw_point.x() > self.start_point.x() else Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
        
        if self.state == 2:
            self._update_preview(final_point)
        return True

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        # 完成框选
        if event.button() == Qt.MouseButton.LeftButton and self.start_point and self.selection_box:
            raw_point = self.canvas.mapToScene(event.pos())
            rect = self.selection_box.rect()
            if rect.width() > 0 and rect.height() > 0:
                mode = Qt.ItemSelectionMode.ContainsItemShape if raw_point.x() > self.start_point.x() else Qt.ItemSelectionMode.IntersectsItemShape
                for item in self.canvas.scene().items(rect, mode):
                    if isinstance(item, (SmartLineItem, SmartPolygonItem)) and item not in self.target_items:
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
        elif event.key() == Qt.Key.Key_Backspace: 
            self.input_buffer = self.input_buffer[:-1]
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.state == 0 and self.target_items:
                # 选完对象，回车进入下一步
                self.state = 1
            elif self.state == 2 and self.input_buffer:
                self._execute_rotate(float(self.input_buffer))
        elif event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
        self._update_hud()
        return True

    def _execute_rotate(self, angle_deg):
        cx, cy = self.base_point.x(), self.base_point.y()
        rotate_data = []
        for item in self.target_items:
            old_c = list(item.coords)
            new_c = [self._rotate_point(x, y, cx, cy, angle_deg) for x, y in old_c]
            rotate_data.append((item, old_c, new_c))
            
        if rotate_data:
            self.canvas.undo_stack.push(CommandRotateGeom(rotate_data))
            
        self.deactivate()
        self.canvas.switch_tool("选择")