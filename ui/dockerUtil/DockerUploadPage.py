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

        # 启动 Docker 按钮
        self.start_docker_btn = QtWidgets.QPushButton("启动 Docker Desktop")
        self.start_docker_btn.setVisible(False)
        self.start_docker_btn.clicked.connect(self.start_docker)
        layout.addWidget(self.start_docker_btn)

        # ---------------------------
        # Buildx 状态提示
        # ---------------------------
        self.buildx_status_label = QtWidgets.QLabel("")
        self.buildx_status_label.setAlignment(QtCore.Qt.AlignLeft)
        layout.addWidget(self.buildx_status_label)

        # 修复 Buildx 按钮
        self.fix_buildx_btn = QtWidgets.QPushButton("修复 Buildx Builder")
        self.fix_buildx_btn.setVisible(False)
        self.fix_buildx_btn.clicked.connect(self.create_buildx_builder)
        layout.addWidget(self.fix_buildx_btn)

        # ---------------------------
        # 文件夹输入
        # ---------------------------
        dir_label = QtWidgets.QLabel("请输入文件夹目录：")
        self.dir_input = QtWidgets.QLineEdit()
        self.dir_input.setPlaceholderText("/Users/xxx/my-docker-files")
        layout.addWidget(dir_label)
        layout.addWidget(self.dir_input)

        layout.addWidget(QtWidgets.QLabel("这里是 Docker 镜像上传界面"))

    # ===============================
    # 页面展示自动检查
    # ===============================
    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(300, self.check_docker_status)

    # ===============================
    # 检查 Docker 状态
    # ===============================
    def check_docker_status(self):
        try:
            process = subprocess.Popen(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=3)

            error_keywords = [
                "ERROR",
                "Error response from daemon",
                "Cannot connect to the Docker daemon",
                "Bad response from Docker engine"
            ]

            if any(err in stdout or err in stderr for err in error_keywords):
                self.set_status_error("Docker 未启动")
                self.set_buildx_hidden()
                return

            if "Server Version" in stdout:
                self.set_status_ok("Docker 已启动")
                self.check_buildx_builder()
            else:
                self.set_status_error("Docker 未启动")
                self.set_buildx_hidden()

        except Exception:
            self.set_status_error("Docker 未启动")
            self.set_buildx_hidden()

    # ===============================
    def set_buildx_hidden(self):
        self.buildx_status_label.setVisible(False)
        self.fix_buildx_btn.setVisible(False)

    # ===============================
    # Docker 已启动
    # ===============================
    def set_status_ok(self, text):
        self.status_label.setStyleSheet("color: green;")
        self.status_label.setText(text)
        self.start_docker_btn.setVisible(False)

    # Docker 未启动
    def set_status_error(self, text):
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setText(text)
        self.start_docker_btn.setVisible(True)

    # 启动 Docker Desktop
    def start_docker(self):
        os.system("open /Applications/Docker.app")
        QtCore.QTimer.singleShot(5000, self.check_docker_status)

    # ===============================
    # 检查 buildx builder
    # ===============================
    def check_buildx_builder(self):
        healthy = self.check_buildx_builder_health()

        self.buildx_status_label.setVisible(True)

        if healthy:
            # Buildx 正常 → 显示绿色
            self.buildx_status_label.setStyleSheet("color: green;")
            self.buildx_status_label.setText("Buildx 已创建")
            self.fix_buildx_btn.setVisible(False)
        else:
            # 异常 → 红色
            self.buildx_status_label.setStyleSheet("color: red;")
            self.buildx_status_label.setText("Buildx 异常，请修复")
            self.fix_buildx_btn.setVisible(True)

    # 判断 buildx 是否健康
    def check_buildx_builder_health(self):
        try:
            process = subprocess.Popen(
                ["docker", "buildx", "inspect", "mybuilder"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=3)

            if "No such builder instance" in stderr:
                return False
            if "Status:" not in stdout or "running" not in stdout:
                return False
            if "Platforms:" not in stdout:
                return False
            if "Buildkit:" not in stdout:
                return False

            return True

        except Exception:
            return False

    # ===============================
    # 修复 buildx builder
    # ===============================
    def create_buildx_builder(self):
        try:
            subprocess.run(["docker", "buildx", "rm", "mybuilder"], check=False)
            subprocess.run([
                "docker", "buildx", "create",
                "--name", "mybuilder",
                "--driver", "docker-container",
                "--use"
            ], check=True)
            subprocess.run(["docker", "buildx", "inspect", "--bootstrap"], check=True)

            self.fix_buildx_btn.setVisible(False)
            self.buildx_status_label.setStyleSheet("color: green;")
            self.buildx_status_label.setText("Buildx 已创建")

            QtWidgets.QMessageBox.information(self, "成功", "Buildx Builder 修复成功")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "失败", f"修复 Buildx Builder 失败:\n{e}")
