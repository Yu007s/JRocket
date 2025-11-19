# ui/docker/DockerUploadPage.py
from PyQt5 import QtWidgets

class DockerUploadPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel("这里是 Docker 镜像上传界面")
        layout.addWidget(label)
