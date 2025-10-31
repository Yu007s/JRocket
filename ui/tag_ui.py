#!/usr/bin/env python3
from PyQt5 import QtWidgets
from ui.webhook_page.webhook_config import WebhookConfigPage
from ui.webhook_page.webhook_publisher import WebhookPublisherPage


class JocketUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JocketUI")
        self.resize(1000, 700)
        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 标签页
        self.config_page = WebhookConfigPage()
        self.publisher_page = WebhookPublisherPage(self.config_page)
        self.add_tab(self.publisher_page, "Webhook发布器")
        self.add_tab(self.config_page, "Webhook配置")
        # 不允许关闭
        self.tab_widget.setTabsClosable(False)

    def add_tab(self, widget, title):
        self.tab_widget.addTab(widget, title)


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = JocketUI()
    win.show()
    sys.exit(app.exec_())
