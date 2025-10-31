from PyQt5 import QtWidgets
from ui.log_out.LogPage import LogPage


class SkinPage(QtWidgets.QWidget):
    """封装主题切换功能"""
    themes = {
        "默认风格": "",  # 保持 PyQt 默认样式
        "深色风格": """
            QWidget { background-color: #1E1E1E; color: #FFFFFF; }
            QPushButton { background-color: #0078D7; color: #FFFFFF; border-radius: 4px; padding: 4px; }
            QLineEdit, QTextEdit { background-color: #2D2D30; color: #FFFFFF; border: 1px solid #3C3C3C; }
        """,
        "VSCode 蓝色": """
            QWidget { background-color: #1E1E2F; color: #D4D4D4; }
            QPushButton { background-color: #0E639C; color: #FFFFFF; border-radius: 3px; padding: 4px; }
            QLineEdit, QTextEdit { background-color: #252526; color: #D4D4D4; border: 1px solid #3C3C3C; }
        """,
        "金属风格": """
            QWidget { background-color: #3A3A3A; color: #F5F5F5; font-family: "Segoe UI"; }
            QPushButton { background-color: #5C5C5C; color: #FFFFFF; border-radius: 5px; padding: 5px; }
            QLineEdit, QTextEdit { background-color: #2F2F2F; color: #FFFFFF; border: 1px solid #4F4F4F; }
        """,
        "ACG 渐变": """
            QWidget { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                       stop:0 #FFB6C1, stop:1 #8A2BE2); color: #FFFFFF; }
            QPushButton { background-color: rgba(255,255,255,0.3); color: #FFFFFF; border-radius: 6px; padding: 6px; }
            QLineEdit, QTextEdit { background-color: rgba(255,255,255,0.2); color: #FFFFFF; border: 1px solid #FFFFFF; }
        """,
        "卡通风格": """
            QWidget { background-color: #FFFAF0; color: #333333; font-family: Comic Sans MS; }
            QPushButton { background-color: #FF69B4; color: #FFFFFF; border-radius: 8px; padding: 6px; }
            QLineEdit, QTextEdit { background-color: #FFF0F5; color: #333333; border: 1px solid #FF69B4; }
        """,
        "霓虹风格": """
            QWidget { background-color: #0C0C0C; color: #39FF14; }
            QPushButton { background-color: #FF00FF; color: #FFFFFF; border-radius: 6px; padding: 5px; }
            QLineEdit, QTextEdit { background-color: #1A1A1A; color: #39FF14; border: 1px solid #FF00FF; }
        """,
        "毛玻璃风格（Mac）": """
            QWidget { background-color: rgba(255,255,255,0.05); color: #FFFFFF; backdrop-filter: blur(20px); }
            QPushButton { background-color: rgba(255,255,255,0.15); color: #FFFFFF; border-radius: 6px; padding: 6px; }
            QLineEdit, QTextEdit { background-color: rgba(255,255,255,0.1); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.3); }
        """
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("选择软件主题:"))

        self.theme_selector = QtWidgets.QComboBox()
        self.theme_selector.addItems(list(self.themes.keys()))
        layout.addWidget(self.theme_selector)

        self.apply_btn = QtWidgets.QPushButton("应用主题")
        layout.addWidget(self.apply_btn)
        self.apply_btn.clicked.connect(self.apply_theme)

    def apply_theme(self):
        theme_name = self.theme_selector.currentText()
        qss = self.themes.get(theme_name, "")
        app = QtWidgets.QApplication.instance()
        if app:
            app.setStyleSheet(qss)
        LogPage.log(f"[主题切换] 已应用主题: {theme_name}")
