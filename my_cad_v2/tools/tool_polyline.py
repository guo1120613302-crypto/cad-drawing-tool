# tools/tool_polyline.py
from tools.base_tool import BaseTool
from core.core_items import SmartPolylineItem
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsTextItem
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPainterPath
import math

class CommandCreatePolyline(QUndoCommand):
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

class PolylineTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.points = []
        self.segments = []  
        self.temp_items = []
        
        self.preview_item = None
        self.chord_preview_item = None    
        self.tangent_preview_item = None  
        
        self.segment_mode = "line"
        self.input_mode = "length" 
        self.length_buffer = ""
        self.angle_buffer = ""
        
        self.current_draw_angle = 0.0
        self.current_bulge = 0.0
        self.last_mouse_point = QPointF(0, 0)

    def get_reference_point(self):
        return QPointF(*self.points[-1]) if self.points else None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._cleanup_temp_items()

    def deactivate(self):
        self._cleanup_temp_items()

    def _cleanup_temp_items(self):
        for item in self.temp_items:
            if item.scene(): self.canvas.scene().removeItem(item)
        if self.preview_item and self.preview_item.scene():
            self.canvas.scene().removeItem(self.preview_item)
        if getattr(self, 'chord_preview_item', None) and self.chord_preview_item.scene():
            self.canvas.scene().removeItem(self.chord_preview_item)
        if getattr(self, 'tangent_preview_item', None) and self.tangent_preview_item.scene():
            self.canvas.scene().removeItem(self.tangent_preview_item)
            
        self.temp_items.clear()
        self.preview_item = None
        self.chord_preview_item = None
        self.tangent_preview_item = None
        
        self.points.clear()
        self.segments.clear()
        self.segment_mode = "line"
        self.input_mode = "length"
        self.length_buffer = ""
        self.angle_buffer = ""
        self.current_bulge = 0.0

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            pt = (final_point.x(), final_point.y())
            if not self.points:
                self.canvas.scene().clearSelection()
                self.points.append(pt)
                
                self.preview_item = QGraphicsPathItem()
                pen = QPen(QColor(255, 255, 255, 200), 1)
                pen.setCosmetic(True)
                self.preview_item.setPen(pen)
                self.canvas.scene().addItem(self.preview_item)
                
                self.chord_preview_item = QGraphicsLineItem()
                pen_chord = QPen(QColor(255, 255, 255, 120), 1, Qt.PenStyle.DashLine)
                pen_chord.setCosmetic(True)
                self.chord_preview_item.setPen(pen_chord)
                self.canvas.scene().addItem(self.chord_preview_item)
                self.chord_preview_item.hide()
                
                self.tangent_preview_item = QGraphicsLineItem()
                pen_tan = QPen(QColor(0, 255, 0, 180), 1, Qt.PenStyle.DashLine)
                pen_tan.setCosmetic(True)
                self.tangent_preview_item.setPen(pen_tan)
                self.canvas.scene().addItem(self.tangent_preview_item)
                self.tangent_preview_item.hide()
                
            else:
                p2, _, _ = self._get_dynamic_p2(final_point)
                self.points.append(p2)
                if self.segment_mode == "line":
                    self.segments.append({"type": "line"})
                else:
                    self.segments.append({"type": "arc", "bulge": self.current_bulge})
                    
                self.length_buffer = ""
                self.angle_buffer = ""
                self.input_mode = "length"
                self._create_temp_preview()
                
            self._update_dynamic_preview(final_point)
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            self._finalize_polyline()
            return True
            
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        if self.points:
            p1 = self.points[-1]
            is_lower = final_point.y() > p1[1]
            if is_lower:
                self.current_draw_angle = (360 - snapped_angle) % 360
            else:
                self.current_draw_angle = snapped_angle
        else:
            self.current_draw_angle = snapped_angle
            
        self.last_mouse_point = final_point
        self._update_dynamic_preview(final_point)
        return True

    def keyPressEvent(self, event):
        if not self.points: return False

        if event.key() == Qt.Key.Key_Tab or event.key() == Qt.Key.Key_Backtab:
            event.accept() 
            self.input_mode = "angle" if self.input_mode == "length" else "length"
            self._update_dynamic_preview(self.last_mouse_point)
            return True

        key = event.text()
        
        if key.lower() == 'a' and not self.length_buffer and not self.angle_buffer:
            self.segment_mode = "arc"
            self._update_dynamic_preview(self.last_mouse_point)
            return True
        elif key.lower() == 'l' and not self.length_buffer and not self.angle_buffer:
            self.segment_mode = "line"
            self._update_dynamic_preview(self.last_mouse_point)
            return True

        if key.isdigit() or key in ['.', '-']:
            if self.input_mode == "length":
                self.length_buffer += key
            else:
                self.angle_buffer += key
            self._update_dynamic_preview(self.last_mouse_point)
            return True

        if event.key() == Qt.Key.Key_Backspace:
            if self.input_mode == "length":
                self.length_buffer = self.length_buffer[:-1]
            else:
                self.angle_buffer = self.angle_buffer[:-1]
            self._update_dynamic_preview(self.last_mouse_point)
            return True

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.length_buffer or self.angle_buffer:
                p2, _, _ = self._get_dynamic_p2(self.last_mouse_point)
                self.points.append(p2)
                
                if self.segment_mode == "line":
                    self.segments.append({"type": "line"})
                else:
                    self.segments.append({"type": "arc", "bulge": self.current_bulge})
                    
                self.length_buffer = ""
                self.angle_buffer = ""
                self.input_mode = "length"
                self._create_temp_preview()
                self._update_dynamic_preview(self.last_mouse_point)
            else:
                self._finalize_polyline()
            return True

        if event.key() == Qt.Key.Key_Escape:
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True

        return False

    def _get_tangent_vector(self):
        if len(self.points) >= 2:
            p1, p2 = self.points[-2], self.points[-1]
            if self.segments[-1]["type"] == "line":
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                length = math.hypot(dx, dy)
                if length == 0: return 1.0, 0.0
                return dx/length, dy/length
            else:
                bulge = self.segments[-1]["bulge"]
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                chord_ang = math.atan2(-dy, dx)
                tang_ang = chord_ang + 2 * math.atan(bulge)
                return math.cos(tang_ang), -math.sin(tang_ang)
        return 1.0, 0.0

    def _get_dynamic_p2(self, raw_point):
        p1 = self.points[-1]
        mx, my = raw_point.x(), raw_point.y()
        tx, ty = self._get_tangent_vector()
        tangent_rad = math.atan2(-ty, tx)

        dist = math.hypot(mx - p1[0], my - p1[1])

        if self.segment_mode == "arc":
            cross = tx * (my - p1[1]) - ty * (mx - p1[0])
            # 【核心修复】：恢复正确的偏转极性
            sign = -1 if cross > 0 else 1

            # --- 修改开始：处理用户手动输入的角度 ---
            if self.angle_buffer:
                try:
                    # 用户输入的角度是“弦切角” (例如 CAD 极轴追踪的 30度)
                    chord_tangent_deg = float(self.angle_buffer)
                    chord_len = float(self.length_buffer) if self.length_buffer else dist
                    
                    # 弦的真实绝对角度 = 切线角度 + (极性符号 * 弦切角)
                    chord_rad = tangent_rad + (sign * math.radians(chord_tangent_deg))
                    nx = p1[0] + chord_len * math.cos(chord_rad)
                    ny = p1[1] - chord_len * math.sin(chord_rad)
                    
                    # 凸度 Bulge = tan(圆心角 / 4) = tan((弦切角 * 2) / 4) = tan(弦切角 / 2)
                    self.current_bulge = sign * math.tan(math.radians(chord_tangent_deg) / 2.0)
                    
                    # 返回新坐标、弦长，以及圆心角（弦切角 * 2）
                    return (nx, ny), chord_len, chord_tangent_deg * 2
                except ValueError: pass
            # --- 修改结束 ---

            chord_dx, chord_dy = mx - p1[0], my - p1[1]
            chord_rad = math.atan2(-chord_dy, chord_dx)
            delta = chord_rad - tangent_rad
            while delta > math.pi: delta -= 2*math.pi
            while delta < -math.pi: delta += 2*math.pi
            self.current_bulge = math.tan(delta / 2.0)

            if self.length_buffer:
                try:
                    chord_len = float(self.length_buffer)
                    nx = p1[0] + chord_len * math.cos(chord_rad)
                    ny = p1[1] - chord_len * math.sin(chord_rad)
                    return (nx, ny), chord_len, math.degrees(delta * 2)
                except ValueError: pass

            return (mx, my), dist, math.degrees(delta * 2)

        if self.length_buffer:
            try: dist = float(self.length_buffer)
            except ValueError: pass
            
        ang = self.current_draw_angle
        if self.angle_buffer and self.segment_mode != "arc":
            try: 
                cad_angle = float(self.angle_buffer)
                is_lower = raw_point.y() > p1[1]
                if is_lower:
                    ang = (360 - cad_angle) % 360
                else:
                    ang = cad_angle
            except ValueError: pass
            
        ang_rad = math.radians(ang)
        nx = p1[0] + dist * math.cos(ang_rad)
        ny = p1[1] - dist * math.sin(ang_rad)
        return (nx, ny), dist, ang

    def _update_dynamic_preview(self, raw_point):
        if not self.points or not self.preview_item: 
            return
            
        p1 = self.points[-1]
        p2, dist, ang = self._get_dynamic_p2(raw_point)
        
        if self.segment_mode == "arc":
            path = self._create_arc_path(p1, p2, self.current_bulge)
            self.preview_item.setPath(path)
            
            if self.chord_preview_item:
                self.chord_preview_item.setLine(QLineF(p1[0], p1[1], p2[0], p2[1]))
                self.chord_preview_item.show()
                
            if self.tangent_preview_item:
                tx, ty = self._get_tangent_vector()
                tan_len = dist if dist > 30 else 50
                self.tangent_preview_item.setLine(QLineF(p1[0], p1[1], p1[0] + tan_len * tx, p1[1] + tan_len * ty))
                self.tangent_preview_item.show()
        else:
            path = QPainterPath()
            path.moveTo(QPointF(p1[0], p1[1]))
            path.lineTo(QPointF(p2[0], p2[1]))
            self.preview_item.setPath(path)
            
            if self.chord_preview_item: self.chord_preview_item.hide()
            if self.tangent_preview_item: self.tangent_preview_item.hide()

    def _create_arc_path(self, p1, p2, bulge):
        """【数学重构】：标准的CAD纯正推导，绝不镜像翻转"""
        path = QPainterPath()
        path.moveTo(QPointF(*p1))
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        chord = math.hypot(dx, dy)
        
        if chord < 1e-4 or abs(bulge) < 1e-4:
            path.lineTo(QPointF(*p2))
            return path

        # 核心算式：求圆心
        d = -(chord / 2.0) * ((1.0 - bulge**2) / (2.0 * bulge))
        mid_x = (p1[0] + p2[0]) / 2.0
        mid_y = (p1[1] + p2[1]) / 2.0
        
        cx = mid_x - d * (dy / chord)
        cy = mid_y - d * (-dx / chord)
        
        radius = math.hypot(p1[0] - cx, p1[1] - cy)

        # 剥离多余负号，纯正的扫掠角
        start_angle = math.degrees(math.atan2(-(p1[1] - cy), p1[0] - cx))
        span_angle = math.degrees(4 * math.atan(bulge))

        rect = QRectF(cx - radius, cy - radius, 2*radius, 2*radius)
        path.arcTo(rect, start_angle, span_angle)
        
        return path

    def _create_temp_preview(self):
        for item in self.temp_items:
            if item.scene(): self.canvas.scene().removeItem(item)
        self.temp_items.clear()
        
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            seg_info = self.segments[i] if i < len(self.segments) else {"type": "line"}
            
            if seg_info.get("type") == "arc":
                path_item = QGraphicsPathItem()
                path = self._create_arc_path(p1, p2, seg_info.get("bulge", 0))
                path_item.setPath(path)
                pen = QPen(QColor(255, 255, 255, 150), 1)
                pen.setCosmetic(True)
                path_item.setPen(pen)
                self.canvas.scene().addItem(path_item)
                self.temp_items.append(path_item)
            else:
                line_item = QGraphicsLineItem(QLineF(p1[0], p1[1], p2[0], p2[1]))
                pen = QPen(QColor(255, 255, 255, 150), 1)
                pen.setCosmetic(True)
                line_item.setPen(pen)
                self.canvas.scene().addItem(line_item)
                self.temp_items.append(line_item)

    def _finalize_polyline(self):
        if len(self.points) > 1:
            final_item = SmartPolylineItem(list(self.points), list(self.segments))
            final_item.setPen(QPen(self.canvas.color_manager.get_color(), 1, Qt.PenStyle.SolidLine))
            final_item.pen().setCosmetic(True)
            self.canvas.layer_manager.apply_current_layer_props(final_item)
            self.canvas.undo_stack.push(CommandCreatePolyline(self.canvas.scene(), final_item))
            
        self.deactivate()
        self.canvas.switch_tool("选择")