# tools/tool_select.py
from tools.base_tool import BaseTool
from PyQt6.QtCore import Qt

class SelectTool(BaseTool):
    """选择工具：不产生新图形，仅负责点选或框选"""
    def activate(self):
        # 激活选择工具时，清空画布之前的选择，并将光标设为标准箭头
        self.canvas.scene().clearSelection()
        self.canvas.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def deactivate(self):
        self.canvas.scene().clearSelection()

    def mousePressEvent(self, event, current_point, snapped_p):
        # 返回 False，让 Qt 原生的图形选择机制（点击/框选）接管
        return False