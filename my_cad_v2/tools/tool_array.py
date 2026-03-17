# tools/tool_array.py
import math
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtGui import QUndoCommand, QTransform
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QGraphicsView, QLineEdit
from core.core_items import (SmartLineItem, SmartPolygonItem, SmartPolylineItem, 
                             SmartArcItem, SmartCircleItem, SmartEllipseItem, SmartSplineItem)

def _create_transformed_item(item, dx, dy, angle, cx, cy):
    transform = QTransform()
    if angle != 0:
        transform.translate(cx, cy)
        transform.rotate(-angle) 
        transform.translate(-cx, -cy)
    transform.translate(dx, dy)

    def map_pt(x, y):
        p = transform.map(QPointF(x, y))
        return p.x(), p.y()

    new_item = None
    try:
        if isinstance(item, SmartLineItem):
            p1 = map_pt(*item.coords[0])
            p2 = map_pt(*item.coords[1])
            new_item = SmartLineItem(p1, p2)
        elif isinstance(item, SmartPolygonItem):
            nc = [map_pt(x, y) for x, y in item.coords]
            new_item = SmartPolygonItem(nc)
        elif isinstance(item, SmartPolylineItem):
            nc = [map_pt(x, y) for x, y in item.coords]
            new_item = SmartPolylineItem(nc)
            if hasattr(item, 'segments'): new_item.segments = list(item.segments)
        elif isinstance(item, SmartArcItem):
            ccx, ccy = map_pt(*item.center)
            n_start = (item.start_angle + angle) % 360
            n_end = (item.end_angle + angle) % 360
            new_item = SmartArcItem((ccx, ccy), item.radius, n_start, n_end)
        elif isinstance(item, SmartCircleItem):
            ccx, ccy = map_pt(*item.center)
            new_item = SmartCircleItem((ccx, ccy), item.radius)
        elif isinstance(item, SmartEllipseItem):
            ccx, ccy = map_pt(*item.center)
            n_rot = (getattr(item, 'rotation_angle', 0) + angle) % 360
            new_item = SmartEllipseItem((ccx, ccy), item.rx, item.ry, n_rot)
        elif isinstance(item, SmartSplineItem):
            nc = [map_pt(x, y) for x, y in item.coords]
            new_item = SmartSplineItem(nc)
        
        if new_item:
            if hasattr(item, 'pen'): new_item.setPen(item.pen())
            if hasattr(item, 'brush') and hasattr(new_item, 'setBrush'): new_item.setBrush(item.brush())
    except Exception:
        pass
    return new_item

class CommandArrayItems(QUndoCommand):
    def __init__(self, scene, original_items, array_type, **kwargs):
        super().__init__()
        self.scene = scene
        self.original_items = original_items
        self.array_type = array_type
        self.kwargs = kwargs
        self.created_items = []
        self._create_array()

    def _create_array(self):
        if self.array_type == 'R': 
            rows = self.kwargs.get('rows', 1)
            cols = self.kwargs.get('cols', 1)
            dx = self.kwargs.get('dx', 0)
            dy = self.kwargs.get('dy', 0)

            for r in range(rows):
                for c in range(cols):
                    if r == 0 and c == 0: continue 
                    for item in self.original_items:
                        new_item = _create_transformed_item(item, c * dx, r * dy, 0, 0, 0)
                        if new_item: self.created_items.append(new_item)

        elif self.array_type == 'P': 
            num_items = self.kwargs.get('num_items', 1)
            fill_angle = self.kwargs.get('fill_angle', 360.0)
            center = self.kwargs.get('center_point', QPointF(0,0))
            cx, cy = center.x(), center.y()

            if num_items > 1:
                if abs(abs(fill_angle) - 360.0) < 1e-5: step_angle = fill_angle / num_items
                else: step_angle = fill_angle / (num_items - 1)
            else: step_angle = 0

            for i in range(1, num_items):
                angle = i * step_angle
                for item in self.original_items:
                    new_item = _create_transformed_item(item, 0, 0, angle, cx, cy)
                    if new_item: self.created_items.append(new_item)

    def redo(self):
        for item in self.original_items:
            if item.scene() == self.scene: item.setSelected(False)
        for item in self.created_items:
            if item not in self.scene.items(): self.scene.addItem(item)

    def undo(self):
        for item in self.created_items:
            if item.scene() == self.scene: self.scene.removeItem(item)
        for item in self.original_items:
            if item not in self.scene.items(): self.scene.addItem(item)
            item.setSelected(True)


class ArrayTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.selected_items = []
        self.ghost_items = []
        self.array_type = ''
        
        self.rows, self.cols = 1, 1
        self.base_point = None
        self.num_items, self.fill_angle = 6, 360.0
        self.center_point = None
        
        # 【核心新增】：在画布上挂载一个真实的原生 Qt 输入框
        self.input_box = QLineEdit(self.canvas.viewport())
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b; color: #00ff00; 
                border: 2px solid #0055ff; border-radius: 4px; 
                padding: 4px; font-size: 14px; font-weight: bold;
            }
        """)
        self.input_box.returnPressed.connect(self._on_input_enter)
        self.input_box.hide()

    def _show_input(self, placeholder_text):
        """让输入框在画布右上角浮现"""
        w = self.canvas.viewport().width()
        self.input_box.setGeometry(w - 280, 20, 260, 40)
        self.input_box.clear()
        self.input_box.setPlaceholderText(placeholder_text)
        self.input_box.show()
        self.input_box.setFocus()

    def activate(self):
        self.state = 0
        self.base_point, self.center_point = None, None
        self._clear_ghosts()
        self.input_box.hide()
        
        self.selected_items = self.canvas.scene().selectedItems()
        if self.selected_items:
            self.state = 1  
            self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.canvas.hud_polar_info.setHtml("<div style='background:#0055ff;color:white;padding:4px;'>✅ 图形已就绪，请在右上方输入框内操作</div>")
            self.canvas.hud_polar_info.show()
            self._show_input("输入阵列类型: R(矩形) 或 P(环形)")
        else:
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:4px;'>请用鼠标 <b>框选</b> 要阵列的图形 (松开鼠标自动确认)</div>")
            self.canvas.hud_polar_info.show()
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self): 
        self.canvas.hud_polar_info.hide()
        self.input_box.hide()
        self._clear_ghosts()
        self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _clear_ghosts(self):
        for data in self.ghost_items:
            ghost = data[0]
            if ghost.scene() == self.canvas.scene(): self.canvas.scene().removeItem(ghost)
        self.ghost_items.clear()

    def _check_auto_advance(self):
        """松开鼠标自动检测框选，跳过按回车的麻烦"""
        if self.state == 0:
            self.selected_items = self.canvas.scene().selectedItems()
            if self.selected_items:
                self.state = 1
                self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.canvas.hud_polar_info.setHtml("<div style='background:#0055ff;color:white;padding:4px;'>✅ 选取成功！请看右上角输入框</div>")
                self.canvas.hud_polar_info.show()
                self._show_input("输入阵列类型: R(矩形) 或 P(环形)")

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            QTimer.singleShot(50, self._check_auto_advance)
            return False
        return False

    def _on_input_enter(self):
        """处理真实输入框的回车事件"""
        text = self.input_box.text().strip().upper()
        
        if self.state == 1:
            if text == 'R':
                self.array_type = 'R'
                self.state = 2
                self._show_input("输入 行数,列数 (例如: 3,4)")
            elif text == 'P':
                self.array_type = 'P'
                self.state = 10
                self.input_box.hide()
                self.canvas.hud_polar_info.setHtml("<div style='background:#0055ff;color:white;padding:4px;'>请在画布上点击指定 <b>旋转中心点</b></div>")
            else:
                self.input_box.clear()
                self.input_box.setPlaceholderText("❌ 无效！请输入字母 R 或 P")
                
        elif self.state == 2:
            clean_text = text.replace('，', ',')
            parts = clean_text.split(',')
            if len(parts) == 2:
                try:
                    self.rows = max(1, int(parts[0]))
                    self.cols = max(1, int(parts[1]))
                    self.state = 3
                    self.input_box.hide()
                    self.canvas.hud_polar_info.setHtml("<div style='background:#0055ff;color:white;padding:4px;'>请在画布上点击一下，指定 <b>阵列基点</b></div>")
                except ValueError:
                    self.input_box.clear()
                    self.input_box.setPlaceholderText("❌ 格式错！请输入数字如 3,4")
            else:
                self.input_box.clear()
                self.input_box.setPlaceholderText("❌ 格式错！必须包含逗号")
                
        elif self.state == 4:
            clean_text = text.replace('，', ',')
            parts = clean_text.split(',')
            try:
                if len(parts) == 2: dx, dy = float(parts[0]), float(parts[1])
                else: dx = dy = float(parts[0])
                cmd = CommandArrayItems(self.canvas.scene(), self.selected_items, 'R', rows=self.rows, cols=self.cols, dx=dx, dy=dy)
                self.canvas.undo_stack.push(cmd)
                self.activate()
            except ValueError:
                self.input_box.clear()
                self.input_box.setPlaceholderText("❌ 格式错！请输入偏移数值")

        elif self.state == 11:
            try: self.num_items = max(2, int(text))
            except: self.num_items = 6
            self.state = 12
            self._init_polar_ghosts()
            self._update_polar_ghosts(360.0)
            self._show_input("输入 填充角度 (如: 360)")
            
        elif self.state == 12:
            try: self.fill_angle = float(text) if text else 360.0
            except: self.fill_angle = 360.0
            cmd = CommandArrayItems(self.canvas.scene(), self.selected_items, 'P', num_items=self.num_items, fill_angle=self.fill_angle, center_point=self.center_point)
            self.canvas.undo_stack.push(cmd)
            self.activate()

    def mousePressEvent(self, event, final_point, snapped_angle):
        if self.state == 0: return False 
        if event.button() != Qt.MouseButton.LeftButton: 
            self.activate(); return True

        if self.state == 3:
            self.base_point = final_point
            self.state = 4
            self._init_rect_ghosts()
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:4px;'>拖动鼠标预览，满意后 <b>点击左键确认</b> (也可在右上角输入框精准指定距离)</div>")
            self._show_input("输入 X间距,Y间距 (如: 100,50)")
            return True
        elif self.state == 4:
            # 鼠标直接点击确认偏移距离
            dx = final_point.x() - self.base_point.x(); dy = final_point.y() - self.base_point.y()
            cmd = CommandArrayItems(self.canvas.scene(), self.selected_items, 'R', rows=self.rows, cols=self.cols, dx=dx, dy=dy)
            self.canvas.undo_stack.push(cmd)
            self.activate()
            return True
        elif self.state == 10:
            self.center_point = final_point
            self.state = 11
            self._show_input("输入 总数量 (例如: 6)")
            return True
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.state == 4 and self.base_point:
            dx = final_point.x() - self.base_point.x(); dy = final_point.y() - self.base_point.y()
            self._update_rect_ghosts(dx, dy)
            return True
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.activate()
            return True
        return False

    def _init_rect_ghosts(self):
        self._clear_ghosts()
        for r in range(self.rows):
            for c in range(self.cols):
                if r == 0 and c == 0: continue
                for item in self.selected_items:
                    ghost = _create_transformed_item(item, 0, 0, 0, 0, 0)
                    if ghost:
                        ghost.is_smart_shape = False
                        ghost.setOpacity(0.4)
                        ghost.setZValue(9000)
                        self.canvas.scene().addItem(ghost)
                        self.ghost_items.append((ghost, r, c))

    def _update_rect_ghosts(self, dx, dy):
        for ghost, r, c in self.ghost_items:
            ghost.setPos(c * dx, r * dy)

    def _init_polar_ghosts(self):
        self._clear_ghosts()
        for i in range(1, self.num_items):
            for item in self.selected_items:
                ghost = _create_transformed_item(item, 0, 0, 0, 0, 0)
                if ghost:
                    ghost.is_smart_shape = False
                    ghost.setOpacity(0.4)
                    ghost.setZValue(9000)
                    self.canvas.scene().addItem(ghost)
                    self.ghost_items.append((ghost, i))

    def _update_polar_ghosts(self, fill_angle):
        if self.num_items > 1:
            step_angle = fill_angle / self.num_items if abs(abs(fill_angle)-360)<1e-5 else fill_angle / (self.num_items - 1)
        else: step_angle = 0
            
        cx, cy = self.center_point.x(), self.center_point.y()
        for ghost, i in self.ghost_items:
            angle = i * step_angle
            transform = QTransform()
            transform.translate(cx, cy)
            transform.rotate(-angle)
            transform.translate(-cx, -cy)
            ghost.setTransform(transform)