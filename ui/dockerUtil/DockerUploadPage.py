# ui/dockerUtil/DockerUploadPage.py
import subprocess
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

        # 下面是你的 UI
        layout.addWidget(QtWidgets.QLabel("这里是 Docker 镜像上传界面"))

        # 自动检测
        QtCore.QTimer.singleShot(200, self.check_docker_status)

    def check_docker_status(self):
        """检测 docker 是否启动（包括 daemon 错误）"""
        try:
            process = subprocess.Popen(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=2)

            # 出错关键字
            error_keywords = [
                "ERROR",
                "Error response from daemon",
                "Cannot connect to the Docker daemon",
                "Bad response from Docker engine"
            ]

            # stdout 或 stderr 包含错误即判定为未启动
            if any(err in stdout or err in stderr for err in error_keywords):
                self.set_status_error("Docker 未启动")
                return

            # 判断 Server Version 是否存在
            if "Server Version" in stdout:
                self.set_status_ok("Docker 已启动")
            else:
                self.set_status_error("Docker 未启动")

        except Exception:
            self.set_status_error("Docker 未启动")

    def set_status_ok(self, text):
        self.status_label.setStyleSheet("color: green;")
        self.status_label.setText(text)

    def set_status_error(self, text):
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setText(text)
