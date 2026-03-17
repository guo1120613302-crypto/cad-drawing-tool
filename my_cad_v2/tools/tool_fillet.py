# tools/tool_fillet.py
import math
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QUndoCommand, QPen, QColor
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QGraphicsLineItem
from core.core_items import SmartLineItem, SmartPolygonItem, SmartPolylineItem, SmartArcItem

class CommandFillet(QUndoCommand):
    def __init__(self, scene, item1, idx1, item2, idx2, radius):
        super().__init__()
        self.scene = scene
        self.item1 = item1
        self.item2 = item2
        self.mode = "invalid"
        self.arc_item = None

        # ==========================================
        # 模式 1: 同一个多边形或多段线 (完美保留段属性)
        # ==========================================
        if item1 == item2 and isinstance(item1, (SmartPolygonItem, SmartPolylineItem)):
            self.mode = "same_poly"
            self.old_coords = list(item1.coords)
            is_closed = isinstance(item1, SmartPolygonItem)
            N_coords = len(self.old_coords)
            N_edges = N_coords if is_closed else N_coords - 1

            # 严格判断是否相邻并找到共用的顶点 (V_idx)
            if is_closed:
                if (idx1 + 1) % N_edges == idx2: e_in, e_out = idx1, idx2
                elif (idx2 + 1) % N_edges == idx1: e_in, e_out = idx2, idx1
                else: return # 边不相邻
                V_idx = (e_in + 1) % N_coords
            else:
                if idx1 + 1 == idx2: e_in, e_out = idx1, idx2
                elif idx2 + 1 == idx1: e_in, e_out = idx2, idx1
                else: return # 边不相邻
                V_idx = e_in + 1

            A = self.old_coords[e_in]
            V = self.old_coords[V_idx]
            B = self.old_coords[(V_idx + 1) % N_coords]

            pts = self._calc_fillet_pts(A, V, B, radius)
            if not pts: return

            self.new_coords = []
            
            # 针对闭合多边形 (无 segments 列表)
            if is_closed:
                for i in range(N_coords):
                    if i == V_idx:
                        self.new_coords.extend(pts)
                    else:
                        self.new_coords.append(self.old_coords[i])
            # 针对多段线 (安全重构 segments，绝不破坏原有圆弧)
            else:
                self.new_segments = []
                self.old_segments = getattr(item1, 'segments', [{"type": "line"} for _ in range(N_edges)])
                
                for i in range(N_coords):
                    if i == V_idx:
                        self.new_coords.extend(pts)
                    else:
                        self.new_coords.append(self.old_coords[i])
                        
                for i in range(N_edges):
                    if i == e_in:
                        self.new_segments.append(self.old_segments[i]) # 保留上一段属性
                        # 插入离散的圆弧段 (皆为直线)
                        for _ in range(len(pts) - 1):
                            self.new_segments.append({"type": "line"})
                    else:
                        self.new_segments.append(self.old_segments[i]) # 完美保留其他所有圆弧/直线属性

        # ==========================================
        # 模式 2: 两条独立的直线
        # ==========================================
        elif isinstance(item1, SmartLineItem) and isinstance(item2, SmartLineItem):
            self.mode = "two_lines"
            self.old_c1 = list(item1.coords)
            self.old_c2 = list(item2.coords)

            res = self._calc_fillet_independent(self.old_c1, self.old_c2, radius)
            if not res[0]: return
            A, V, B, t1, t2, cx, cy, sa, ea = res

            self.new_c1 = [A, t1]
            self.new_c2 = [B, t2]
            
            self.arc_item = SmartArcItem((cx, cy), radius, sa, ea)
            if hasattr(item1, 'pen'): self.arc_item.setPen(item1.pen())

    def _calc_fillet_pts(self, A, V, B, radius):
        """核心几何引擎：生成极其平滑的过渡点集"""
        uAx, uAy = A[0] - V[0], A[1] - V[1]
        uBx, uBy = B[0] - V[0], B[1] - V[1]
        lenA, lenB = math.hypot(uAx, uAy), math.hypot(uBx, uBy)
        if lenA < 1e-6 or lenB < 1e-6: return None

        uAx, uAy = uAx/lenA, uAy/lenA
        uBx, uBy = uBx/lenB, uBy/lenB

        dot = max(-1.0, min(1.0, uAx*uBx + uAy*uBy))
        theta = math.acos(dot)
        if theta < 1e-4 or theta > math.pi - 1e-4: return None

        d = radius / math.tan(theta / 2.0)
        if d > lenA or d > lenB: return None 

        bx, by = uAx + uBx, uAy + uBy
        len_b = math.hypot(bx, by)
        bx, by = bx / len_b, by / len_b

        dist_VC = radius / math.sin(theta / 2.0)
        cx, cy = V[0] + bx * dist_VC, V[1] + by * dist_VC

        t1x, t1y = V[0] + uAx * d, V[1] + uAy * d
        t2x, t2y = V[0] + uBx * d, V[1] + uBy * d

        v1x, v1y = t1x - cx, t1y - cy
        v2x, v2y = t2x - cx, t2y - cy
        a1 = math.atan2(v1y, v1x)
        a2 = math.atan2(v2y, v2x)

        diff = a2 - a1
        while diff > math.pi: diff -= 2*math.pi
        while diff < -math.pi: diff += 2*math.pi

        pts = []
        steps = max(12, int(abs(diff) * radius / 5))
        steps = min(48, steps)
        for i in range(steps + 1):
            a = a1 + diff * (i / steps)
            pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
        return pts

    def _calc_fillet_independent(self, c1, c2, radius):
        p1, p2 = c1
        p3, p4 = c2
        den = (p1[0]-p2[0])*(p3[1]-p4[1]) - (p1[1]-p2[1])*(p3[0]-p4[0])
        if abs(den) < 1e-6: return [None]*9
        
        ix = ((p1[0]*p2[1]-p1[1]*p2[0])*(p3[0]-p4[0]) - (p1[0]-p2[0])*(p3[0]*p4[1]-p3[1]*p4[0])) / den
        iy = ((p1[0]*p2[1]-p1[1]*p2[0])*(p3[1]-p4[1]) - (p1[1]-p2[1])*(p3[0]*p4[1]-p3[1]*p4[0])) / den
        V = (ix, iy)

        A = p1 if math.hypot(p1[0]-ix, p1[1]-iy) > math.hypot(p2[0]-ix, p2[1]-iy) else p2
        B = p3 if math.hypot(p3[0]-ix, p3[1]-iy) > math.hypot(p4[0]-ix, p4[1]-iy) else p4

        pts = self._calc_fillet_pts(A, V, B, radius)
        if not pts: return [None]*9

        t1, t2 = pts[0], pts[-1]
        uAx, uAy = A[0] - V[0], A[1] - V[1]
        uBx, uBy = B[0] - V[0], B[1] - V[1]
        lenA, lenB = math.hypot(uAx, uAy), math.hypot(uBx, uBy)
        bx, by = uAx/lenA + uBx/lenB, uAy/lenA + uBy/lenB
        len_b = math.hypot(bx, by)
        bx, by = bx / len_b, by / len_b
        
        theta = math.acos(max(-1.0, min(1.0, (uAx/lenA)*(uBx/lenB) + (uAy/lenA)*(uBy/lenB))))
        dist_VC = radius / math.sin(theta / 2.0)
        cx, cy = V[0] + bx * dist_VC, V[1] + by * dist_VC

        sa = math.degrees(math.atan2(-(t1[1] - cy), t1[0] - cx))
        ea = math.degrees(math.atan2(-(t2[1] - cy), t2[0] - cx))
        if sa < 0: sa += 360
        if ea < 0: ea += 360
        span = ea - sa
        if span < 0: span += 360
        if span > 180: sa, ea = ea, sa

        return A, V, B, t1, t2, cx, cy, sa, ea

    def redo(self):
        if self.mode == "same_poly":
            self.item1.set_coords(self.new_coords)
            if hasattr(self, 'new_segments'):
                self.item1.segments = self.new_segments
        elif self.mode == "two_lines":
            self.item1.set_coords(self.new_c1)
            self.item2.set_coords(self.new_c2)
            if self.arc_item not in self.scene.items():
                self.scene.addItem(self.arc_item)

    def undo(self):
        if self.mode == "same_poly":
            self.item1.set_coords(self.old_coords)
            if hasattr(self, 'old_segments'):
                self.item1.segments = self.old_segments
        elif self.mode == "two_lines":
            self.item1.set_coords(self.old_c1)
            self.item2.set_coords(self.old_c2)
            if self.arc_item.scene() == self.scene:
                self.scene.removeItem(self.arc_item)


class FilletTool(BaseTool):
    """V2.0 倒圆角工具 (带自动覆盖旧数值功能)"""
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.radius = 20.0 
        self.input_buffer = ""
        self.l1 = None
        self.idx1 = -1
        self.l2 = None
        self.idx2 = -1
        
        self.overlays = []
        self.hud_anchor = None 
        
        # 新增：判断是否是弹出蓝框后的第一次按键
        self.is_first_input = True 

        self.local_hud = QGraphicsTextItem()
        self.local_hud.setZValue(9999)
        self.local_hud.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.canvas.scene().addItem(self.local_hud)
        self.local_hud.hide()

    def _clear_overlays(self):
        for o in self.overlays:
            if o.scene() == self.canvas.scene():
                self.canvas.scene().removeItem(o)
        self.overlays.clear()

    def _highlight_segment(self, item, idx):
        is_closed = isinstance(item, SmartPolygonItem)
        n = len(item.coords)
        if idx < 0 or idx >= (n if is_closed else n - 1): return
        
        p1 = item.coords[idx]
        p2 = item.coords[(idx + 1) % n]
        
        overlay = QGraphicsLineItem(p1[0], p1[1], p2[0], p2[1])
        overlay.setPen(QPen(QColor(0, 120, 215), 3))
        overlay.setZValue(9999)
        self.canvas.scene().addItem(overlay)
        self.overlays.append(overlay)

    def activate(self):
        self.state = 0
        self._clear_overlays()
        self.l1 = None; self.l2 = None
        self.idx1 = -1; self.idx2 = -1
        self.input_buffer = ""
        self.is_first_input = True # 工具激活时重置标志
        self.local_hud.hide()
        self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒圆角: 请点击第一条边</div>")
        self.canvas.hud_polar_info.show()

    def deactivate(self): 
        self.canvas.hud_polar_info.hide()
        self.local_hud.hide()
        self._clear_overlays()

    def _update_hud(self):
        if not self.hud_anchor: return
        display_text = f"R: {self.input_buffer}" if self.input_buffer else f"R: {self.radius}"
        lod = self.canvas.transform().m11()
        self.local_hud.setHtml(f"<div style='background-color:#0055ff; color:white; padding:2px 4px; border:1px solid #777; font-family:Arial; font-size:12px; text-align:center;'>{display_text}</div>")
        self.local_hud.setPos(self.hud_anchor.x() + 15/lod, self.hud_anchor.y() + 15/lod)
        self.local_hud.show()

    def _get_closest_segment(self, coords, pos, is_closed):
        min_dist = float('inf')
        best_i = -1
        n = len(coords)
        n_edges = n if is_closed else n - 1
        for i in range(n_edges):
            p1 = coords[i]
            p2 = coords[(i+1)%n]
            px, py = pos.x(), pos.y()
            x1, y1 = p1; x2, y2 = p2
            dx, dy = x2 - x1, y2 - y1
            if dx == 0 and dy == 0:
                dist = math.hypot(px - x1, py - y1)
            else:
                t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
                t = max(0, min(1, t))
                qx, qy = x1 + t * dx, y1 + t * dy
                dist = math.hypot(px - qx, py - qy)
            if dist < min_dist:
                min_dist = dist
                best_i = i
        return best_i

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() != Qt.MouseButton.LeftButton: 
            self.activate() 
            return True
            
        items = self.canvas.items(event.pos())
        selected_item = None
        for it in items:
            if isinstance(it, (SmartLineItem, SmartPolygonItem, SmartPolylineItem)):
                selected_item = it
                break
        if not selected_item: return True 
        
        is_closed = isinstance(selected_item, SmartPolygonItem)
        idx = self._get_closest_segment(selected_item.coords, final_point, is_closed)
        if idx == -1: return True

        if self.state == 0:
            self.l1 = selected_item
            self.idx1 = idx
            self._highlight_segment(self.l1, self.idx1)
            self.state = 1
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒圆角: 请点击相邻的第二条边</div>")
        
        elif self.state == 1:
            self.l2 = selected_item
            self.idx2 = idx
            self._highlight_segment(self.l2, self.idx2)
            self.state = 2
            
            self.hud_anchor = final_point
            self.input_buffer = str(int(self.radius)) if self.radius.is_integer() else str(self.radius)
            self.is_first_input = True # 弹出输入框时，标记等待覆盖
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒圆角: 请输入半径并按回车</div>")
            self._update_hud()
                
        return True

    def keyPressEvent(self, event):
        if self.state == 2:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                try: 
                    if self.input_buffer:
                        new_r = float(self.input_buffer)
                        if new_r > 0: self.radius = new_r 
                    
                    cmd = CommandFillet(self.canvas.scene(), self.l1, self.idx1, self.l2, self.idx2, self.radius)
                    if hasattr(cmd, 'new_coords') or cmd.arc_item:
                        self.canvas.undo_stack.push(cmd)
                        self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒圆角成功</div>")
                    else:
                        self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒圆角失败：未相邻或半径过大</div>")
                except ValueError: 
                    pass
                
                self.activate() 
                return True
                
            elif event.key() == Qt.Key.Key_Backspace: 
                # 按退格也算打破了初始状态
                self.is_first_input = False 
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud()
                return True
                
            elif event.text().replace('.', '', 1).isdigit(): 
                # 敲击数字时，如果是第一次，直接清空原有缓冲
                if self.is_first_input:
                    self.input_buffer = ""
                    self.is_first_input = False
                self.input_buffer += event.text()
                self._update_hud()
                return True
                
            elif event.key() == Qt.Key.Key_Escape:
                self.activate()
                return True
                
        return False