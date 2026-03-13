# tools/tool_trim.py
import traceback, math
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand
from utils.geom_engine import GeometryEngine

class CommandTrimGeom(QUndoCommand):
    def __init__(self, scene, items_to_remove, items_to_add):
        super().__init__()
        self.scene = scene
        self.items_to_remove = items_to_remove
        self.items_to_add = items_to_add
        
    def redo(self):
        self.scene.clearSelection()
        for item in self.items_to_remove:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        for item in self.items_to_add:
            if item.scene() != self.scene:
                self.scene.addItem(item)
                
    def undo(self):
        self.scene.clearSelection()
        for item in self.items_to_add:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        for item in self.items_to_remove:
            if item.scene() != self.scene:
                self.scene.addItem(item)

class TrimTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        # 预览专用的幽灵实体
        self.preview_ghost = None
        self.preview_cross_1 = None
        self.preview_cross_2 = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._update_hud()

    def deactivate(self):
        self._cleanup_preview()

    def _cleanup_preview(self):
        if self.preview_ghost and self.preview_ghost.scene():
            self.canvas.scene().removeItem(self.preview_ghost)
            self.canvas.scene().removeItem(self.preview_cross_1)
            self.canvas.scene().removeItem(self.preview_cross_2)
        self.preview_ghost = None
        self.preview_cross_1 = None
        self.preview_cross_2 = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        self.canvas.hud_polar_info.setHtml(
            "<div style='background-color:#d9534f; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>✂️ 极简修剪: 移动鼠标预览，点击剪断红线部分</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _is_point_on_segment(self, pt, p1, p2):
        min_x, max_x = min(p1[0], p2[0]) - 1e-3, max(p1[0], p2[0]) + 1e-3
        min_y, max_y = min(p1[1], p2[1]) - 1e-3, max(p1[1], p2[1]) + 1e-3
        return min_x <= pt[0] <= max_x and min_y <= pt[1] <= max_y

    def _point_to_segment_dist(self, pt, p1, p2):
        px, py = pt
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        l2 = dx*dx + dy*dy
        if l2 == 0: return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / l2))
        proj_x, proj_y = x1 + t * dx, y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def _calculate_trim_pieces(self, p1, p2, ignore_item, click_pt, is_polygon_edge=False, polygon_coords=None):
        intersections = []
        
        # 1. 和场景中其他实体求交
        for other_item in self.canvas.scene().items():
            if other_item == ignore_item: continue
            if not isinstance(other_item, (SmartLineItem, SmartPolygonItem)): continue
            
            if isinstance(other_item, SmartPolygonItem):
                coords = other_item.coords
                for i in range(len(coords)):
                    sp1 = coords[i]
                    sp2 = coords[(i+1)%len(coords)]
                    pts = GeometryEngine.get_intersections([p1, p2], [sp1, sp2], False, False)
                    for pt in pts:
                        if self._is_point_on_segment(pt, p1, p2): intersections.append(pt)
            else:
                pts = GeometryEngine.get_intersections([p1, p2], other_item.coords, False, False)
                for pt in pts:
                    if self._is_point_on_segment(pt, p1, p2): intersections.append(pt)

        # 2. 如果剪的是多边形自己的边，还需要和自己的其他边求交
        if is_polygon_edge and polygon_coords:
            for i in range(len(polygon_coords)):
                sp1 = polygon_coords[i]
                sp2 = polygon_coords[(i+1)%len(polygon_coords)]
                if (sp1 == p1 and sp2 == p2) or (sp1 == p2 and sp2 == p1): continue
                pts = GeometryEngine.get_intersections([p1, p2], [sp1, sp2], False, False)
                for pt in pts:
                    if self._is_point_on_segment(pt, p1, p2): intersections.append(pt)

        nodes = [p1] + intersections + [p2]
        
        # 去重与拓扑排序
        unique_nodes = []
        for n in nodes:
            if not any(math.hypot(n[0]-un[0], n[1]-un[1]) < 1e-4 for un in unique_nodes):
                unique_nodes.append(n)
        unique_nodes.sort(key=lambda n: math.hypot(n[0]-p1[0], n[1]-p1[1]))

        dx, dy = p2[0]-p1[0], p2[1]-p1[1]
        l2 = dx*dx + dy*dy
        if l2 == 0: return None, None
        
        t = max(0, min(1, ((click_pt[0]-p1[0])*dx + (click_pt[1]-p1[1])*dy) / l2))
        proj_pt = (p1[0] + t*dx, p1[1] + t*dy)
        click_dist = math.hypot(proj_pt[0]-p1[0], proj_pt[1]-p1[1])

        # 寻找落入的修剪区间
        cut_index = -1
        for i in range(len(unique_nodes)-1):
            d1 = math.hypot(unique_nodes[i][0]-p1[0], unique_nodes[i][1]-p1[1])
            d2 = math.hypot(unique_nodes[i+1][0]-p1[0], unique_nodes[i+1][1]-p1[1])
            if d1 - 1e-4 <= click_dist <= d2 + 1e-4:
                cut_index = i
                break
                
        if cut_index == -1: return None, None

        # 分离出“保留段”和“删除段”
        pieces_to_keep = []
        for i in range(len(unique_nodes)-1):
            if i != cut_index:
                pieces_to_keep.append((unique_nodes[i], unique_nodes[i+1]))
                
        piece_to_remove = (unique_nodes[cut_index], unique_nodes[cut_index+1])
        
        return pieces_to_keep, piece_to_remove

    def _get_trim_data(self, raw_point):
        """核心解析器：提取修剪目标和数据，用于预览和执行双向调用"""
        target_item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
        if not isinstance(target_item, (SmartLineItem, SmartPolygonItem)):
            return None, None, None

        click_pt = (raw_point.x(), raw_point.y())

        if isinstance(target_item, SmartLineItem):
            p1, p2 = target_item.coords
            pieces_to_keep, piece_to_remove = self._calculate_trim_pieces(p1, p2, target_item, click_pt)
            if piece_to_remove:
                return target_item, pieces_to_keep, piece_to_remove
                
        elif isinstance(target_item, SmartPolygonItem):
            coords = target_item.coords
            min_dist = float('inf')
            clicked_idx = -1
            
            for i in range(len(coords)):
                p1 = coords[i]
                p2 = coords[(i+1)%len(coords)]
                d = self._point_to_segment_dist(click_pt, p1, p2)
                if d < min_dist:
                    min_dist = d
                    clicked_idx = i
            
            if clicked_idx == -1: return None, None, None

            pieces_to_keep = []
            for i in range(len(coords)):
                if i != clicked_idx:
                    pieces_to_keep.append((coords[i], coords[(i+1)%len(coords)]))

            cp1 = coords[clicked_idx]
            cp2 = coords[(clicked_idx+1)%len(coords)]
            res_keep, res_remove = self._calculate_trim_pieces(cp1, cp2, target_item, click_pt, True, coords)
            
            if res_remove:
                pieces_to_keep.extend(res_keep)
                return target_item, pieces_to_keep, res_remove
                
        return None, None, None

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        """【新增】：实时下刀预览系统，指哪红哪"""
        raw_point = self.canvas.mapToScene(event.pos())
        target_item, _, piece_to_remove = self._get_trim_data(raw_point)

        if piece_to_remove:
            if not self.preview_ghost:
                self.preview_ghost = QGraphicsLineItem()
                pen = QPen(QColor(255, 0, 0, 220), 2.5, Qt.PenStyle.DashLine) # 红色粗虚线
                pen.setCosmetic(True)
                self.preview_ghost.setPen(pen)
                self.preview_ghost.setZValue(5000)
                
                self.preview_cross_1 = QGraphicsLineItem()
                self.preview_cross_2 = QGraphicsLineItem()
                cross_pen = QPen(QColor(255, 0, 0, 220), 2)
                cross_pen.setCosmetic(True)
                self.preview_cross_1.setPen(cross_pen)
                self.preview_cross_2.setPen(cross_pen)
                self.preview_cross_1.setZValue(5000)
                self.preview_cross_2.setZValue(5000)
                
                self.canvas.scene().addItem(self.preview_ghost)
                self.canvas.scene().addItem(self.preview_cross_1)
                self.canvas.scene().addItem(self.preview_cross_2)
                
            p1, p2 = piece_to_remove
            self.preview_ghost.setLine(QLineF(p1[0], p1[1], p2[0], p2[1]))
            
            # 在被修剪的线段正中间画一个 ❌ 符号
            mx, my = (p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0
            size = 6.0 / self.canvas.transform().m11()
            self.preview_cross_1.setLine(QLineF(mx-size, my-size, mx+size, my+size))
            self.preview_cross_2.setLine(QLineF(mx-size, my+size, mx+size, my-size))
            
            self.preview_ghost.show()
            self.preview_cross_1.show()
            self.preview_cross_2.show()
        else:
            if self.preview_ghost:
                self.preview_ghost.hide()
                self.preview_cross_1.hide()
                self.preview_cross_2.hide()
                
        return True

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            raw_point = self.canvas.mapToScene(event.pos())
            target_item, pieces_to_keep, piece_to_remove = self._get_trim_data(raw_point)
            
            if target_item and piece_to_remove:
                items_to_remove = [target_item]
                items_to_add = []
                pen = target_item.pen()
                
                # 把保留下来的线段重新生成
                for p1, p2 in pieces_to_keep:
                    new_line = SmartLineItem(p1, p2)
                    new_line.setPen(pen)
                    items_to_add.append(new_line)
                    
                cmd = CommandTrimGeom(self.canvas.scene(), items_to_remove, items_to_add)
                self.canvas.undo_stack.push(cmd)
                
                # 修剪成功后立刻清空预览
                self._cleanup_preview()
                self.canvas.viewport().update()
                
            return True
            
        elif event.button() == Qt.MouseButton.RightButton:
            self.canvas.switch_tool("选择")
            return True
        return False
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canvas.switch_tool("选择")
            return True
        return False