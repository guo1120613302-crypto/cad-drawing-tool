# tools/tool_break.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand

class CommandBreakGeom(QUndoCommand):
    def __init__(self, scene, old_item, new_items):
        super().__init__()
        self.scene = scene
        self.old_item = old_item
        self.new_items = new_items
        
    def redo(self):
        self.scene.clearSelection()
        if self.old_item.scene() == self.scene:
            self.scene.removeItem(self.old_item)
        for item in self.new_items:
            if item.scene() != self.scene:
                self.scene.addItem(item)
                
    def undo(self):
        self.scene.clearSelection()
        for item in self.new_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        if self.old_item.scene() != self.scene:
            self.scene.addItem(self.old_item)

class BreakTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.preview_marker_1 = None
        self.preview_marker_2 = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._update_hud()

    def deactivate(self):
        self._cleanup_preview()

    def _cleanup_preview(self):
        if self.preview_marker_1 and self.preview_marker_1.scene():
            self.canvas.scene().removeItem(self.preview_marker_1)
            self.canvas.scene().removeItem(self.preview_marker_2)
        self.preview_marker_1 = None
        self.preview_marker_2 = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        self.canvas.hud_polar_info.setHtml(
            "<div style='background-color:#f0ad4e; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>🔪 单点打断: 移动鼠标确定打断点，点击左键一分为二</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _project_point_on_segment(self, pt, p1, p2):
        """精准捕捉鼠标在数学线段上的投影点"""
        px, py = pt
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        l2 = dx*dx + dy*dy
        if l2 == 0: return p1, 0.0
        t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / l2))
        return (x1 + t * dx, y1 + t * dy), math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    def _get_break_data(self, raw_point):
        target_item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
        if not isinstance(target_item, (SmartLineItem, SmartPolygonItem)):
            return None, None

        click_pt = (raw_point.x(), raw_point.y())
        
        if isinstance(target_item, SmartLineItem):
            p1, p2 = target_item.coords
            proj_pt, dist = self._project_point_on_segment(click_pt, p1, p2)
            
            # 防止在端点上打断（没有意义）
            if math.hypot(proj_pt[0]-p1[0], proj_pt[1]-p1[1]) < 1e-3 or math.hypot(proj_pt[0]-p2[0], proj_pt[1]-p2[1]) < 1e-3:
                return None, None
                
            return target_item, {
                'type': 'line',
                'p1': p1, 'p2': p2,
                'break_pt': proj_pt
            }
            
        elif isinstance(target_item, SmartPolygonItem):
            coords = target_item.coords
            min_dist = float('inf')
            best_edge_idx = -1
            best_proj_pt = None
            
            # 找到离鼠标最近的多边形边
            for i in range(len(coords)):
                p1 = coords[i]
                p2 = coords[(i+1)%len(coords)]
                proj_pt, dist = self._project_point_on_segment(click_pt, p1, p2)
                if dist < min_dist:
                    min_dist = dist
                    best_edge_idx = i
                    best_proj_pt = proj_pt
                    
            if best_edge_idx == -1: return None, None
            
            p1 = coords[best_edge_idx]
            p2 = coords[(best_edge_idx+1)%len(coords)]
            if math.hypot(best_proj_pt[0]-p1[0], best_proj_pt[1]-p1[1]) < 1e-3 or math.hypot(best_proj_pt[0]-p2[0], best_proj_pt[1]-p2[1]) < 1e-3:
                return None, None
                
            return target_item, {
                'type': 'poly',
                'coords': coords,
                'edge_idx': best_edge_idx,
                'break_pt': best_proj_pt
            }
            
        return None, None

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        raw_point = self.canvas.mapToScene(event.pos())
        target_item, break_data = self._get_break_data(raw_point)

        if break_data:
            if not self.preview_marker_1:
                self.preview_marker_1 = QGraphicsLineItem()
                self.preview_marker_2 = QGraphicsLineItem()
                pen = QPen(QColor(255, 165, 0), 2) # 橙色预警十字标
                pen.setCosmetic(True)
                self.preview_marker_1.setPen(pen)
                self.preview_marker_2.setPen(pen)
                self.preview_marker_1.setZValue(5000)
                self.preview_marker_2.setZValue(5000)
                self.canvas.scene().addItem(self.preview_marker_1)
                self.canvas.scene().addItem(self.preview_marker_2)
                
            bx, by = break_data['break_pt']
            size = 6.0 / self.canvas.transform().m11()
            
            self.preview_marker_1.setLine(QLineF(bx-size, by-size, bx+size, by+size))
            self.preview_marker_2.setLine(QLineF(bx-size, by+size, bx+size, by-size))
            
            self.preview_marker_1.show()
            self.preview_marker_2.show()
        else:
            self._cleanup_preview()
            
        return True

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            raw_point = self.canvas.mapToScene(event.pos())
            target_item, break_data = self._get_break_data(raw_point)
            
            if target_item and break_data:
                new_items = []
                pen = target_item.pen()
                bx, by = break_data['break_pt']
                
                if break_data['type'] == 'line':
                    p1 = break_data['p1']
                    p2 = break_data['p2']
                    l1 = SmartLineItem(p1, (bx, by))
                    l2 = SmartLineItem((bx, by), p2)
                    l1.setPen(pen)
                    l2.setPen(pen)
                    new_items.extend([l1, l2])
                    
                elif break_data['type'] == 'poly':
                    coords = break_data['coords']
                    edge_idx = break_data['edge_idx']
                    
                    for i in range(len(coords)):
                        if i == edge_idx:
                            p1 = coords[i]
                            p2 = coords[(i+1)%len(coords)]
                            l1 = SmartLineItem(p1, (bx, by))
                            l2 = SmartLineItem((bx, by), p2)
                            l1.setPen(pen)
                            l2.setPen(pen)
                            new_items.extend([l1, l2])
                        else:
                            p1 = coords[i]
                            p2 = coords[(i+1)%len(coords)]
                            l = SmartLineItem(p1, p2)
                            l.setPen(pen)
                            new_items.append(l)
                            
                cmd = CommandBreakGeom(self.canvas.scene(), target_item, new_items)
                self.canvas.undo_stack.push(cmd)
                
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