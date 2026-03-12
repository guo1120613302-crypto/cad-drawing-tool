# core_canvas.py
from PyQt6.QtWidgets import QGraphicsView, QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QLineF, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QPainter, QKeyEvent, QUndoStack, QUndoCommand, QKeySequence, QBrush
import math

from managers.color_manager import ColorManager
from tools.tool_select import SelectTool
from tools.tool_line import LineTool
from tools.tool_rect import RectTool
from tools.tool_offset import OffsetTool
class CommandDeleteLines(QUndoCommand):
    def __init__(self, scene, items):
        super().__init__()
        self.scene = scene
        self.items = items
    def redo(self):
        for item in self.items:
            if item in self.scene.items():
                item.setSelected(False)
                self.scene.removeItem(item)
    def undo(self):
        for item in self.items:
            if item not in self.scene.items():
                self.scene.addItem(item)

class CADGraphicsView(QGraphicsView):
    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window
        
        self.color_manager = ColorManager()
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) 
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setStyleSheet("background-color: transparent;")
        self.setBackgroundBrush(QColor("#222222"))
        
        # 禁用默认锚点，防止场景动态扩大时锚点偏移
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        
        self.undo_stack = QUndoStack(self)
        
        self._is_panning = False
        self._pan_start_pos = None
        
        self.last_cursor_point = QPointF(0, 0)
        self.acquired_point = None 
        
        self._init_global_ui_components()

        self.tools = {
            "选择": SelectTool(self),
            "直线": LineTool(self),
            "矩形": RectTool(self),
            "偏移": OffsetTool(self)
        }
        self.current_tool = self.tools["直线"] 
        self.current_tool.activate()
        
        if hasattr(self.main_window, 'toolbox'):
            for action in self.main_window.toolbox.actions():
                action.triggered.connect(lambda checked, name=action.text(): self.switch_tool(name))

    def _init_global_ui_components(self):
        self.polar_line = QGraphicsLineItem()
        polar_pen = QPen(QColor(0, 255, 0), 1, Qt.PenStyle.DashLine)
        polar_pen.setCosmetic(True)
        self.polar_line.setPen(polar_pen)
        self.polar_line.hide()
        self.scene().addItem(self.polar_line)
        
        self.tracking_line = QGraphicsLineItem()
        track_pen = QPen(QColor(0, 255, 0), 1, Qt.PenStyle.DotLine)
        track_pen.setCosmetic(True)
        self.tracking_line.setPen(track_pen)
        self.tracking_line.hide()
        self.scene().addItem(self.tracking_line)
        
        tm_pen = QPen(QColor(0, 255, 0), 1)
        tm_pen.setCosmetic(True)
        self.track_marker_h = QGraphicsLineItem()
        self.track_marker_v = QGraphicsLineItem()
        self.track_marker_h.setPen(tm_pen)
        self.track_marker_v.setPen(tm_pen)
        self.track_marker_h.hide()
        self.track_marker_v.hide()
        self.scene().addItem(self.track_marker_h)
        self.scene().addItem(self.track_marker_v)
        
        self.snap_marker = QGraphicsRectItem(-4, -4, 8, 8) 
        self.snap_marker.setPen(tm_pen)
        self.snap_marker.setZValue(2000)
        self.snap_marker.hide()
        self.scene().addItem(self.snap_marker)
        
        self.hud_snap_tip = QGraphicsTextItem()
        self.hud_snap_tip.setHtml("<div style='background-color:#555555; color:white; padding:1px 3px; font-size:11px;'>端点</div>")
        self.hud_snap_tip.setZValue(2000)
        self.hud_snap_tip.hide()
        self.scene().addItem(self.hud_snap_tip)
        
        self.hud_length = QGraphicsTextItem()
        self.hud_length.setZValue(1000)
        self.scene().addItem(self.hud_length)
        self.hud_angle = QGraphicsTextItem()
        self.hud_angle.setZValue(1000)
        self.scene().addItem(self.hud_angle)
        self.hud_polar_info = QGraphicsTextItem()
        self.hud_polar_info.setZValue(1000)
        self.scene().addItem(self.hud_polar_info)

    def switch_tool(self, tool_name):
        if tool_name in self.tools:
            if self.current_tool:
                self.current_tool.deactivate()
            self._cleanup_tracking_huds()
            self.scene().clearSelection()
            self.current_tool = self.tools[tool_name]
            self.current_tool.activate()

    def _cleanup_tracking_huds(self):
        self.acquired_point = None
        self.polar_line.hide()
        self.tracking_line.hide()
        self.track_marker_h.hide()
        self.track_marker_v.hide()
        self.hud_length.hide()
        self.hud_angle.hide()
        self.hud_polar_info.hide()

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        lod = self.transform().m11() 
        grid_size = 10
        if lod < 0.2: grid_size = 50
        if lod < 0.04: grid_size = 250
        if lod < 0.008: grid_size = 1000
        major_grid_size = grid_size * 5
        
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        
        lines, major_lines = [], []
        for x in range(left, int(rect.right()), grid_size):
            if x % major_grid_size == 0: major_lines.append(QLineF(x, rect.top(), x, rect.bottom()))
            else: lines.append(QLineF(x, rect.top(), x, rect.bottom()))
                
        for y in range(top, int(rect.bottom()), grid_size):
            if y % major_grid_size == 0: major_lines.append(QLineF(rect.left(), y, rect.right(), y))
            else: lines.append(QLineF(rect.left(), y, rect.right(), y))
        
        pen = QPen(QColor(55, 55, 55), 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLines(lines)
        
        pen_major = QPen(QColor(85, 85, 85), 1)
        pen_major.setCosmetic(True)
        painter.setPen(pen_major)
        painter.drawLines(major_lines)
        
    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        
        selected_items = self.scene().selectedItems()
        if not selected_items: return
            
        lod = self.transform().m11()
        if lod <= 0: return
        grip_size = 8.0 / lod
        half_size = grip_size / 2.0
        
        pen = QPen(QColor(255, 255, 255), 1.0 / lod)
        pen.setCosmetic(True)
        painter.setPen(pen)
        
        for item in selected_items:
            if hasattr(item, 'get_grips'):
                hot_idx = getattr(item, 'hot_grip_index', -1)
                for i, p in enumerate(item.get_grips()):
                    if i == hot_idx: painter.setBrush(QBrush(QColor(255, 0, 0))) 
                    else: painter.setBrush(QBrush(QColor(0, 120, 215))) 
                    painter.drawRect(QRectF(p.x() - half_size, p.y() - half_size, grip_size, grip_size))

    def _get_snapped_endpoint(self, raw_point):
        snap_threshold = 10.0 / self.transform().m11() 
        closest_dist = float('inf')
        snapped_p = None

        for item in self.scene().items():
            # 只要实体有 get_grips 方法，并且不是系统辅助线，就纳入吸附检测
            if hasattr(item, 'get_grips') and item not in (self.polar_line, self.tracking_line, self.track_marker_h, self.track_marker_v):
                
                # 排除正在绘制中、还没落笔的临时直线和临时矩形
                if hasattr(self.current_tool, 'temp_line') and item == getattr(self.current_tool, 'temp_line', None):
                    continue
                if hasattr(self.current_tool, 'temp_rect') and item == getattr(self.current_tool, 'temp_rect', None):
                    continue
                
                # 【核心修复】：直接遍历图元自身的夹点作为吸附目标，不再强行调用 item.line()
                for p in item.get_grips():
                    dist = math.hypot(p.x() - raw_point.x(), p.y() - raw_point.y())
                    if dist < snap_threshold and dist < closest_dist:
                        closest_dist = dist
                        snapped_p = p
        return snapped_p

    def _calculate_global_snap(self, raw_point):
        final_point = QPointF(raw_point)
        snap_threshold_scene = 10.0 / self.transform().m11() 
        snapped_p = self._get_snapped_endpoint(raw_point)
        is_object_snapped = False
        
        if snapped_p:
            final_point = QPointF(snapped_p) 
            is_object_snapped = True
            self.acquired_point = QPointF(snapped_p)
            self.snap_marker.setPos(final_point)
            self.hud_snap_tip.setPos(final_point.x() + 8, final_point.y() + 8)
            self.snap_marker.show()
            self.hud_snap_tip.show()
        else:
            self.snap_marker.hide()
            self.hud_snap_tip.hide()

        ref_point = self.current_tool.get_reference_point()
        
        if not ref_point:
            self.polar_line.hide()
            self.tracking_line.hide()
            self.track_marker_h.hide()
            self.track_marker_v.hide()
            self.hud_length.hide()
            self.hud_angle.hide()
            self.hud_polar_info.hide()
            return final_point, 0.0

        snap_x = final_point.x()
        snap_y = final_point.y()
        is_polar_h = is_polar_v = False
        is_track_h = is_track_v = False
        polar_angle = track_angle = 0.0
        
        if not is_object_snapped:
            if self.acquired_point and self.acquired_point != ref_point:
                if math.hypot(snap_x - self.acquired_point.x(), snap_y - self.acquired_point.y()) > snap_threshold_scene:
                    dist_h_track = abs(snap_y - self.acquired_point.y())
                    dist_v_track = abs(snap_x - self.acquired_point.x())

                    if dist_h_track < snap_threshold_scene:
                        is_track_h = True
                        snap_y = self.acquired_point.y()
                        track_angle = 0.0 if snap_x >= self.acquired_point.x() else 180.0
                    elif dist_v_track < snap_threshold_scene:
                        is_track_v = True
                        snap_x = self.acquired_point.x()
                        track_angle = 90.0 if snap_y <= self.acquired_point.y() else 270.0

            dist_h_polar = abs(snap_y - ref_point.y())
            dist_v_polar = abs(snap_x - ref_point.x())

            if dist_h_polar < snap_threshold_scene:
                is_polar_h = True
                snap_y = ref_point.y()
                polar_angle = 0.0 if snap_x >= ref_point.x() else 180.0
            elif dist_v_polar < snap_threshold_scene:
                is_polar_v = True
                snap_x = ref_point.x()
                polar_angle = 90.0 if snap_y <= ref_point.y() else 270.0

            final_point.setX(snap_x)
            final_point.setY(snap_y)

        raw_length = math.hypot(final_point.x() - ref_point.x(), final_point.y() - ref_point.y())
        if is_polar_h or is_polar_v: snapped_angle = polar_angle
        else:
            raw_angle = math.degrees(math.atan2(-(final_point.y() - ref_point.y()), final_point.x() - ref_point.x()))
            snapped_angle = raw_angle if raw_angle >= 0 else raw_angle + 360

        if is_polar_h or is_polar_v:
            rad = math.radians(polar_angle)
            p_end_x = ref_point.x() + 10000 * math.cos(rad)
            p_end_y = ref_point.y() - 10000 * math.sin(rad)
            p_start_x = ref_point.x() - 10000 * math.cos(rad)
            p_start_y = ref_point.y() + 10000 * math.sin(rad)
            self.polar_line.setLine(QLineF(p_start_x, p_start_y, p_end_x, p_end_y))
            self.polar_line.show()
        else: self.polar_line.hide()
            
        if is_track_h or is_track_v:
            m_x, m_y = self.acquired_point.x(), self.acquired_point.y()
            cross_size = 5.0 / self.transform().m11()
            self.track_marker_h.setLine(m_x - cross_size, m_y, m_x + cross_size, m_y)
            self.track_marker_v.setLine(m_x, m_y - cross_size, m_x, m_y + cross_size)
            self.track_marker_h.show()
            self.track_marker_v.show()
            self.tracking_line.setLine(QLineF(m_x, m_y, final_point.x(), final_point.y()))
            self.tracking_line.show()
        else:
            self.tracking_line.hide()
            self.track_marker_h.hide()
            self.track_marker_v.hide()

        tool_buffer = self.current_tool.get_input_buffer()
        display_length = tool_buffer if tool_buffer else f"{raw_length:.4f}"
        hud_bg_color = "#a0a0a0"
        hud_text = f"极轴追踪: {display_length} &lt; {snapped_angle:.0f}°"
        
        if (is_polar_h or is_polar_v) and (is_track_h or is_track_v):
            hud_text = f"交点 | 极轴: &lt; {polar_angle:.0f}°, 端点: &lt; {track_angle:.0f}°"
            hud_bg_color = "#8b9dc3"
        elif is_polar_h or is_polar_v:
            hud_text = f"极轴: {display_length} &lt; {polar_angle:.0f}°"
        elif is_track_h or is_track_v:
            track_dist = math.hypot(final_point.x() - self.acquired_point.x(), final_point.y() - self.acquired_point.y())
            hud_text = f"延长线: {track_dist:.4f} &lt; {track_angle:.0f}°"

        if is_object_snapped or is_polar_h or is_polar_v or is_track_h or is_track_v:
            self.hud_length.setHtml(f"<div style='background-color:#0055ff; color:white; padding:2px 4px; border:1px solid white; font-family:Arial; font-size:12px;'>{display_length}</div>")
            self.hud_angle.setHtml(f"<div style='background-color:#c0c0c0; color:black; padding:2px 4px; border:1px solid black; font-family:Arial; font-size:12px;'>{snapped_angle:.0f}°</div>")
            self.hud_polar_info.setHtml(f"<div style='background-color:{hud_bg_color}; color:black; padding:2px 4px; border:1px solid black; font-family:Arial; font-size:12px;'>{hud_text}</div>")
            
            self.hud_length.setPos(final_point.x() - 60, final_point.y() - 25)
            self.hud_angle.setPos(final_point.x() + 15, final_point.y() + 15)
            self.hud_polar_info.setPos(final_point.x() + 50, final_point.y() + 15)
            
            self.hud_length.show()
            self.hud_angle.show()
            self.hud_polar_info.show()
        else:
            self.hud_length.hide()
            self.hud_angle.hide()
            self.hud_polar_info.hide()

        if hasattr(self.main_window, 'lbl_transform_info'):
            info_text = f" 当前坐标与尺寸提示  |  X: {final_point.x():.2f}   Y: {-final_point.y():.2f}   长度: {raw_length:.2f}   角度: {snapped_angle:.2f} "
            self.main_window.lbl_transform_info.setText(info_text)

        return final_point, snapped_angle

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor
        
        # 手动接管坐标缩放与平移
        mouse_pos = event.position().toPoint()
        old_scene_pos = self.mapToScene(mouse_pos)
        
        self.scale(zoom_factor, zoom_factor)
        
        new_scene_pos = self.mapToScene(mouse_pos)
        delta = new_scene_pos - old_scene_pos
        self.translate(delta.x(), delta.y())
        
        # 刷新画布和工具状态
        current_point = self.mapToScene(mouse_pos)
        final_point, snapped_angle = self._calculate_global_snap(current_point)
        
        class DummyEvent:
            def pos(self): return mouse_pos
            
        self.current_tool.mouseMoveEvent(DummyEvent(), final_point, snapped_angle)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
            
        self.setFocus() 
        current_point = self.mapToScene(event.pos())
        
        item = self.itemAt(event.pos())
        is_selectable = item and (item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        if is_selectable and not self._get_snapped_endpoint(current_point):
            super().mousePressEvent(event)
            return

        final_point, snapped_angle = self._calculate_global_snap(current_point)
        handled = self.current_tool.mousePressEvent(event, final_point, snapped_angle)
        if not handled:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning and self._pan_start_pos is not None:
            delta = event.pos() - self._pan_start_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start_pos = event.pos()
            event.accept()
            return

        self.last_cursor_point = self.mapToScene(event.pos())
        final_point, snapped_angle = self._calculate_global_snap(self.last_cursor_point)
        
        handled = self.current_tool.mouseMoveEvent(event, final_point, snapped_angle)
        if not handled:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.current_tool.activate() 
            event.accept()
            return
            
        final_point, snapped_angle = self._calculate_global_snap(self.mapToScene(event.pos()))
        handled = self.current_tool.mouseReleaseEvent(event, final_point, snapped_angle)
        if not handled:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo_stack.undo()
            self.scene().clearSelection()
            self._calculate_global_snap(self.last_cursor_point)
            return
        elif event.matches(QKeySequence.StandardKey.Redo):
            self.undo_stack.redo()
            self.scene().clearSelection()
            self._calculate_global_snap(self.last_cursor_point)
            return
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            for item in self.scene().items():
                if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable:
                    item.setSelected(True)
            return
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not self.current_tool.get_reference_point():
            selected = self.scene().selectedItems()
            if selected:
                cmd = CommandDeleteLines(self.scene(), selected)
                self.undo_stack.push(cmd)
                return
            
        handled = self.current_tool.keyPressEvent(event)
        if handled:
            self._calculate_global_snap(self.last_cursor_point)
        else:
            super().keyPressEvent(event)