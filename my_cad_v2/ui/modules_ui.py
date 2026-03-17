# ui/modules_ui.py
import math 
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QDockWidget, 
                             QFormLayout, QLineEdit, QLabel, QListWidget, 
                             QGraphicsScene, QGridLayout, QPushButton, QFrame, QMenu, QToolButton)
from PyQt6.QtCore import Qt, QSize, QPointF, QObject, QEvent
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QPen, QActionGroup, QPolygonF,QPainterPath



def generate_cad_style_icon(tool_type, has_submenu=False):
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
        painter.drawLine(cx, 6, cx, 26); painter.drawLine(6, cy, 26, cy)
        painter.drawLine(cx, 6, cx - 3, 9); painter.drawLine(cx, 6, cx + 3, 9)
        painter.drawLine(cx, 26, cx - 3, 23); painter.drawLine(cx, 26, cx + 3, 23)
        painter.drawLine(6, cy, 9, cy - 3); painter.drawLine(6, cy, 9, cy + 3)
        painter.drawLine(26, cy, 23, cy - 3); painter.drawLine(26, cy, 23, cy + 3)
    elif tool_type == "直线":
        painter.drawLine(ix, iy+ih, ix+iw, iy)
    elif tool_type == "多段线":
        painter.drawLine(6, 26, 12, 12)
        painter.drawLine(12, 12, 20, 20)
        painter.drawLine(20, 20, 26, 6)
        painter.drawEllipse(5, 25, 2, 2); painter.drawEllipse(11, 11, 2, 2)
        painter.drawEllipse(19, 19, 2, 2); painter.drawEllipse(25, 5, 2, 2)
    elif tool_type == "矩形":
        painter.drawRect(ix, iy, iw, ih)

    elif tool_type == "多边形":
        poly = QPolygonF()
        cx, cy, r = 16, 16, 11
        for i in range(6):
            a = math.radians(i * 60)
            poly.append(QPointF(cx + r * math.cos(a), cy - r * math.sin(a)))
        painter.drawPolygon(poly)
        painter.drawPoint(cx, cy)

    elif tool_type == "圆":
        painter.drawEllipse(6, 6, 20, 20)
        painter.drawLine(14, 16, 18, 16)
        painter.drawLine(16, 14, 16, 18)
    elif tool_type == "椭圆":
        painter.drawEllipse(4, 10, 24, 12)
        pen_dash = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
        pen_dash.setCosmetic(True)
        painter.setPen(pen_dash)
        painter.drawLine(4, 16, 28, 16)
        painter.drawLine(16, 10, 16, 22)
        painter.setPen(pen)

    elif tool_type == "文字":
        font = painter.font()
        font.setPointSize(16)
        font.setBold(True)
        font.setFamily("Arial")
        painter.setFont(font)
        painter.drawText(ix, iy, iw, ih, Qt.AlignmentFlag.AlignCenter, "T")

    elif tool_type == "圆弧":
        painter.drawArc(6, 6, 20, 20, 0 * 16, 270 * 16)
        painter.drawEllipse(25, 15, 2, 2)
        painter.drawEllipse(15, 5, 2, 2)
    elif tool_type == "三点圆弧":
        painter.drawArc(6, 6, 20, 20, 0 * 16, 270 * 16)
        painter.drawEllipse(25, 15, 2, 2)
        painter.drawEllipse(15, 5, 2, 2)
        painter.drawEllipse(5, 15, 2, 2)
    elif tool_type == "起点-圆心-终点":
        painter.drawArc(6, 6, 20, 20, 0 * 16, 270 * 16)
        painter.drawLine(14, 16, 18, 16)
        painter.drawLine(16, 14, 16, 18)
        painter.drawEllipse(25, 15, 2, 2)
        painter.drawEllipse(15, 5, 2, 2)
    elif tool_type == "起点-终点-半径":
        painter.drawArc(6, 6, 20, 20, 0 * 16, 270 * 16)
        painter.drawEllipse(25, 15, 2, 2)
        painter.drawEllipse(15, 5, 2, 2)
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)
        painter.drawText(12, 20, "R")
    elif tool_type == "偏移":
        pen_bold = QPen(QColor(255, 255, 255), 1.5) 
        painter.setPen(pen_bold)
        painter.drawLine(ix, iy, ix+14, iy); painter.drawLine(ix, iy, ix, iy+14)
        painter.drawLine(ix+10, iy+10, ix+iw, iy+10); painter.drawLine(ix+10, iy+10, ix+10, iy+ih)
    elif tool_type == "旋转":
        painter.drawArc(6, 6, 20, 20, 45 * 16, 270 * 16)
        painter.drawLine(26, 16, 22, 12); painter.drawLine(26, 16, 30, 12); painter.drawPoint(16, 16)
    elif tool_type == "镜像":
        pen_dash = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
        pen_dash.setCosmetic(True); painter.setPen(pen_dash)
        painter.drawLine(16, 4, 16, 28) 
        painter.setPen(pen)
        painter.drawLine(6, 8, 14, 16); painter.drawLine(14, 16, 6, 24); painter.drawLine(6, 24, 6, 8)
        painter.setPen(pen_dash)
        painter.drawLine(26, 8, 18, 16); painter.drawLine(18, 16, 26, 24); painter.drawLine(26, 24, 26, 8)
    elif tool_type == "修剪":
        painter.drawLine(6, 16, 12, 16); painter.drawLine(20, 16, 26, 16); painter.drawLine(16, 6, 16, 26)
        pen_dash = QPen(QColor(255, 0, 0), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash); painter.drawLine(12, 16, 20, 16)
    elif tool_type == "延伸":
        painter.drawLine(24, 6, 24, 26); painter.drawLine(6, 16, 15, 16)
        pen_dash = QPen(QColor(0, 255, 0), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash); painter.drawLine(15, 16, 24, 16)
    elif tool_type == "打断":
        painter.drawLine(4, 16, 12, 16); painter.drawLine(20, 16, 28, 16) 
        pen_break = QPen(QColor(255, 165, 0), 1.5); painter.setPen(pen_break)
        painter.drawLine(16, 12, 16, 20); painter.drawLine(12, 16, 20, 16)
    elif tool_type == "样条曲线":
        path = QPainterPath()
        path.moveTo(4, 24)
        path.cubicTo(12, 4, 20, 28, 28, 8)
        painter.drawPath(path)
        painter.drawEllipse(3, 23, 2, 2)
        painter.drawEllipse(27, 7, 2, 2)
    elif tool_type in ("标注", "线性标注"):
        pen_solid = QPen(QColor(255, 255, 255), 1); painter.setPen(pen_solid)
        painter.drawLine(6, 6, 6, 26); painter.drawLine(26, 6, 26, 26); painter.drawLine(6, 16, 26, 16)
        painter.drawLine(6, 16, 9, 13); painter.drawLine(6, 16, 9, 19)
        painter.drawLine(26, 16, 23, 13); painter.drawLine(26, 16, 23, 19)
        font = painter.font(); font.setPointSize(6); painter.setFont(font); painter.drawText(12, 14, "10")

    elif tool_type == "智能标注":
        pen_dim = QPen(QColor(255, 255, 255), 1)
        painter.setPen(pen_dim)
        painter.drawLine(6, 24, 6, 8); painter.drawLine(26, 24, 26, 8)
        painter.drawLine(6, 12, 26, 12)
        # 画个小闪电代表“智能”
        pen_spark = QPen(QColor(255, 200, 0), 1.5)
        painter.setPen(pen_spark)
        painter.drawLine(14, 8, 12, 16); painter.drawLine(12, 16, 18, 14); painter.drawLine(18, 14, 16, 22)
    elif tool_type == "多重引线":
        painter.drawLine(6, 24, 14, 14); painter.drawLine(14, 14, 26, 14)
        painter.drawLine(16, 10, 26, 10); painter.drawLine(16, 18, 26, 18)
        painter.drawEllipse(4, 22, 3, 3)

    elif tool_type == "角度标注":
        painter.drawLine(6, 26, 26, 26); painter.drawLine(6, 26, 20, 12)
        painter.drawArc(10, 10, 32, 32, 135*16, 45*16)
        painter.drawEllipse(18, 14, 2, 2); painter.drawEllipse(22, 24, 2, 2)
    elif tool_type == "弧长标注":
        painter.drawArc(6, 12, 20, 20, 45*16, 90*16)
        painter.drawLine(6, 22, 6, 10); painter.drawLine(26, 22, 26, 10)
        font = painter.font(); font.setPointSize(8); painter.setFont(font)
        painter.drawText(12, 14, "⌒")

    elif tool_type == "缩放":
        painter.drawRect(6, 16, 10, 10)
        pen_dash = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash)
        painter.drawRect(6, 6, 20, 20)
        painter.drawLine(16, 16, 26, 6)
        
    elif tool_type == "阵列":
        for x in [6, 14, 22]:
            for y in [6, 14, 22]:
                painter.drawRect(x, y, 4, 4)

    elif tool_type == "打散":
        painter.drawLine(6, 6, 12, 6); painter.drawLine(6, 6, 6, 12)
        painter.drawLine(26, 6, 20, 6); painter.drawLine(26, 6, 26, 12)
        painter.drawLine(6, 26, 12, 26); painter.drawLine(6, 26, 6, 20)
        painter.drawLine(26, 26, 20, 26); painter.drawLine(26, 26, 26, 20)
        painter.drawPoint(16, 16)
        
    elif tool_type == "合并":
        painter.drawLine(6, 16, 12, 16); painter.drawLine(20, 16, 26, 16)
        pen_blue = QPen(QColor(0, 120, 215), 2)
        painter.setPen(pen_blue)
        painter.drawLine(12, 16, 20, 16)
        
    elif tool_type == "倒直角":
        painter.drawLine(6, 26, 6, 14); painter.drawLine(26, 6, 14, 6)
        pen_cyan = QPen(QColor(0, 255, 255), 1.5)
        painter.setPen(pen_cyan)
        painter.drawLine(6, 14, 14, 6)
        
    elif tool_type == "倒圆角":
        painter.drawLine(6, 26, 6, 14); painter.drawLine(26, 6, 14, 6)
        pen_cyan = QPen(QColor(0, 255, 255), 1.5)
        painter.setPen(pen_cyan)
        painter.drawArc(6, 6, 16, 16, 90 * 16, 90 * 16)
    elif tool_type == "复制":  # <--- 新增这段复制图标的绘制
        painter.setPen(QPen(Qt.GlobalColor.white, 1.5))
        painter.drawRect(6, 6, 12, 12)
        painter.setPen(QPen(QColor(0, 255, 255), 1.5, Qt.PenStyle.DashLine))
        painter.drawRect(14, 14, 12, 12)
    elif tool_type == "比例缩放":   # <--- 把 "缩放" 改成 "比例缩放"
        painter.drawRect(6, 16, 10, 10)
        pen_dash = QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash)
        painter.drawRect(6, 6, 20, 20)
        painter.drawLine(16, 16, 26, 6)
    
    if has_submenu:
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        triangle = QPolygonF([QPointF(24, 28), QPointF(28, 28), QPointF(28, 24)])
        painter.drawPolygon(triangle)
        
    elif tool_type == "建块":
        # 画两个小方块，外面加一个虚线框，表示将它们“打包”成一个整体
        painter.drawRect(8, 8, 8, 8)
        painter.drawRect(18, 16, 8, 8)
        
        pen_dash = QPen(QColor(255, 255, 255, 180), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash)
        painter.drawRect(4, 4, 26, 26)
    painter.end()
    return QIcon(pixmap)

def create_menu_bar(main_window):
    dark_night_theme = """
    QWidget { background-color: #333333; color: #FFFFFF; font-family: Arial, Microsoft YaHei; font-size: 12px; border: none; }
    QMenuBar { background-color: #222222; border-bottom: 1px solid #111111; padding-left: 5px; }
    QMenuBar::item { background-color: transparent; padding: 5px 10px; color: #BBBBBB; }
    QMenuBar::item:selected { background-color: #555555; color: #FFFFFF; }
    
    /* === 修改：将 padding 和 spacing 设为 0 === */
    QToolBar { background-color: #2b2b2b; border-right: 1px solid #111111; padding: 0px; spacing: 0px; }
    
    /* === 修改：将 padding 从 4px 缩小为 2px === */
    QToolButton { background-color: transparent; padding: 2px; border: 1px solid transparent; border-radius: 3px; }
    
    QToolButton:hover { background-color: #444444; }
    QToolButton:checked { background-color: #1a1a1a; border: 1px solid #000000; } 
    QToolButton::menu-button { border: none; width: 0px; }
    QToolButton::menu-arrow { image: none; width: 0px; }
    QToolButton::menu-indicator { image: none; width: 0px; }
    QDockWidget { background-color: #333333; color: #AAAAAA; font-weight: bold; titlebar-close-icon: url(none); titlebar-normal-icon: url(none); }
    QDockWidget::title { background-color: #2b2b2b; padding-left: 10px; padding-top: 6px; padding-bottom: 6px; border-bottom: 1px solid #111111; }
    QStatusBar { background-color: #111111; color: #888888; border-top: 1px solid #000000; padding-left: 5px; }
    QStatusBar QLabel { background-color: transparent; color: #AAAAAA; }
    QLineEdit { background-color: #1a1a1a; color: #FFFFFF; border: 1px solid #111111; border-radius: 2px; padding: 3px 5px; }
    QListWidget { background-color: #2b2b2b; color: #FFFFFF; border: none; outline: none; }
    QListWidget::item { border-bottom: 1px solid #222222; }
    QListWidget::item:selected { background-color: #4a4a4a; } 
    """
    main_window.setStyleSheet(dark_night_theme)
def create_left_toolbox(main_window):
    toolbox = QToolBar("绘图工具")
    main_window.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbox)
    toolbox.setMovable(False)
    
    # 🌟 修改：将整体图标尺寸从 32x32 缩小为 24x24
    toolbox.setIconSize(QSize(24, 24))
    
    # 完全禁用工具栏的右键菜单
    toolbox.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    def toolbar_context_menu(event):
        event.ignore()
    toolbox.contextMenuEvent = toolbar_context_menu
    
    ag = QActionGroup(main_window)
    ag.setExclusive(True)

    # 🌟 修改：重新组织工具列表，将 5 个标注合并为二级菜单
    tool_definitions = [
        ("选择", "选择", False, []),
        ("直线", "直线", False, []),
        ("多段线", "多段线", False, []),
        ("样条曲线", "样条曲线", False, []),
        ("多边形", "多边形", False, []),
        ("矩形", "矩形", False, []),
        ("圆", "圆", False, []),
        ("椭圆", "椭圆", False, []),
        ("三点圆弧", "圆弧", True, [
            ("三点圆弧", "3point"),
            ("起点-圆心-终点", "center"),
            ("起点-终点-半径", "radius")
        ]),
        ("偏移", "偏移", False, []),
        ("复制", "复制", False, []),
        ("旋转", "旋转", False, []),
        ("镜像", "镜像", False, []),
        ("修剪", "修剪", False, []),
        ("延伸", "延伸", False, []),
        ("打断", "打断", False, []),
        ("文字", "文字", False, []),

        # --- 新增的 6 个高级编辑工具 ---
        ("比例缩放", "比例缩放", False, []),
        ("阵列", "阵列", False, []),
        
        ("倒直角", "倒直角", False, []),
        ("倒圆角", "倒圆角", False, []),
        ("打散", "打散", False, []),
        ("合并", "合并", False, []),
        ("建块", "建块", False, []),
        # --- 合并的标注组 ---
        ("智能标注", "标注组", True, [
            ("智能标注", "智能标注"),
            ("角度标注", "角度标注"),
            ("弧长标注", "弧长标注"),
            ("多重引线", "多重引线"),
            ("线性标注", "标注")
        ])
    ]

    for display_name, tool_name, has_submenu, subtools in tool_definitions:
        if has_submenu:
            icon = generate_cad_style_icon(display_name, has_submenu=True)
            action = QAction(icon, display_name, main_window)
            action.setCheckable(True)
            ag.addAction(action)

            # 动态记录当前激活的子工具状态
            setattr(main_window, f"current_{tool_name}_tool", display_name)
            setattr(main_window, f"{tool_name}_action", action)
            
            # 主按钮直接点击时，应用当前记录的子工具
            def make_main_click_handler(tn=tool_name, subs=subtools):
                def handler():
                    current_sub = getattr(main_window, f"current_{tn}_tool")
                    if tn == "圆弧":
                        main_window.view_2d.switch_tool("圆弧")
                        for sd, sv in subs:
                            if sd == current_sub:
                                main_window.view_2d.current_tool.set_mode(sv)
                                break
                    else:  # 标注组
                        for sd, sv in subs:
                            if sd == current_sub:
                                main_window.view_2d.switch_tool(sv)
                                break
                return handler
            
            action.triggered.connect(make_main_click_handler())
            
            menu = QMenu(main_window)
            
            for subtool_name, mode_or_tool in subtools:
                def make_submenu_handler(st_name, m, tn=tool_name, act=action):
                    def handler():
                        if tn == "圆弧":
                            main_window.view_2d.switch_tool("圆弧")
                            main_window.view_2d.current_tool.set_mode(m)
                        else:  # 标注组
                            main_window.view_2d.switch_tool(m)
                            
                        setattr(main_window, f"current_{tn}_tool", st_name)
                        new_icon = generate_cad_style_icon(st_name, has_submenu=True)
                        act.setIcon(new_icon)
                        act.setText(st_name)
                        act.setChecked(True)
                    return handler
                
                submenu_action = QAction(subtool_name, main_window)
                submenu_action.triggered.connect(make_submenu_handler(subtool_name, mode_or_tool))
                menu.addAction(submenu_action)
            
            toolbox.addAction(action)
            tool_button = toolbox.widgetForAction(action)
            if isinstance(tool_button, QToolButton):
                tool_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                tool_button.setMenu(menu)
                
                menu.setStyleSheet("""
                    QMenu {
                        background-color: #2b2b2b;
                        color: #FFFFFF;
                        border: 1px solid #555555;
                        padding: 4px;
                    }
                    QMenu::item {
                        background-color: transparent;
                        padding: 6px 20px;
                        border-radius: 2px;
                    }
                    QMenu::item:selected {
                        background-color: #0078d4;
                        color: #FFFFFF;
                    }
                    QMenu::item:hover {
                        background-color: #0078d4;
                        color: #FFFFFF;
                    }
                """)
        else:
            icon = generate_cad_style_icon(display_name)
            action = QAction(icon, display_name, main_window)
            action.setCheckable(True)
            if tool_name == "直线": 
                action.setChecked(True)
            
            ag.addAction(action)
            action.triggered.connect(lambda checked, name=tool_name: main_window.view_2d.switch_tool(name))
            toolbox.addAction(action)
        
    main_window.tool_actions = ag 
    return toolbox
def create_status_bar(main_window):
    lbl_transform_info = QLabel(" 坐标提示区 ")
    main_window.statusBar().addPermanentWidget(lbl_transform_info)
    return lbl_transform_info

def create_2d_viewport(main_window):
    dock_2d = QDockWidget("⬛ 2D 绘图视窗", main_window)
    from core.core_canvas import CADGraphicsView
    scene_2d = QGraphicsScene()
    view_2d = CADGraphicsView(scene_2d, main_window) 
    dock_2d.setWidget(view_2d)
    return dock_2d, view_2d, scene_2d

def create_3d_viewport(main_window):
    dock_3d = QDockWidget("🧊 3D 白模视窗", main_window)
    view_3d = QWidget()
    layout_3d = QVBoxLayout()
    layout_3d.addWidget(QLabel("3D 白模预览区\n(将接入 trimesh 和 pyqtgraph)", alignment=Qt.AlignmentFlag.AlignCenter))
    view_3d.setLayout(layout_3d)
    dock_3d.setWidget(view_3d)
    return dock_3d

def create_properties_panel(main_window):
    prop_dock = QDockWidget("▼ 属性与图层", main_window)
    widget = QWidget()
    layout = QVBoxLayout() 
    layout.setContentsMargins(5, 5, 5, 5)

    layout.addWidget(QLabel("🎨 主题色板 (Color Palette):"))
    grid_matrix = QGridLayout()
    grid_matrix.setSpacing(1) 
    
    matrix = main_window.view_2d.color_manager.color_matrix
    
    def make_color_callback(c):
        main_window.view_2d.color_manager.set_color(c)
        for item in main_window.view_2d.scene().selectedItems():
            pen = item.pen()
            pen.setColor(QColor(c))
            item.setPen(pen)

    for r_idx, row in enumerate(matrix):
        for c_idx, hex_col in enumerate(row):
            btn = QPushButton()
            btn.setFixedSize(16, 16)
            btn.setStyleSheet(f"background-color: {hex_col}; border: 1px solid #555; border-radius: 2px;")
            btn.clicked.connect(lambda checked, c=hex_col: make_color_callback(c))
            grid_matrix.addWidget(btn, r_idx, c_idx)
            
    layout.addLayout(grid_matrix)
    
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #444;")
    layout.addWidget(line)

    layout.addWidget(QLabel("📚 图层面板 (Layers):"))
    layout.addWidget(main_window.view_2d.layer_manager)
    
    widget.setLayout(layout)
    prop_dock.setWidget(widget)
    return prop_dock

def create_library_panel(main_window):
    lib_dock = QDockWidget("▼ 本地组件库", main_window)
    lib_list = QListWidget()
    lib_list.addItems(["📁 标准壁龛", "📁 门套异形包边", "📁 踢脚线"])
    lib_dock.setWidget(lib_list)
    return lib_dock
