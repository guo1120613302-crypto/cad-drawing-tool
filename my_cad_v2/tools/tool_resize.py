# tools/tool_resize.py
import math
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QUndoCommand, QTransform
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QGraphicsView
from core.core_items import (SmartLineItem, SmartPolygonItem, SmartPolylineItem, 
                             SmartArcItem, SmartCircleItem, SmartEllipseItem, SmartSplineItem)

class CommandResizeItems(QUndoCommand):
    """撤销/重做栈支持的比例缩放命令：物理重算底层几何坐标"""
    def __init__(self, scene, old_items, base_point, scale_factor):
        super().__init__()
        self.scene = scene
        self.old_items = old_items
        self.bp = base_point
        self.sf = scale_factor
        self.new_items = []
        self._create_scaled_items()

    def _create_scaled_items(self):
        bx, by = self.bp.x(), self.bp.y()
        s = self.sf
        
        for item in self.old_items:
            try:
                new_item = None
                if isinstance(item, SmartLineItem):
                    p1 = (bx + (item.coords[0][0] - bx) * s, by + (item.coords[0][1] - by) * s)
                    p2 = (bx + (item.coords[1][0] - bx) * s, by + (item.coords[1][1] - by) * s)
                    new_item = SmartLineItem(p1, p2)
                elif isinstance(item, SmartPolygonItem):
                    nc = [(bx + (x - bx) * s, by + (y - by) * s) for x, y in item.coords]
                    new_item = SmartPolygonItem(nc)
                elif isinstance(item, SmartPolylineItem):
                    nc = [(bx + (x - bx) * s, by + (y - by) * s) for x, y in item.coords]
                    new_item = SmartPolylineItem(nc)
                    if hasattr(item, 'segments'): new_item.segments = list(item.segments)
                elif isinstance(item, SmartArcItem):
                    cx, cy = item.center
                    new_center = (bx + (cx - bx) * s, by + (cy - by) * s)
                    new_item = SmartArcItem(new_center, item.radius * abs(s), item.start_angle, item.end_angle)
                elif isinstance(item, SmartCircleItem):
                    cx, cy = item.center
                    new_center = (bx + (cx - bx) * s, by + (cy - by) * s)
                    new_item = SmartCircleItem(new_center, item.radius * abs(s))
                elif isinstance(item, SmartEllipseItem):
                    cx, cy = item.center
                    new_center = (bx + (cx - bx) * s, by + (cy - by) * s)
                    new_item = SmartEllipseItem(new_center, item.rx * abs(s), item.ry * abs(s))
                elif isinstance(item, SmartSplineItem):
                    nc = [(bx + (x - bx) * s, by + (y - by) * s) for x, y in item.coords]
                    new_item = SmartSplineItem(nc)
                
                if new_item:
                    # 完美继承原有画笔和笔刷属性
                    if hasattr(item, 'pen'): new_item.setPen(item.pen())
                    if hasattr(item, 'brush') and hasattr(new_item, 'setBrush'): new_item.setBrush(item.brush())
                    self.new_items.append(new_item)
            except Exception as e:
                pass # 忽略未知或无法缩放的图元

    def redo(self):
        # 隐藏老图形，显示新图形
        for item in self.old_items:
            if item.scene() == self.scene:
                item.setSelected(False)
                self.scene.removeItem(item)
        for item in self.new_items:
            if item not in self.scene.items():
                self.scene.addItem(item)
                item.setSelected(True) 

    def undo(self):
        # 撤销时反转操作
        for item in self.new_items:
            if item.scene() == self.scene:
                item.setSelected(False)
                self.scene.removeItem(item)
        for item in self.old_items:
            if item not in self.scene.items():
                self.scene.addItem(item)
                item.setSelected(True)


class ResizeTool(BaseTool):
    """V2.0 精准比例缩放工具 (支持先选/后选、橡皮筋框选、键盘输入比例、动态预览)"""
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.selected_items = []
        self.ghost_items = []
        self.base_point = None
        
        self.input_buffer = ""
        self.is_first_input = True 

        # 独立悬浮输入框，用于输入比例因子
        self.local_hud = QGraphicsTextItem()
        self.local_hud.setZValue(9999)
        self.local_hud.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.canvas.scene().addItem(self.local_hud)
        self.local_hud.hide()

    def activate(self):
        self.base_point = None
        self.input_buffer = ""
        self.is_first_input = True
        self._clear_ghosts()
        self.local_hud.hide()
        
        # 智能判断：如果激活工具时已经选中了图形，直接跳过框选阶段
        self.selected_items = self.canvas.scene().selectedItems()
        if self.selected_items:
            self.state = 1  
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>比例缩放: 请指定基点 (Base Point)</div>")
            self.canvas.hud_polar_info.show()
            self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            self.state = 0  # 没有选中，进入后选模式
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>请点选或框选要缩放的图形，完成后按【回车键】确认</div>")
            self.canvas.hud_polar_info.show()
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def deactivate(self): 
        self.canvas.hud_polar_info.hide()
        self.local_hud.hide()
        self._clear_ghosts()
        self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _clear_ghosts(self):
        for ghost in self.ghost_items:
            if ghost.scene() == self.canvas.scene():
                self.canvas.scene().removeItem(ghost)
        self.ghost_items.clear()

    def _create_ghosts(self):
        """生成 1:1 的克隆虚影，后续鼠标移动时只通过矩阵高效缩放这个虚影"""
        cmd = CommandResizeItems(self.canvas.scene(), self.selected_items, self.base_point, 1.0)
        for ghost in cmd.new_items:
            ghost.is_smart_shape = False # 彻底关闭虚影捕捉
            ghost.setOpacity(0.4) 
            ghost.setZValue(9000)
            self.canvas.scene().addItem(ghost)
            self.ghost_items.append(ghost)

    def _update_ghosts(self, factor):
        """使用 QTransform 高效且平滑地实时缩放虚影"""
        if not self.base_point: return
        bx, by = self.base_point.x(), self.base_point.y()
        transform = QTransform()
        transform.translate(bx, by)
        transform.scale(factor, factor)
        transform.translate(-bx, -by)
        for ghost in self.ghost_items:
            ghost.setTransform(transform)

    def get_reference_point(self):
        if self.state == 2 and self.base_point:
            return self.base_point
        return None

    def _update_hud(self, point, factor):
        if self.state != 2 or not self.base_point: return
        display_text = f"比例因子: {self.input_buffer}" if self.input_buffer else f"比例: {factor:.2f} x"
        lod = self.canvas.transform().m11()
        self.local_hud.setHtml(f"<div style='background-color:#0055ff; color:white; padding:2px 4px; border:1px solid #777; font-family:Arial; font-size:12px; text-align:center;'>{display_text}</div>")
        self.local_hud.setPos(point.x() + 15/lod, point.y() + 15/lod)
        self.local_hud.show()

    def mousePressEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            return False # 移交控制权给画板进行框选

        if event.button() != Qt.MouseButton.LeftButton: 
            self.activate() 
            return True

        if self.state == 1:
            # 第一步：锁定基点
            self.base_point = final_point
            self._create_ghosts() 
            self.state = 2
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>比例缩放: 直接输入比例(如 0.5 或 2)并回车，或拖动鼠标点击确认</div>")
            return True
        
        elif self.state == 2:
            # 第二步：鼠标点击确认动态缩放
            mouse_dist = math.hypot(final_point.x() - self.base_point.x(), final_point.y() - self.base_point.y())
            factor = mouse_dist / 100.0 if mouse_dist > 0 else 1.0 # 默认将100像素作为 1倍 的参照
            
            if self.input_buffer:
                try: factor = float(self.input_buffer)
                except: factor = 1.0
                
            cmd = CommandResizeItems(self.canvas.scene(), self.selected_items, self.base_point, factor)
            self.canvas.undo_stack.push(cmd)
            
            self.activate() # 缩放是一次性操作，完成后重置工具
            return True
                
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.state == 0:
            return False

        if self.state == 2 and self.base_point:
            mouse_dist = math.hypot(final_point.x() - self.base_point.x(), final_point.y() - self.base_point.y())
            
            if self.input_buffer:
                try: factor = float(self.input_buffer)
                except: factor = 1.0
            else:
                factor = max(0.01, mouse_dist / 100.0) # 视觉参照：距离基点100单位即为原大小
                
            self._update_ghosts(factor)
            self._update_hud(final_point, factor)
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
                    self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag) 
                    self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>比例缩放: 请指定基点 (Base Point)</div>")
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self.activate()
                return True
            return False

        elif self.state == 2:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                try:
                    if self.input_buffer:
                        factor = float(self.input_buffer)
                    else:
                        mouse_dist = math.hypot(self.canvas.last_cursor_point.x() - self.base_point.x(), 
                                                self.canvas.last_cursor_point.y() - self.base_point.y())
                        factor = max(0.01, mouse_dist / 100.0)
                        
                    cmd = CommandResizeItems(self.canvas.scene(), self.selected_items, self.base_point, factor)
                    self.canvas.undo_stack.push(cmd)
                    
                    self.activate() # 应用缩放后重置工具
                except ValueError: 
                    pass
                return True
                
            elif event.key() == Qt.Key.Key_Backspace: 
                self.is_first_input = False 
                self.input_buffer = self.input_buffer[:-1]
                
                # 动态刷新预览
                factor = 1.0
                if self.input_buffer:
                    try: factor = float(self.input_buffer)
                    except: pass
                else:
                    mouse_dist = math.hypot(self.canvas.last_cursor_point.x() - self.base_point.x(), 
                                            self.canvas.last_cursor_point.y() - self.base_point.y())
                    factor = max(0.01, mouse_dist / 100.0)
                
                self._update_ghosts(factor)
                self._update_hud(self.canvas.last_cursor_point, factor)
                return True
                
            elif event.text().replace('.', '', 1).replace('-', '', 1).isdigit(): 
                if self.is_first_input:
                    self.input_buffer = ""
                    self.is_first_input = False
                self.input_buffer += event.text()
                
                # 键盘敲击过程中，虚影也会实时跟着您的数字放大缩小
                try: factor = float(self.input_buffer)
                except: factor = 1.0
                self._update_ghosts(factor)
                self._update_hud(self.canvas.last_cursor_point, factor)
                
                return True
                
            elif event.key() == Qt.Key.Key_Escape:
                self.activate() 
                return True
                
        elif self.state == 1:
            if event.key() == Qt.Key.Key_Escape:
                self.activate()
                return True

        return False