# modules_ui.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QDockWidget, 
                             QFormLayout, QLineEdit, QLabel, QListWidget, 
                             QGraphicsView, QGraphicsScene,
                             QGridLayout, QPushButton, QHBoxLayout, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QPen
from core_canvas import CADGraphicsView 

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

def create_menu_bar(main_window):
    dark_night_theme = """
    QWidget {
        background-color: #333333;
        color: #FFFFFF;
        font-family: Arial, Microsoft YaHei;
        font-size: 12px;
        border: none;
    }
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
    QLineEdit:focus { border: 1px solid #555555; }
    QListWidget { background-color: #1a1a1a; color: #FFFFFF; border: 1px solid #111111; padding: 5px; }
    QListWidget::item { padding: 6px; }
    QListWidget::item:selected { background-color: #555555; color: #FFFFFF; }
    """
    main_window.setStyleSheet(dark_night_theme)
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
    lbl_transform_info = QLabel(" 当前坐标与尺寸提示  |  X: 0.00   Y: 0.00   长度: 0.00   角度: 0.00 ")
    main_window.statusBar().addPermanentWidget(lbl_transform_info)
    return lbl_transform_info

def create_2d_viewport(main_window):
    dock_2d = QDockWidget("⬛ 2D 绘图视窗", main_window)
    dock_2d.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    
    scene_2d = QGraphicsScene()
    view_2d = CADGraphicsView(scene_2d, main_window) 
    scene_2d.addText("2D 绘图区 (支持坐标与对象捕捉追踪)").setDefaultTextColor(Qt.GlobalColor.white)
    dock_2d.setWidget(view_2d)
    return dock_2d, view_2d, scene_2d

def create_3d_viewport(main_window):
    dock_3d = QDockWidget("🧊 3D 白模视窗", main_window)
    dock_3d.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    
    view_3d = QWidget()
    layout_3d = QVBoxLayout()
    layout_3d.addWidget(QLabel("3D 白模实时预览区", alignment=Qt.AlignmentFlag.AlignCenter))
    view_3d.setLayout(layout_3d)
    dock_3d.setWidget(view_3d)
    return dock_3d

def create_properties_panel(main_window):
    prop_dock = QDockWidget("▼ 实例属性与色板", main_window)
    prop_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    
    widget = QWidget()
    layout = QVBoxLayout() 
    layout.setSpacing(10)
    
    # 1. 属性表单
    form_layout = QFormLayout()
    form_layout.addRow("主宽 W (mm):", QLineEdit("300"))
    form_layout.addRow("侧深 D (mm):", QLineEdit("150"))
    form_layout.addRow("板厚 T (mm):", QLineEdit("1.2"))
    label_area = QLabel("0.00 ㎡")
    label_area.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 14px;")
    form_layout.addRow("展开面积:", label_area)
    layout.addLayout(form_layout)

    # 分割线
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #444;")
    layout.addWidget(line)

    # 2. 颜色选择区
    layout.addWidget(QLabel("主题色板:"))

    # 主颜色矩阵 (6行 x 9列)
    grid_matrix = QGridLayout()
    grid_matrix.setSpacing(1) # 紧凑排布
    matrix = main_window.view_2d.color_manager.color_matrix
    
    def make_color_callback(c):
        main_window.view_2d.color_manager.set_color(c)
        main_window.view_2d.color_manager.apply_color_to_selected(main_window.view_2d)

    for row_idx, row in enumerate(matrix):
        for col_idx, color_hex in enumerate(row):
            btn = QPushButton()
            btn.setFixedSize(16, 16) # CAD风格的小方块
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #555;")
            btn.clicked.connect(lambda checked, c=color_hex: make_color_callback(c))
            grid_matrix.addWidget(btn, row_idx, col_idx)
            
    layout.addLayout(grid_matrix)
    
    layout.addSpacing(5)
    layout.addWidget(QLabel("标准索引颜色:"))
    
    # 底部索引色
    grid_index = QGridLayout()
    grid_index.setSpacing(1)
    index_colors = main_window.view_2d.color_manager.index_colors
    for i, color_hex in enumerate(index_colors):
        btn = QPushButton()
        btn.setFixedSize(16, 16)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #777;")
        btn.clicked.connect(lambda checked, c=color_hex: make_color_callback(c))
        grid_index.addWidget(btn, 0, i)
        
    layout.addLayout(grid_index)
    layout.addStretch() 
    
    widget.setLayout(layout)
    prop_dock.setWidget(widget)
    return prop_dock

def create_library_panel(main_window):
    lib_dock = QDockWidget("▼ 本地组件库", main_window)
    lib_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    lib_list = QListWidget()
    lib_list.addItems(["📁 [默认] 标准壁龛", "📁 [门套] 异形包边", "📁 [型材]踢脚线"])
    lib_dock.setWidget(lib_list)
    return lib_dock