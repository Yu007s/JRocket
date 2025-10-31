#!/usr/bin/env python3
import os
from PyQt5 import QtWidgets
from git import Repo
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
        self.num_commits = QtWidgets.QLineEdit("5")
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
        self.update_git_btn = QtWidgets.QPushButton("更新当前 git 提交")
        self.push_all_btn = QtWidgets.QPushButton("推送全部 webhook")
        btn_layout.addWidget(self.update_git_btn)
        btn_layout.addWidget(self.push_all_btn)
        layout.addLayout(btn_layout)

        # 信号
        self.load_btn.clicked.connect(self.load_changed_files)
        self.push_all_btn.clicked.connect(self.push_all_webhooks)

    def load_changed_files(self):
        git_url = self.config_page.git_url.text()
        git_branch = self.config_page.git_branch.text()
        if not git_url or not git_branch:
            QtWidgets.QMessageBox.warning(self,"警告","请先配置 Git 地址和分支")
            return

        num = int(self.num_commits.text())
        self.file_list.clear()
        tmp_dir = os.path.join(os.path.expanduser("~"), "JRocket","tmp_repo")

        if not os.path.exists(tmp_dir):
            Repo.clone_from(git_url, tmp_dir, branch=git_branch)
        repo = Repo(tmp_dir)
        commits = list(repo.iter_commits(git_branch, max_count=num))
        changed_files = set()
        for commit in commits:
            changed_files.update(commit.stats.files.keys())

        # 显示文件
        for f in changed_files:
            item = QtWidgets.QListWidgetItem(f)
            push_btn = QtWidgets.QPushButton("推送 webhook")
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, push_btn)
            push_btn.clicked.connect(lambda _, fp=f: self.push_webhook(fp))

    def push_webhook(self, file_path):
        for row in range(self.config_page.table.rowCount()):
            path_item = self.config_page.table.item(row,0)
            webhook_item = self.config_page.table.item(row,1)
            if path_item and webhook_item and path_item.text() == file_path:
                QtWidgets.QMessageBox.information(self,"Webhook","已推送: "+file_path)
                break

    def push_all_webhooks(self):
        for row in range(self.config_page.table.rowCount()):
            path_item = self.config_page.table.item(row,0)
            webhook_item = self.config_page.table.item(row,1)
            if path_item and webhook_item:
                print(f"推送 {path_item.text()} -> {webhook_item.text()}")
        QtWidgets.QMessageBox.information(self,"Webhook","已推送全部 webhook")
