# core/core_canvas.py
from PyQt6.QtWidgets import QGraphicsView, QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QLineF, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QPainter, QKeyEvent, QUndoStack, QUndoCommand, QKeySequence, QBrush
import math
import traceback  # 引入全局防崩溃追踪

from utils.geom_engine import GeometryEngine
from core.core_items import SmartLineItem, SmartPolygonItem

from managers.color_manager import ColorManager
from managers.layer_manager import LayerManager

# 导入 V2.0 重写后的工具
from tools.tool_select import SelectTool
from tools.tool_line import LineTool
from tools.tool_rect import RectTool
from tools.tool_offset import OffsetTool
from tools.tool_trim import TrimTool
from tools.tool_extend import ExtendTool
from tools.tool_break import BreakTool
# 导入新增的变换工具
from tools.tool_rotate import RotateTool
from tools.tool_mirror import MirrorTool

class CommandPasteGeom(QUndoCommand):
    """复制粘贴对应的撤销栈封装"""
    def __init__(self, scene, data):
        super().__init__()
        self.scene = scene
        self.created_items = []
        for d in data:
            ItemClass = d['type']
            # 粘贴时默认向右下偏移 50 像素，方便看清
            new_c = [(x + 50, y + 50) for x, y in d['coords']] 
            item = ItemClass(new_c) if ItemClass == SmartPolygonItem else ItemClass(new_c[0], new_c[1])
            pen = QPen(QColor(255, 255, 255), 1)
            pen.setCosmetic(True)
            item.setPen(pen)
            self.created_items.append(item)
            
    def redo(self):
        self.scene.clearSelection()
        for item in self.created_items:
            if item not in self.scene.items():
                self.scene.addItem(item)
            item.setSelected(True)
            
    def undo(self):
        for item in self.created_items:
            if item.scene() == self.scene:
                item.setSelected(False)
                self.scene.removeItem(item)

class CADGraphicsView(QGraphicsView):
    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window



        # 【图层系统核心挂载点】
        self.layer_manager = LayerManager(self)
        self.color_manager = ColorManager()
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) 
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setStyleSheet("background-color: transparent;")
        self.setBackgroundBrush(QColor("#222222"))
        
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.undo_stack = QUndoStack(self)
        
        self._is_panning = False
        self._pan_start_pos = None
        self.last_cursor_point = QPointF(0, 0)
        self.acquired_point = None 
        
        # 剪贴板数据存储区
        self.clipboard_data = []
        
        # 1. 初始化追踪与 HUD 组件
        self._init_global_ui_components()

        # 2. 注册 V2.0 工具
        self.tools = {
            "选择": SelectTool(self),
            "直线": LineTool(self),
            "矩形": RectTool(self),
            "偏移": OffsetTool(self),
            "旋转": RotateTool(self),
            "镜像": MirrorTool(self),
            "修剪": TrimTool(self),
            "延伸": ExtendTool(self),
            "打断": BreakTool(self)
        }
        self.current_tool = self.tools["直线"]
        self.current_tool.activate()

    def _init_global_ui_components(self):
        """初始化极轴追踪线、十字光标标靶和浮动数据显示"""
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
        self.hud_snap_tip.setHtml("<div style='background-color:#555555; color:white; padding:1px 3px; font-size:11px;'>捕捉</div>")
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
        self.snap_marker.hide()
        self.hud_snap_tip.hide()

    def drawBackground(self, painter, rect):
        """自适应网格绘制"""
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
        """渲染选中的夹点 (适配 V2.0 SmartItems)"""
        super().drawForeground(painter, rect)
        selected_items = self.scene().selectedItems()
        if not selected_items: return
            
        lod = self.transform().m11()
        if lod <= 0: return
        
        grip_size = 6.0 / lod 
        half_size = grip_size / 2.0
        
        hot_grip_size = 2.0 / lod 
        half_hot_size = hot_grip_size / 2.0
        
        pen = QPen(QColor(255, 255, 255), 1.0 / lod)
        pen.setCosmetic(True)
        painter.setPen(pen)
        
        for item in selected_items:
            if isinstance(item, (SmartLineItem, SmartPolygonItem)):
                hot_idx = getattr(item, 'hot_grip_index', -1)
                for i, (gx, gy) in enumerate(item.get_grips()):
                    if i == hot_idx:
                        painter.setBrush(QBrush(QColor(255, 0, 0)))
                        painter.drawRect(QRectF(gx - half_hot_size, gy - half_hot_size, hot_grip_size, hot_grip_size))
                    else:
                        painter.setBrush(QBrush(QColor(0, 120, 215))) 
                        painter.drawRect(QRectF(gx - half_size, gy - half_size, grip_size, grip_size))

    def _get_snapped_endpoint(self, raw_point):
        """【V2.0 核心引擎】：全局交点与夹点捕捉"""
        snap_threshold = 10.0 / self.transform().m11() 
        closest_dist = float('inf')
        snapped_p = None
        snap_type = "端点"
        
        raw_x, raw_y = raw_point.x(), raw_point.y()
        valid_items = []

        # 1. 筛选有效的数学实体
        for item in self.scene().items():
            if isinstance(item, (SmartLineItem, SmartPolygonItem)):
                # 排除正在绘制的临时图形
                if self.current_tool and hasattr(self.current_tool, 'temp_item') and item == getattr(self.current_tool, 'temp_item', None):
                    continue
                valid_items.append(item)

        # 2. 基础捕捉：端点、中点、角点
        for item in valid_items:
            for gx, gy in item.get_grips():
                dist = math.hypot(gx - raw_x, gy - raw_y)
                if dist < snap_threshold and dist < closest_dist:
                    closest_dist = dist
                    snapped_p = QPointF(gx, gy)
                    snap_type = "端点"

        # 3. 高级捕捉：全局真实相交点 (唤醒 Shapely 内核)
        for i in range(len(valid_items)):
            for j in range(i + 1, len(valid_items)):
                item1, item2 = valid_items[i], valid_items[j]
                
                if item1.boundingRect().intersects(item2.boundingRect()):
                    is_poly1 = isinstance(item1, SmartPolygonItem)
                    is_poly2 = isinstance(item2, SmartPolygonItem)
                    
                    intersections = GeometryEngine.get_intersections(
                        item1.coords, item2.coords, is_poly1, is_poly2
                    )
                    
                    for ix, iy in intersections:
                        dist = math.hypot(ix - raw_x, iy - raw_y)
                        if dist < snap_threshold and dist < closest_dist:
                            closest_dist = dist
                            snapped_p = QPointF(ix, iy)
                            snap_type = "交点"

        return snapped_p, snap_type

    def _calculate_global_snap(self, raw_point):
        """保留完美的全局极轴追踪、延长线吸附与 HUD 显示系统"""
        final_point = QPointF(raw_point)
        snap_threshold_scene = 10.0 / self.transform().m11() 
        
        snapped_res = self._get_snapped_endpoint(raw_point)
        snapped_p = snapped_res[0] if snapped_res else None
        snap_type = snapped_res[1] if snapped_res else "端点"
        
        is_object_snapped = False
        
        if snapped_p:
            final_point = QPointF(snapped_p) 
            is_object_snapped = True
            self.acquired_point = QPointF(snapped_p)
            self.snap_marker.setPos(final_point)
            self.hud_snap_tip.setHtml(f"<div style='background-color:#555555; color:white; padding:1px 3px; font-size:11px;'>{snap_type}</div>")
            self.hud_snap_tip.setPos(final_point.x() + 8, final_point.y() + 8)
            self.snap_marker.show()
            self.hud_snap_tip.show()
        else:
            self.snap_marker.hide()
            self.hud_snap_tip.hide()

        ref_point = self.current_tool.get_reference_point()
        
        if not ref_point:
            self._cleanup_tracking_huds()
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

        # 画极轴线
        if is_polar_h or is_polar_v:
            rad = math.radians(polar_angle)
            p_end_x = ref_point.x() + 10000 * math.cos(rad)
            p_end_y = ref_point.y() - 10000 * math.sin(rad)
            p_start_x = ref_point.x() - 10000 * math.cos(rad)
            p_start_y = ref_point.y() + 10000 * math.sin(rad)
            self.polar_line.setLine(QLineF(p_start_x, p_start_y, p_end_x, p_end_y))
            self.polar_line.show()
        else: self.polar_line.hide()
            
        # 画追踪线
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

        # HUD 信息更新
        tool_buffer = self.current_tool.get_input_buffer()
        display_length = tool_buffer if tool_buffer else f"{raw_length:.4f}"
        hud_bg_color = "#a0a0a0"
        hud_text = f"极轴追踪: {display_length} < {snapped_angle:.0f}°"
        
        if (is_polar_h or is_polar_v) and (is_track_h or is_track_v):
            hud_text = f"交点 | 极轴: < {polar_angle:.0f}°, 端点: < {track_angle:.0f}°"
            hud_bg_color = "#8b9dc3"
        elif is_polar_h or is_polar_v:
            hud_text = f"极轴: {display_length} < {polar_angle:.0f}°"
        elif is_track_h or is_track_v:
            track_dist = math.hypot(final_point.x() - self.acquired_point.x(), final_point.y() - self.acquired_point.y())
            hud_text = f"延长线: {track_dist:.4f} < {track_angle:.0f}°"

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

    # ================= 鼠标与键盘事件分发 (全局防火墙) =================
    def wheelEvent(self, event):
        try:
            zoom_in_factor = 1.15
            zoom_out_factor = 1.0 / zoom_in_factor
            zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor
            mouse_pos = event.position().toPoint()
            old_scene_pos = self.mapToScene(mouse_pos)
            
            self.scale(zoom_factor, zoom_factor)
            new_scene_pos = self.mapToScene(mouse_pos)
            delta = new_scene_pos - old_scene_pos
            self.translate(delta.x(), delta.y())
            
            current_point = self.mapToScene(mouse_pos)
            final_point, snapped_angle = self._calculate_global_snap(current_point)
            
            class DummyEvent:
                def pos(self): return mouse_pos
            if self.current_tool:
                self.current_tool.mouseMoveEvent(DummyEvent(), final_point, snapped_angle)
        except Exception as e:
            print(f"【系统级防火墙】拦截到滚轮缩放崩溃: {e}")
            traceback.print_exc()

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.MiddleButton:
                self._is_panning = True
                self._pan_start_pos = event.pos()
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
                
            self.setFocus() 
            current_point = self.mapToScene(event.pos())
            final_point, snapped_angle = self._calculate_global_snap(current_point)
            
            handled = False
            if self.current_tool:
                handled = self.current_tool.mousePressEvent(event, final_point, snapped_angle)
                
            if not handled:
                super().mousePressEvent(event)
        except Exception as e:
            print(f"【系统级防火墙】拦截到鼠标按下崩溃: {e}")
            traceback.print_exc()

    def mouseMoveEvent(self, event):
        try:
            if self._is_panning and self._pan_start_pos is not None:
                delta = event.pos() - self._pan_start_pos
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
                self._pan_start_pos = event.pos()
                event.accept()
                return

            self.last_cursor_point = self.mapToScene(event.pos())
            final_point, snapped_angle = self._calculate_global_snap(self.last_cursor_point)
            
            handled = False
            if self.current_tool:
                handled = self.current_tool.mouseMoveEvent(event, final_point, snapped_angle)
                
            if not handled:
                super().mouseMoveEvent(event)
        except Exception as e:
            print(f"【系统级防火墙】拦截到鼠标移动崩溃: {e}")
            traceback.print_exc()

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.MiddleButton:
                self._is_panning = False
                if self.current_tool: 
                    self.current_tool.activate() 
                event.accept()
                return
                
            final_point, snapped_angle = self._calculate_global_snap(self.mapToScene(event.pos()))
            
            handled = False
            if self.current_tool:
                handled = self.current_tool.mouseReleaseEvent(event, final_point, snapped_angle)
                
            if not handled:
                super().mouseReleaseEvent(event)
        except Exception as e:
            print(f"【系统级防火墙】拦截到鼠标释放崩溃: {e}")
            traceback.print_exc()

    def keyPressEvent(self, event: QKeyEvent):
        try:
            # ================= [快捷键逻辑] =================
            if event.matches(QKeySequence.StandardKey.Copy):
                selected = self.scene().selectedItems()
                self.clipboard_data.clear()
                for item in selected:
                    if isinstance(item, (SmartLineItem, SmartPolygonItem)):
                        self.clipboard_data.append({'type': type(item), 'coords': list(item.coords)})
                return
                
            elif event.matches(QKeySequence.StandardKey.Paste):
                if self.clipboard_data:
                    cmd = CommandPasteGeom(self.scene(), self.clipboard_data)
                    self.undo_stack.push(cmd)
                return
                
            elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_R:
                self.switch_tool("旋转")
                return

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
            elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if self.current_tool and not self.current_tool.get_reference_point():
                    selected = self.scene().selectedItems()
                    if selected:
                        for item in selected:
                            if item in self.scene().items():
                                item.setSelected(False)
                                self.scene().removeItem(item)
                        return
                
            handled = False
            if self.current_tool:
                handled = self.current_tool.keyPressEvent(event)
                
            if handled:
                self._calculate_global_snap(self.last_cursor_point)
            else:
                super().keyPressEvent(event)
        except Exception as e:
            print(f"【系统级防火墙】拦截到键盘敲击崩溃: {e}")
            traceback.print_exc()