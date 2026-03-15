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
        self.mode = "3point"  # 默认三点模式
        self.points = []
        self.preview_item = None
        self.circle_preview_item = None  # 用于显示完整圆的预览
        self.center_marker_item = None  # 用于显示圆心标记
        self.input_buffer = ""
        self.current_draw_angle = 0.0  # 保存当前绘制角度（用于键盘输入）
        
    def set_mode(self, mode):
        """切换圆弧绘制模式"""
        self.mode = mode
        self._cleanup()
        self._update_hud()
        
    def get_input_buffer(self):
        return self.input_buffer
        
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

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'):
            return
            
        self.canvas.hud_polar_info.show()
        
        # 显示输入缓冲区（如果有）
        buffer_display = f" {self.input_buffer}" if self.input_buffer else ""
        
        if self.mode == "3point":
            if len(self.points) == 0:
                text = f"圆弧(三点): 请指定起点{buffer_display}"
            elif len(self.points) == 1:
                text = f"圆弧(三点): 请指定第二点{buffer_display}"
            else:
                text = f"圆弧(三点): 请指定终点{buffer_display}"
        elif self.mode == "center":
            if len(self.points) == 0:
                text = f"圆弧(起点-圆心-终点): 请指定起点{buffer_display}"
            elif len(self.points) == 1:
                text = f"圆弧(起点-圆心-终点): 请指定圆心{buffer_display}"
            else:
                text = f"圆弧(起点-圆心-终点): 请指定终点{buffer_display}"
        else:  # radius mode
            if len(self.points) == 0:
                text = f"圆弧(起点-终点-半径): 请指定起点{buffer_display}"
            elif len(self.points) == 1:
                text = f"圆弧(起点-终点-半径): 请指定终点{buffer_display}"
            else:
                text = f"圆弧(起点-终点-半径): 请输入半径{buffer_display}"
                
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
                # 等待输入半径
                pass
                
            self._update_hud()
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            # 如果还没有点击任何点，右键切换模式
            if len(self.points) == 0:
                if self.mode == "3point":
                    self.set_mode("center")
                elif self.mode == "center":
                    self.set_mode("radius")
                else:
                    self.set_mode("3point")
                return True
            else:
                # 如果已经有点了，右键取消并切换到选择工具
                self._cleanup()
                self.canvas.switch_tool("选择")
                return True
            
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        # 保存当前角度（用于键盘输入）
        self.current_draw_angle = snapped_angle
        
        self._update_hud()
        
        # 如果有距离输入，使用输入的距离而不是鼠标位置
        if self.input_buffer and self.mode != "radius":
            try:
                distance = float(self.input_buffer)
                ref_point = self.get_reference_point()
                if ref_point:
                    # 使用保存的snapped_angle，而不是重新计算
                    angle_rad = math.radians(snapped_angle)
                    
                    # 使用输入的距离（可以是负数，表示反向）
                    new_x = ref_point.x() + distance * math.cos(angle_rad)
                    new_y = ref_point.y() - distance * math.sin(angle_rad)
                    final_point = QPointF(new_x, new_y)
            except ValueError:
                pass
        
        if self.mode == "3point" and len(self.points) == 2:
            self._preview_arc_3point(final_point)
        elif self.mode == "center" and len(self.points) == 2:
            self._preview_arc_center(final_point)
        elif self.mode == "radius" and len(self.points) == 2:
            # 如果已经输入了半径，使用输入的半径预览
            if self.input_buffer:
                try:
                    radius = float(self.input_buffer)
                    # 半径必须为正数
                    if radius > 0:
                        self._preview_arc_radius_with_value(radius, final_point)
                except ValueError:
                    pass
            else:
                # 如果还没输入半径，根据鼠标位置动态预览
                self._preview_arc_radius(final_point)
            
        return True

    def keyPressEvent(self, event):
        # 处理半径模式的半径输入（当已经有两个点时）
        if self.mode == "radius" and len(self.points) >= 2:
            key = event.text()
            if key.isdigit() or key == '.' or key == '-':
                # 负号只能在开头
                if key == '-' and len(self.input_buffer) > 0:
                    return True
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
                        # 使用绝对值作为半径，负数表示选择大圆弧（反转逻辑）
                        self._create_arc_radius(abs(radius), radius < 0)
                        return True
                    except ValueError:
                        self.input_buffer = ""
                        self._update_hud()
                        return True
                return True
        
        # 处理所有模式的距离/角度输入（当有参考点但还没到半径输入阶段时）
        ref_point = self.get_reference_point()
        if ref_point and not (self.mode == "radius" and len(self.points) >= 2):
            key = event.text()
            if key.isdigit() or key == '.' or key == '-':
                # 负号只能在开头
                if key == '-' and len(self.input_buffer) > 0:
                    return True
                self.input_buffer += key
                self._update_hud()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud()
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.input_buffer:
                    self._apply_distance_input()
                return True
                
        if event.key() == Qt.Key.Key_Escape:
            self._cleanup()
            self.canvas.switch_tool("选择")
            return True
            
        return False
    
    def _apply_distance_input(self):
        """应用距离或角度输入，center模式下第一段是距离，第二段是角度"""
        if not self.input_buffer:
            return
            
        try:
            value = float(self.input_buffer)
        except ValueError:
            return
        
        ref_point = self.get_reference_point()
        if not ref_point:
            return
        
        # center模式：第一段输入距离，第二段输入角度
        if self.mode == "center" and len(self.points) == 2:
            # 第二段：输入角度
            angle_rad = math.radians(value)
            # 使用当前鼠标距离作为半径
            cursor_pos = self.canvas.last_cursor_point
            distance = math.hypot(cursor_pos.x() - ref_point.x(), cursor_pos.y() - ref_point.y())
            
            new_x = ref_point.x() + distance * math.cos(angle_rad)
            new_y = ref_point.y() - distance * math.sin(angle_rad)
        else:
            # 其他情况：输入距离
            angle_rad = math.radians(self.current_draw_angle)
            distance = value
            
            new_x = ref_point.x() + distance * math.cos(angle_rad)
            new_y = ref_point.y() - distance * math.sin(angle_rad)
        
        # 创建点并添加
        pt = (new_x, new_y)
        self.points.append(pt)
        self.input_buffer = ""
        
        # 根据模式判断是否完成
        if self.mode == "3point" and len(self.points) == 3:
            self._create_arc_3point()
        elif self.mode == "center" and len(self.points) == 3:
            self._create_arc_center()
        elif self.mode == "radius" and len(self.points) == 2:
            # 半径模式需要等待半径输入
            pass
        
        self._update_hud()

    def _calculate_arc_3point(self, p1, p2, p3):
        """通过三点计算圆弧的圆心、半径、起始角度和终止角度"""
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        
        # 计算圆心
        d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(d) < 1e-6:
            return None
            
        ux = ((x1*x1 + y1*y1) * (y2 - y3) + (x2*x2 + y2*y2) * (y3 - y1) + (x3*x3 + y3*y3) * (y1 - y2)) / d
        uy = ((x1*x1 + y1*y1) * (x3 - x2) + (x2*x2 + y2*y2) * (x1 - x3) + (x3*x3 + y3*y3) * (x2 - x1)) / d
        
        # 计算半径
        r = math.hypot(x1 - ux, y1 - uy)
        
        # 计算角度
        angle1 = math.degrees(math.atan2(uy - y1, x1 - ux))
        angle3 = math.degrees(math.atan2(uy - y3, x3 - ux))
        
        if angle1 < 0:
            angle1 += 360
        if angle3 < 0:
            angle3 += 360
            
        return (ux, uy), r, angle1, angle3

    def _preview_arc_3point(self, final_point):
        if len(self.points) < 2:
            return
            
        p3 = (final_point.x(), final_point.y())
        result = self._calculate_arc_3point(self.points[0], self.points[1], p3)
        
        if not result:
            if self.preview_item:
                self.preview_item.hide()
            return
            
        center, radius, start_angle, end_angle = result
        self._show_preview(center, radius, start_angle, end_angle)

    def _preview_arc_center(self, final_point):
        if len(self.points) < 2:
            return
            
        p1 = self.points[0]
        center = self.points[1]
        p3 = (final_point.x(), final_point.y())
        
        radius = math.hypot(p1[0] - center[0], p1[1] - center[1])
        
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p3[1], p3[0] - center[0]))
        
        if start_angle < 0:
            start_angle += 360
        if end_angle < 0:
            end_angle += 360
            
        self._show_preview(center, radius, start_angle, end_angle)

    def _preview_arc_radius(self, final_point):
        if len(self.points) < 2:
            return
            
        p1 = self.points[0]
        p2 = self.points[1]
        
        # 计算两点中点
        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2
        
        # 计算弦长
        chord = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        
        # 根据鼠标位置估算半径
        mouse_pt = (final_point.x(), final_point.y())
        dist_to_mid = math.hypot(mouse_pt[0] - mx, mouse_pt[1] - my)
        
        # 半径至少要是弦长的一半
        radius = max(chord / 2, dist_to_mid + chord / 2)
        
        if chord > 2 * radius:
            return
            
        # 计算圆心到弦中点的距离
        h = math.sqrt(radius * radius - (chord / 2) ** 2)
        
        # 计算垂直方向
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        nx = -dy / chord
        ny = dx / chord
        
        # 两个可能的圆心
        c1 = (mx + h * nx, my + h * ny)
        c2 = (mx - h * nx, my - h * ny)
        
        # 选择离鼠标更近的圆心
        dist1 = math.hypot(c1[0] - mouse_pt[0], c1[1] - mouse_pt[1])
        dist2 = math.hypot(c2[0] - mouse_pt[0], c2[1] - mouse_pt[1])
        
        center = c1 if dist1 < dist2 else c2
        
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p2[1], p2[0] - center[0]))
        
        if start_angle < 0:
            start_angle += 360
        if end_angle < 0:
            end_angle += 360
            
        self._show_preview(center, radius, start_angle, end_angle)
    
    def _preview_arc_radius_with_value(self, radius, final_point):
        """使用固定半径值预览圆弧，显示完整圆并根据鼠标位置确定圆弧范围"""
        if len(self.points) < 2:
            return
            
        p1 = self.points[0]
        p2 = self.points[1]
        
        # 计算两点中点
        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2
        
        # 计算弦长
        chord = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        
        if chord > 2 * radius:
            # 半径太小，隐藏预览
            if self.preview_item:
                self.preview_item.hide()
            return
            
        # 计算圆心到弦中点的距离
        h = math.sqrt(radius * radius - (chord / 2) ** 2)
        
        # 计算垂直方向
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        nx = -dy / chord
        ny = dx / chord
        
        # 两个可能的圆心
        c1 = (mx + h * nx, my + h * ny)
        c2 = (mx - h * nx, my - h * ny)
        
        # 选择离鼠标更远的圆心（反转逻辑：正数画小圆弧，负数画大圆弧）
        mouse_pt = (final_point.x(), final_point.y())
        dist1 = math.hypot(c1[0] - mouse_pt[0], c1[1] - mouse_pt[1])
        dist2 = math.hypot(c2[0] - mouse_pt[0], c2[1] - mouse_pt[1])
        
        center = c1 if dist1 > dist2 else c2
        
        # 计算起点和终点的角度
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p2[1], p2[0] - center[0]))
        
        if start_angle < 0:
            start_angle += 360
        if end_angle < 0:
            end_angle += 360
        
        # 显示预览（包括完整圆和圆弧）
        self._show_preview_with_full_circle(center, radius, start_angle, end_angle)

    def _show_preview(self, center, radius, start_angle, end_angle):
        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            # 【修改】：虚线改为实线 SolidLine，透明度提升至 200
            pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            self.preview_item.setPen(pen)
            self.canvas.scene().addItem(self.preview_item)
            
        path = QPainterPath()
        span = end_angle - start_angle
        if span <= 0:
            span += 360
            
        rect = QRectF(center[0] - radius, center[1] - radius, 2*radius, 2*radius)
        path.arcMoveTo(rect, start_angle)
        path.arcTo(rect, start_angle, span)
        
        self.preview_item.setPath(path)
        self.preview_item.show()
    
    def _show_preview_with_full_circle(self, center, radius, start_angle, end_angle):
        """显示完整圆（虚线）和圆弧（实线）的预览，类似CAD"""
        # 创建或更新完整圆的预览（虚线）
        if not self.circle_preview_item:
            self.circle_preview_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 255, 255, 100), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.circle_preview_item.setPen(pen)
            self.canvas.scene().addItem(self.circle_preview_item)
        
        # 绘制完整圆
        circle_path = QPainterPath()
        rect = QRectF(center[0] - radius, center[1] - radius, 2*radius, 2*radius)
        circle_path.addEllipse(rect)
        self.circle_preview_item.setPath(circle_path)
        self.circle_preview_item.show()
        
        # 创建或更新圆弧预览（实线）
        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            self.preview_item.setPen(pen)
            self.canvas.scene().addItem(self.preview_item)
        
        # 绘制圆弧
        arc_path = QPainterPath()
        span = end_angle - start_angle
        if span <= 0:
            span += 360
        
        arc_path.arcMoveTo(rect, start_angle)
        arc_path.arcTo(rect, start_angle, span)
        
        self.preview_item.setPath(arc_path)
        self.preview_item.show()
        
        # 创建或更新圆心标记
        if not self.center_marker_item:
            from PyQt6.QtWidgets import QGraphicsEllipseItem
            self.center_marker_item = QGraphicsEllipseItem()
            pen = QPen(QColor(255, 255, 0), 1)
            pen.setCosmetic(True)
            self.center_marker_item.setPen(pen)
            self.center_marker_item.setBrush(QColor(255, 255, 0, 100))
            self.canvas.scene().addItem(self.center_marker_item)
        
        # 绘制圆心标记（小圆点）
        marker_size = 4
        self.center_marker_item.setRect(
            center[0] - marker_size/2, 
            center[1] - marker_size/2, 
            marker_size, 
            marker_size
        )
        self.center_marker_item.show()

    def _create_arc_3point(self):
        result = self._calculate_arc_3point(self.points[0], self.points[1], self.points[2])
        if result:
            center, radius, start_angle, end_angle = result
            self._finalize_arc(center, radius, start_angle, end_angle)

    def _create_arc_center(self):
        p1 = self.points[0]
        center = self.points[1]
        p3 = self.points[2]
        
        radius = math.hypot(p1[0] - center[0], p1[1] - center[1])
        
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p3[1], p3[0] - center[0]))
        
        if start_angle < 0:
            start_angle += 360
        if end_angle < 0:
            end_angle += 360
            
        self._finalize_arc(center, radius, start_angle, end_angle)

    def _create_arc_radius(self, radius, use_opposite_center=False):
        if len(self.points) < 2:
            return
            
        p1 = self.points[0]
        p2 = self.points[1]
        
        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2
        
        chord = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        
        if chord > 2 * radius:
            # 半径太小，无法连接两点
            print(f"半径 {radius} 太小，弦长为 {chord:.2f}，需要至少 {chord/2:.2f}")
            self.input_buffer = ""
            self._update_hud()
            return
            
        h = math.sqrt(radius * radius - (chord / 2) ** 2)
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        nx = -dy / chord
        ny = dx / chord
        
        # 根据参数选择圆心：正半径选小圆弧（离鼠标远），负半径选大圆弧（离鼠标近）
        if use_opposite_center:
            center = (mx + h * nx, my + h * ny)
        else:
            center = (mx - h * nx, my - h * ny)
        
        start_angle = math.degrees(math.atan2(center[1] - p1[1], p1[0] - center[0]))
        end_angle = math.degrees(math.atan2(center[1] - p2[1], p2[0] - center[0]))
        
        if start_angle < 0:
            start_angle += 360
        if end_angle < 0:
            end_angle += 360
            
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
