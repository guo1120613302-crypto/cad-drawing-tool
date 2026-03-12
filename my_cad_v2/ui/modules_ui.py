# ui/modules_ui.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QDockWidget, 
                             QFormLayout, QLineEdit, QLabel, QListWidget, 
                             QGraphicsScene, QGridLayout, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QPen
from core.core_canvas import CADGraphicsView 

def generate_cad_style_icon(tool_type):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(255, 255, 255), 1.5) 
    pen.setCosmetic(True)
    painter.setPen(pen)
    
    ix, iy, iw, ih = 4, 4, 24, 24

    if tool_type == "选择":
        cx, cy = 16, 16
        painter.drawLine(cx, 6, cx, 26) 
        painter.drawLine(6, cy, 26, cy)
        painter.drawLine(cx, 6, cx - 3, 9); painter.drawLine(cx, 6, cx + 3, 9)
        painter.drawLine(cx, 26, cx - 3, 23); painter.drawLine(cx, 26, cx + 3, 23)
        painter.drawLine(6, cy, 9, cy - 3); painter.drawLine(6, cy, 9, cy + 3)
        painter.drawLine(26, cy, 23, cy - 3); painter.drawLine(26, cy, 23, cy + 3)
    elif tool_type == "直线":
        painter.drawLine(ix, iy+ih, ix+iw, iy)
    elif tool_type == "矩形":
        painter.drawRect(ix, iy, iw, ih)
    elif tool_type == "偏移":
        pen_bold = QPen(QColor(255, 255, 255), 1.5) 
        painter.setPen(pen_bold)
        painter.drawLine(ix, iy, ix+14, iy)
        painter.drawLine(ix, iy, ix, iy+14)
        painter.drawLine(ix+10, iy+10, ix+iw, iy+10)
        painter.drawLine(ix+10, iy+10, ix+10, iy+ih)
    elif tool_type == "移动":
        # 绘制移动图标：十字箭头（四个方向）
        cx, cy = 16, 16
        arrow_len = 10
        arrow_head = 3
        # 上箭头
        painter.drawLine(cx, cy - arrow_len, cx, cy + arrow_len)
        painter.drawLine(cx, cy - arrow_len, cx - arrow_head, cy - arrow_len + arrow_head)
        painter.drawLine(cx, cy - arrow_len, cx + arrow_head, cy - arrow_len + arrow_head)
        # 下箭头
        painter.drawLine(cx, cy + arrow_len, cx - arrow_head, cy + arrow_len - arrow_head)
        painter.drawLine(cx, cy + arrow_len, cx + arrow_head, cy + arrow_len - arrow_head)
        # 左箭头
        painter.drawLine(cx - arrow_len, cy, cx + arrow_len, cy)
        painter.drawLine(cx - arrow_len, cy, cx - arrow_len + arrow_head, cy - arrow_head)
        painter.drawLine(cx - arrow_len, cy, cx - arrow_len + arrow_head, cy + arrow_head)
        # 右箭头
        painter.drawLine(cx + arrow_len, cy, cx + arrow_len - arrow_head, cy - arrow_head)
        painter.drawLine(cx + arrow_len, cy, cx + arrow_len - arrow_head, cy + arrow_head)
        
    painter.end()
    return QIcon(pixmap)

def create_menu_bar(main_window):
    dark_night_theme = """
    QWidget { background-color: #333333; color: #FFFFFF; font-family: Arial, Microsoft YaHei; font-size: 12px; border: none; }
    QMenuBar { background-color: #222222; border-bottom: 1px solid #111111; padding-left: 5px; }
    QMenuBar::item { background-color: transparent; padding: 5px 10px; color: #BBBBBB; }
    QMenuBar::item:selected { background-color: #555555; color: #FFFFFF; }
    QToolBar { background-color: #2b2b2b; border-right: 1px solid #111111; padding: 5px; }
    QToolButton { background-color: transparent; padding: 5px; border: 1px solid transparent; border-radius: 3px; }
    QToolButton:hover { background-color: #444444; }
    QToolButton:pressed, QToolButton:checked { background-color: #555555; }
    QDockWidget { background-color: #333333; color: #AAAAAA; font-weight: bold; titlebar-close-icon: url(none); titlebar-normal-icon: url(none); }
    QDockWidget::title { background-color: #2b2b2b; padding-left: 10px; padding-top: 6px; padding-bottom: 6px; border-bottom: 1px solid #111111; }
    QStatusBar { background-color: #111111; color: #888888; border-top: 1px solid #000000; padding-left: 5px; }
    QStatusBar QLabel { background-color: transparent; color: #AAAAAA; }
    QLineEdit { background-color: #1a1a1a; color: #FFFFFF; border: 1px solid #111111; border-radius: 2px; padding: 3px 5px; }
    QListWidget { background-color: #1a1a1a; color: #FFFFFF; border: 1px solid #111111; padding: 5px; }
    QListWidget::item:selected { background-color: #555555; color: #FFFFFF; }
    """
    main_window.setStyleSheet(dark_night_theme)

def create_left_toolbox(main_window):
    toolbox = QToolBar("绘图工具")
    main_window.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbox)
    toolbox.setMovable(False)
    toolbox.setIconSize(QSize(32, 32))
    
    # 暂时只挂载 V2.0 已完成的三个核心工具
    tool_definitions = ["选择", "直线", "矩形", "偏移", "移动"]

    for tool_name in tool_definitions:
        icon = generate_cad_style_icon(tool_name)
        action = QAction(icon, tool_name, main_window)
        action.triggered.connect(lambda checked, name=tool_name: main_window.view_2d.switch_tool(name))
        toolbox.addAction(action)
        
    return toolbox

def create_status_bar(main_window):
    lbl_transform_info = QLabel(" 坐标提示区 ")
    main_window.statusBar().addPermanentWidget(lbl_transform_info)
    return lbl_transform_info

def create_2d_viewport(main_window):
    dock_2d = QDockWidget("⬛ 2D 绘图视窗", main_window)
    scene_2d = QGraphicsScene()
    view_2d = CADGraphicsView(scene_2d, main_window) 
    dock_2d.setWidget(view_2d)
    return dock_2d, view_2d, scene_2d

def create_3d_viewport(main_window):
    dock_3d = QDockWidget("🧊 3D 白模视窗 (V2.0 预留)", main_window)
    view_3d = QWidget()
    layout_3d = QVBoxLayout()
    layout_3d.addWidget(QLabel("3D 白模预览区\n(将接入 trimesh 和 pyqtgraph)", alignment=Qt.AlignmentFlag.AlignCenter))
    view_3d.setLayout(layout_3d)
    dock_3d.setWidget(view_3d)
    return dock_3d

def create_properties_panel(main_window):
    prop_dock = QDockWidget("▼ 属性与色板", main_window)
    widget = QWidget()
    layout = QVBoxLayout() 
    layout.addWidget(QLabel("待接入 V2.0 面积报价系统..."))
    
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    layout.addWidget(line)

    layout.addWidget(QLabel("主题色板:"))
    grid_matrix = QGridLayout()
    grid_matrix.setSpacing(1) 
    matrix = main_window.view_2d.color_manager.color_matrix
    
    def make_color_callback(c):
        main_window.view_2d.color_manager.set_color(c)
        # 通知画板更新选中的实体颜色
        for item in main_window.view_2d.scene().selectedItems():
            pen = item.pen()
            pen.setColor(QColor(c))
            item.setPen(pen)

    for r_idx, row in enumerate(matrix):
        for c_idx, hex_col in enumerate(row):
            btn = QPushButton()
            btn.setFixedSize(16, 16)
            btn.setStyleSheet(f"background-color: {hex_col}; border: 1px solid #555;")
            btn.clicked.connect(lambda checked, c=hex_col: make_color_callback(c))
            grid_matrix.addWidget(btn, r_idx, c_idx)
            
    layout.addLayout(grid_matrix)
    layout.addStretch() 
    widget.setLayout(layout)
    prop_dock.setWidget(widget)
    return prop_dock

def create_library_panel(main_window):
    lib_dock = QDockWidget("▼ 本地组件库", main_window)
    lib_list = QListWidget()
    lib_list.addItems(["📁 标准壁龛", "📁 门套异形包边", "📁 踢脚线"])
    lib_dock.setWidget(lib_list)
    return lib_dock