# main.py
import sys
from PyQt6.QtWidgets import QApplication
from core_window import CADWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 全局字体设置
    font = app.font()
    font.setFamily("Microsoft YaHei")
    font.setPointSize(10)
    app.setFont(font)

    # 启动主窗口
    window = CADWindow()
    window.show()
    sys.exit(app.exec())