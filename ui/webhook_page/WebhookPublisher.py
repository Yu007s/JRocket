#!/usr/bin/env python3
import os
import requests
from PyQt5 import QtWidgets, QtCore, QtGui
from git import Repo, GitCommandError
from ui.webhook_page.WebhookConfig import WebhookConfigPage
from ui.log_out.LogPage import LogPage


class WebhookPublisherPage(QtWidgets.QWidget):
    def __init__(self, config_page: WebhookConfigPage):
        super().__init__()
        self.config_page = config_page
        layout = QtWidgets.QVBoxLayout(self)

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

        self.on_config_changed(self.config_page.config_selector.currentText())

    def on_config_changed(self, config_name):
        LogPage.log(f"[配置切换] 已切换到: {config_name}")
        self.file_list.clear()

    def load_changed_files(self):
        git_url = self.config_page.git_url.text()
        git_branch = self.config_page.git_branch.text()

        if not git_url or not git_branch:
            QtWidgets.QMessageBox.warning(self, "警告", "请先配置 Git 地址和分支")
            return

        num = int(self.num_commits.text())
        LogPage.log(f"[加载变动] 仓库: {git_url}, 分支: {git_branch}, 最近提交数: {num}")

        self.file_list.clear()
        tmp_dir = os.path.join(os.path.expanduser("~"), "JRocket", "tmp_repo")

        try:
            if not os.path.exists(tmp_dir):
                LogPage.log("[Git] 本地不存在仓库，正在 clone...")
                repo = Repo.clone_from(git_url, tmp_dir, branch=git_branch)
            else:
                repo = Repo(tmp_dir)
                LogPage.log("[Git] 获取最新远程仓库内容...")
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

        LogPage.log(f"[变动文件] 共检测到 {len(changed_files)} 个文件")

        for f in changed_files:
            for row in range(self.config_page.table.rowCount()):
                path_item = self.config_page.table.item(row, 0)
                webhook_item = self.config_page.table.item(row, 1)
                if path_item and webhook_item and path_item.text() == f:
                    container = QtWidgets.QWidget()
                    hlayout = QtWidgets.QHBoxLayout(container)
                    hlayout.setContentsMargins(0, 0, 0, 0)
                    label = QtWidgets.QLabel(f)
                    label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
                    hlayout.addWidget(label)

                    push_btn = QtWidgets.QPushButton("推送 webhook")
                    hlayout.addWidget(push_btn)
                    push_btn.clicked.connect(lambda _, fp=f: self.push_webhook(fp))

                    list_item = QtWidgets.QListWidgetItem(self.file_list)
                    list_item.setSizeHint(container.sizeHint())
                    self.file_list.addItem(list_item)
                    self.file_list.setItemWidget(list_item, container)

    def push_webhook(self, file_path):
        path_to_webhook = {
            self.config_page.table.item(row, 0).text(): self.config_page.table.item(row, 1).text()
            for row in range(self.config_page.table.rowCount())
        }

        url = path_to_webhook.get(file_path)
        if not url:
            LogPage.log(f"[跳过] 未配置 webhook: {file_path}")
            return

        LogPage.log(f"[推送] {file_path} -> {url}")

        try:
            response = requests.post(url, json={"file": file_path})
            if 200 <= response.status_code < 300:
                LogPage.log(f"[成功] {file_path} (状态码 {response.status_code})")
            else:
                LogPage.log(f"[失败] {file_path} (状态码 {response.status_code})")
        except Exception as e:
            LogPage.log(f"[异常] 推送时错误: {file_path}\n{str(e)}")

    def push_all_webhooks(self):
        LogPage.log("[批量推送] 开始推送所有列表文件")
        for index in range(self.file_list.count()):
            item_widget = self.file_list.itemWidget(self.file_list.item(index))
            if item_widget:
                label = item_widget.findChild(QtWidgets.QLabel)
                if label:
                    self.push_webhook(label.text())
        QtWidgets.QMessageBox.information(self, "Webhook", "已推送全部文件")
        LogPage.log("[批量推送] 完成")
