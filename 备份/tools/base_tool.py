# tools/base_tool.py
class BaseTool:
    """所有绘图工具的基类，定义统一的接口规范"""
    def __init__(self, canvas):
        self.canvas = canvas

    def activate(self):
        pass

    def deactivate(self):
        pass

    def get_reference_point(self):
        """【核心新增】返回当前工具正在使用的参考点（如直线的起点），供全局画布计算极轴追踪使用"""
        return None

    def get_input_buffer(self):
        """返回当前工具正在键盘键入的字符，供全局画布 HUD 显示"""
        return ""

    def mousePressEvent(self, event, final_point, snapped_angle):
        """接收的已经是经过全局画布吸附和修正后的完美 final_point"""
        return False

    def mouseMoveEvent(self, event, final_point, snapped_angle):
        return False

    def mouseReleaseEvent(self, event, final_point, snapped_angle):
        return False

    def keyPressEvent(self, event):
        return False