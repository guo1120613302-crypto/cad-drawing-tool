# tools/tool_extend.py
import math
from tools.base_tool import BaseTool
from core.core_items import SmartLineItem, SmartPolygonItem
from PyQt6.QtWidgets import QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QUndoCommand

class CommandExtendGeom(QUndoCommand):
    def __init__(self, item, old_coords, new_coords):
        super().__init__()
        self.item = item
        self.old_coords = old_coords
        self.new_coords = new_coords
        # 保存图层属性
        self.layer_name = getattr(item, 'layer_name', None)
        
    def redo(self):
        if self.item.scene():
            self.item.set_coords(self.new_coords)
            # 恢复图层属性
            if self.layer_name:
                self.item.layer_name = self.layer_name
            
    def undo(self):
        if self.item.scene():
            self.item.set_coords(self.old_coords)
            # 恢复图层属性
            if self.layer_name:
                self.item.layer_name = self.layer_name

class ExtendTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.preview_ghost = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._update_hud()

    def deactivate(self):
        self._cleanup_preview()

    def _cleanup_preview(self):
        if self.preview_ghost and self.preview_ghost.scene():
            self.canvas.scene().removeItem(self.preview_ghost)
        self.preview_ghost = None

    def _update_hud(self):
        if not hasattr(self.canvas, 'hud_polar_info'): return
        self.canvas.hud_polar_info.show()
        self.canvas.hud_polar_info.setHtml(
            "<div style='background-color:#5cb85c; color:white; padding:4px 8px; border-radius:2px; font-family:Arial; font-size:12px;'>📏 智能延伸: 移动鼠标预览，点击延伸至最近边界</div>"
        )
        self.canvas.hud_polar_info.setPos(self.canvas.mapToScene(20, 20))

    def _ray_intersect_segment(self, O, D, A, B):
        """核心射线碰撞检测算法：计算射线 O+t*D 与线段 AB 的交点"""
        Px, Py = O
        Rx, Ry = D
        Qx, Qy = A
        Sx, Sy = B[0] - A[0], B[1] - A[1]

        cross_RS = Rx * Sy - Ry * Sx
        # 如果平行或共线，无视
        if abs(cross_RS) < 1e-8: 
            return None

        Q_minus_Px = Qx - Px
        Q_minus_Py = Qy - Py

        t = (Q_minus_Px * Sy - Q_minus_Py * Sx) / cross_RS
        u = (Q_minus_Px * Ry - Q_minus_Py * Rx) / cross_RS

        # t > 1e-4 确保射线是向前发射且不包含起点本身
        # 0 <= u <= 1 确保交点落在目标边界线段上
        if t > 1e-4 and 0 <= u <= 1:
            return (Px + t * Rx, Py + t * Ry), t
        return None

    def _get_extend_data(self, raw_point):
        """解析器：获取当前鼠标悬停的直线，并发射射线寻找目标边界"""
        target_item = self.canvas.scene().itemAt(raw_point, self.canvas.transform())
        
        # 目前只支持延伸单根直线，不直接延伸闭合多边形
        if not isinstance(target_item, SmartLineItem):
            return None, None, None, None

        p1, p2 = target_item.coords
        click_pt = (raw_point.x(), raw_point.y())
        
        # 判断鼠标离哪个端点更近，决定延伸方向
        d1 = math.hypot(click_pt[0] - p1[0], click_pt[1] - p1[1])
        d2 = math.hypot(click_pt[0] - p2[0], click_pt[1] - p2[1])

        if d1 < d2:
            # 离 p1 近，向 p1 方向延伸 (p2 -> p1)
            origin = p1
            direction = (p1[0] - p2[0], p1[1] - p2[1])
            static_pt = p2
        else:
            # 离 p2 近，向 p2 方向延伸 (p1 -> p2)
            origin = p2
            direction = (p2[0] - p1[0], p2[1] - p1[1])
            static_pt = p1

        length = math.hypot(direction[0], direction[1])
        if length < 1e-5: return None, None, None, None
        
        # 归一化方向向量
        direction = (direction[0]/length, direction[1]/length)

        # 收集场景中所有的边界线段
        boundaries = []
        for item in self.canvas.scene().items():
            if item == target_item: continue
            if isinstance(item, SmartLineItem):
                boundaries.append(item.coords)
            elif isinstance(item, SmartPolygonItem):
                coords = item.coords
                for i in range(len(coords)):
                    boundaries.append((coords[i], coords[(i+1)%len(coords)]))

        # 寻找最近的交点
        min_t = float('inf')
        best_pt = None

        for A, B in boundaries:
            res = self._ray_intersect_segment(origin, direction, A, B)
            if res:
                pt, t = res
                if t < min_t:
                    min_t = t
                    best_pt = pt

        if best_pt:
            new_coords = [best_pt, p2] if d1 < d2 else [p1, best_pt]
            return target_item, target_item.coords, new_coords, (origin, best_pt)

        return None, None, None, None

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        raw_point = self.canvas.mapToScene(event.pos())
        target_item, _, _, extend_segment = self._get_extend_data(raw_point)

        if extend_segment:
            if not self.preview_ghost:
                self.preview_ghost = QGraphicsLineItem()
                pen = QPen(QColor(0, 255, 0, 220), 2.5, Qt.PenStyle.DashLine) # 绿色粗虚线表示将要生长的部分
                pen.setCosmetic(True)
                self.preview_ghost.setPen(pen)
                self.preview_ghost.setZValue(5000)
                self.canvas.scene().addItem(self.preview_ghost)
                
            p1, p2 = extend_segment
            self.preview_ghost.setLine(QLineF(p1[0], p1[1], p2[0], p2[1]))
            self.preview_ghost.show()
        else:
            if self.preview_ghost:
                self.preview_ghost.hide()
                
        return True

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() == Qt.MouseButton.LeftButton:
            raw_point = self.canvas.mapToScene(event.pos())
            target_item, old_coords, new_coords, _ = self._get_extend_data(raw_point)
            
            if target_item and new_coords:
                cmd = CommandExtendGeom(target_item, old_coords, new_coords)
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