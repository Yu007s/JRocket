# ui/dockerUtil/DockerUploadPage.py
import subprocess
from PyQt5 import QtWidgets, QtCore


class DockerInfo(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)

        # 文本显示框（支持自动换行、滚动）
        self.text_box = QtWidgets.QPlainTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setStyleSheet("font-family: Menlo, Consolas, monospace; font-size: 13px;")

        # 刷新按钮
        self.refresh_btn = QtWidgets.QPushButton("刷新 Docker Info")
        self.refresh_btn.clicked.connect(self.load_docker_info)

        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.text_box)

        # 启动时自动加载一次
        self.load_docker_info()

    def load_docker_info(self):
        """执行 'dockerUtil info' 并显示结果"""
        try:
            # 执行命令并获取输出
            process = subprocess.Popen(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            if stdout:
                self.text_box.setPlainText(stdout)
            elif stderr:
                self.text_box.setPlainText("错误信息：\n" + stderr)

        except Exception as e:
            self.text_box.setPlainText(f"执行失败：\n{e}")
