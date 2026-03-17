# tools/tool_mirror.py
import math
import copy
from tools.base_tool import BaseTool
from core.core_items import (
    SmartLineItem, SmartPolygonItem, SmartDimensionItem, 
    SmartCircleItem, SmartPolylineItem, SmartArcItem,
    SmartEllipseItem, SmartSplineItem, SmartTextItem,
    SmartOrthogonalDimensionItem, SmartLeaderItem,
    SmartRadiusDimensionItem, SmartAngleDimensionItem,
    SmartArcLengthDimensionItem
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem, 
    QGraphicsPathItem, QGraphicsRectItem
)
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPen, QColor, QUndoCommand, QPolygonF, QPainterPath, QBrush, QTransform

class CommandMirrorGeom(QUndoCommand):
    def __init__(self, scene, mirror_data, layer_manager):
        super().__init__()
        self.scene = scene
        self.mirror_data = mirror_data 
        self.layer_manager = layer_manager
        self.created_items = []
        
        for original_item, new_data in self.mirror_data:
            ItemClass = type(original_item)
            
            # 支持 V2.0 全系图形的镜像重构分发
            if ItemClass == SmartArcItem: 
                new_item = ItemClass(new_data['center'], new_data['radius'], new_data['sa'], new_data['ea'])
            elif ItemClass == SmartEllipseItem:
                new_item = ItemClass(new_data['center'], new_data['rx'], new_data['ry'], new_data['rotation_angle'])
            elif ItemClass == SmartArcLengthDimensionItem:
                new_item = ItemClass(new_data['center'], new_data['radius'], new_data['sa'], new_data['ea'], new_data['offset_pt'])
            elif ItemClass in (SmartPolygonItem, SmartSplineItem): 
                new_item = ItemClass(new_data)
            elif ItemClass == SmartPolylineItem:
                # 镜像多段线时，如果有包含圆弧（凸度），则必须将凸度取反
                segs = []
                if getattr(original_item, 'segments', None):
                    segs = copy.deepcopy(original_item.segments)
                    for seg in segs:
                        if 'bulge' in seg:
                            seg['bulge'] = -seg['bulge']
                new_item = ItemClass(new_data, segments=segs)
            elif ItemClass in (SmartDimensionItem, SmartOrthogonalDimensionItem): 
                new_item = ItemClass(new_data[0], new_data[1], new_data[2])
            elif ItemClass == SmartAngleDimensionItem:
                new_item = ItemClass(new_data[0], new_data[1], new_data[2], new_data[3])
            elif ItemClass == SmartRadiusDimensionItem:
                new_item = ItemClass(new_data[0], new_data[1], original_item.prefix)
            elif ItemClass == SmartCircleItem:
                new_item = ItemClass(new_data[0], original_item.radius)
            elif ItemClass == SmartLeaderItem:
                new_item = ItemClass(new_data[0], new_data[1])
                new_item.text_item.setPlainText(original_item.text_item.toPlainText())
            elif ItemClass == SmartTextItem:
                new_item = ItemClass(original_item.toPlainText(), new_data[0])
            else: 
                # Fallback For Line
                new_item = ItemClass(new_data[0], new_data[1])
            
            pen = QPen(original_item.pen().color(), 1, original_item.pen().style())
            pen.setCosmetic(True)
            new_item.setPen(pen)
            
            self.layer_manager.copy_layer_props(new_item, original_item)
            self.created_items.append(new_item)
            
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


class MirrorTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.target_items = []
        self.p1 = None
        self.p2 = None
        self.ghost_items = []
        self.mirror_line_ghost = None
        self.state = 0 
        self.selection_box = None
        self.start_point = None

    def get_reference_point(self): 
        return QPointF(*self.p1) if self.state == 2 else None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.state = 0
        self.p1 = None
        self.p2 = None
        self._cleanup_ghosts()
        
        selected = self.canvas.scene().selectedItems() if self.canvas.scene() else []
        self.target_items = [item for item in selected if getattr(item, 'is_smart_shape', False)]
        if self.target_items: 
            self.state = 1
        self._update_hud()

    def deactivate(self):
        self._cleanup_ghosts()
        for item in self.target_items: 
            item.setSelected(False)
        self.target_items.clear()
        
        if self.selection_box: 
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
            
        if hasattr(self.canvas, '_cleanup_tracking_huds'): 
            self.canvas._cleanup_tracking_huds()

    def _cleanup_ghosts(self):
        for ghost_dict in self.ghost_items:
            if ghost_dict['ghost'].scene(): 
                self.canvas.scene().removeItem(ghost_dict['ghost'])
        self.ghost_items.clear()
        
        if self.mirror_line_ghost and self.mirror_line_ghost.scene():
            self.canvas.scene().removeItem(self.mirror_line_ghost)
            self.mirror_line_ghost = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): 
            return
            
        self.canvas.hud_polar_info.show()
        if self.state == 0: 
            text, color = "镜像: 框选或点击要镜像的对象 (选完按右键或回车确认)", "#5bc0de"
        elif self.state == 1: 
            text, color = "镜像: 指定镜像线的【第一点】", "#f0ad4e"
        elif self.state == 2: 
            text, color = "镜像: 指定镜像线的【第二点】", "#5cb85c"
            
        self.canvas.hud_polar_info.setHtml(
            f"<div style='background-color:{color}; color:white; padding:4px 8px; "
            f"border-radius:2px; font-family:Arial; font-size:12px;'>🪞 {text}</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _update_preview(self, p2):
        if not self.target_items or not self.p1: 
            return
            
        x1, y1 = self.p1
        x2, y2 = p2.x(), p2.y()
        
        if not self.mirror_line_ghost:
            self.mirror_line_ghost = QGraphicsLineItem()
            pen_line = QPen(QColor(0, 255, 255, 150), 1, Qt.PenStyle.DashDotLine)
            pen_line.setCosmetic(True)
            self.mirror_line_ghost.setPen(pen_line)
            self.canvas.scene().addItem(self.mirror_line_ghost)
            
        self.mirror_line_ghost.setLine(QLineF(x1, y1, x2, y2))

        if not self.ghost_items:
            pen = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            for item in self.target_items:
                ghost = QGraphicsPathItem()
                ghost.setPen(pen)
                self.canvas.scene().addItem(ghost)
                self.ghost_items.append({
                    'item': item, 
                    'ghost': ghost, 
                    'type': getattr(item, 'geom_type', 'unknown')
                })

        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx*dx + dy*dy
        
        mirror_a = math.degrees(math.atan2(-dy, dx)) if length_sq > 1e-6 else 0
        if mirror_a < 0: 
            mirror_a += 360
            
        # 提取通用的坐标点求镜像函数
        def get_mirror_pt(px, py):
            if length_sq < 1e-6: return px, py
            t = ((px - x1)*dx + (py - y1)*dy) / length_sq
            proj_x = x1 + t*dx
            proj_y = y1 + t*dy
            return 2*proj_x - px, 2*proj_y - py
        
        for data in self.ghost_items:
            item = data['item']
            ghost = data['ghost']
            g_type = data['type']
            path = QPainterPath()
            
            if g_type == 'arc':
                nx, ny = get_mirror_pt(*item.center)
                new_sa = (2 * mirror_a - item.end_angle) % 360
                new_ea = (2 * mirror_a - item.start_angle) % 360
                span = new_ea - new_sa
                if span <= 0: span += 360
                path.arcMoveTo(QRectF(nx-item.radius, ny-item.radius, 2*item.radius, 2*item.radius), new_sa)
                path.arcTo(QRectF(nx-item.radius, ny-item.radius, 2*item.radius, 2*item.radius), new_sa, span)
                
            elif g_type == 'ellipse':
                nx, ny = get_mirror_pt(*item.center)
                new_rot = (2 * mirror_a - item.rotation_angle) % 360
                temp_path = QPainterPath()
                temp_path.addEllipse(QRectF(-item.rx, -item.ry, 2*item.rx, 2*item.ry))
                trans = QTransform()
                trans.translate(nx, ny)
                trans.rotate(-new_rot)
                path = trans.map(temp_path)
                
            elif g_type == 'arclen_dim':
                nx, ny = get_mirror_pt(*item.coords[0])
                off_nx, off_ny = get_mirror_pt(*item.coords[1])
                dim_radius = math.hypot(off_nx - nx, off_ny - ny)
                new_sa = (2 * mirror_a - item.end_angle) % 360
                new_ea = (2 * mirror_a - item.start_angle) % 360
                span = new_ea - new_sa
                if span <= 0: span += 360
                path.arcMoveTo(QRectF(nx-dim_radius, ny-dim_radius, 2*dim_radius, 2*dim_radius), new_sa)
                path.arcTo(QRectF(nx-dim_radius, ny-dim_radius, 2*dim_radius, 2*dim_radius), new_sa, span)

            else:
                new_c = [get_mirror_pt(x, y) for x, y in item.coords]
                if not new_c: continue
                
                if g_type in ('line', 'leader', 'rad_dim'): 
                    path.moveTo(QPointF(*new_c[0]))
                    path.lineTo(QPointF(*new_c[1]))
                elif g_type in ('poly', 'polyline', 'spline'):
                    path.moveTo(QPointF(*new_c[0]))
                    for nx, ny in new_c[1:]: 
                        path.lineTo(QPointF(nx, ny))
                    if g_type == 'poly': path.closeSubpath()
                elif g_type in ('dim', 'ortho_dim'): 
                    path.moveTo(QPointF(*new_c[0]))
                    path.lineTo(QPointF(*new_c[1]))
                elif g_type == 'angle_dim':
                    path.moveTo(QPointF(*new_c[0]))
                    path.lineTo(QPointF(*new_c[1]))
                    path.lineTo(QPointF(*new_c[2]))
                elif g_type == 'circle':
                    c = new_c[0]
                    r = getattr(item, 'radius', 0)
                    path.addEllipse(QPointF(*c), r, r)
                elif g_type == 'text':
                    br = item.boundingRect()
                    path.addRect(QRectF(new_c[0][0], new_c[0][1], br.width(), br.height()))
                        
            ghost.setPath(path)

    def mousePressEvent(self, event, final_point, snapped_angle):
        raw_point = self.canvas.mapToScene(event.pos())
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == 0:
                item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
                if getattr(item, 'is_smart_shape', False):
                    if item not in self.target_items: 
                        self.target_items.append(item)
                        item.setSelected(True)
                else:
                    self.start_point = raw_point
                    self.selection_box = QGraphicsRectItem()
                    pen = QPen(QColor(0, 120, 215), 1)
                    pen.setCosmetic(True)
                    self.selection_box.setPen(pen)
                    self.selection_box.setBrush(QColor(0, 120, 215, 40))
                    self.selection_box.setZValue(5000)
                    self.canvas.scene().addItem(self.selection_box)
                self._update_hud()
                return True
                
            elif self.state == 1:
                self.p1 = (final_point.x(), final_point.y())
                self.state = 2
                self._update_hud()
                return True
                
            elif self.state == 2:
                self._finalize_mirror(final_point)
                return True
                
        elif event.button() == Qt.MouseButton.RightButton:
            if self.state == 0 and self.target_items: 
                self.state = 1
            elif self.state == 2: 
                self._cleanup_ghosts()
                self.state = 1
            elif self.state == 1:
                self.state = 0
                for item in self.target_items: 
                    item.setSelected(False)
                self.target_items.clear()
            else: 
                self.deactivate()
                self.canvas.switch_tool("选择")
            self._update_hud()
            return True
            
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        raw_point = self.canvas.mapToScene(event.pos())
        self._update_hud()
        
        if self.state == 0 and self.selection_box and self.start_point:
            x = min(self.start_point.x(), raw_point.x())
            y = min(self.start_point.y(), raw_point.y())
            w = abs(self.start_point.x() - raw_point.x())
            h = abs(self.start_point.y() - raw_point.y())
            
            self.selection_box.setRect(x, y, w, h)
            
            is_blue = raw_point.x() > self.start_point.x()
            color = QColor(0, 120, 215) if is_blue else QColor(76, 175, 80)
            pen_style = Qt.PenStyle.SolidLine if is_blue else Qt.PenStyle.DashLine
            
            pen = QPen(color, 1, pen_style)
            pen.setCosmetic(True)
            self.selection_box.setPen(pen)
            self.selection_box.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
            return True
            
        if self.state == 2 and self.p1: 
            self._update_preview(final_point)
            
        return True
        
    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton and self.state == 0 and self.selection_box:
            rect = self.selection_box.rect()
            if rect.width() > 0 and rect.height() > 0:
                raw_point = self.canvas.mapToScene(event.pos())
                is_blue = raw_point.x() > self.start_point.x()
                mode = Qt.ItemSelectionMode.ContainsItemShape if is_blue else Qt.ItemSelectionMode.IntersectsItemShape
                
                for item in self.canvas.scene().items(rect, mode):
                    if getattr(item, 'is_smart_shape', False) and item not in self.target_items:
                        self.target_items.append(item)
                        item.setSelected(True)
                        
            self.canvas.scene().removeItem(self.selection_box)
            self.selection_box = None
            self.start_point = None
            return True
            
        return False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.state == 0 and self.target_items: 
                self.state = 1
                self._update_hud()
            elif self.state == 2: 
                self._finalize_mirror(getattr(self.canvas, 'last_cursor_point', QPointF(0,0)))
            return True
        elif event.key() == Qt.Key.Key_Escape: 
            self.deactivate()
            self.canvas.switch_tool("选择")
            return True
            
        return False

    def _finalize_mirror(self, p2):
        if not self.target_items or not self.p1: 
            return
            
        x1, y1 = self.p1
        x2, y2 = p2.x(), p2.y()
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx*dx + dy*dy
        
        if length_sq < 1e-6: 
            self.deactivate()
            self.canvas.switch_tool("选择")
            return
            
        mirror_a = math.degrees(math.atan2(-dy, dx))
        if mirror_a < 0: 
            mirror_a += 360

        def get_mirror_pt(px, py):
            t = ((px - x1)*dx + (py - y1)*dy) / length_sq
            proj_x = x1 + t*dx
            proj_y = y1 + t*dy
            return 2*proj_x - px, 2*proj_y - py

        mirror_data = []
        for item in self.target_items:
            g_type = getattr(item, 'geom_type', '')
            
            if g_type == 'arc':
                nx, ny = get_mirror_pt(*item.center)
                new_sa = (2 * mirror_a - item.end_angle) % 360
                new_ea = (2 * mirror_a - item.start_angle) % 360
                mirror_data.append((item, {'center': (nx, ny), 'radius': item.radius, 'sa': new_sa, 'ea': new_ea}))
            elif g_type == 'ellipse':
                nx, ny = get_mirror_pt(*item.center)
                new_rot = (2 * mirror_a - item.rotation_angle) % 360
                mirror_data.append((item, {'center': (nx, ny), 'rx': item.rx, 'ry': item.ry, 'rotation_angle': new_rot}))
            elif g_type == 'arclen_dim':
                nx, ny = get_mirror_pt(*item.coords[0])
                off_nx, off_ny = get_mirror_pt(*item.coords[1])
                new_sa = (2 * mirror_a - item.end_angle) % 360
                new_ea = (2 * mirror_a - item.start_angle) % 360
                mirror_data.append((item, {'center': (nx, ny), 'radius': item.radius, 'sa': new_sa, 'ea': new_ea, 'offset_pt': (off_nx, off_ny)}))
            else:
                new_c = [get_mirror_pt(x, y) for x, y in item.coords]
                mirror_data.append((item, new_c))
            
        if mirror_data: 
            self.canvas.undo_stack.push(CommandMirrorGeom(self.canvas.scene(), mirror_data, self.canvas.layer_manager))
            
        self.deactivate()
        self.canvas.switch_tool("选择")