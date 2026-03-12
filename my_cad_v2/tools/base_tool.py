# tools/base_tool.py
class BaseTool:
    """V2.0 所有工具的基类"""
    def __init__(self, canvas):
        self.canvas = canvas
        self.temp_item = None # 统一命名临时绘制的图形

    def activate(self): pass
    def deactivate(self): pass
    def get_reference_point(self): return None
    def get_input_buffer(self): return ""
    def mousePressEvent(self, event, final_point, snapped_angle): return False
    def mouseMoveEvent(self, event, final_point, snapped_angle): return False
    def mouseReleaseEvent(self, event, final_point, snapped_angle): return False
    def keyPressEvent(self, event): return False