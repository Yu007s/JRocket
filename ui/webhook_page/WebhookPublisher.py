#!/usr/bin/env python3
import os
import requests
from PyQt5 import QtWidgets, QtCore, QtGui
from git import Repo, GitCommandError
from ui.webhook_page.WebhookConfig import WebhookConfigPage
from ui.log_out.LogPage import LogPage


class WebhookWorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(str, bool, str)  # file_path, success, status_text


class WebhookWorker(QtCore.QRunnable):
    def __init__(self, file_path: str, url: str, timeout: int = 10):
        super().__init__()
        self.file_path = file_path
        self.url = url
        self.timeout = timeout
        self.signals = WebhookWorkerSignals()

    def run(self):
        try:
            # 明确不走任何代理：忽略环境变量中的代理设置
            session = requests.Session()
            session.trust_env = False
            response = session.post(self.url, json={"file": self.file_path}, timeout=self.timeout)
            if 200 <= response.status_code < 300:
                self.signals.finished.emit(self.file_path, True, f"成功 ✅ (状态码 {response.status_code})")
            else:
                # 尝试拿到服务端返回的报错信息（优先 JSON，其次文本），并做长度限制避免刷屏
                error_detail = ""
                try:
                    # 优先 JSON（常见报错结构包含 message/error）
                    data = response.json()
                    if isinstance(data, dict):
                        # 常见字段兜底拼接
                        msg = data.get("message") or data.get("error") or data.get("msg") or ""
                        if msg:
                            error_detail = str(msg)
                        else:
                            error_detail = str(data)
                    else:
                        error_detail = str(data)
                except Exception:
                    try:
                        error_detail = response.text or ""
                    except Exception:
                        error_detail = ""

                if error_detail:
                    # 截断过长文本
                    max_len = 2000
                    if len(error_detail) > max_len:
                        error_detail = error_detail[:max_len] + " …(已截断)"
                    self.signals.finished.emit(
                        self.file_path,
                        False,
                        f"失败 ❌ (状态码 {response.status_code}) 错误: {error_detail}"
                    )
                else:
                    self.signals.finished.emit(
                        self.file_path,
                        False,
                        f"失败 ❌ (状态码 {response.status_code})"
                    )
        except Exception as e:
            self.signals.finished.emit(self.file_path, False, f"异常 ❌: {str(e)}")


class WebhookPublisherPage(QtWidgets.QWidget):
    def __init__(self, config_page: WebhookConfigPage):
        super().__init__()
        self.config_page = config_page
        layout = QtWidgets.QVBoxLayout(self)

        # 行组件缓存: file_path -> {label, button, status}
        self.row_widgets = {}
        self.thread_pool = QtCore.QThreadPool.globalInstance()

        # 获取最近 X 次 git 提交
        form_layout = QtWidgets.QHBoxLayout()
        form_layout.addWidget(QtWidgets.QLabel("获取"))
        self.num_commits = QtWidgets.QLineEdit("1")
        self.num_commits.setValidator(QtGui.QIntValidator(1, 100))
        form_layout.addWidget(self.num_commits)
        form_layout.addWidget(QtWidgets.QLabel("次 git 提交"))
        self.load_btn = QtWidgets.QPushButton("加载变动文件")
        form_layout.addWidget(self.load_btn)
        layout.addLayout(form_layout)

        # 文件列表
        self.file_list = QtWidgets.QListWidget()
        layout.addWidget(self.file_list)

        # 底部按钮
        btn_layout = QtWidgets.QHBoxLayout()
        self.push_all_btn = QtWidgets.QPushButton("推送全部 webhook")
        btn_layout.addWidget(self.push_all_btn)
        layout.addLayout(btn_layout)

        # 信号
        self.load_btn.clicked.connect(self.load_changed_files)
        self.push_all_btn.clicked.connect(self.push_all_webhooks)

        # 监听配置切换
        self.config_page.config_selector.currentTextChanged.connect(self.on_config_changed)

        # 初次加载
        self.on_config_changed(self.config_page.config_selector.currentText())

    def on_config_changed(self, config_name):
        LogPage.log(f"[配置切换] 当前配置: {config_name}")
        self.file_list.clear()

    def load_changed_files(self):
        git_url = self.config_page.git_url.text()
        git_branch = self.config_page.git_branch.text()

        if not git_url or not git_branch:
            QtWidgets.QMessageBox.warning(self, "警告", "请先配置 Git 地址和分支")
            return

        num = int(self.num_commits.text())
        LogPage.log(f"[加载变动] 仓库: {git_url} 分支: {git_branch} 最近提交数: {num}")

        self.file_list.clear()
        self.row_widgets.clear()
        tmp_dir = os.path.join(os.path.expanduser("~"), "JRocket", "tmp_repo")

        try:
            if not os.path.exists(tmp_dir):
                LogPage.log(f"[Git] 本地未找到仓库，正在 clone 到: {tmp_dir}")
                repo = Repo.clone_from(git_url, tmp_dir, branch=git_branch)
            else:
                LogPage.log(f"[Git] 使用本地仓库: {tmp_dir}，正在 fetch + reset")
                repo = Repo(tmp_dir)
                origin = repo.remotes.origin
                origin.fetch()
                repo.git.checkout(git_branch)
                repo.git.reset('--hard', f'origin/{git_branch}')
        except GitCommandError as e:
            LogPage.log(f"[Git错误] {str(e)}")
            QtWidgets.QMessageBox.warning(self, "Git", f"更新失败: {str(e)}")
            return

        commits = list(repo.iter_commits(git_branch, max_count=num))
        changed_files = set()

        for commit in commits:
            LogPage.log(f"[Commit] {commit.hexsha[:8]} {commit.message.strip()}")
            changed_files.update(commit.stats.files.keys())

        LogPage.log(f"[变动文件统计] 共 {len(changed_files)} 个文件发生变化")

        # 构造 path->webhook 映射，避免多次遍历
        path_to_webhook = {
            self.config_page.table.item(row, 0).text(): self.config_page.table.item(row, 1).text()
            for row in range(self.config_page.table.rowCount())
        }

        for f in changed_files:
            if f in path_to_webhook:
                LogPage.log(f"[匹配到配置] {f} -> {path_to_webhook[f]}")
                container = QtWidgets.QWidget()
                hlayout = QtWidgets.QHBoxLayout(container)
                hlayout.setContentsMargins(0, 0, 0, 0)

                label = QtWidgets.QLabel(f)
                label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
                hlayout.addWidget(label)

                push_btn = QtWidgets.QPushButton("推送 webhook")
                hlayout.addWidget(push_btn)
                push_btn.clicked.connect(lambda _, fp=f: self.push_webhook(fp))

                status_label = QtWidgets.QLabel("")
                status_label.setMinimumWidth(140)
                status_label.setStyleSheet("color: #888;")
                hlayout.addWidget(status_label)

                list_item = QtWidgets.QListWidgetItem(self.file_list)
                list_item.setSizeHint(container.sizeHint())
                self.file_list.addItem(list_item)
                self.file_list.setItemWidget(list_item, container)

                # 记录该行组件
                self.row_widgets[f] = {
                    "label": label,
                    "button": push_btn,
                    "status": status_label,
                }
            else:
                LogPage.log(f"[未配置 webhook] 跳过文件: {f}")

    def push_webhook(self, file_path):
        path_to_webhook = {
            self.config_page.table.item(row, 0).text(): self.config_page.table.item(row, 1).text()
            for row in range(self.config_page.table.rowCount())
        }

        url = path_to_webhook.get(file_path)
        if not url:
            LogPage.log(f"[跳过] 未配置 webhook: {file_path}")
            return

        LogPage.log(f"[推送开始] {file_path} -> {url}")

        # 更新行 UI 状态
        row = self.row_widgets.get(file_path)
        if row:
            row["button"].setEnabled(False)
            row["status"].setText("推送中…")
            row["status"].setStyleSheet("color: #888;")

        worker = WebhookWorker(file_path, url)
        worker.signals.finished.connect(self.on_webhook_finished)
        self.thread_pool.start(worker)

    @QtCore.pyqtSlot(str, bool, str)
    def on_webhook_finished(self, file_path: str, success: bool, status_text: str):
        # 日志
        if success:
            LogPage.log(f"[推送成功] {file_path} {status_text}")
        else:
            LogPage.log(f"[推送失败] {file_path} {status_text}")

        # 更新对应行提示
        row = self.row_widgets.get(file_path)
        if row:
            row["button"].setEnabled(True)
            color = "#16a34a" if success else "#dc2626"
            row["status"].setStyleSheet(f"color: {color};")
            row["status"].setText(status_text)

    def push_all_webhooks(self):
        LogPage.log("[批量推送] 开始执行 (并发)")

        for index in range(self.file_list.count()):
            item_widget = self.file_list.itemWidget(self.file_list.item(index))
            if item_widget:
                label = item_widget.findChild(QtWidgets.QLabel)
                if label:
                    self.push_webhook(label.text())

        QtWidgets.QMessageBox.information(self, "Webhook", "已开始并发推送，结果将在每一行显示")
        LogPage.log("[批量推送] 任务已全部提交 ✅")
