#!/usr/bin/env python3
from PyQt5 import QtWidgets
from ui.skin.SkinPage import SkinPage
from ui.webhook_page.WebhookConfig import WebhookConfigPage
from ui.webhook_page.WebhookPublisher import WebhookPublisherPage
from ui.log_out.LogPage import LogPage
from ui.docker.DockerUploadPage import DockerUploadPage
from ui.docker.DockerInfo import DockerInfo

class JRocketUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JRocketUI")
        self.resize(1000, 700)
        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 标签页
        self.WebhookConfigPage = WebhookConfigPage()
        self.WebhookPublisherPage = WebhookPublisherPage(self.WebhookConfigPage)
        self.LogPage = LogPage()
        self.SkinPage = SkinPage()
        self.DockerUploadPage = DockerUploadPage()
        self.DockerInfo = DockerInfo()

        self.add_tab(self.WebhookConfigPage, "Webhook发布器")
        self.add_tab(self.WebhookPublisherPage, "Webhook配置")
        self.add_tab(self.DockerInfo, "docker 信息查询")
        self.add_tab(self.DockerUploadPage, "docker镜像上传")
        self.add_tab(self.LogPage, "软件日志")
        self.add_tab(self.SkinPage, "换皮")

        self.tab_widget.setTabsClosable(False)

    def add_tab(self, widget, title):
        self.tab_widget.addTab(widget, title)


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = JRocketUI()
    win.show()
    sys.exit(app.exec_())
