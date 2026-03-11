# modules_ui.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QDockWidget, 
                             QFormLayout, QLineEdit, QLabel, QListWidget, 
                             QGraphicsView, QGraphicsScene)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QPen
# 注意：把独立出去的画布类引进来
from core_canvas import CADGraphicsView 

# 修改 modules_ui.py 中的图标生成逻辑
def generate_cad_style_icon(tool_type):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # 线宽设为 1.5 让图标更饱满清晰
    pen = QPen(QColor(255, 255, 255), 1.5) 
    pen.setCosmetic(True)
    painter.setPen(pen)
    
    ix, iy, iw, ih = 4, 4, 24, 24

    if tool_type == "选择":
        # 严格对标图片的四向移动/选择箭头
        cx, cy = 16, 16
        # 十字主线
        painter.drawLine(cx, 6, cx, 26) 
        painter.drawLine(6, cy, 26, cy)
        # 上下左右四个小箭头
        painter.drawLine(cx, 6, cx - 3, 9); painter.drawLine(cx, 6, cx + 3, 9)       # 上
        painter.drawLine(cx, 26, cx - 3, 23); painter.drawLine(cx, 26, cx + 3, 23)   # 下
        painter.drawLine(6, cy, 9, cy - 3); painter.drawLine(6, cy, 9, cy + 3)       # 左
        painter.drawLine(26, cy, 23, cy - 3); painter.drawLine(26, cy, 23, cy + 3)   # 右
        
    elif tool_type == "直线":
        painter.drawLine(ix, iy+ih, ix+iw, iy)
    elif tool_type == "矩形":
        painter.drawRect(ix, iy, iw, ih)
    elif tool_type == "圆形":
        painter.drawEllipse(ix, iy, iw, ih)
    elif tool_type == "偏移":
        pen_bold = QPen(QColor(255, 255, 255), 1.5) 
        painter.setPen(pen_bold)
        painter.drawLine(ix, iy, ix+14, iy)
        painter.drawLine(ix, iy, ix, iy+14)
        painter.drawLine(ix+10, iy+10, ix+iw, iy+10)
        painter.drawLine(ix+10, iy+10, ix+10, iy+ih)
    elif tool_type == "标注":
        mid_y = iy + ih//2
        painter.drawLine(ix+4, mid_y, ix+iw-4, mid_y)
        painter.drawLine(ix+4-3, mid_y+3, ix+4+3, mid_y-3)
        painter.drawLine(ix+iw-4-3, mid_y+3, ix+iw-4+3, mid_y-3)
    elif tool_type == "修剪":
        painter.drawLine(ix, iy+ih, ix+iw-8, iy)
        mid_y = iy + ih//2
        painter.drawLine(ix, mid_y, ix+14, mid_y)
        pen_dash = QPen(QColor(180, 180, 180), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash)
        painter.drawLine(ix+14, mid_y, ix+iw, mid_y)
    elif tool_type == "漫游":
        pen_bold = QPen(QColor(255, 255, 255), 1.5)
        painter.setPen(pen_bold)
        palm_rect = ix+6, iy+8, iw-12, ih-12
        painter.drawRoundedRect(palm_rect[0], palm_rect[1], palm_rect[2], palm_rect[3], 3, 3)
        finger_x = palm_rect[0] + palm_rect[2]//2
        painter.drawLine(finger_x, palm_rect[1], finger_x, iy)
        painter.drawLine(finger_x-4, palm_rect[1], finger_x-4, iy+2)
        painter.drawLine(finger_x+4, palm_rect[1], finger_x+4, iy+2)
        
    painter.end()
    return QIcon(pixmap)
# ================= 2. 界面创建与配色应用 (核心换装区) =================

def create_menu_bar(main_window):
    """【修复】：在最开始注入 PS 暗夜模式整体配色样式"""
    
    # 【核心注入】： Photohsop 暗夜模式整体 QSS 样式表
    dark_night_theme = """
    /* === 核心：全局基础设定 === */
    QWidget {
        background-color: #333333; /* Photoshop 暗夜灰背景 */
        color: #FFFFFF; /* 纯白文字 */
        font-family: Arial, Microsoft YaHei; /* 字体对齐 */
        font-size: 12px;
        border: none; /* 剔除多余边框，保持极简 */
    }
    
    /* === 顶部菜单栏 (QMenuBar) === */
    QMenuBar {
        background-color: #222222; /* 比主体稍微深一点，压住界面 */
        border-bottom: 1px solid #111111;
        padding-left: 5px;
    }
    QMenuBar::item {
        background-color: transparent;
        padding: 5px 10px;
        color: #BBBBBB; /* 菜单文字稍微暗一点，鼠标悬停时亮 */
    }
    QMenuBar::item:selected {
        background-color: #555555; /* PS 选中反馈色 (暗灰蓝) */
        color: #FFFFFF;
    }
    
    /* === 左侧工具栏 (QToolBar) === */
    QToolBar {
        background-color: #2b2b2b; /* 工具栏背景 */
        border-right: 1px solid #111111;
        padding: 5px;
    }
    QToolButton {
        background-color: transparent;
        padding: 5px;
        border: 1px solid transparent;
        border-radius: 3px;
    }
    QToolButton:hover {
        background-color: #444444; /* 悬停反馈色 */
    }
    QToolButton:pressed, QToolButton:checked {
        background-color: #555555; /* 激活/选中反馈色 (PS经典) */
    }
    
    /* === 停靠窗体 (QDockWidget) === */
    QDockWidget {
        background-color: #333333;
        color: #AAAAAA; /* 窗体标题文字颜色 */
        font-weight: bold;
        titlebar-close-icon: url(none); /* 隐藏关闭图标 */
        titlebar-normal-icon: url(none); /* 隐藏还原图标 */
    }
    QDockWidget::title {
        background-color: #2b2b2b; /* 停靠窗体标题栏深色 */
        padding-left: 10px;
        padding-top: 6px;
        padding-bottom: 6px;
        border-bottom: 1px solid #111111;
    }
    
    /* === 底部状态栏 (QStatusBar) === */
    QStatusBar {
        background-color: #111111; /* 最深色压底 */
        color: #888888; /* 状态栏文字低调显示 */
        border-top: 1px solid #000000;
        padding-left: 5px;
    }
    QStatusBar QLabel {
        background-color: transparent; /* 状态栏里的 Label 背景透明 */
        color: #AAAAAA;
    }
    
    /* === 属性面板里的输入框 (QLineEdit) === */
    QLineEdit {
        background-color: #1a1a1a; /* 输入框内背景 */
        color: #FFFFFF;
        border: 1px solid #111111;
        border-radius: 2px;
        padding: 3px 5px;
    }
    QLineEdit:focus {
        border: 1px solid #555555; /* 输入框焦点时加亮一点 */
    }
    
    /* === 列表控件 (QListWidget) === */
    QListWidget {
        background-color: #1a1a1a;
        color: #FFFFFF;
        border: 1px solid #111111;
        padding: 5px;
    }
    QListWidget::item {
        padding: 6px;
    }
    QListWidget::item:selected {
        background-color: #555555; /* 列表选中色 (PS暗灰蓝) */
        color: #FFFFFF;
    }
    """
    
    # 3. 将整套 PS 暗夜模式皮肤应用到 MainWindow
    main_window.setStyleSheet(dark_night_theme)
    
    # 保持原有的菜单创建逻辑 (逻辑未改动)
    menubar = main_window.menuBar()
    menubar.addMenu("文件(F)")
    menubar.addMenu("编辑(E)")
    menubar.addMenu("视图(V)")
    menubar.addMenu("窗口(W)")
    menubar.addMenu("帮助(H)")
def create_left_toolbox(main_window):
    toolbox = QToolBar("绘图工具")
    main_window.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbox)
    toolbox.setMovable(False)
    toolbox.setIconSize(QSize(32, 32))
    toolbox.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

    # 数组中最前面加入了“选择”
    tool_definitions = [
        "选择", "直线", "矩形", "圆形", "偏移", "标注", "修剪", "漫游"
    ]

    for tool_name in tool_definitions:
        icon = generate_cad_style_icon(tool_name)
        action = QAction(icon, tool_name, main_window)
        action.setToolTip(tool_name)
        toolbox.addAction(action)
        
    return toolbox
def create_status_bar(main_window):
    # 【修复】：移除原有的 styleSheet 设定，全部移入顶部 QSS 统一管理
    lbl_transform_info = QLabel(" 当前坐标与尺寸提示  |  X: 0.00   Y: 0.00   长度: 0.00   角度: 0.00 ")
    main_window.statusBar().addPermanentWidget(lbl_transform_info)
    # 不再在此设置 Message，通过 QSS 统一控制
    return lbl_transform_info

def create_2d_viewport(main_window):
    # 【修复】：移除原有的 styleSheet 设定，全部移入顶部 QSS 统一管理
    dock_2d = QDockWidget("⬛ 2D 绘图视窗", main_window)
    dock_2d.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    
    scene_2d = QGraphicsScene()
    view_2d = CADGraphicsView(scene_2d, main_window) 
    # 保持画布底色由 core_canvas.py 管理 (暗灰)
    scene_2d.addText("2D 绘图区 (支持坐标与对象捕捉追踪)").setDefaultTextColor(Qt.GlobalColor.white)
    dock_2d.setWidget(view_2d)
    return dock_2d, view_2d, scene_2d

def create_3d_viewport(main_window):
    # 【修复】：移除原有的 styleSheet 设定，全部移入顶部 QSS 统一管理
    dock_3d = QDockWidget("🧊 3D 白模视窗", main_window)
    dock_3d.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    
    view_3d = QWidget()
    # 修复：3D 视窗背景移入 QSS，在此处移除
    layout_3d = QVBoxLayout()
    layout_3d.addWidget(QLabel("3D 白模实时预览区", alignment=Qt.AlignmentFlag.AlignCenter))
    view_3d.setLayout(layout_3d)
    dock_3d.setWidget(view_3d)
    return dock_3d

def create_properties_panel(main_window):
    prop_dock = QDockWidget("▼ 实例属性与算量", main_window)
    prop_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    
    widget = QWidget()
    layout = QFormLayout()
    layout.addRow("主宽 W (mm):", QLineEdit("300"))
    layout.addRow("侧深 D (mm):", QLineEdit("150"))
    layout.addRow("板厚 T (mm):", QLineEdit("1.2"))
    
    # 面积 Label 特殊处理：颜色稍微突出一点，但仍保持在暗色系内
    label_area = QLabel("0.00 ㎡")
    label_area.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 14px;")
    layout.addRow("展开面积:", label_area)
    
    widget.setLayout(layout)
    prop_dock.setWidget(widget)
    return prop_dock

def create_library_panel(main_window):
    lib_dock = QDockWidget("▼ 本地组件库", main_window)
    lib_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    
    # 【修复】：QListWidget 的样式和选中色已通过顶部 QSS 统一设置
    lib_list = QListWidget()
    lib_list.addItems(["📁 [默认] 标准壁龛", "📁 [门套] 异形包边", "📁 [型材]踢脚线"])
    lib_dock.setWidget(lib_list)
    return lib_dock