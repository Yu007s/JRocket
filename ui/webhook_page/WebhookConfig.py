#!/usr/bin/env python3
import json
import os
from PyQt5 import QtWidgets, QtCore


class WebhookConfigPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # 初始化配置目录
        self.config_dir = os.path.join(os.path.expanduser('~'), 'JRocket')
        os.makedirs(self.config_dir, exist_ok=True)

        # UI
        layout = QtWidgets.QVBoxLayout(self)

        # 配置选择下拉框 + 新增/删除配置按钮
        config_layout = QtWidgets.QHBoxLayout()
        self.config_selector = QtWidgets.QComboBox()
        self.new_config_btn = QtWidgets.QPushButton("新增配置")
        self.delete_config_btn = QtWidgets.QPushButton("删除配置")
        config_layout.addWidget(QtWidgets.QLabel("选择配置:"))
        config_layout.addWidget(self.config_selector)
        config_layout.addWidget(self.new_config_btn)
        config_layout.addWidget(self.delete_config_btn)
        layout.addLayout(config_layout)

        # 表单输入
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

        # 保存配置按钮
        self.save_btn = QtWidgets.QPushButton('保存配置')
        layout.addWidget(self.save_btn)

        # 信号连接
        self.save_btn.clicked.connect(self.save_config)
        self.add_row_btn.clicked.connect(self.add_row)
        self.remove_row_btn.clicked.connect(self.remove_selected_rows)
        self.new_config_btn.clicked.connect(self.create_new_config)
        self.delete_config_btn.clicked.connect(self.delete_current_config)
        self.config_selector.currentTextChanged.connect(self.on_config_selected)

        # 加载配置文件
        self.load_configs()

    # ---------- 配置文件管理 ----------
    def load_configs(self):
        """扫描 ~/.JRocket 目录下的所有配置文件"""
        self.config_selector.clear()
        for fname in os.listdir(self.config_dir):
            if fname.endswith('.json'):
                self.config_selector.addItem(fname)
        if self.config_selector.count() > 0:
            self.config_selector.setCurrentIndex(0)
            self.load_config(self.config_selector.currentText())

    def on_config_selected(self, config_name):
        self.load_config(config_name)

    def load_config(self, config_name):
        path = os.path.join(self.config_dir, config_name)
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
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

    def save_config(self):
        config_name = self.config_selector.currentText()
        if not config_name:
            QtWidgets.QMessageBox.warning(self, "保存失败", "请选择或创建一个配置")
            return
        path = os.path.join(self.config_dir, config_name)

        table_data = []
        for row in range(self.table.rowCount()):
            path_item = self.table.item(row, 0)
            webhook_item = self.table.item(row, 1)
            path_text = path_item.text() if path_item else ''
            webhook_text = webhook_item.text() if webhook_item else ''
            if path_text and webhook_text:
                table_data.append({'path': path_text, 'webhook': webhook_text})

        data = {
            'git_url': self.git_url.text(),
            'git_branch': self.git_branch.text(),
            'update_cycle': self.update_cycle.text(),
            'path_webhook_map': table_data
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        QtWidgets.QMessageBox.information(self, "保存", f"配置已保存到 {path}")

    def create_new_config(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "新建配置", "请输入配置名:")
        if ok and name:
            # 确保后缀为 .json
            if not name.lower().endswith(".json"):
                name += ".json"

            path = os.path.join(self.config_dir, name)
            if os.path.exists(path):
                QtWidgets.QMessageBox.warning(self, "提示", "该配置已存在")
                return

            # 创建空配置文件
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=4)

            # 更新下拉框并切换到新配置
            self.config_selector.addItem(name)
            self.config_selector.setCurrentText(name)

    def delete_current_config(self):
        config_name = self.config_selector.currentText()
        if not config_name:
            return
        path = os.path.join(self.config_dir, config_name)
        reply = QtWidgets.QMessageBox.question(
            self, '删除配置', f"确定要删除配置 {config_name} 吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            os.remove(path)
            self.load_configs()

    # ---------- 表格行操作 ----------
    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

    def remove_selected_rows(self):
        for idx in sorted(set(i.row() for i in self.table.selectedIndexes()), reverse=True):
            self.table.removeRow(idx)
