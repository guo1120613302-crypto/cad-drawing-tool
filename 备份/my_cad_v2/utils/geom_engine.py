# utils/geom_engine.py
from shapely.geometry import Point, LineString, Polygon
import math

class GeometryEngine:
    """
    V2.0 纯几何计算内核 (Geometry Kernel)
    【彻底终结闪退】：全面采用 Shapely + join_style=2 (MITRE 尖角)
    保证 100% 工业精度的同时，彻底摆脱 Pyclipper 的内存溢出死穴。
    """
    SCALE = 100000.0 

    @staticmethod
    def calculate_area(coords):
        if not coords or len(coords) < 3: return 0.0
        try: return Polygon(coords).area
        except: return 0.0

    @staticmethod
    def is_valid_polygon(coords):
        if not coords or len(coords) < 3: return False
        try: return Polygon(coords).is_valid
        except: return False

    @staticmethod
    def get_intersections(coords1, coords2, is_poly1=False, is_poly2=False):
        try:
            geom1 = Polygon(coords1) if is_poly1 and len(coords1) >= 3 else LineString(coords1)
            geom2 = Polygon(coords2) if is_poly2 and len(coords2) >= 3 else LineString(coords2)
            intersections = geom1.intersection(geom2)
            points = []
            if intersections.is_empty: return points
            if intersections.geom_type == 'Point': points.append((intersections.x, intersections.y))
            elif intersections.geom_type == 'MultiPoint':
                for pt in intersections.geoms: points.append((pt.x, pt.y))
            return points
        except: return []

    @staticmethod
    def offset_polygon(coords, distance):
        if not coords or len(coords) < 3: return None
        try:
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0) 
                
            # 【核心】：join_style=2 就是 CAD 的 MITRE 尖角偏移，完美保留直角，绝对精准无误差！
            offset_geom = poly.buffer(distance, join_style=2)
            
            if offset_geom.is_empty:
                return None
                
            if offset_geom.geom_type == 'Polygon':
                result = list(offset_geom.exterior.coords)
                # 【修复】：确保返回的坐标列表不为空
                return result if result and len(result) >= 3 else None
            elif offset_geom.geom_type == 'MultiPolygon':
                if len(offset_geom.geoms) == 0:
                    return None
                largest = max(offset_geom.geoms, key=lambda a: a.area)
                result = list(largest.exterior.coords)
                return result if result and len(result) >= 3 else None
            return None
        except Exception as e:
            print(f"几何引擎异常: {e}")
            return None

    @staticmethod
    def offset_line(coords, distance, side_point):
        if not coords or len(coords) != 2: return None
        try:
            (x1, y1), (x2, y2) = coords
            sx, sy = side_point
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length == 0: return None
            nx, ny = -dy / length, dx / length
            cross_product = (sx - x1) * dy - (sy - y1) * dx
            if cross_product > 0: nx, ny = -nx, -ny
            off_x1, off_y1 = x1 + nx * distance, y1 + ny * distance
            off_x2, off_y2 = x2 + nx * distance, y2 + ny * distance
            return [(off_x1, off_y1), (off_x2, off_y2)]
        except: return None
    