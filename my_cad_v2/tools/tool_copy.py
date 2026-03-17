# tools/tool_copy.py
import math
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QGraphicsView
from core.core_items import (SmartLineItem, SmartPolygonItem, SmartPolylineItem, 
                             SmartArcItem, SmartCircleItem, SmartEllipseItem, SmartSplineItem, SmartBlockReference)

class CommandCopyItems(QUndoCommand):
    """撤销/重做栈支持的复制命令"""
    def __init__(self, scene, original_items, dx, dy):
        super().__init__()
        self.scene = scene
        self.original_items = original_items
        self.dx = dx
        self.dy = dy
        self.cloned_items = []
        self._create_clones()

    def _create_clones(self):
        """核心复制引擎：深度克隆图元，并将其绝对坐标平移 dx, dy"""
        for item in self.original_items:
            try:
                new_item = None
                if isinstance(item, SmartLineItem):
                    new_item = SmartLineItem((item.coords[0][0]+self.dx, item.coords[0][1]+self.dy),
                                             (item.coords[1][0]+self.dx, item.coords[1][1]+self.dy))
                elif isinstance(item, SmartPolygonItem):
                    new_item = SmartPolygonItem([(x+self.dx, y+self.dy) for x, y in item.coords])
                elif isinstance(item, SmartPolylineItem):
                    new_item = SmartPolylineItem([(x+self.dx, y+self.dy) for x, y in item.coords])
                    if hasattr(item, 'segments'): new_item.segments = list(item.segments)
                elif isinstance(item, SmartArcItem):
                    cx, cy = item.center
                    new_item = SmartArcItem((cx+self.dx, cy+self.dy), item.radius, item.start_angle, item.end_angle)
                elif isinstance(item, SmartCircleItem):
                    cx, cy = item.center
                    new_item = SmartCircleItem((cx+self.dx, cy+self.dy), item.radius)
                elif isinstance(item, SmartEllipseItem):
                    cx, cy = item.center
                    new_item = SmartEllipseItem((cx+self.dx, cy+self.dy), item.rx, item.ry)
                elif isinstance(item, SmartSplineItem):
                    new_item = SmartSplineItem([(x+self.dx, y+self.dy) for x, y in item.coords])
                elif isinstance(item, SmartBlockReference):
                    # 复制投影仪，并加上鼠标移动的偏移量！
                    new_item = SmartBlockReference(item.block_name)
                    new_item.setPos(item.x() + self.dx, item.y() + self.dy)
                
                if new_item:
                    # 完美继承原有画笔和笔刷属性
                    if hasattr(item, 'pen'): new_item.setPen(item.pen())
                    if hasattr(item, 'brush') and hasattr(new_item, 'setBrush'): new_item.setBrush(item.brush())
                    self.cloned_items.append(new_item)
            except Exception as e:
                pass # 忽略未知或无法克隆的图元

    def redo(self):
        for item in self.cloned_items:
            if item not in self.scene.items():
                self.scene.addItem(item)
                item.setSelected(True) # 复制出的新对象保持选中状态

    def undo(self):
        for item in self.cloned_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)


class CopyTool(BaseTool):
    """V2.0 精准复制工具 (支持先选/后选、橡皮筋框选、极轴输入、基点游离)"""
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.selected_items = []
        self.ghost_items = []
        self.base_point = None
        self.last_snapped_point = None
        
        self.input_buffer = ""
        self.is_first_input = True 

        # 独立悬浮输入框，用于输入移动距离
        self.local_hud = QGraphicsTextItem()
        self.local_hud.setZValue(9999)
        self.local_hud.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.canvas.scene().addItem(self.local_hud)
        self.local_hud.hide()

    def activate(self):
        self.base_point = None
        self.input_buffer = ""
        self.is_first_input = True
        self.last_snapped_point = None
        self._clear_ghosts()
        self.local_hud.hide()
        
        # 智能判断：如果激活工具时已经选中了图形，直接跳过框选阶段
        self.selected_items = self.canvas.scene().selectedItems()
        if self.selected_items:
            self.state = 1  
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>精准复制: 请指定基点 (Base Point)</div>")
            self.canvas.hud_polar_info.show()
            self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            self.state = 0  # 没有选中，进入后选模式
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>请点选或框选要复制的图形，完成后按【回车键】确认</div>")
            self.canvas.hud_polar_info.show()
            # 开启底层画板的橡皮筋框选模式
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self): 
        self.canvas.hud_polar_info.hide()
        self.local_hud.hide()
        self._clear_ghosts()
        # 退出工具时必须恢复画板的拖拽状态
        self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _clear_ghosts(self):
        for ghost in self.ghost_items:
            if ghost.scene() == self.canvas.scene():
                self.canvas.scene().removeItem(ghost)
        self.ghost_items.clear()

    def _create_ghosts(self):
        """生成跟随鼠标的虚影，不写入撤销栈，仅供视觉预览"""
        cmd = CommandCopyItems(self.canvas.scene(), self.selected_items, 0, 0)
        for ghost in cmd.cloned_items:
            ghost.is_smart_shape = False # 彻底关闭虚影捕捉，防止遮盖真实端点
            ghost.setOpacity(0.4) 
            ghost.setZValue(9000)
            self.canvas.scene().addItem(ghost)
            self.ghost_items.append(ghost)

    def get_reference_point(self):
        """告诉底层画板，极轴追踪的原点在哪里"""
        if self.state == 2 and self.base_point:
            return self.base_point
        return None

    def _update_hud(self, point):
        if self.state != 2 or not self.base_point: return
        dx = point.x() - self.base_point.x()
        dy = point.y() - self.base_point.y()
        current_dist = math.hypot(dx, dy)
        display_text = f"L: {self.input_buffer}" if self.input_buffer else f"L: {current_dist:.2f}"
        lod = self.canvas.transform().m11()
        self.local_hud.setHtml(f"<div style='background-color:#0055ff; color:white; padding:2px 4px; border:1px solid #777; font-family:Arial; font-size:12px; text-align:center;'>{display_text}</div>")
        self.local_hud.setPos(point.x() + 15/lod, point.y() + 15/lod)
        self.local_hud.show()

    def mousePressEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            return False # 返回 False，把鼠标事件全权交给画板原生逻辑，实现框选/点选

        if event.button() != Qt.MouseButton.LeftButton: 
            self.activate() 
            return True

        if self.state == 1:
            # 第一步：锁定基点
            self.base_point = final_point
            self._create_ghosts() 
            self.state = 2
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>精准复制: 请指定目标点，或往极轴方向拉并输入距离</div>")
            return True
        
        elif self.state == 2:
            # 第二步：鼠标点击盖章
            dx = final_point.x() - self.base_point.x()
            dy = final_point.y() - self.base_point.y()
            
            for item in self.canvas.scene().selectedItems(): item.setSelected(False)
            cmd = CommandCopyItems(self.canvas.scene(), self.selected_items, dx, dy)
            self.canvas.undo_stack.push(cmd)
            
            # 鼠标连续点击：不更新母版和基点，实现无限印章
            self.input_buffer = ""
            self.is_first_input = True
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>已复制！可继续点击盖章，或按 Esc 退出</div>")
            self._update_hud(final_point)
            return True
                
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            return False

        if self.state == 2 and self.base_point:
            self.last_snapped_point = final_point
            dx = final_point.x() - self.base_point.x()
            dy = final_point.y() - self.base_point.y()
            for ghost in self.ghost_items:
                ghost.setPos(dx, dy)
            self._update_hud(final_point)
            return True
        return False

    def keyPressEvent(self, event):
        if self.state == 0:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.selected_items = self.canvas.scene().selectedItems()
                if not self.selected_items:
                    self.canvas.hud_polar_info.setHtml("<div style='background:#ff4444;color:white;padding:2px;'>未选择任何图形！请框选后按回车</div>")
                else:
                    self.state = 1
                    self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag) # 选完立刻关闭框选模式
                    self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>精准复制: 请指定基点 (Base Point)</div>")
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self.activate()
                return True
            return False

        elif self.state == 2:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                try: 
                    if self.input_buffer:
                        dist = float(self.input_buffer)
                        target_pt = getattr(self, 'last_snapped_point', self.canvas.last_cursor_point)
                        if not target_pt: target_pt = self.canvas.last_cursor_point
                        
                        angle = math.atan2(target_pt.y() - self.base_point.y(), 
                                           target_pt.x() - self.base_point.x())
                        
                        dx = dist * math.cos(angle)
                        dy = dist * math.sin(angle)
                        
                        for item in self.canvas.scene().selectedItems(): item.setSelected(False)
                        cmd = CommandCopyItems(self.canvas.scene(), self.selected_items, dx, dy)
                        self.canvas.undo_stack.push(cmd)
                        
                        # 键盘输入模式：推进母版和基点，实现等距平推
                        self.selected_items = cmd.cloned_items
                        self.base_point = QPointF(self.base_point.x() + dx, self.base_point.y() + dy)
                        
                        self._clear_ghosts()
                        self._create_ghosts()
                        
                        self.input_buffer = ""
                        self.is_first_input = True
                        self._update_hud(self.canvas.last_cursor_point)
                except ValueError: 
                    pass
                return True
                
            elif event.key() == Qt.Key.Key_Backspace: 
                self.is_first_input = False 
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud(self.canvas.last_cursor_point)
                return True
                
            elif event.text().replace('.', '', 1).isdigit(): 
                if self.is_first_input:
                    self.input_buffer = ""
                    self.is_first_input = False
                self.input_buffer += event.text()
                self._update_hud(self.canvas.last_cursor_point)
                return True
                
            elif event.key() == Qt.Key.Key_Escape:
                self.activate() 
                return True
                
        elif self.state == 1:
            if event.key() == Qt.Key.Key_Escape:
                self.activate()
                return True

        return False