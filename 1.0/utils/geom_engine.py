# utils/geom_engine.py
import pyclipper
from shapely.geometry import Point, LineString, Polygon
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QPolygonF
import math

class GeometryEngine:
    """
    CAD 核心几何计算引擎
    整合 Pyclipper (专注于工业级多边形偏移) 和 Shapely (专注于布尔运算、交点计算与拓扑)
    """
    
    # Clipper 内部使用整数计算以保证绝对精度，所以需要乘数放大
    SCALE = 100000.0 

    # ==========================================
    # 1. 偏移 (Offset) 计算模块 (基于 Pyclipper)
    # ==========================================
    @staticmethod
    def offset_polygon(qpolygon, distance):
        """
        对 QPolygonF (矩形/多段线) 进行多边形等距偏移
        distance: 正数向外扩展，负数向内收缩
        """
        if qpolygon.count() < 3:
            return None

        # 1. Qt 数据转化为 Clipper 认识的数据格式 (List of Tuples)
        path = [(p.x(), p.y()) for p in qpolygon]
        
        # 2. 初始化 Clipper 偏移引擎
        pco = pyclipper.PyclipperOffset()
        
        # 采用 JT_MITER (尖角模式，CAD 默认)，ET_CLOSEDPOLYGON (闭合多边形)
        pco.AddPath(
            pyclipper.scale_to_clipper(path, GeometryEngine.SCALE), 
            pyclipper.JT_MITER, 
            pyclipper.ET_CLOSEDPOLYGON
        )
        
        # 3. 执行偏移计算 (注意：因 Qt Y 轴向下，若要保持正向外、负向内，距离需取反)
        solution = pco.Execute(pyclipper.scale_to_clipper(-distance, GeometryEngine.SCALE))
        
        # 4. 如果向内偏移太多导致图形自相交直至消失，solution 为空
        if not solution:
            return None
            
        # 5. 提取计算结果，转回 Qt 的 QPolygonF
        new_poly = QPolygonF()
        # 取最大的那个外轮廓 (防自交产生的碎块)
        out_path = pyclipper.scale_from_clipper(solution[0], GeometryEngine.SCALE)
        for x, y in out_path:
            new_poly.append(QPointF(x, y))
            
        return new_poly

    @staticmethod
    def offset_line(qline, distance, side_point_q):
        """
        对 QLineF (直线) 进行平行偏移
        distance: 绝对距离
        side_point_q: 鼠标点击的一侧坐标，用于判断往哪边偏
        """
        p1, p2 = qline.p1(), qline.p2()
        dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length == 0: return None
        
        # 计算法向量 (垂直于直线的方向)
        nx, ny = -dy / length, dx / length
        
        # 利用二维叉乘判断 side_point_q 在直线的哪一侧
        cross_product = (side_point_q.x() - p1.x()) * dy - (side_point_q.y() - p1.y()) * dx
        if cross_product > 0:
            nx, ny = -nx, -ny  # 翻转法向量
            
        # 生成新线段的端点
        off_p1 = QPointF(p1.x() + nx * distance, p1.y() + ny * distance)
        off_p2 = QPointF(p2.x() + nx * distance, p2.y() + ny * distance)
        
        return QLineF(off_p1, off_p2)

    # ==========================================
    # 2. 相交与布尔运算模块 (基于 Shapely)
    # ==========================================
    @staticmethod
    def find_intersection(geom1_qt, geom2_qt):
        """
        计算两个 Qt 图形的交点 (未来用于修剪 Trim 和交点捕捉)
        返回: 交点 QPointF 列表
        """
        shape1 = GeometryEngine._qt_to_shapely(geom1_qt)
        shape2 = GeometryEngine._qt_to_shapely(geom2_qt)
        
        if not shape1 or not shape2:
            return []
            
        intersections = shape1.intersection(shape2)
        
        points = []
        if intersections.is_empty:
            return points
            
        # 提取交点
        if intersections.geom_type == 'Point':
            points.append(QPointF(intersections.x, intersections.y))
        elif intersections.geom_type == 'MultiPoint':
            for pt in intersections.geoms:
                points.append(QPointF(pt.x, pt.y))
                
        return points

    # --- 内部辅助方法：Qt 数据转 Shapely ---
    @staticmethod
    def _qt_to_shapely(geom_qt):
        if isinstance(geom_qt, QLineF):
            return LineString([(geom_qt.x1(), geom_qt.y1()), (geom_qt.x2(), geom_qt.y2())])
        elif isinstance(geom_qt, QPolygonF):
            pts = [(p.x(), p.y()) for p in geom_qt]
            if len(pts) >= 3:
                return Polygon(pts)
        return None