#!/usr/bin/env python3
import os
import json
from PyQt5 import QtWidgets

class WebhookConfigPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        # 表单输入：git 地址、分支、更新周期
        form = QtWidgets.QFormLayout()
        self.git_url = QtWidgets.QLineEdit()
        self.git_branch = QtWidgets.QLineEdit()
        self.update_cycle = QtWidgets.QLineEdit()
        form.addRow('Git地址:', self.git_url)
        form.addRow('Git分支:', self.git_branch)
        form.addRow('自动更新周期(秒):', self.update_cycle)
        layout.addLayout(form)

        # 文件路径与 webhook 对应关系表
        self.table_label = QtWidgets.QLabel('文件路径与 webhook 对应关系表:')
        layout.addWidget(self.table_label)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['文件路径', 'Webhook URL'])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # 添加/删除行按钮
        btn_layout = QtWidgets.QHBoxLayout()
        self.add_row_btn = QtWidgets.QPushButton('新增行')
        self.remove_row_btn = QtWidgets.QPushButton('删除选中行')
        btn_layout.addWidget(self.add_row_btn)
        btn_layout.addWidget(self.remove_row_btn)
        layout.addLayout(btn_layout)

        self.save_btn = QtWidgets.QPushButton('保存配置')
        layout.addWidget(self.save_btn)

        # 保存路径
        self.config_dir = os.path.join(os.path.expanduser('~'), 'JRocket')
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, 'config.json')

        # 信号
        self.save_btn.clicked.connect(self.save_config)
        self.add_row_btn.clicked.connect(self.add_row)
        self.remove_row_btn.clicked.connect(self.remove_selected_rows)

        self.load_config()

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

    def remove_selected_rows(self):
        for idx in sorted(set(i.row() for i in self.table.selectedIndexes()), reverse=True):
            self.table.removeRow(idx)

    def save_config(self):
        table_data = []
        for row in range(self.table.rowCount()):
            path_item = self.table.item(row, 0)
            webhook_item = self.table.item(row, 1)
            path = path_item.text() if path_item else ''
            webhook = webhook_item.text() if webhook_item else ''
            if path and webhook:
                table_data.append({'path': path, 'webhook': webhook})

        data = {
            'git_url': self.git_url.text(),
            'git_branch': self.git_branch.text(),
            'update_cycle': self.update_cycle.text(),
            'path_webhook_map': table_data
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        QtWidgets.QMessageBox.information(self, '保存', f'配置已保存到 {self.config_file}')

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.git_url.setText(data.get('git_url', ''))
            self.git_branch.setText(data.get('git_branch', ''))
            self.update_cycle.setText(data.get('update_cycle', ''))
            self.table.setRowCount(0)
            for item in data.get('path_webhook_map', []):
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('path', '')))
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('webhook', '')))
