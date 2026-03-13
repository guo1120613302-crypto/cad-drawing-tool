# tools/tool_mirror.py
import traceback
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF, QBrush

class CommandMirrorGeom(QUndoCommand):
    def __init__(self, scene, items_data, layer_manager):
        super().__init__()
        self.scene = scene
        self.items_data = items_data  # [(ItemClass, coords, source_item)]
        self.layer_manager = layer_manager
        self.created_items = []
    def redo(self):
        self.created_items.clear()
        self.scene.clearSelection()
        for ItemClass, coords, source_item in self.items_data:
            item = ItemClass(coords) if ItemClass == SmartPolygonItem else ItemClass(coords[0], coords[1])
            pen = QPen(QColor(255, 255, 255), 1)
            pen.setCosmetic(True)
            item.setPen(pen)
            # 【修复】：继承源图形的图层属性
            self.layer_manager.copy_layer_props(item, source_item)
            self.scene.addItem(item)
            item.setSelected(True)
            self.created_items.append(item)
    def undo(self):
        for item in self.created_items:
            if item.scene(): self.scene.removeItem(item)

class MirrorTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_items = []
        self.axis_p1 = None
        self.ghost_items = []
        self.mirror_line = None 
        self.state = 0
        # 框选相关
        self.start_point = None
        self.selection_box = None

    def get_reference_point(self): return self.axis_p1 if self.state == 2 else None
    
    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.axis_p1 = None
        self._cleanup_ghosts()
        
        # 智能继承选中状态
        selected = self.canvas.scene().selectedItems() if self.canvas.scene() else []
        self.target_items = [i for i in selected if isinstance(i, (SmartLineItem, SmartPolygonItem))]
        
        if self.target_items:
            self.state = 1
        else:
            self.state = 0
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghosts()
        if self.selection_box:
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
        for i in self.target_items:
            i.setSelected(False)
        self.target_items.clear()

    def _cleanup_ghosts(self):
        for g in self.ghost_items:
            if g['ghost'].scene(): 
                self.canvas.scene().removeItem(g['ghost'])
        self.ghost_items.clear()
        if self.mirror_line and self.mirror_line.scene():
            self.canvas.scene().removeItem(self.mirror_line)
        self.mirror_line = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        text = "选择要镜像的对象 (框选/点选，回车确认)" if self.state==0 else "指定镜像轴【第一点】" if self.state==1 else "指定镜像轴【第二点】"
        color = "#5bc0de" if self.state==0 else "#f0ad4e" if self.state==1 else "#5cb85c"
        self.canvas.hud_polar_info.setHtml(f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>{text}</div>")
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _mirror_point(self, px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0: return px, py
        a, b, c = dy, -dx, dx * y1 - dy * x1
        temp = -2 * (a * px + b * py + c) / (a * a + b * b)
        return px + temp * a, py + temp * b

    def _update_preview(self, final_point):
        if not self.target_items or not self.axis_p1: return
        x1, y1 = self.axis_p1.x(), self.axis_p1.y()
        x2, y2 = final_point.x(), final_point.y()
        
        if not self.mirror_line:
            self.mirror_line = QGraphicsLineItem()
            pen_axis = QPen(QColor(255, 255, 0), 1, Qt.PenStyle.DashDotLine)
            pen_axis.setCosmetic(True)
            self.mirror_line.setPen(pen_axis)
            self.canvas.scene().addItem(self.mirror_line)
        self.mirror_line.setLine(QLineF(x1, y1, x2, y2))
        
        if not self.ghost_items:
            pen = QPen(QColor(255, 0, 255, 150), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            for item in self.target_items:
                ghost = QGraphicsLineItem() if isinstance(item, SmartLineItem) else QGraphicsPolygonItem()
                ghost.setPen(pen)
                self.canvas.scene().addItem(ghost)
                self.ghost_items.append({'item': item, 'ghost': ghost})
                
        for data in self.ghost_items:
            item, ghost = data['item'], data['ghost']
            new_c = [self._mirror_point(px, py, x1, y1, x2, y2) for px, py in item.coords]
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
                self.axis_p1 = final_point
                self.state = 2
            elif self.state == 2:
                self._execute_mirror(final_point)
                
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
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.state == 0 and self.target_items:
                # 选完对象，回车进入下一步
                self.state = 1
                self._update_hud()
        elif event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
        return True

    def _execute_mirror(self, axis_p2):
        x1, y1 = self.axis_p1.x(), self.axis_p1.y()
        x2, y2 = axis_p2.x(), axis_p2.y()
        items_data = []
        for item in self.target_items:
            new_c = [self._mirror_point(px, py, x1, y1, x2, y2) for px, py in item.coords]
            items_data.append((type(item), new_c, item))  # 添加源图形引用
        if items_data:
            self.canvas.undo_stack.push(CommandMirrorGeom(self.canvas.scene(), items_data, self.canvas.layer_manager))
        self.deactivate()
        self.canvas.switch_tool("选择")