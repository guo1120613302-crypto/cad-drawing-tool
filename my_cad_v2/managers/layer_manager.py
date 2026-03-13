# managers/layer_manager.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, 
                             QColorDialog, QInputDialog, QMessageBox, QSlider)
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QGraphicsItem

class LayerListWidget(QListWidget):
    """支持 Delete 键快速删除的自定义列表"""
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.manager.delete_layer()
        else:
            super().keyPressEvent(event)

class LayerManager(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        
        # 核心数据增加 opacity (不透明度)
        self.layers = {
            "0": {"color": QColor(255, 255, 255), "visible": True, "locked": False, "opacity": 1.0},
            "轮廓线": {"color": QColor(0, 255, 0), "visible": True, "locked": False, "opacity": 1.0},
            "中心线": {"color": QColor(255, 0, 0), "visible": True, "locked": False, "opacity": 1.0}
        }
        self.current_layer = "0"
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 5, 0, 0)
        
        # 1. PS 风格：不透明度拉杆
        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("不透明度:"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.valueChanged.connect(self.on_opacity_changed)
        op_layout.addWidget(self.slider_opacity)
        self.lbl_opacity_val = QLabel("100%")
        self.lbl_opacity_val.setFixedWidth(35)
        op_layout.addWidget(self.lbl_opacity_val)
        layout.addLayout(op_layout)
        
        # 2. 图层列表
        self.list_widget = LayerListWidget(self)
        self.list_widget.currentRowChanged.connect(self.on_row_changed)
        layout.addWidget(self.list_widget)
        
        # 3. PS 风格：底部新建与删除按钮
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("➕ 新建")
        self.btn_add.clicked.connect(self.add_layer)
        self.btn_del = QPushButton("🗑️ 删除")
        self.btn_del.clicked.connect(self.delete_layer)
        
        # 按钮样式美化
        btn_style = "QPushButton { background-color: #444; border: 1px solid #222; padding: 4px; border-radius: 3px; } QPushButton:hover { background-color: #555; }"
        self.btn_add.setStyleSheet(btn_style)
        self.btn_del.setStyleSheet(btn_style)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_del)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.refresh_list()
        
    def refresh_list(self):
        self.list_widget.clear()
        for name, data in self.layers.items():
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 32))
            self.list_widget.addItem(item)
            
            row_widget = QWidget()
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(5, 0, 5, 0)
            
            # 色块
            btn_color = QPushButton()
            btn_color.setFixedSize(16, 16)
            btn_color.setStyleSheet(f"background-color: {data['color'].name()}; border: 1px solid #555; border-radius: 2px;")
            btn_color.clicked.connect(lambda checked, n=name: self.change_color(n))
            
            # 图层名称高亮
            lbl_name = QLabel(name)
            if name == self.current_layer:
                lbl_name.setStyleSheet("color: #00FF00; font-weight: bold;")
            else:
                lbl_name.setStyleSheet("color: #DDDDDD;")
            
            # 眼睛 (可见性)
            btn_vis = QPushButton("👁️" if data['visible'] else "❌")
            btn_vis.setFixedSize(24, 24)
            btn_vis.setStyleSheet("background: transparent; border: none; font-size: 14px;")
            btn_vis.clicked.connect(lambda checked, n=name: self.toggle_visible(n))
            
            # 锁头 (锁定)
            btn_lock = QPushButton("🔒" if data['locked'] else "🔓")
            btn_lock.setFixedSize(24, 24)
            btn_lock.setStyleSheet("background: transparent; border: none; font-size: 14px;")
            btn_lock.clicked.connect(lambda checked, n=name: self.toggle_lock(n))
            
            row_layout.addWidget(btn_color)
            row_layout.addWidget(lbl_name)
            row_layout.addStretch()
            row_layout.addWidget(btn_vis)
            row_layout.addWidget(btn_lock)
            row_widget.setLayout(row_layout)
            
            self.list_widget.setItemWidget(item, row_widget)
            if name == self.current_layer:
                item.setSelected(True)

    def on_row_changed(self, index):
        if index >= 0:
            name = list(self.layers.keys())[index]
            self.current_layer = name
            # 切换图层时，同步不透明度拉杆的值
            op_val = int(self.layers[name]["opacity"] * 100)
            self.slider_opacity.blockSignals(True)
            self.slider_opacity.setValue(op_val)
            self.lbl_opacity_val.setText(f"{op_val}%")
            self.slider_opacity.blockSignals(False)
            self.refresh_list()
            
    def on_opacity_changed(self, value):
        self.lbl_opacity_val.setText(f"{value}%")
        self.layers[self.current_layer]["opacity"] = value / 100.0
        self.sync_items_to_layer(self.current_layer)

    def add_layer(self):
        name, ok = QInputDialog.getText(self, "新建图层", "请输入图层名称:")
        if ok and name:
            if name in self.layers:
                QMessageBox.warning(self, "错误", "图层名称已存在！")
                return
            self.layers[name] = {"color": QColor(255, 255, 255), "visible": True, "locked": False, "opacity": 1.0}
            self.refresh_list()

    def delete_layer(self):
        # 只对基准图层"0"显示警告
        if self.current_layer == "0":
            reply = QMessageBox.question(self, '确认删除', "默认图层 0 是基准层，确定要删除吗？")
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # 收集要删除的图形
        items_to_remove = [item for item in self.canvas.scene().items() if getattr(item, 'layer_name', None) == self.current_layer]
        
        # 创建撤销命令
        from PyQt6.QtGui import QUndoCommand
        
        class CommandDeleteLayer(QUndoCommand):
            def __init__(self, manager, layer_name, layer_data, items):
                super().__init__()
                self.manager = manager
                self.layer_name = layer_name
                self.layer_data = layer_data.copy()
                self.items = items
                
            def redo(self):
                # 删除图层和图形
                for item in self.items:
                    if item.scene() == self.manager.canvas.scene():
                        self.manager.canvas.scene().removeItem(item)
                if self.layer_name in self.manager.layers:
                    del self.manager.layers[self.layer_name]
                self.manager.current_layer = "0"
                self.manager.refresh_list()
                self.manager.canvas.viewport().update()
                
            def undo(self):
                # 恢复图层和图形
                self.manager.layers[self.layer_name] = self.layer_data.copy()
                for item in self.items:
                    if item.scene() != self.manager.canvas.scene():
                        self.manager.canvas.scene().addItem(item)
                self.manager.current_layer = self.layer_name
                self.manager.refresh_list()
                self.manager.canvas.viewport().update()
        
        # 执行删除命令
        cmd = CommandDeleteLayer(self, self.current_layer, self.layers[self.current_layer], items_to_remove)
        self.canvas.undo_stack.push(cmd)

    def change_color(self, name):
        color = QColorDialog.getColor(self.layers[name]["color"], self, "选择图层颜色")
        if color.isValid():
            self.layers[name]["color"] = color
            self.sync_items_to_layer(name)
            self.refresh_list()
            
    def toggle_visible(self, name):
        self.layers[name]["visible"] = not self.layers[name]["visible"]
        self.sync_items_to_layer(name)
        self.refresh_list()
        
    def toggle_lock(self, name):
        self.layers[name]["locked"] = not self.layers[name]["locked"]
        self.sync_items_to_layer(name)
        self.refresh_list()

    def sync_items_to_layer(self, layer_name):
        layer_data = self.layers[layer_name]
        for item in self.canvas.scene().items():
            if getattr(item, "layer_name", None) == layer_name:
                item.setVisible(layer_data["visible"])
                item.setOpacity(layer_data["opacity"])
                if layer_data["locked"]:
                    item.setSelected(False)
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                else:
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.canvas.viewport().update()

    def apply_current_layer_props(self, item):
        """【防 Bug 核心】：将当前图层的属性，强行打入刚刚新建的图形中"""
        layer_name = self.current_layer
        item.layer_name = layer_name
        data = self.layers[layer_name]
        item.setVisible(data["visible"])
        item.setOpacity(data["opacity"])
        if data["locked"]:
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def copy_layer_props(self, target_item, source_item):
        """【新增】：从源图形复制图层属性到目标图形"""
        if not hasattr(source_item, 'layer_name'):
            # 如果源图形没有图层属性，使用当前图层
            self.apply_current_layer_props(target_item)
            return
            
        layer_name = source_item.layer_name
        if layer_name not in self.layers:
            # 如果图层不存在，使用当前图层
            self.apply_current_layer_props(target_item)
            return
            
        target_item.layer_name = layer_name
        data = self.layers[layer_name]
        target_item.setVisible(data["visible"])
        target_item.setOpacity(data["opacity"])
        if data["locked"]:
            target_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        else:
            target_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)


    def get_color(self):
        """兼容接口：防止绘图工具在定点时找不到颜色而崩溃卡死"""
        if hasattr(self, 'override_color'):
            return self.override_color
        return self.layers[self.current_layer]["color"]

    def set_color(self, color_hex):
        """兼容接口：接收右侧局部色板的点按"""
        self.override_color = QColor(color_hex)