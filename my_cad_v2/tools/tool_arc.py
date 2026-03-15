# tools/tool_arc.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartArcItem
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPainterPath

class CommandCreateArc(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__()
        self.scene = scene
        self.item = item
        
    def redo(self):
        if self.item not in self.scene.items():
            self.scene.addItem(self.item)
            
    def undo(self):
        if self.item in self.scene.items():
            self.item.setSelected(False)
            self.scene.removeItem(self.item)


class ArcTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.mode = "3point"  
        self.points = []
        self.preview_item = None
        self.circle_preview_item = None  
        self.center_marker_item = None  
        
        # 半径模式的单输入缓冲
        self.input_buffer = ""
        
        # 极坐标双输入支持 (长度 + 角度，支持 Tab 切换)
        self.input_mode = "length" 
        self.length_buffer = ""
        self.angle_buffer = ""
        
        self.current_draw_angle = 0.0  
        
    def set_mode(self, mode):
        self.mode = mode
        self._cleanup()
        self._update_hud()
        
    def get_input_buffer(self):
        # 兼容 core_canvas 的底层 HUD 动态读取
        if self.mode == "radius" and len(self.points) >= 2:
            return self.input_buffer
        if self.input_mode == 'length':
            return self.length_buffer
        else:
            return self.angle_buffer
        
    def get_reference_point(self):
        if self.points:
            return QPointF(*self.points[-1])
        return None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._cleanup()
        self._update_hud()

    def deactivate(self):
        self._cleanup()

    def _cleanup(self):
        if self.preview_item and self.preview_item.scene():
            self.canvas.scene().removeItem(self.preview_item)
        self.preview_item = None
        
        if self.circle_preview_item and self.circle_preview_item.scene():
            self.canvas.scene().removeItem(self.circle_preview_item)
        self.circle_preview_item = None
        
        if self.center_marker_item and self.center_marker_item.scene():
            self.canvas.scene().removeItem(self.center_marker_item)
        self.center_marker_item = None
        
        self.points.clear()
        self.input_buffer = ""
        self.length_buffer = ""
        self.angle_buffer = ""
        self.input_mode = "length"

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'):
            return
            
        self.canvas.hud_polar_info.show()
        
        if self.mode == "radius" and len(self.points) >= 2:
            buffer_display = f" {self.input_buffer}" if self.input_buffer else ""
        else:
            if self.length_buffer or self.angle_buffer:
                buffer_display = f" [长:{self.length_buffer} 角:{self.angle_buffer}]"
            else:
                buffer_display = ""
        
        if self.mode == "3point":
            if len(self.points) == 0: text = f"圆弧(三点): 请指定起点{buffer_display}"
            elif len(self.points) == 1: text = f"圆弧(三点): 请指定第二点{buffer_display}"
            else: text = f"圆弧(三点): 请指定终点{buffer_display}"
        elif self.mode == "center":
            if len(self.points) == 0: text = f"圆弧(起点-圆心-终点): 请指定起点{buffer_display}"
            elif len(self.points) == 1: text = f"圆弧(起点-圆心-终点): 请指定圆心{buffer_display}"
            else: text = f"圆弧(起点-圆心-终点): 请指定终点{buffer_display}"
        else: 
            if len(self.points) == 0: text = f"圆弧(起点-终点-半径): 请指定起点{buffer_display}"
            elif len(self.points) == 1: text = f"圆弧(起点-终点-半径): 请指定终点{buffer_display}"
            else: text = f"圆弧(起点-终点-半径): 请输入半径{buffer_display}"
                
        color = "#5bc0de"
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:{color}; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>⌒ {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            pt = (final_point.x(), final_point.y())
            self.points.append(pt)
            
            if self.mode == "3point" and len(self.points) == 3:
                self._create_arc_3point()
            elif self.mode == "center" and len(self.points) == 3:
                self._create_arc_center()
            elif self.mode == "radius" and len(self.points) == 2:
                pass
                
            self._update_hud()
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            if len(self.points) == 0:
                if self.mode == "3point": self.set_mode("center")
                elif self.mode == "center": self.set_mode("radius")
                else: self.set_mode("3point")
                return True
            else:
                self._cleanup()
                self.canvas.switch_tool("选择")
                return True
            
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        self.current_draw_angle = snapped_angle
        self.last_mouse_point = QPointF(final_point)  # 新增：记录当前鼠标真实位置
        self._update_hud()
        
        # 处理双输入预览的坐标覆盖
        if self.mode != "radius" and (self.length_buffer or self.angle_buffer):
            ref_point = self.get_reference_point()
            if ref_point:
                if self.length_buffer:
                    try: distance = float(self.length_buffer)
                    except ValueError: distance = math.hypot(final_point.x() - ref_point.x(), final_point.y() - ref_point.y())
                else:
                    distance = math.hypot(final_point.x() - ref_point.x(), final_point.y() - ref_point.y())
                    
                if self.angle_buffer:
                    try: angle_deg = float(self.angle_buffer)
                    except ValueError: angle_deg = snapped_angle
                else:
                    # 修改：当没有手动输入角度时，根据鼠标相对起点的位置实时计算角度
                    dx = final_point.x() - ref_point.x()
                    dy = final_point.y() - ref_point.y()
                    angle_deg = math.degrees(math.atan2(-dy, dx)) if (dx != 0 or dy != 0) else 0
                    
                angle_rad = math.radians(angle_deg)
                new_x = ref_point.x() + distance * math.cos(angle_rad)
                new_y = ref_point.y() - distance * math.sin(angle_rad)
                final_point = QPointF(new_x, new_y)
        
        # --- 之前的预览逻辑保持完全不变 ---
        # 补充：确保你在上一步加上的直线预览逻辑（len(self.points) == 1）也在这里
        if len(self.points) == 1:
            self._preview_line(self.points[0], final_point)
        elif self.mode == "3point" and len(self.points) == 2:
            self._preview_arc_3point(final_point)
        elif self.mode == "center" and len(self.points) == 2:
            self._preview_arc_center(final_point)
        elif self.mode == "radius" and len(self.points) == 2:
            if self.input_buffer:
                try:
                    radius = float(self.input_buffer)
                    if radius > 0: self._preview_arc_radius_with_value(radius, final_point)
                except ValueError: pass
            else:
                self._preview_arc_radius(final_point)
            
        return True
    def keyPressEvent(self, event):
        # 1. 半径模式，单输入处理
        if self.mode == "radius" and len(self.points) >= 2:
            key = event.text()
            if key.isdigit() or key == '.' or key == '-':
                if key == '-' and len(self.input_buffer) > 0: return True
                self.input_buffer += key
                self._update_hud()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud()
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    try:
                        radius = float(self.input_buffer)
                        self._create_arc_radius(abs(radius), radius < 0)
                        return True
                    except ValueError:
                        self.input_buffer = ""
                        self._update_hud()
                        return True
                return True
        
        # 2. 极坐标双输入 (长度 + 角度，支持 Tab 切换)
        ref_point = self.get_reference_point()
        if ref_point and not (self.mode == "radius" and len(self.points) >= 2):
            if event.key() == Qt.Key.Key_Tab or event.key() == Qt.Key.Key_Backtab:
                self.input_mode = 'angle' if self.input_mode == 'length' else 'length'
                self.canvas.viewport().update()
                return True
                
            key = event.text()
            if key.isdigit() or key == '.' or key == '-':
                if self.input_mode == 'length':
                    if key == '-' and len(self.length_buffer) > 0: return True
                    self.length_buffer += key
                else:
                    if key == '-' and len(self.angle_buffer) > 0: return True
                    self.angle_buffer += key
                self.canvas.viewport().update()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                if self.input_mode == 'length': self.length_buffer = self.length_buffer[:-1]
                else: self.angle_buffer = self.angle_buffer[:-1]
                self.canvas.viewport().update()
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.length_buffer or self.angle_buffer:
                    self._apply_polar_input()
                return True
                
        if event.key() == Qt.Key.Key_Escape:
            self._cleanup()
            self.canvas.switch_tool("选择")
            return True
            
        return False
    
    def _apply_polar_input(self):
        """将双输入的极坐标参数固化为点"""
        ref_point = self.get_reference_point()
        if not ref_point: return
            
        # 修改：使用 tool 内部记录的最后一个鼠标点
        cursor_pos = getattr(self, 'last_mouse_point', QPointF(ref_point.x() + 1, ref_point.y()))
            
        if self.length_buffer:
            try: distance = float(self.length_buffer)
            except ValueError: distance = 0.0
        else:
            distance = math.hypot(cursor_pos.x() - ref_point.x(), cursor_pos.y() - ref_point.y())
            
        if self.angle_buffer:
            try: angle_deg = float(self.angle_buffer)
            except ValueError: angle_deg = self.current_draw_angle
        else:
            # 修改：如果没有输入角度，使用鼠标与起点的实际夹角
            dx = cursor_pos.x() - ref_point.x()
            dy = cursor_pos.y() - ref_point.y()
            angle_deg = math.degrees(math.atan2(-dy, dx)) if (dx != 0 or dy != 0) else 0
            
        angle_rad = math.radians(angle_deg)
        new_x = ref_point.x() + distance * math.cos(angle_rad)
        new_y = ref_point.y() - distance * math.sin(angle_rad)
        
        pt = (new_x, new_y)
        self.points.append(pt)
        
        self.length_buffer = ""
        self.angle_buffer = ""
        self.input_mode = "length"
        
        if self.mode == "3point" and len(self.points) == 3: self._create_arc_3point()
        elif self.mode == "center" and len(self.points) == 3: self._create_arc_center()
        elif self.mode == "radius" and len(self.points) == 2: pass
            
        self._update_hud()
    def _calculate_arc_3point(self, p1, p2, p3):
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        
        d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(d) < 1e-6: return None
            
        ux = ((x1*x1 + y1*y1) * (y2 - y3) + (x2*x2 + y2*y2) * (y3 - y1) + (x3*x3 + y3*y3) * (y1 - y2)) / d
        uy = ((x1*x1 + y1*y1) * (x3 - x2) + (x2*x2 + y2*y2) * (x1 - x3) + (x3*x3 + y3*y3) * (x2 - x1)) / d
        
        r = math.hypot(x1 - ux, y1 - uy)
        angle1 = math.degrees(math.atan2(uy - y1, x1 - ux))
        angle2 = math.degrees(math.atan2(uy - y2, x2 - ux))  # 新增：计算中间点的角度
        angle3 = math.degrees(math.atan2(uy - y3, x3 - ux))
        
        if angle1 < 0: angle1 += 360
        if angle2 < 0: angle2 += 360  # 新增
        if angle3 < 0: angle3 += 360
            
        return (ux, uy), r, angle1, angle2, angle3  # 返回 5 个值
            
        return (ux, uy), r, angle1, angle3

    def _preview_arc_3point(self, final_point):
        if len(self.points) < 2: return
        p3 = (final_point.x(), final_point.y())
        result = self._calculate_arc_3point(self.points[0], self.points[1], p3)
        
        if not result:
            if self.preview_item: self.preview_item.hide()
            return
            
        center, radius, a1, a2, a3 = result
        
        # === 修改：根据中间点决定画圆弧的方向，防止翻转 ===
        span3 = (a3 - a1) % 360
        span2 = (a2 - a1) % 360
        
        if span2 <= span3:
            start_angle = a1
            end_angle = a3
        else:
            # 如果按原方向不经过中间点，则反转起点和终点
            start_angle = a3
            end_angle = a1
            
        self._show_preview(center, radius, start_angle, end_angle)

    def _preview_arc_center(self, final_point):
        if len(self.points) < 2: return
        p1 = self.points[0]
        center = self.points[1]
        p3 = (final_point.x(), final_point.y())
        
        radius = math.hypot(p1[0] - center[0], p1[1] - center[1])
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p3[1], p3[0] - center[0]))
        
        if start_angle < 0: start_angle += 360
        if end_angle < 0: end_angle += 360
            
        self._show_preview(center, radius, start_angle, end_angle)

    def _preview_arc_radius(self, final_point):
        if len(self.points) < 2: return
        p1 = self.points[0]
        p2 = self.points[1]
        
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        chord = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        mouse_pt = (final_point.x(), final_point.y())
        dist_to_mid = math.hypot(mouse_pt[0] - mx, mouse_pt[1] - my)
        radius = max(chord / 2, dist_to_mid + chord / 2)
        
        if chord > 2 * radius: return
            
        h = math.sqrt(radius * radius - (chord / 2) ** 2)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        nx, ny = -dy / chord, dx / chord
        
        c1 = (mx + h * nx, my + h * ny)
        c2 = (mx - h * nx, my - h * ny)
        
        dist1 = math.hypot(c1[0] - mouse_pt[0], c1[1] - mouse_pt[1])
        dist2 = math.hypot(c2[0] - mouse_pt[0], c2[1] - mouse_pt[1])
        
        center = c1 if dist1 < dist2 else c2
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p2[1], p2[0] - center[0]))
        
        if start_angle < 0: start_angle += 360
        if end_angle < 0: end_angle += 360
            
        self._show_preview(center, radius, start_angle, end_angle)
    
    def _preview_arc_radius_with_value(self, radius, final_point):
        if len(self.points) < 2: return
        p1 = self.points[0]
        p2 = self.points[1]
        
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        chord = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        
        if chord > 2 * radius:
            if self.preview_item: self.preview_item.hide()
            return
            
        h = math.sqrt(radius * radius - (chord / 2) ** 2)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        nx, ny = -dy / chord, dx / chord
        
        c1 = (mx + h * nx, my + h * ny)
        c2 = (mx - h * nx, my - h * ny)
        
        mouse_pt = (final_point.x(), final_point.y())
        dist1 = math.hypot(c1[0] - mouse_pt[0], c1[1] - mouse_pt[1])
        dist2 = math.hypot(c2[0] - mouse_pt[0], c2[1] - mouse_pt[1])
        
        center = c1 if dist1 > dist2 else c2
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p2[1], p2[0] - center[0]))
        
        if start_angle < 0: start_angle += 360
        if end_angle < 0: end_angle += 360
        
        self._show_preview_with_full_circle(center, radius, start_angle, end_angle)



    # === 新增：用于找寻下一个点时的直线引导预览 ===
    def _preview_line(self, p1, p2_pointf):
        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            self.canvas.scene().addItem(self.preview_item)
            
        # 设置为虚线
        pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.preview_item.setPen(pen)
            
        path = QPainterPath()
        path.moveTo(p1[0], p1[1])
        path.lineTo(p2_pointf.x(), p2_pointf.y())
        self.preview_item.setPath(path)
        self.preview_item.show()
    def _show_preview(self, center, radius, start_angle, end_angle):
        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            self.canvas.scene().addItem(self.preview_item)
            
        # 修改：恢复为实线（防止受上面直线预览的虚线影响）
        pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        self.preview_item.setPen(pen)
        
        path = QPainterPath()
        span = end_angle - start_angle
        if span <= 0: span += 360
            
        rect = QRectF(center[0] - radius, center[1] - radius, 2*radius, 2*radius)
        path.arcMoveTo(rect, start_angle)
        path.arcTo(rect, start_angle, span)
        
        self.preview_item.setPath(path)
        self.preview_item.show()
    
    def _show_preview_with_full_circle(self, center, radius, start_angle, end_angle):
        if not self.circle_preview_item:
            self.circle_preview_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 255, 255, 100), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.circle_preview_item.setPen(pen)
            self.canvas.scene().addItem(self.circle_preview_item)
        
        circle_path = QPainterPath()
        rect = QRectF(center[0] - radius, center[1] - radius, 2*radius, 2*radius)
        circle_path.addEllipse(rect)
        self.circle_preview_item.setPath(circle_path)
        self.circle_preview_item.show()
        
        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            self.preview_item.setPen(pen)
            self.canvas.scene().addItem(self.preview_item)
        
        arc_path = QPainterPath()
        span = end_angle - start_angle
        if span <= 0: span += 360
        
        arc_path.arcMoveTo(rect, start_angle)
        arc_path.arcTo(rect, start_angle, span)
        
        self.preview_item.setPath(arc_path)
        self.preview_item.show()
        
        if not self.center_marker_item:
            from PyQt6.QtWidgets import QGraphicsEllipseItem
            self.center_marker_item = QGraphicsEllipseItem()
            pen = QPen(QColor(255, 255, 0), 1)
            pen.setCosmetic(True)
            self.center_marker_item.setPen(pen)
            self.center_marker_item.setBrush(QColor(255, 255, 0, 100))
            self.canvas.scene().addItem(self.center_marker_item)
        
        marker_size = 4
        self.center_marker_item.setRect(center[0] - marker_size/2, center[1] - marker_size/2, marker_size, marker_size)
        self.center_marker_item.show()

    def _create_arc_3point(self):
        result = self._calculate_arc_3point(self.points[0], self.points[1], self.points[2])
        if result:
            center, radius, a1, a2, a3 = result
            
            # === 修改：同样处理最终创建时的翻转判断 ===
            span3 = (a3 - a1) % 360
            span2 = (a2 - a1) % 360
            
            if span2 <= span3:
                start_angle = a1
                end_angle = a3
            else:
                start_angle = a3
                end_angle = a1
                
            self._finalize_arc(center, radius, start_angle, end_angle)

    def _create_arc_center(self):
        p1 = self.points[0]
        center = self.points[1]
        p3 = self.points[2]
        
        radius = math.hypot(p1[0] - center[0], p1[1] - center[1])
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p3[1], p3[0] - center[0]))
        
        if start_angle < 0: start_angle += 360
        if end_angle < 0: end_angle += 360
            
        self._finalize_arc(center, radius, start_angle, end_angle)

    def _create_arc_radius(self, radius, use_opposite_center=False):
        if len(self.points) < 2: return
        p1 = self.points[0]
        p2 = self.points[1]
        
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        chord = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        
        if chord > 2 * radius:
            self.input_buffer = ""
            self._update_hud()
            return
            
        h = math.sqrt(radius * radius - (chord / 2) ** 2)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        nx, ny = -dy / chord, dx / chord
        
        if use_opposite_center: center = (mx + h * nx, my + h * ny)
        else: center = (mx - h * nx, my - h * ny)
        
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p2[1], p2[0] - center[0]))
        
        if start_angle < 0: start_angle += 360
        if end_angle < 0: end_angle += 360
            
        self._finalize_arc(center, radius, start_angle, end_angle)

    def _finalize_arc(self, center, radius, start_angle, end_angle):
        arc_item = SmartArcItem(center, radius, start_angle, end_angle)
        arc_item.setPen(QPen(self.canvas.color_manager.get_color(), 1, Qt.PenStyle.SolidLine))
        arc_item.pen().setCosmetic(True)
        self.canvas.layer_manager.apply_current_layer_props(arc_item)
        
        cmd = CommandCreateArc(self.canvas.scene(), arc_item)
        self.canvas.undo_stack.push(cmd)
        
        self._cleanup()
        self._update_hud()