# ui/dockerUtil/DockerUploadPage.py
import subprocess
import os
from PyQt5 import QtWidgets, QtGui, QtCore


class DockerUploadPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        # 状态提示
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setAlignment(QtCore.Qt.AlignLeft)

        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.status_label.setFont(font)

        layout.addWidget(self.status_label)

        # “启动 Docker” 按钮（默认隐藏）
        self.start_button = QtWidgets.QPushButton("启动 Docker Desktop")
        self.start_button.setVisible(False)
        self.start_button.clicked.connect(self.start_docker)
        layout.addWidget(self.start_button)

        # 下面是你的上传界面内容
        layout.addWidget(QtWidgets.QLabel("这里是 Docker 镜像上传界面"))

        # 自动检测
        QtCore.QTimer.singleShot(200, self.check_docker_status)

    # ---------------------------
    # 检查 Docker 状态
    # ---------------------------
    def check_docker_status(self):
        try:
            process = subprocess.Popen(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=2)

            # 出错关键字（docker engine 未启动）
            error_keywords = [
                "ERROR",
                "Error response from daemon",
                "Cannot connect to the Docker daemon",
                "Bad response from Docker engine"
            ]

            if any(err in stdout or err in stderr for err in error_keywords):
                self.set_status_error("Docker 未启动")
                return

            if "Server Version" in stdout:
                self.set_status_ok("Docker 已启动")
            else:
                self.set_status_error("Docker 未启动")

        except Exception:
            self.set_status_error("Docker 未启动")

    # ---------------------------
    # UI 展示：Docker 已启动
    # ---------------------------
    def set_status_ok(self, text):
        self.status_label.setStyleSheet("color: green;")
        self.status_label.setText(text)
        self.start_button.setVisible(False)

    # ---------------------------
    # UI 展示：Docker 未启动
    # ---------------------------
    def set_status_error(self, text):
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setText(text)
        self.start_button.setVisible(True)

    # ---------------------------
    # 点击按钮启动 Docker Desktop
    # ---------------------------
    def start_docker(self):
        # Mac 启动 Docker Desktop
        os.system("open /Applications/Docker.app")
        # 延迟几秒后自动重新检测
        QtCore.QTimer.singleShot(5000, self.check_docker_status)
