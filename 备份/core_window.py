# core_window.py
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt
import modules_ui  # 引入我们分离出去的 UI 模块

class CADWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("轻量级参数化线稿与 3D 预览工具 - 模块化分类版")
        self.resize(1280, 800)

        # 核心架构设置
        self.setCentralWidget(None) 
        self.setDockNestingEnabled(True)
        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks | 
                            QMainWindow.DockOption.AllowTabbedDocks)

        # 1. 调用外部模块生成 UI 组件
        modules_ui.create_menu_bar(self)
        self.toolbox = modules_ui.create_left_toolbox(self)
        self.lbl_transform_info = modules_ui.create_status_bar(self)
        
        self.dock_2d, self.view_2d, self.scene_2d = modules_ui.create_2d_viewport(self)
        self.dock_3d = modules_ui.create_3d_viewport(self)
        self.prop_dock = modules_ui.create_properties_panel(self)
        self.lib_dock = modules_ui.create_library_panel(self)

        # 2. 初始布局排列
        self.arrange_default_layout()

    def arrange_default_layout(self):
        """严格保持之前的自动排布逻辑"""
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_2d)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_3d)
        
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.prop_dock)
        self.splitDockWidget(self.dock_3d, self.prop_dock, Qt.Orientation.Horizontal)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.lib_dock)
        self.splitDockWidget(self.prop_dock, self.lib_dock, Qt.Orientation.Vertical)