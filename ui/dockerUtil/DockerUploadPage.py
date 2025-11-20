# ui/dockerUtil/DockerUploadPage.py
import subprocess
import os
from PyQt5 import QtWidgets, QtGui, QtCore


class DockerUploadPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        # ---------------------------
        # Docker 状态提示
        # ---------------------------
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setAlignment(QtCore.Qt.AlignLeft)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)

        # ---------------------------
        # 启动 Docker 按钮
        # ---------------------------
        self.start_docker_btn = QtWidgets.QPushButton("启动 Docker Desktop")
        self.start_docker_btn.setVisible(False)
        self.start_docker_btn.clicked.connect(self.start_docker)
        layout.addWidget(self.start_docker_btn)

        # ---------------------------
        # 文件夹输入框
        # ---------------------------
        dir_label = QtWidgets.QLabel("请输入文件夹目录：")
        self.dir_input = QtWidgets.QLineEdit()
        self.dir_input.setPlaceholderText("/Users/xxx/my-docker-files")
        layout.addWidget(dir_label)
        layout.addWidget(self.dir_input)

        # ---------------------------
        # buildx builder 按钮
        # ---------------------------
        self.buildx_btn = QtWidgets.QPushButton("创建 Docker Buildx Builder")
        self.buildx_btn.setVisible(False)
        self.buildx_btn.clicked.connect(self.create_buildx_builder)
        layout.addWidget(self.buildx_btn)

        # 下面是原来的上传界面内容
        layout.addWidget(QtWidgets.QLabel("这里是 Docker 镜像上传界面"))

        # ---------------------------
        # 页面加载后检测
        # ---------------------------
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
                # 检测 buildx
                self.check_buildx_builder()
            else:
                self.set_status_error("Docker 未启动")

        except Exception:
            self.set_status_error("Docker 未启动")

    # ---------------------------
    # Docker 已启动
    # ---------------------------
    def set_status_ok(self, text):
        self.status_label.setStyleSheet("color: green;")
        self.status_label.setText(text)
        self.start_docker_btn.setVisible(False)

    # ---------------------------
    # Docker 未启动
    # ---------------------------
    def set_status_error(self, text):
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setText(text)
        self.start_docker_btn.setVisible(True)
        self.buildx_btn.setVisible(False)  # Docker 都没启动就不显示 buildx 按钮

    # ---------------------------
    # 启动 Docker Desktop
    # ---------------------------
    def start_docker(self):
        os.system("open /Applications/Docker.app")
        QtCore.QTimer.singleShot(5000, self.check_docker_status)

    # ---------------------------
    # 检查 buildx builder 是否存在
    # ---------------------------
    def check_buildx_builder(self):
        try:
            process = subprocess.Popen(
                ["docker", "buildx", "inspect", "mybuilder"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=2)
            if "No such builder instance" in stderr or "error" in stderr.lower():
                # builder 不存在，显示按钮
                self.buildx_btn.setVisible(True)
            else:
                # builder 存在，隐藏按钮
                self.buildx_btn.setVisible(False)
        except Exception:
            self.buildx_btn.setVisible(True)

    # ---------------------------
    # 点击按钮创建 buildx builder
    # ---------------------------
    def create_buildx_builder(self):
        try:
            subprocess.run(["docker", "buildx", "create", "--name", "mybuilder", "--use"], check=True)
            subprocess.run(["docker", "buildx", "inspect", "--bootstrap"], check=True)
            self.buildx_btn.setVisible(False)
            QtWidgets.QMessageBox.information(self, "成功", "Docker Buildx Builder 已创建并启用")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "失败", f"创建 Buildx Builder 失败:\n{e}")
