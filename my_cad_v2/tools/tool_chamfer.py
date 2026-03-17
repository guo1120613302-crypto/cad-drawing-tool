# tools/tool_chamfer.py
import math
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QUndoCommand, QPen, QColor
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QGraphicsLineItem
from core.core_items import SmartLineItem, SmartPolygonItem, SmartPolylineItem

class CommandChamfer(QUndoCommand):
    def __init__(self, scene, item1, idx1, item2, idx2, val1, val2, is_angle_mode=False):
        super().__init__()
        self.scene = scene
        self.item1 = item1
        self.item2 = item2
        self.mode = "invalid"
        self.chamfer_line = None

        if item1 == item2 and isinstance(item1, (SmartPolygonItem, SmartPolylineItem)):
            self.mode = "same_poly"
            self.old_coords = list(item1.coords)
            is_closed = isinstance(item1, SmartPolygonItem)
            N_coords = len(self.old_coords)
            N_edges = N_coords if is_closed else N_coords - 1

            if is_closed:
                if (idx1 + 1) % N_edges == idx2: 
                    e_in, e_out = idx1, idx2; V_idx = idx2
                    v_in, v_out = val1, val2
                elif (idx2 + 1) % N_edges == idx1: 
                    e_in, e_out = idx2, idx1; V_idx = idx1
                    # 如果是角度模式，顺序反了的话，需要重新按用户点击的第一条线计算，这里简化处理，优先以点击为准
                    v_in, v_out = (val2, val1) if not is_angle_mode else (val1, val2) 
                else: return 
            else:
                if idx1 + 1 == idx2: 
                    e_in, e_out = idx1, idx2; V_idx = idx2
                    v_in, v_out = val1, val2
                elif idx2 + 1 == idx1: 
                    e_in, e_out = idx2, idx1; V_idx = idx1
                    v_in, v_out = (val2, val1) if not is_angle_mode else (val1, val2)
                else: return 

            A = self.old_coords[e_in]
            V = self.old_coords[V_idx]
            B = self.old_coords[(e_out + 1) % N_coords]

            # 只有当用户真的反着点，并且是角度模式时，我们要把 A 和 B 对调，确保距离作用在第一根线上
            if is_angle_mode and (idx2 + 1) % N_edges == idx1:
                 pts = self._calc_chamfer_pts(B, V, A, val1, val2, True)
                 if pts: pts = [pts[1], pts[0]] # 算完之后调换端点顺序以适配原有的插入逻辑
            else:
                 pts = self._calc_chamfer_pts(A, V, B, v_in, v_out, is_angle_mode)

            if not pts: return

            self.new_coords = []
            if is_closed:
                for i in range(N_coords):
                    if i == V_idx: self.new_coords.extend(pts)
                    else: self.new_coords.append(self.old_coords[i])
            else:
                self.new_segments = []
                self.old_segments = getattr(item1, 'segments', [{"type": "line"} for _ in range(N_edges)])
                for i in range(N_coords):
                    if i == V_idx: self.new_coords.extend(pts)
                    else: self.new_coords.append(self.old_coords[i])
                for i in range(N_edges):
                    if i == e_in:
                        self.new_segments.append(self.old_segments[i])
                        self.new_segments.append({"type": "line"})
                    else:
                        self.new_segments.append(self.old_segments[i])

        elif isinstance(item1, SmartLineItem) and isinstance(item2, SmartLineItem):
            self.mode = "two_lines"
            self.old_c1 = list(item1.coords)
            self.old_c2 = list(item2.coords)

            res = self._calc_chamfer_independent(self.old_c1, self.old_c2, val1, val2, is_angle_mode)
            if not res[0]: return
            A, V, B, t1, t2 = res
            self.new_c1 = [A, t1]; self.new_c2 = [B, t2]
            self.chamfer_line = SmartLineItem(t1, t2)
            if hasattr(item1, 'pen'): self.chamfer_line.setPen(item1.pen())

    def _calc_chamfer_pts(self, A, V, B, val1, val2, is_angle_mode):
        uAx, uAy = A[0] - V[0], A[1] - V[1]
        uBx, uBy = B[0] - V[0], B[1] - V[1]
        lenA, lenB = math.hypot(uAx, uAy), math.hypot(uBx, uBy)
        if lenA < 1e-6 or lenB < 1e-6: return None

        uAx, uAy = uAx/lenA, uAy/lenA
        uBx, uBy = uBx/lenB, uBy/lenB

        if is_angle_mode:
            d1 = val1
            angle_deg = val2
            # 计算两条线之间的夹角 theta
            dot = max(-1.0, min(1.0, uAx*uBx + uAy*uBy))
            theta = math.acos(dot)
            alpha = math.radians(angle_deg)
            
            # 使用正弦定理推算第二条边应该切除的距离 d2
            den = math.sin(theta + alpha)
            if abs(den) < 1e-6 or alpha < 0 or (theta + alpha) >= math.pi:
                return None # 角度无效或切不中第二条线
            d2 = d1 * math.sin(alpha) / den
        else:
            d1 = val1
            d2 = val2

        if d1 > lenA or d2 > lenB or d1 < 0 or d2 < 0: return None

        t1x, t1y = V[0] + uAx * d1, V[1] + uAy * d1
        t2x, t2y = V[0] + uBx * d2, V[1] + uBy * d2
        return [(t1x, t1y), (t2x, t2y)]

    def _calc_chamfer_independent(self, c1, c2, val1, val2, is_angle_mode):
        p1, p2 = c1; p3, p4 = c2
        den = (p1[0]-p2[0])*(p3[1]-p4[1]) - (p1[1]-p2[1])*(p3[0]-p4[0])
        if abs(den) < 1e-6: return [None]*5
        
        ix = ((p1[0]*p2[1]-p1[1]*p2[0])*(p3[0]-p4[0]) - (p1[0]-p2[0])*(p3[0]*p4[1]-p3[1]*p4[0])) / den
        iy = ((p1[0]*p2[1]-p1[1]*p2[0])*(p3[1]-p4[1]) - (p1[1]-p2[1])*(p3[0]*p4[1]-p3[1]*p4[0])) / den
        V = (ix, iy)

        A = p1 if math.hypot(p1[0]-ix, p1[1]-iy) > math.hypot(p2[0]-ix, p2[1]-iy) else p2
        B = p3 if math.hypot(p3[0]-ix, p3[1]-iy) > math.hypot(p4[0]-ix, p4[1]-iy) else p4

        pts = self._calc_chamfer_pts(A, V, B, val1, val2, is_angle_mode)
        if not pts: return [None]*5
        return A, V, B, pts[0], pts[1]

    def redo(self):
        if self.mode == "same_poly":
            self.item1.set_coords(self.new_coords)
            if hasattr(self, 'new_segments'): self.item1.segments = self.new_segments
        elif self.mode == "two_lines":
            self.item1.set_coords(self.new_c1); self.item2.set_coords(self.new_c2)
            if self.chamfer_line not in self.scene.items(): self.scene.addItem(self.chamfer_line)

    def undo(self):
        if self.mode == "same_poly":
            self.item1.set_coords(self.old_coords)
            if hasattr(self, 'old_segments'): self.item1.segments = self.old_segments
        elif self.mode == "two_lines":
            self.item1.set_coords(self.old_c1); self.item2.set_coords(self.old_c2)
            if self.chamfer_line.scene() == self.scene: self.scene.removeItem(self.chamfer_line)


class ChamferTool(BaseTool):
    """V2.0 倒直角工具 (智能识别距离和角度输入)"""
    def __init__(self, canvas):
        super().__init__(canvas)
        self.state = 0
        self.val1 = 20.0 
        self.val2 = 20.0 
        self.is_angle_mode = False 
        self.input_buffer = ""
        self.l1 = None; self.idx1 = -1
        self.l2 = None; self.idx2 = -1
        
        self.overlays = []; self.hud_anchor = None 
        self.is_first_input = True 

        self.local_hud = QGraphicsTextItem()
        self.local_hud.setZValue(9999)
        self.local_hud.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.canvas.scene().addItem(self.local_hud)
        self.local_hud.hide()

    def _clear_overlays(self):
        for o in self.overlays:
            if o.scene() == self.canvas.scene(): self.canvas.scene().removeItem(o)
        self.overlays.clear()

    def _highlight_segment(self, item, idx):
        is_closed = isinstance(item, SmartPolygonItem)
        n = len(item.coords)
        if idx < 0 or idx >= (n if is_closed else n - 1): return
        p1, p2 = item.coords[idx], item.coords[(idx + 1) % n]
        overlay = QGraphicsLineItem(p1[0], p1[1], p2[0], p2[1])
        overlay.setPen(QPen(QColor(0, 120, 215), 3)); overlay.setZValue(9999)
        self.canvas.scene().addItem(overlay); self.overlays.append(overlay)

    def activate(self):
        self.state = 0; self._clear_overlays()
        self.l1 = None; self.l2 = None; self.idx1 = -1; self.idx2 = -1
        self.input_buffer = ""; self.is_first_input = True 
        self.local_hud.hide()
        self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒直角: 请点击第一条边</div>")
        self.canvas.hud_polar_info.show()

    def deactivate(self): 
        self.canvas.hud_polar_info.hide(); self.local_hud.hide(); self._clear_overlays()

    def _update_hud(self):
        if not self.hud_anchor: return
        if self.is_angle_mode:
            default_str = f"{int(self.val1) if self.val1.is_integer() else self.val1}<{int(self.val2) if self.val2.is_integer() else self.val2}"
        else:
            default_str = f"{int(self.val1) if self.val1.is_integer() else self.val1}"
            if self.val1 != self.val2: default_str += f",{int(self.val2) if self.val2.is_integer() else self.val2}"
            
        display_text = f"D: {self.input_buffer}" if self.input_buffer else f"D: {default_str}"
        
        # 【核心修复】：防止 < 号被 HTML 当作标签隐藏掉
        display_text = display_text.replace('<', '&lt;')
        
        lod = self.canvas.transform().m11()
        self.local_hud.setHtml(f"<div style='background-color:#0055ff; color:white; padding:2px 4px; border:1px solid #777; font-family:Arial; font-size:12px; text-align:center;'>{display_text}</div>")
        self.local_hud.setPos(self.hud_anchor.x() + 15/lod, self.hud_anchor.y() + 15/lod)
        self.local_hud.show()

    def _get_closest_segment(self, coords, pos, is_closed):
        min_dist = float('inf'); best_i = -1
        n = len(coords)
        for i in range(n if is_closed else n - 1):
            p1, p2 = coords[i], coords[(i+1)%n]
            px, py = pos.x(), pos.y()
            x1, y1 = p1; x2, y2 = p2
            dx, dy = x2 - x1, y2 - y1
            if dx == 0 and dy == 0: dist = math.hypot(px - x1, py - y1)
            else:
                t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
                dist = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            if dist < min_dist: min_dist = dist; best_i = i
        return best_i

    def mousePressEvent(self, event, final_point, snapped_angle):
        if event.button() != Qt.MouseButton.LeftButton: 
            self.activate(); return True
            
        items = self.canvas.items(event.pos())
        selected_item = next((it for it in items if isinstance(it, (SmartLineItem, SmartPolygonItem, SmartPolylineItem))), None)
        if not selected_item: return True 
        
        idx = self._get_closest_segment(selected_item.coords, final_point, isinstance(selected_item, SmartPolygonItem))
        if idx == -1: return True

        if self.state == 0:
            self.l1 = selected_item; self.idx1 = idx
            self._highlight_segment(self.l1, self.idx1)
            self.state = 1
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒直角: 请点击相邻的第二条边</div>")
        
        elif self.state == 1:
            self.l2 = selected_item; self.idx2 = idx
            self._highlight_segment(self.l2, self.idx2)
            self.state = 2; self.hud_anchor = final_point
            
            if self.is_angle_mode:
                self.input_buffer = f"{int(self.val1) if self.val1.is_integer() else self.val1}<{int(self.val2) if self.val2.is_integer() else self.val2}"
            else:
                self.input_buffer = f"{int(self.val1) if self.val1.is_integer() else self.val1}" if self.val1 == self.val2 else f"{int(self.val1) if self.val1.is_integer() else self.val1},{int(self.val2) if self.val2.is_integer() else self.val2}"
                
            self.is_first_input = True 
            self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒角: 输入 '10,20' 或 '10&lt;30' 按回车</div>")
            self._update_hud()
        return True

    def keyPressEvent(self, event):
        if self.state == 2:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                try: 
                    if self.input_buffer:
                        # 兼容中文书名号作为角度符号
                        buf = self.input_buffer.replace('《', '<').replace('〈', '<')
                        
                        # 模式 1: 角度识别
                        if '<' in buf:
                            parts = buf.split('<')
                            if len(parts) == 2 and parts[0] and parts[1]:
                                new_v1, new_v2 = float(parts[0]), float(parts[1])
                                if new_v1 >= 0 and new_v2 >= 0:
                                    self.val1, self.val2 = new_v1, new_v2
                                    self.is_angle_mode = True
                            else: raise ValueError
                        
                        # 模式 2: 距离识别
                        else:
                            parts = buf.replace(' ', ',').replace('，', ',').replace('、', ',').split(',')
                            parts = [p for p in parts if p]
                            if len(parts) == 1:
                                new_v1 = float(parts[0])
                                if new_v1 >= 0:
                                    self.val1 = self.val2 = new_v1
                                    self.is_angle_mode = False
                            elif len(parts) >= 2:
                                new_v1, new_v2 = float(parts[0]), float(parts[1])
                                if new_v1 >= 0 and new_v2 >= 0:
                                    self.val1, self.val2 = new_v1, new_v2
                                    self.is_angle_mode = False
                            else: raise ValueError
                    
                    cmd = CommandChamfer(self.canvas.scene(), self.l1, self.idx1, self.l2, self.idx2, self.val1, self.val2, self.is_angle_mode)
                    if hasattr(cmd, 'new_coords') or cmd.chamfer_line:
                        self.canvas.undo_stack.push(cmd)
                        self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒直角成功</div>")
                    else:
                        self.canvas.hud_polar_info.setHtml("<div style='background:#555;color:white;padding:2px;'>倒直角失败：未相邻或参数过大</div>")
                except ValueError: 
                    pass
                self.activate() 
                return True
                
            elif event.key() == Qt.Key.Key_Backspace: 
                self.is_first_input = False 
                self.input_buffer = self.input_buffer[:-1]
                self._update_hud()
                return True
                
            # 允许输入数字、小数点、中英逗号、空格以及角度符号 < 和 《
            elif event.text() in '0123456789.,， 、<《〈': 
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