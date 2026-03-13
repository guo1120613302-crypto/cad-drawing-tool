# tools/tool_move.py
import traceback
import math
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF, QCursor

class CommandMoveGeom(QUndoCommand):
    def __init__(self, move_data):
        super().__init__()
        self.move_data = move_data  # 格式: [(item, old_coords, new_coords)]
    def redo(self):
        for item, _, new_c in self.move_data:
            if item.scene(): item.set_coords(new_c)
    def undo(self):
        for item, old_c, _ in self.move_data:
            if item.scene(): item.set_coords(old_c)

class MoveTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_items = []
        self.base_point = None
        self.input_buffer = ""
        self.ghost_items = []
        # 状态机：0=选对象, 1=定基点, 2=定目标点
        self.state = 0 

    def get_reference_point(self):
        # 移动时，极轴追踪的参考点就是我们点下的“基点”
        return self.base_point if self.state == 2 else None

    def get_input_buffer(self): return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.input_buffer = ""
        self.base_point = None
        self._cleanup_ghosts()
        
        # 智能判断：如果激活工具时画布上已经有选中的东西，直接跳到状态1
        selected = self.canvas.scene().selectedItems()
        self.target_items = [item for item in selected if isinstance(item, (SmartLineItem, SmartPolygonItem))]
        
        if self.target_items:
            self.state = 1
        else:
            self.state = 0
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghosts()
        for item in self.target_items:
            item.setSelected(False)
        self.target_items.clear()
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghosts(self):
        for ghost in self.ghost_items:
            if ghost.scene(): self.canvas.scene().removeItem(ghost)
        self.ghost_items.clear()

    def _update_hud(self):
        try:
            if not hasattr(self.canvas, 'hud_polar_info'): return
            self.canvas.hud_polar_info.show()
            if self.state == 0:
                text = "请选择要移动的对象 (选完按右键或回车确认)"
                color = "#5bc0de" 
            elif self.state == 1:
                text = "请指定移动的【基点】"
                color = "#f0ad4e" 
            elif self.state == 2:
                text = f"指定第二个点或输入距离: {self.input_buffer}"
                color = "#5cb85c" 
                
            self.canvas.hud_polar_info.setHtml(
                f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>{text}</div>"
            )
            pos = self.canvas.mapToScene(20, 20)
            self.canvas.hud_polar_info.setPos(pos)
        except: pass

    def _update_preview(self, target_point):
        """独立的预览计算，彻底防崩溃"""
        if not self.target_items or not self.base_point: return
        try:
            dx = target_point.x() - self.base_point.x()
            dy = target_point.y() - self.base_point.y()
            
            # 如果幽灵实体还没创建，先创建它们
            if not self.ghost_items:
                pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                for item in self.target_items:
                    if isinstance(item, SmartLineItem):
                        ghost = QGraphicsLineItem()
                        ghost.setPen(pen)
                        self.canvas.scene().addItem(ghost)
                        self.ghost_items.append({'item': item, 'ghost': ghost, 'type': 'line'})
                    elif isinstance(item, SmartPolygonItem):
                        ghost = QGraphicsPolygonItem()
                        ghost.setPen(pen)
                        self.canvas.scene().addItem(ghost)
                        self.ghost_items.append({'item': item, 'ghost': ghost, 'type': 'poly'})

            # 更新幽灵实体的坐标
            for data in self.ghost_items:
                item = data['item']
                ghost = data['ghost']
                if data['type'] == 'line':
                    old_c = item.coords
                    new_x1, new_y1 = old_c[0][0] + dx, old_c[0][1] + dy
                    new_x2, new_y2 = old_c[1][0] + dx, old_c[1][1] + dy
                    ghost.setLine(QLineF(new_x1, new_y1, new_x2, new_y2))
                elif data['type'] == 'poly':
                    old_c = item.coords
                    poly_f = QPolygonF()
                    for x, y in old_c:
                        poly_f.append(QPointF(x + dx, y + dy))
                    ghost.setPolygon(poly_f)
        except Exception as e:
            print("【移动预览拦截】:", e)

    def mousePressEvent(self, event, final_point, snapped_angle):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                if self.state == 0:
                    # 点选增加对象
                    item = self.canvas.scene().itemAt(final_point, self.canvas.transform())
                    if isinstance(item, (SmartLineItem, SmartPolygonItem)):
                        if item not in self.target_items:
                            self.target_items.append(item)
                            item.setSelected(True)
                    self._update_hud()
                    return True
                    
                elif self.state == 1:
                    # 确定基点
                    self.base_point = final_point
                    self.state = 2
                    self._update_hud()
                    return True

                elif self.state == 2:
                    # 确定落点，执行移动
                    self._finalize_move(final_point)
                    return True
                    
            elif event.button() == Qt.MouseButton.RightButton:
                if self.state == 0 and self.target_items:
                    # 选完对象后，右键确认进入下一步
                    self.state = 1
                elif self.state == 2:
                    self._cleanup_ghosts()
                    self.state = 1
                elif self.state == 1:
                    self.state = 0
                    for item in self.target_items: item.setSelected(False)
                    self.target_items.clear()
                else:
                    self.deactivate()
                    self.canvas.switch_tool("选择")
                self._update_hud()
                return True
        except Exception as e:
            print("【移动点击拦截】:", e)
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        try:
            self._update_hud()
            if self.state == 2 and self.base_point:
                self._update_preview(final_point)
            return True
        except Exception as e:
            print("【移动预览拦截】:", e)
        return False

    def keyPressEvent(self, event):
        try:
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
                            dist = float(self.input_buffer)
                            # 根据极轴角度计算绝对落点
                            rad = math.radians(getattr(self.canvas, 'last_snapped_angle', 0.0))
                            hud_info = self.canvas.hud_polar_info.toPlainText() if self.canvas.hud_polar_info else ""
                            if "极轴" in hud_info:
                                try: rad = math.radians(float(hud_info.split("<")[1].split("°")[0].strip()))
                                except: pass
                                
                            new_x = self.base_point.x() + dist * math.cos(rad)
                            new_y = self.base_point.y() - dist * math.sin(rad)
                            self._finalize_move(QPointF(new_x, new_y))
                        except ValueError: pass
                    else:
                        safe_point = getattr(self.canvas, 'last_cursor_point', QPointF(0,0))
                        self._finalize_move(safe_point)
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self.deactivate()
                self.canvas.switch_tool("选择")
                return True
        except Exception as e:
            print("【移动键盘拦截】:", e)
        return False

    def _finalize_move(self, target_point):
        try:
            if not self.target_items or not self.base_point: return
            
            dx = target_point.x() - self.base_point.x()
            dy = target_point.y() - self.base_point.y()
            
            move_data = []
            for item in self.target_items:
                old_c = list(item.coords)
                new_c = [(x + dx, y + dy) for x, y in old_c]
                move_data.append((item, old_c, new_c))
                
            if move_data:
                self.canvas.undo_stack.push(CommandMoveGeom(move_data))
                
            self.deactivate()
            self.canvas.switch_tool("选择")
        except Exception as e:
            print("【执行移动拦截】:", e)