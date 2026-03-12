# utils/geom_engine.py
import pyclipper
from shapely.geometry import Point, LineString, Polygon
import numpy as np
import math

class GeometryEngine:
    """
    V2.0 纯几何计算内核 (Geometry Kernel)
    绝对无状态、无 UI 依赖。只处理纯粹的数学坐标 (x, y)。
    """
    
    # Pyclipper 内部使用整数计算以保证绝对精度，所以需要乘数放大
    SCALE = 100000.0 

    # ==========================================
    # 1. 基础计算与校验模块 (基于 Shapely)
    # ==========================================
    @staticmethod
    def calculate_area(coords):
        """
        计算绝对展开面积
        coords: [(x, y), (x, y), ...]
        返回: 面积数值
        """
        if len(coords) < 3: 
            return 0.0
        return Polygon(coords).area

    @staticmethod
    def is_valid_polygon(coords):
        """
        校验图形是否合法（用于拦截拖拽导致的图形“自交”或“畸变”）
        返回: bool
        """
        if len(coords) < 3: 
            return False
        return Polygon(coords).is_valid

    # ==========================================
    # 2. 相交与捕捉模块 (基于 Shapely)
    # ==========================================
    @staticmethod
    def get_intersections(coords1, coords2, is_poly1=False, is_poly2=False):
        """
        计算任意两个几何图形的绝对交点 (用于全局交点捕捉和修剪)
        coords: 坐标列表 [(x, y), ...]
        is_poly: 是否为闭合多边形
        返回: 交点坐标列表 [(x, y), ...]
        """
        geom1 = Polygon(coords1) if is_poly1 and len(coords1) >= 3 else LineString(coords1)
        geom2 = Polygon(coords2) if is_poly2 and len(coords2) >= 3 else LineString(coords2)
        
        intersections = geom1.intersection(geom2)
        
        points = []
        if intersections.is_empty:
            return points
            
        if intersections.geom_type == 'Point':
            points.append((intersections.x, intersections.y))
        elif intersections.geom_type == 'MultiPoint':
            for pt in intersections.geoms:
                points.append((pt.x, pt.y))
        return points

    # ==========================================
    # 3. 工业级偏移模块 (基于 Pyclipper)
    # ==========================================
    @staticmethod
    def offset_polygon(coords, distance):
        """
        多段线/矩形等距偏移 (生成板材厚度必备)
        coords: [(x, y), ...]
        distance: 正数向外扩展，负数向内收缩 (具体受顺逆时针坐标系影响)
        返回: 新的坐标列表 [(x, y), ...] 或 None (如果向内偏移导致图形消失)
        """
        if len(coords) < 3: 
            return None
        
        pco = pyclipper.PyclipperOffset()
        # JT_MITER 保证工业标准的尖角偏移, ET_CLOSEDPOLYGON 代表处理闭合图形
        pco.AddPath(
            pyclipper.scale_to_clipper(coords, GeometryEngine.SCALE),
            pyclipper.JT_MITER,
            pyclipper.ET_CLOSEDPOLYGON
        )
        
        solution = pco.Execute(pyclipper.scale_to_clipper(distance, GeometryEngine.SCALE))
        
        if not solution: 
            return None
            
        # 取最大的那个外轮廓（防止复杂偏移产生碎块碎片）
        return pyclipper.scale_from_clipper(solution[0], GeometryEngine.SCALE)

    @staticmethod
    def offset_line(coords, distance, side_point):
        """
        单根直线的平行偏移
        coords: [(x1, y1), (x2, y2)]
        distance: 偏移的绝对距离
        side_point: 鼠标点击的一侧坐标 (x, y)，用于判断往哪边偏
        """
        if len(coords) != 2: return None
        (x1, y1), (x2, y2) = coords
        sx, sy = side_point
        
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length == 0: return None
        
        nx, ny = -dy / length, dx / length
        
        # 叉乘判断方向
        cross_product = (sx - x1) * dy - (sy - y1) * dx
        if cross_product > 0:
            nx, ny = -nx, -ny
            
        off_x1, off_y1 = x1 + nx * distance, y1 + ny * distance
        off_x2, off_y2 = x2 + nx * distance, y2 + ny * distance
        
        return [(off_x1, off_y1), (off_x2, off_y2)]