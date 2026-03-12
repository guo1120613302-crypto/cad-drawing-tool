# managers/color_manager.py
from PyQt6.QtGui import QColor

class ColorManager:
    """全局颜色管理器 (V2.0 直接继承)"""
    def __init__(self):
        # 默认绘图颜色（白色）
        self.current_color = QColor(255, 255, 255)
        
        # 1. 顶部 6x9 渐变色矩阵 (仿 CAD)
        self.color_matrix = [
            ["#000000", "#FFC000", "#E36C09", "#C00000", "#7030A0", "#002060", "#000080", "#003300", "#333300"],
            ["#333333", "#FFFF00", "#FFC000", "#FF0000", "#C000C0", "#0070C0", "#0066CC", "#008000", "#808000"],
            ["#666666", "#FFFF66", "#FFD966", "#FF6666", "#FF33CC", "#3399FF", "#33CCCC", "#33CC33", "#99CC00"],
            ["#999999", "#FFFF99", "#FFE699", "#FF9999", "#FF66FF", "#66B2FF", "#66FFFF", "#66FF66", "#CCFF33"],
            ["#CCCCCC", "#FFFFCC", "#FFF2CC", "#FFCCCC", "#FF99FF", "#99CCFF", "#99FFFF", "#99FF99", "#E6FF99"],
            ["#FFFFFF", "#FFFFE6", "#FFF9E6", "#FFE6E6", "#FFCCFF", "#CCE5FF", "#CCFFFF", "#CCFFCC", "#F2FFCC"]
        ]
        
        # 2. 底部 CAD 标准索引颜色
        self.index_colors = [
            "#FF0000", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF", "#FF00FF", "#FFFFFF", "#808080", "#C0C0C0"
        ]

    def set_color(self, color_hex):
        self.current_color = QColor(color_hex)

    def get_color(self):
        return self.current_color

    def apply_color_to_selected(self, canvas):
        """将当前颜色应用到已选中的所有线条上"""
        selected_items = canvas.scene().selectedItems()
        if not selected_items:
            return
            
        for item in selected_items:
            if hasattr(item, 'setPen'):
                new_pen = item.pen()
                new_pen.setColor(self.current_color)
                item.setPen(new_pen)
                item.update()