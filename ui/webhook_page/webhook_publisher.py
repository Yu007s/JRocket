#!/usr/bin/env python3
import os

import requests
from PyQt5 import QtWidgets, QtCore
from git import Repo, GitCommandError
from ui.webhook_page.webhook_config import WebhookConfigPage
from PyQt5 import QtWidgets, QtGui


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

    def load_changed_files(self):
        git_url = self.config_page.git_url.text()
        git_branch = self.config_page.git_branch.text()
        if not git_url or not git_branch:
            QtWidgets.QMessageBox.warning(self, "警告", "请先配置 Git 地址和分支")
            return

        num = int(self.num_commits.text())
        self.file_list.clear()
        tmp_dir = os.path.join(os.path.expanduser("~"), "JRocket", "tmp_repo")

        tmp_dir = os.path.join(os.path.expanduser("~"), "JRocket", "tmp_repo")
        if not os.path.exists(tmp_dir):
            repo = Repo.clone_from(git_url, tmp_dir, branch=git_branch)
        else:
            repo = Repo(tmp_dir)
            try:
                origin = repo.remotes.origin
                origin.fetch()
                repo.git.checkout(git_branch)
                repo.git.reset('--hard', f'origin/{git_branch}')  # 保证和远程一致
            except GitCommandError as e:
                QtWidgets.QMessageBox.warning(self, "Git", f"更新失败: {str(e)}")
        repo = Repo(tmp_dir)
        commits = list(repo.iter_commits(git_branch, max_count=num))
        changed_files = set()
        for commit in commits:
            changed_files.update(commit.stats.files.keys())

        # 显示文件
        for f in changed_files:
            # 检查 f 是否在配置表中有 webhook
            matched = False
            for row in range(self.config_page.table.rowCount()):
                path_item = self.config_page.table.item(row, 0)
                webhook_item = self.config_page.table.item(row, 1)
                if path_item and webhook_item and path_item.text() == f:
                    matched = True
                    break
            f_display = self.utf8_to_str(f)
            container = QtWidgets.QWidget()
            h_lay_out = QtWidgets.QHBoxLayout(container)
            h_lay_out.setContentsMargins(0, 0, 0, 0)
            label = QtWidgets.QLabel(f_display)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            h_lay_out.addWidget(label)

            # 只有 matched=True 才加按钮
            if matched:
                push_btn = QtWidgets.QPushButton("推送 webhook")
                h_lay_out.addWidget(push_btn)
                push_btn.clicked.connect(lambda _, fp=f: self.push_webhook(fp))

            list_item = QtWidgets.QListWidgetItem(self.file_list)
            list_item.setSizeHint(container.sizeHint())
            self.file_list.addItem(list_item)
            self.file_list.setItemWidget(list_item, container)

    def utf8_to_str(self, s):
        # 将 \xxx 转成中文
        return bytes(s, 'latin1').decode('unicode_escape').encode('latin1').decode('utf-8')

    def push_webhook(self, file_path):
        for row in range(self.config_page.table.rowCount()):
            path_item = self.config_page.table.item(row, 0)
            webhook_item = self.config_page.table.item(row, 1)
            if path_item and webhook_item and path_item.text() == file_path:
                url = webhook_item.text()
                try:
                    response = requests.post(url, json={"file": file_path})
                    if 200 <= response.status_code < 300:
                        QtWidgets.QMessageBox.information(
                            self,
                            "Webhook",
                            f"已推送成功: {file_path} (状态码 {response.status_code})"
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Webhook",
                            f"推送失败 ({response.status_code}): {file_path}"
                        )
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Webhook",
                        f"推送异常: {file_path}\n{str(e)}"
                    )
                break

    def push_all_webhooks(self):
        for row in range(self.config_page.table.rowCount()):
            path_item = self.config_page.table.item(row, 0)
            webhook_item = self.config_page.table.item(row, 1)
            if path_item and webhook_item:
                print(f"推送 {path_item.text()} -> {webhook_item.text()}")
        QtWidgets.QMessageBox.information(self, "Webhook", "已推送全部 webhook")
