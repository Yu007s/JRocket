# ui/docker/DockerUploadPage.py
from PyQt5 import QtWidgets

class DockerInfo(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel("这里是 DockerInfo")
        layout.addWidget(label)
