from PyQt5 import QtWidgets


class LogPage(QtWidgets.QWidget):
    log_widget = None  # 保存唯一实例

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

        # 保存实例用于静态方法调用
        LogPage.log_widget = self

    @staticmethod
    def log(msg: str):
        """全局静态日志方法"""
        if LogPage.log_widget:
            LogPage.log_widget.text_edit.append(msg)
        else:
            print("[LogPage未初始化] ", msg)
