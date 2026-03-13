# tools/tool_offset.py
import traceback
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF
from utils.geom_engine import GeometryEngine

class CommandCreateGeom(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__()
        self.scene = scene
        self.item = item
    def redo(self):
        if self.item.scene() != self.scene: 
            self.scene.addItem(self.item)
    def undo(self):
        if self.item.scene() == self.scene:
            self.item.setSelected(False)
            self.scene.removeItem(self.item)

class OffsetTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_item = None
        self.offset_distance = 10.0  # 历史记忆数值
        self.input_buffer = ""
        self.ghost_item = None
        self.ghost_coords = None
        self.state = 0 

    def get_reference_point(self): return None
    def get_input_buffer(self): return self.input_buffer

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.input_buffer = ""
        self.target_item = None
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghost()
        if self.target_item:
            self.target_item.setSelected(False)
        self.target_item = None
        if hasattr(self.canvas, '_cleanup_tracking_huds'):
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghost(self):
        if self.ghost_item and self.ghost_item.scene():
            self.canvas.scene().removeItem(self.ghost_item)
        self.ghost_item = None
        self.ghost_coords = None

    def _update_hud(self):
        try:
            if not hasattr(self.canvas, 'hud_polar_info'): return
            self.canvas.hud_polar_info.show()
            if self.state == 0:
                text = "请选择要偏移的对象"
                color = "#5bc0de" 
            elif self.state == 1:
                text = f"指定偏移距离 <{self.offset_distance}>: {self.input_buffer}"
                color = "#d9534f" 
            elif self.state == 2:
                text = "请在要偏移的一侧点击鼠标"
                color = "#5cb85c" 
                
            self.canvas.hud_polar_info.setHtml(
                f"<div style='background-color:{color}; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>{text}</div>"
            )
            pos = self.canvas.mapToScene(20, 20)
            self.canvas.hud_polar_info.setPos(pos)
        except Exception as e:
            pass

    def _update_preview(self, raw_point):
        """【防崩溃核心架构】：独立的纯 Python 预览逻辑，彻底隔离 Qt 虚假事件传参陷阱"""
        if not self.target_item: return
        try:
            dist = abs(float(self.offset_distance))
            
            if isinstance(self.target_item, SmartPolygonItem):
                poly_f = QPolygonF()
                for x, y in self.target_item.coords: poly_f.append(QPointF(x, y))
                is_inside = poly_f.containsPoint(raw_point, Qt.FillRule.OddEvenFill)
                
                c1 = GeometryEngine.offset_polygon(self.target_item.coords, dist)
                c2 = GeometryEngine.offset_polygon(self.target_item.coords, -dist)
                
                # 纯原生安全面积计算
                def get_a(c):
                    if not c or len(c) < 3: return 0
                    a = 0.0
                    for i in range(len(c)):
                        j = (i + 1) % len(c)
                        a += c[i][0]*c[j][1] - c[j][0]*c[i][1]
                    return abs(a / 2.0)
                    
                a1 = get_a(c1)
                a2 = get_a(c2)
                
                if a1 > a2: c_out, c_in = c1, c2
                else: c_out, c_in = c2, c1
                    
                self.ghost_coords = c_in if is_inside else c_out

                # 【修复】：检查 ghost_coords 是否为 None 且不为空
                if self.ghost_coords and len(self.ghost_coords) > 0:
                    if not self.ghost_item or not isinstance(self.ghost_item, QGraphicsPolygonItem):
                        self._cleanup_ghost()
                        self.ghost_item = QGraphicsPolygonItem()
                        pen = QPen(QColor(0, 255, 0), 1, Qt.PenStyle.DashLine)
                        pen.setCosmetic(True)
                        self.ghost_item.setPen(pen)
                        self.canvas.scene().addItem(self.ghost_item)
                    
                    poly_f2 = QPolygonF()
                    for x, y in self.ghost_coords: poly_f2.append(QPointF(x, y))
                    self.ghost_item.setPolygon(poly_f2)
                else:
                    # 如果偏移失败，清理幽灵图形
                    self._cleanup_ghost()
                    
            elif isinstance(self.target_item, SmartLineItem):
                self.ghost_coords = GeometryEngine.offset_line(
                    self.target_item.coords, dist, (raw_point.x(), raw_point.y())
                )
                
                # 【修复】：检查 ghost_coords 是否为 None 且长度正确
                if self.ghost_coords and len(self.ghost_coords) == 2:
                    if not self.ghost_item or not isinstance(self.ghost_item, QGraphicsLineItem):
                        self._cleanup_ghost()
                        self.ghost_item = QGraphicsLineItem()
                        pen = QPen(QColor(0, 255, 0), 1, Qt.PenStyle.DashLine)
                        pen.setCosmetic(True)
                        self.ghost_item.setPen(pen)
                        self.canvas.scene().addItem(self.ghost_item)
                        
                    (x1, y1), (x2, y2) = self.ghost_coords
                    self.ghost_item.setLine(QLineF(x1, y1, x2, y2))
                else:
                    # 如果偏移失败，清理幽灵图形
                    self._cleanup_ghost()
        except Exception as e:
            print("【预览刷新异常，已被安全拦截】:")
            traceback.print_exc()

    def mousePressEvent(self, event, final_point, snapped_angle):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                if self.state == 0:
                    item = self.canvas.scene().itemAt(final_point, self.canvas.transform())
                    if isinstance(item, (SmartLineItem, SmartPolygonItem)):
                        self.target_item = item
                        self.canvas.scene().clearSelection()
                        self.target_item.setSelected(True)
                        self.state = 1  
                        self.input_buffer = ""
                        self._update_hud()
                    return True
                    
                elif self.state == 1:
                    if self.input_buffer:
                        try: self.offset_distance = float(self.input_buffer)
                        except ValueError: pass
                    self.input_buffer = ""
                    self.state = 2  
                    self._update_hud()
                    # 安全调用独立的预览函数，不再跨界借用 mouseMoveEvent
                    self._update_preview(final_point)
                    return True

                elif self.state == 2:
                    if self.target_item and self.ghost_item and self.ghost_coords:
                        self._finalize_offset()
                    return True
                    
            elif event.button() == Qt.MouseButton.RightButton:
                if self.state == 2:
                    self._cleanup_ghost()
                    self.state = 1
                elif self.state == 1:
                    if self.target_item: self.target_item.setSelected(False)
                    self.target_item = None
                    self.state = 0
                else:
                    self.deactivate()
                    self.canvas.switch_tool("选择")
                self._update_hud()
                return True
        except Exception as e:
            print("【鼠标点击崩溃已被拦截】:")
            traceback.print_exc()
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        try:
            self._update_hud()
            if self.state == 2 and self.target_item:
                # 安全调用
                self._update_preview(final_point)
            return True
        except Exception as e:
            print("【鼠标移动崩溃已被拦截】:")
            traceback.print_exc()
        return False

    def keyPressEvent(self, event):
        try:
            key = event.text()
            if key.isdigit() or key == '.':
                self.input_buffer += key
                self._update_hud()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud()
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.state == 1:
                    if self.input_buffer:
                        try: self.offset_distance = float(self.input_buffer)
                        except ValueError: pass
                    self.input_buffer = ""
                    self.state = 2
                    self._update_hud()
                    
                    # 安全触发预览刷新
                    safe_point = getattr(self.canvas, 'last_cursor_point', QPointF(0,0))
                    self._update_preview(safe_point)
                elif self.state == 2:
                    if self.target_item and self.ghost_item and self.ghost_coords:
                        self._finalize_offset()
                return True
            elif event.key() == Qt.Key.Key_Escape:
                if self.state == 2:
                    self._cleanup_ghost()
                    self.state = 1
                elif self.state == 1:
                    if self.target_item: self.target_item.setSelected(False)
                    self.target_item = None
                    self.state = 0
                else:
                    self.deactivate()
                    self.canvas.switch_tool("选择")
                self._update_hud()
                return True
        except Exception as e:
            print("【键盘敲击崩溃已被拦截】:")
            traceback.print_exc()
        return False

    def _finalize_offset(self):
        try:
            if not self.ghost_coords: return
            
            new_item = None
            if isinstance(self.target_item, SmartPolygonItem):
                new_item = SmartPolygonItem(self.ghost_coords)
            elif isinstance(self.target_item, SmartLineItem):
                new_item = SmartLineItem(self.ghost_coords[0], self.ghost_coords[1])
                
            if new_item:
                current_color = self.canvas.color_manager.get_color()
                pen = QPen(current_color, 1)
                pen.setCosmetic(True)
                new_item.setPen(pen)
                
                # 【修复】：继承源图形的图层属性
                self.canvas.layer_manager.copy_layer_props(new_item, self.target_item)
                
                self.canvas.undo_stack.push(CommandCreateGeom(self.canvas.scene(), new_item))
                
            self._cleanup_ghost()
            self.target_item.setSelected(False)
            self.target_item = None
            
            self.state = 0
            self._update_hud()
        except Exception as e:
            print("【生成实体异常已被拦截】:")
            traceback.print_exc()