#!/usr/bin/env python3
from PyQt5 import QtWidgets
from ui.webhook_page.WebhookConfig import WebhookConfigPage
from ui.webhook_page.WebhookPublisher import WebhookPublisherPage
from ui.log_out.LogPage import LogPage


class JRocketUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JRocketUI")
        self.resize(1000, 700)
        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 标签页
        self.config_page = WebhookConfigPage()
        self.publisher_page = WebhookPublisherPage(self.config_page)
        self.log_page = LogPage()
        self.add_tab(self.publisher_page, "Webhook发布器")
        self.add_tab(self.config_page, "Webhook配置")
        self.add_tab(self.log_page, "软件日志")
        # 不允许关闭
        self.tab_widget.setTabsClosable(False)

    def add_tab(self, widget, title):
        self.tab_widget.addTab(widget, title)


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = JRocketUI()
    win.show()
    sys.exit(app.exec_())
