# core/core_canvas.py
from PyQt6.QtWidgets import QGraphicsView, QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem, QGraphicsItem, QLabel
from PyQt6.QtCore import Qt, QLineF, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QPainter, QKeyEvent, QUndoStack, QUndoCommand, QKeySequence, QBrush
import math
import traceback

from utils.geom_engine import GeometryEngine
from core.core_items import SmartLineItem, SmartPolygonItem, SmartDimensionItem, SmartCircleItem, SmartPolylineItem

from managers.color_manager import ColorManager
from managers.layer_manager import LayerManager

# 导入所有工具
from tools.tool_select import SelectTool
from tools.tool_line import LineTool
from tools.tool_rect import RectTool
from tools.tool_offset import OffsetTool
from tools.tool_trim import TrimTool
from tools.tool_extend import ExtendTool
from tools.tool_break import BreakTool
from tools.tool_rotate import RotateTool
from tools.tool_mirror import MirrorTool
from tools.tool_move import MoveTool
from tools.tool_dimension import DimensionTool
from tools.tool_circle import CircleTool
from tools.tool_polyline import PolylineTool
from tools.tool_arc import ArcTool

class CommandPasteGeom(QUndoCommand):
    """复制粘贴对应的撤销栈封装"""
    def __init__(self, scene, data):
        super().__init__()
        self.scene = scene
        self.created_items = []
        for d in data:
            ItemClass = d['type']
            new_c = [(x + 50, y + 50) for x, y in d['coords']] 
            
            if ItemClass == SmartPolygonItem or ItemClass == SmartPolylineItem:
                item = ItemClass(new_c)
            elif ItemClass == SmartDimensionItem:
                item = ItemClass(new_c[0], new_c[1], new_c[2])
            elif ItemClass == SmartCircleItem:
                # 兼容圆的粘贴
                r = math.hypot(new_c[1][0]-new_c[0][0], new_c[1][1]-new_c[0][1])
                item = ItemClass(new_c[0], r)
            else:
                item = ItemClass(new_c[0], new_c[1])
                
            pen = QPen(QColor(255, 255, 255), 1)
            pen.setCosmetic(True)
            item.setPen(pen)
            self.created_items.append(item)
            
    def redo(self):
        self.scene.clearSelection()
        for item in self.created_items:
            if item not in self.scene.items(): self.scene.addItem(item)
            item.setSelected(True)
            
    def undo(self):
        for item in self.created_items:
            if item.scene() == self.scene:
                item.setSelected(False)
                self.scene.removeItem(item)

class HUDProxy:
    """【智能 HUD 代理】：分离顶部固定提示和跟随光标的极轴信息"""
    def __init__(self, canvas):
        self.canvas = canvas
        self.real_polar_item = QGraphicsTextItem()
        self.real_polar_item.setZValue(1000)
        self.real_polar_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.real_polar_item.hide()
        self.canvas.scene().addItem(self.real_polar_item)
        
        self.instruction_label = QLabel(self.canvas.viewport())
        self.instruction_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.instruction_label.setStyleSheet("background-color: transparent;")
        self.instruction_label.move(20, 20)
        self.instruction_label.hide()
        
    def show(self): pass 
    def hide(self): self.real_polar_item.hide()
    def hide_all(self):
        self.real_polar_item.hide()
        self.instruction_label.hide()
        
    def setHtml(self, html):
        if "极轴" in html or "延长线" in html or "交点" in html or "指定" in html or "距离" in html:
            self.real_polar_item.setHtml(html)
            self.real_polar_item.show()
        else:
            self.instruction_label.setText(html)
            self.instruction_label.show()
            self.instruction_label.adjustSize()
            
    def setPos(self, x, y=None):
        if y is None:
            y = x.y()
            x = x.x()
        self.real_polar_item.setPos(x, y)
        
    def toPlainText(self): return self.real_polar_item.toPlainText()


class CADGraphicsView(QGraphicsView):
    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window

        self.color_manager = ColorManager()
        self.layer_manager = LayerManager(self)
        
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
        self.clipboard_data = []
        
        self._init_global_ui_components()

        # 挂载新工具
        self.tools = {
            "选择": SelectTool(self),
            "直线": LineTool(self),
            "多段线": PolylineTool(self),
            "矩形": RectTool(self),
            "圆": CircleTool(self),
            "圆弧": ArcTool(self),
            "偏移": OffsetTool(self),
            "旋转": RotateTool(self),
            "镜像": MirrorTool(self),
            "修剪": TrimTool(self),
            "延伸": ExtendTool(self),
            "打断": BreakTool(self),
            "标注": DimensionTool(self)
        }
        self.current_tool = self.tools["直线"]
        self.current_tool.activate()

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
        self.snap_marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.snap_marker.hide()
        self.scene().addItem(self.snap_marker)
        
        self.hud_snap_tip = QGraphicsTextItem()
        self.hud_snap_tip.setZValue(2000)
        self.hud_snap_tip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.hud_snap_tip.hide()
        self.scene().addItem(self.hud_snap_tip)
        
        self.hud_length = QGraphicsTextItem()
        self.hud_length.setZValue(1000)
        self.hud_length.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.scene().addItem(self.hud_length)
        
        self.hud_angle = QGraphicsTextItem()
        self.hud_angle.setZValue(1000)
        self.hud_angle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.scene().addItem(self.hud_angle)
        
        self.hud_polar_info = HUDProxy(self)

    def switch_tool(self, tool_name):
        if tool_name in self.tools:
            if self.current_tool: self.current_tool.deactivate()
            self._cleanup_tracking_huds()
            self.current_tool = self.tools[tool_name]
            self.current_tool.activate()
            
            if hasattr(self.main_window, 'tool_actions'):
                for action in self.main_window.tool_actions.actions():
                    if action.text() == tool_name:
                        action.setChecked(True)
                        break

    def _cleanup_tracking_huds(self):
        self.acquired_point = None
        self.polar_line.hide()
        self.tracking_line.hide()
        self.track_marker_h.hide()
        self.track_marker_v.hide()
        self.hud_length.hide()
        self.hud_angle.hide()
        if hasattr(self, 'hud_polar_info'):
            if hasattr(self.hud_polar_info, 'hide_all'): self.hud_polar_info.hide_all()
            else: self.hud_polar_info.hide()
        self.snap_marker.hide()
        self.hud_snap_tip.hide()

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
        
        grip_size = 6.0 / lod 
        half_size = grip_size / 2.0
        hot_grip_size = 2.0 / lod 
        half_hot_size = hot_grip_size / 2.0
        
        pen = QPen(QColor(255, 255, 255), 1.0 / lod)
        pen.setCosmetic(True)
        painter.setPen(pen)
        
        for item in selected_items:
            # 兼容所有实体夹点渲染
            if getattr(item, 'is_smart_shape', False):
                hot_idx = getattr(item, 'hot_grip_index', -1)
                for i, (gx, gy) in enumerate(item.get_grips()):
                    if i == hot_idx:
                        painter.setBrush(QBrush(QColor(255, 0, 0)))
                        painter.drawRect(QRectF(gx - half_hot_size, gy - half_hot_size, hot_grip_size, hot_grip_size))
                    else:
                        painter.setBrush(QBrush(QColor(0, 120, 215))) 
                        painter.drawRect(QRectF(gx - half_size, gy - half_size, grip_size, grip_size))

    def _get_snapped_endpoint(self, raw_point):
        snap_threshold = 10.0 / self.transform().m11() 
        closest_dist = float('inf')
        snapped_p, marker_p = None, None
        snap_type = "端点"
        
        raw_x, raw_y = raw_point.x(), raw_point.y()
        valid_items = []
        active_tool = self.current_tool

        exclude_items, moving_grips = [], []
        base_point = None

        if isinstance(active_tool, SelectTool) and active_tool.is_moving and active_tool.move_start_pos:
            exclude_items = active_tool.move_items
            base_point = active_tool.move_start_pos
            for item in exclude_items: moving_grips.extend(item.get_grips())
        elif hasattr(active_tool, 'state') and active_tool.__class__.__name__ == 'MoveTool' and active_tool.state == 2 and active_tool.base_point:
            exclude_items = active_tool.target_items
            base_point = active_tool.base_point
            for item in exclude_items: moving_grips.extend(item.get_grips())

        for item in self.scene().items():
            if not item.isVisible() or item in exclude_items: continue 
            if getattr(item, 'is_smart_shape', False):
                if active_tool and hasattr(active_tool, 'temp_item') and item == getattr(active_tool, 'temp_item', None): continue
                valid_items.append(item)

        static_grips = []
        for item in valid_items: static_grips.extend(item.get_grips())
        
        # 【新增】支持多段线工具的临时点吸附
        if hasattr(active_tool, 'points') and active_tool.__class__.__name__ == 'PolylineTool':
            for pt in active_tool.points:
                static_grips.append(pt)

        # 捕捉优先级（按CAD标准）：
        # 1. 端点/夹点（最高优先级）
        # 2. 交点
        # 3. 最近点（最低优先级，只在没有其他捕捉时使用）
        
        # 第一步：收集所有可能的捕捉点
        endpoint_candidates = []
        intersection_candidates = []
        nearest_candidates = []
        
        # 1. 收集端点和夹点
        for gx, gy in static_grips:
            dist = math.hypot(gx - raw_x, gy - raw_y)
            if dist < snap_threshold:
                endpoint_candidates.append((dist, QPointF(gx, gy), QPointF(gx, gy), "端点"))

        if base_point and moving_grips:
            dx, dy = raw_x - base_point.x(), raw_y - base_point.y()
            for mgx, mgy in moving_grips:
                proj_x, proj_y = mgx + dx, mgy + dy
                for sgx, sgy in static_grips:
                    dist = math.hypot(proj_x - sgx, proj_y - sgy)
                    if dist < snap_threshold:
                        endpoint_candidates.append((
                            dist,
                            QPointF(sgx - mgx + base_point.x(), sgy - mgy + base_point.y()),
                            QPointF(sgx, sgy),
                            "对齐"
                        ))

        # 2. 收集交点
        for i in range(len(valid_items)):
            for j in range(i + 1, len(valid_items)):
                item1, item2 = valid_items[i], valid_items[j]
                if isinstance(item1, SmartDimensionItem) or isinstance(item2, SmartDimensionItem): continue
                if item1.boundingRect().intersects(item2.boundingRect()):
                    is_poly1 = isinstance(item1, (SmartPolygonItem, SmartCircleItem))
                    is_poly2 = isinstance(item2, (SmartPolygonItem, SmartCircleItem))
                    
                    coords1 = item1.get_geom_coords() if hasattr(item1, 'get_geom_coords') else item1.coords
                    coords2 = item2.get_geom_coords() if hasattr(item2, 'get_geom_coords') else item2.coords
                    
                    intersections = GeometryEngine.get_intersections(coords1, coords2, is_poly1, is_poly2)
                    for ix, iy in intersections:
                        dist = math.hypot(ix - raw_x, iy - raw_y)
                        if dist < snap_threshold:
                            intersection_candidates.append((dist, QPointF(ix, iy), QPointF(ix, iy), "交点"))

        # 3. 收集最近点（只在没有端点和交点时使用）
        for item in valid_items:
            if isinstance(item, SmartDimensionItem):
                continue
                
            nearest_pt = None
            
            # 直线的最近点
            if isinstance(item, SmartLineItem):
                p1, p2 = item.coords
                # 计算点到线段的垂直投影
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                length_sq = dx * dx + dy * dy
                if length_sq > 1e-10:
                    t = ((raw_x - p1[0]) * dx + (raw_y - p1[1]) * dy) / length_sq
                    t = max(0, min(1, t))  # 限制在线段范围内
                    nearest_pt = (p1[0] + t * dx, p1[1] + t * dy)
            
            # 圆的最近点
            elif isinstance(item, SmartCircleItem):
                cx, cy = item.center
                dx, dy = raw_x - cx, raw_y - cy
                dist_to_center = math.hypot(dx, dy)
                if dist_to_center > 1e-10:
                    # 圆上最近的点
                    nearest_pt = (cx + dx / dist_to_center * item.radius, 
                                 cy + dy / dist_to_center * item.radius)
            
            # 圆弧的最近点
            elif hasattr(item, 'geom_type') and item.geom_type == 'arc':
                cx, cy = item.center
                dx, dy = raw_x - cx, raw_y - cy
                dist_to_center = math.hypot(dx, dy)
                if dist_to_center > 1e-10:
                    # 计算鼠标相对圆心的角度
                    mouse_angle = math.degrees(math.atan2(cy - raw_y, raw_x - cx))
                    if mouse_angle < 0:
                        mouse_angle += 360
                    
                    # 检查角度是否在圆弧范围内
                    start_angle = item.start_angle
                    end_angle = item.end_angle
                    span = end_angle - start_angle
                    if span <= 0:
                        span += 360
                    
                    # 判断鼠标角度是否在圆弧范围内
                    angle_in_arc = False
                    if span < 360:
                        if start_angle <= end_angle:
                            angle_in_arc = start_angle <= mouse_angle <= end_angle
                        else:
                            angle_in_arc = mouse_angle >= start_angle or mouse_angle <= end_angle
                    else:
                        angle_in_arc = True
                    
                    if angle_in_arc:
                        # 在圆弧范围内，投影到圆弧上
                        angle_rad = math.radians(mouse_angle)
                        nearest_pt = (cx + item.radius * math.cos(angle_rad),
                                     cy - item.radius * math.sin(angle_rad))
            
            # 多段线的最近点
            elif isinstance(item, SmartPolylineItem):
                for i in range(len(item.coords) - 1):
                    p1, p2 = item.coords[i], item.coords[i + 1]
                    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                    length_sq = dx * dx + dy * dy
                    if length_sq > 1e-10:
                        t = ((raw_x - p1[0]) * dx + (raw_y - p1[1]) * dy) / length_sq
                        t = max(0, min(1, t))
                        seg_nearest = (p1[0] + t * dx, p1[1] + t * dy)
                        seg_dist = math.hypot(seg_nearest[0] - raw_x, seg_nearest[1] - raw_y)
                        if seg_dist < snap_threshold and seg_dist < closest_dist:
                            closest_dist = seg_dist
                            nearest_pt = seg_nearest
            
            if nearest_pt:
                dist = math.hypot(nearest_pt[0] - raw_x, nearest_pt[1] - raw_y)
                if dist < snap_threshold:
                    nearest_candidates.append((dist, QPointF(nearest_pt[0], nearest_pt[1]), QPointF(nearest_pt[0], nearest_pt[1]), "最近点"))

        # 按优先级选择捕捉点：端点 > 交点 > 最近点
        if endpoint_candidates:
            endpoint_candidates.sort(key=lambda x: x[0])
            _, snapped_p, marker_p, snap_type = endpoint_candidates[0]
            return snapped_p, snap_type, marker_p
        elif intersection_candidates:
            intersection_candidates.sort(key=lambda x: x[0])
            _, snapped_p, marker_p, snap_type = intersection_candidates[0]
            return snapped_p, snap_type, marker_p
        elif nearest_candidates:
            nearest_candidates.sort(key=lambda x: x[0])
            _, snapped_p, marker_p, snap_type = nearest_candidates[0]
            return snapped_p, snap_type, marker_p
        
        return None

    def _calculate_global_snap(self, raw_point):
        final_point = QPointF(raw_point)
        snap_threshold_scene = 10.0 / self.transform().m11() 
        
        snapped_res = self._get_snapped_endpoint(raw_point)
        snapped_p = snapped_res[0] if snapped_res else None
        snap_type = snapped_res[1] if snapped_res else "端点"
        marker_p = snapped_res[2] if snapped_res else None
        
        is_object_snapped = False
        lod = self.transform().m11()
        if lod <= 0: lod = 1.0
        
        if snapped_p and marker_p:
            final_point = QPointF(snapped_p)
            is_object_snapped = True
            self.acquired_point = QPointF(marker_p)
            self.snap_marker.setPos(marker_p)
            self.hud_snap_tip.setHtml(f"<div style='background-color:#555555; color:white; padding:1px 3px; font-size:11px;'>{snap_type}</div>")
            self.hud_snap_tip.setPos(marker_p.x() + 8 / lod, marker_p.y() + 8 / lod)
            self.snap_marker.show()
            self.hud_snap_tip.show()
        else:
            self.snap_marker.hide(); self.hud_snap_tip.hide()

        ref_point = self.current_tool.get_reference_point()
        
        if not ref_point:
            self.polar_line.hide(); self.tracking_line.hide()
            self.track_marker_h.hide(); self.track_marker_v.hide()
            self.hud_length.hide(); self.hud_angle.hide(); self.hud_polar_info.hide() 
            return final_point, 0.0

        snap_x, snap_y = final_point.x(), final_point.y()
        is_polar_h = is_polar_v = is_track_h = is_track_v = False
        polar_angle = track_angle = 0.0
        
        if not is_object_snapped:
            if self.acquired_point and self.acquired_point != ref_point:
                if math.hypot(snap_x - self.acquired_point.x(), snap_y - self.acquired_point.y()) > snap_threshold_scene:
                    dist_h_track = abs(snap_y - self.acquired_point.y())
                    dist_v_track = abs(snap_x - self.acquired_point.x())

                    if dist_h_track < snap_threshold_scene:
                        is_track_h = True; snap_y = self.acquired_point.y(); track_angle = 0.0 if snap_x >= self.acquired_point.x() else 180.0
                    elif dist_v_track < snap_threshold_scene:
                        is_track_v = True; snap_x = self.acquired_point.x(); track_angle = 90.0 if snap_y <= self.acquired_point.y() else 270.0

            dist_h_polar = abs(snap_y - ref_point.y()); dist_v_polar = abs(snap_x - ref_point.x())

            if dist_h_polar < snap_threshold_scene:
                is_polar_h = True; snap_y = ref_point.y(); polar_angle = 0.0 if snap_x >= ref_point.x() else 180.0
            elif dist_v_polar < snap_threshold_scene:
                is_polar_v = True; snap_x = ref_point.x(); polar_angle = 90.0 if snap_y <= ref_point.y() else 270.0

            final_point.setX(snap_x); final_point.setY(snap_y)

        # 计算角度：即使发生了对象捕捉，如果极轴捕捉也激活，优先使用极轴角度
        # 检查是否应该使用极轴角度（即使没有调整坐标，只要鼠标接近极轴线）
        if not (is_polar_h or is_polar_v):
            dist_h_polar = abs(final_point.y() - ref_point.y())
            dist_v_polar = abs(final_point.x() - ref_point.x())
            if dist_h_polar < snap_threshold_scene:
                is_polar_h = True
                polar_angle = 0.0 if final_point.x() >= ref_point.x() else 180.0
            elif dist_v_polar < snap_threshold_scene:
                is_polar_v = True
                polar_angle = 90.0 if final_point.y() <= ref_point.y() else 270.0
        
        raw_length = math.hypot(final_point.x() - ref_point.x(), final_point.y() - ref_point.y())
        if is_polar_h or is_polar_v: snapped_angle = polar_angle
        else:
            raw_angle = math.degrees(math.atan2(-(final_point.y() - ref_point.y()), final_point.x() - ref_point.x()))
            snapped_angle = raw_angle if raw_angle >= 0 else raw_angle + 360

        if is_polar_h or is_polar_v:
            rad = math.radians(polar_angle)
            p_end_x = ref_point.x() + 10000 * math.cos(rad); p_end_y = ref_point.y() - 10000 * math.sin(rad)
            p_start_x = ref_point.x() - 10000 * math.cos(rad); p_start_y = ref_point.y() + 10000 * math.sin(rad)
            self.polar_line.setLine(QLineF(p_start_x, p_start_y, p_end_x, p_end_y)); self.polar_line.show()
        else: self.polar_line.hide()
            
        if is_track_h or is_track_v:
            m_x, m_y = self.acquired_point.x(), self.acquired_point.y(); cross_size = 5.0 / lod
            self.track_marker_h.setLine(m_x - cross_size, m_y, m_x + cross_size, m_y)
            self.track_marker_v.setLine(m_x, m_y - cross_size, m_x, m_y + cross_size)
            self.track_marker_h.show(); self.track_marker_v.show()
            self.tracking_line.setLine(QLineF(m_x, m_y, final_point.x(), final_point.y())); self.tracking_line.show()
        else:
            self.tracking_line.hide(); self.track_marker_h.hide(); self.track_marker_v.hide()

        tool_buffer = self.current_tool.get_input_buffer()
        display_length = tool_buffer if tool_buffer else f"{raw_length:.4f}"
        hud_bg_color = "#a0a0a0"
        hud_text = f"极轴追踪: {display_length} < {snapped_angle:.0f}°"
        
        if (is_polar_h or is_polar_v) and (is_track_h or is_track_v):
            hud_text = f"交点 | 极轴: < {polar_angle:.0f}°, 端点: < {track_angle:.0f}°"; hud_bg_color = "#8b9dc3"
        elif is_polar_h or is_polar_v: hud_text = f"极轴: {display_length} < {polar_angle:.0f}°"
        elif is_track_h or is_track_v:
            track_dist = math.hypot(final_point.x() - self.acquired_point.x(), final_point.y() - self.acquired_point.y())
            hud_text = f"延长线: {track_dist:.4f} < {track_angle:.0f}°"

        if is_object_snapped or is_polar_h or is_polar_v or is_track_h or is_track_v:
            self.hud_length.setHtml(f"<div style='background-color:#0055ff; color:white; padding:2px 4px; border:1px solid white; font-family:Arial; font-size:12px;'>{display_length}</div>")
            self.hud_angle.setHtml(f"<div style='background-color:#c0c0c0; color:black; padding:2px 4px; border:1px solid black; font-family:Arial; font-size:12px;'>{snapped_angle:.0f}°</div>")
            
            anchor_p = marker_p if (is_object_snapped and marker_p) else final_point
            self.hud_length.setPos(anchor_p.x() - 60 / lod, anchor_p.y() - 25 / lod)
            self.hud_angle.setPos(anchor_p.x() + 15 / lod, anchor_p.y() + 15 / lod)
            
            self.hud_polar_info.setHtml(f"<div style='background-color:{hud_bg_color}; color:black; padding:2px 4px; border:1px solid black; font-family:Arial; font-size:12px;'>{hud_text}</div>")
            self.hud_polar_info.setPos(anchor_p.x() + 50 / lod, anchor_p.y() + 15 / lod)
            
            self.hud_length.show(); self.hud_angle.show()
        else:
            self.hud_length.hide(); self.hud_angle.hide(); self.hud_polar_info.hide()

        if hasattr(self.main_window, 'lbl_transform_info'):
            info_text = f" 当前坐标与尺寸提示  |  X: {final_point.x():.2f}   Y: {-final_point.y():.2f}   长度: {raw_length:.2f}   角度: {snapped_angle:.2f} "
            self.main_window.lbl_transform_info.setText(info_text)
        return final_point, snapped_angle

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
            if self.current_tool: self.current_tool.mouseMoveEvent(DummyEvent(), final_point, snapped_angle)
        except Exception as e: traceback.print_exc()

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.MiddleButton:
                self._is_panning = True; self._pan_start_pos = event.pos(); self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return
            self.setFocus() 
            current_point = self.mapToScene(event.pos())
            final_point, snapped_angle = self._calculate_global_snap(current_point)
            handled = False
            if self.current_tool: handled = self.current_tool.mousePressEvent(event, final_point, snapped_angle)
            if not handled: super().mousePressEvent(event)
        except Exception as e: traceback.print_exc()

    def mouseMoveEvent(self, event):
        try:
            if self._is_panning and self._pan_start_pos is not None:
                delta = event.pos() - self._pan_start_pos
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
                self._pan_start_pos = event.pos(); event.accept(); return
            self.last_cursor_point = self.mapToScene(event.pos())
            final_point, snapped_angle = self._calculate_global_snap(self.last_cursor_point)
            handled = False
            if self.current_tool: handled = self.current_tool.mouseMoveEvent(event, final_point, snapped_angle)
            if not handled: super().mouseMoveEvent(event)
        except Exception as e: traceback.print_exc()

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.MiddleButton:
                self._is_panning = False
                if self.current_tool: self.current_tool.activate() 
                event.accept(); return
            final_point, snapped_angle = self._calculate_global_snap(self.mapToScene(event.pos()))
            handled = False
            if self.current_tool: handled = self.current_tool.mouseReleaseEvent(event, final_point, snapped_angle)
            if not handled: super().mouseReleaseEvent(event)
        except Exception as e: traceback.print_exc()

    def keyPressEvent(self, event: QKeyEvent):
        try:
            if event.matches(QKeySequence.StandardKey.Copy):
                selected = self.scene().selectedItems()
                self.clipboard_data.clear()
                for item in selected:
                    if getattr(item, 'is_smart_shape', False):
                        self.clipboard_data.append({'type': type(item), 'coords': list(item.coords)})
                return
            elif event.matches(QKeySequence.StandardKey.Paste):
                if self.clipboard_data:
                    cmd = CommandPasteGeom(self.scene(), self.clipboard_data); self.undo_stack.push(cmd)
                return
            elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_R:
                self.switch_tool("旋转"); return
            if event.matches(QKeySequence.StandardKey.Undo):
                self.undo_stack.undo(); self.scene().clearSelection(); self._calculate_global_snap(self.last_cursor_point); return
            elif event.matches(QKeySequence.StandardKey.Redo):
                self.undo_stack.redo(); self.scene().clearSelection(); self._calculate_global_snap(self.last_cursor_point); return
            elif event.matches(QKeySequence.StandardKey.SelectAll):
                for item in self.scene().items():
                    if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable: item.setSelected(True)
                return
            elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if self.current_tool and not self.current_tool.get_reference_point():
                    selected = self.scene().selectedItems()
                    if selected:
                        for item in selected:
                            if item in self.scene().items():
                                item.setSelected(False); self.scene().removeItem(item)
                        return
            handled = False
            if self.current_tool: handled = self.current_tool.keyPressEvent(event)
            if handled: self._calculate_global_snap(self.last_cursor_point)
            else: super().keyPressEvent(event)
        except Exception as e: traceback.print_exc()