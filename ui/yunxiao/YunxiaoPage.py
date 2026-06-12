#!/usr/bin/env python3
import json
import os
import re
import subprocess
from datetime import datetime
from urllib.parse import urlparse

import requests
from PyQt5 import QtCore, QtGui, QtWidgets

from ui.log_out.LogPage import LogPage


CONFIG_PATH = os.path.join(os.path.expanduser("~"), "JRocket", "yunxiao_config.json")
TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yunxiaotoken.txt")
DEFAULT_ORG_URL = "https://sovell-cn-shanghai.devops.aliyuncs.com"
DEFAULT_ROOTS = [
    "/Users/devjys/Desktop/WorkSpaces/sovell/sovell15~20",
    "/Users/devjys/Desktop/WorkSpaces/sovell/sovell11~14",
    "/Users/devjys/Desktop/WorkSpaces/sovell/sovell21~",
]


def run_git(repo_path, args, timeout=8):
    process = subprocess.Popen(
        ["git", "-C", repo_path] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = process.communicate(timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError(stderr.strip() or stdout.strip())
    return stdout.strip()


def load_yunxiao_token():
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as file:
            token = file.read().strip()
            if token:
                return token
    except FileNotFoundError:
        pass
    except Exception as exc:
        LogPage.log(f"[云效] 读取 token 文件失败: {exc}")
    return os.environ.get("YUNXIAO_TOKEN", "")


def normalize_remote_url(remote_url):
    remote_url = (remote_url or "").strip()
    if remote_url.startswith("git@"):
        match = re.match(r"git@([^:]+):(.+)", remote_url)
        if match:
            return f"https://{match.group(1)}/{match.group(2)}"
    if remote_url.startswith("ssh://git@"):
        parsed = urlparse(remote_url)
        path = parsed.path.lstrip("/")
        return f"https://{parsed.hostname}/{path}"
    return remote_url


def normalize_for_match(value):
    value = normalize_remote_url(value or "").lower().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value


def repo_path_from_remote(remote_url):
    normalized = normalize_remote_url(remote_url)
    parsed = urlparse(normalized)
    path = parsed.path.lstrip("/") if parsed.path else normalized
    path = path.lower().rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def repo_name_from_text(value):
    normalized = normalize_for_match(value)
    if not normalized:
        return ""
    return normalized.split("/")[-1]


def mapping_matches_repo(mapping, remote_url, repo_name, allow_repo_name=False):
    key = mapping.get("key", "").strip()
    if not key:
        return False
    repo_url_key = normalize_for_match(remote_url)
    repo_path_key = repo_path_from_remote(remote_url)
    repo_short_key = normalize_for_match(repo_name)
    candidate = normalize_for_match(key)
    candidate_path = repo_path_from_remote(candidate)
    if repo_url_key and candidate == repo_url_key:
        return True
    if repo_path_key and (candidate == repo_path_key or candidate_path == repo_path_key):
        return True
    if allow_repo_name and repo_short_key and (candidate == repo_short_key or repo_name_from_text(candidate) == repo_short_key):
        return True
    return False


def match_pipeline(remote_url, repo_name, manual_mappings, automatic_mappings):
    for mapping in manual_mappings:
        pipeline_id = mapping.get("pipeline_id", "").strip()
        if pipeline_id and mapping_matches_repo(mapping, remote_url, repo_name, allow_repo_name=True):
            return pipeline_id, "手动映射"
    for mapping in automatic_mappings:
        pipeline_id = mapping.get("pipeline_id", "").strip()
        if pipeline_id and mapping_matches_repo(mapping, remote_url, repo_name):
            name = mapping.get("pipeline_name", "").strip()
            return pipeline_id, f"OpenAPI: {name}" if name else "OpenAPI"
    exact_name_mappings = []
    repo_short_key = normalize_for_match(repo_name)
    for mapping in automatic_mappings:
        pipeline_id = mapping.get("pipeline_id", "").strip()
        mapping_repo_name = normalize_for_match(mapping.get("repo_name", ""))
        mapping_key_name = repo_name_from_text(mapping.get("key", ""))
        if pipeline_id and repo_short_key and repo_short_key in (mapping_repo_name, mapping_key_name):
            exact_name_mappings.append(mapping)
    if len(exact_name_mappings) == 1:
        mapping = exact_name_mappings[0]
        name = mapping.get("pipeline_name", "").strip()
        return mapping.get("pipeline_id", "").strip(), f"OpenAPI: {name}" if name else "OpenAPI"
    return "", ""


def normalize_branch_name(branch):
    branch = (branch or "").strip()
    for prefix in ("remotes/origin/", "origin/"):
        if branch.startswith(prefix):
            return branch[len(prefix):]
    return branch


def branch_for_commit(repo_path, short_hash):
    try:
        output = run_git(repo_path, ["branch", "--all", "--contains", short_hash, "--format=%(refname:short)"])
        branches = [normalize_branch_name(line.strip()) for line in output.splitlines() if line.strip()]
        for branch in branches:
            if not branch.startswith("remotes/") and branch != "HEAD":
                return branch
        for branch in branches:
            if branch.startswith("origin/"):
                return normalize_branch_name(branch)
        if branches:
            return normalize_branch_name(branches[0])
    except Exception:
        pass
    return normalize_branch_name(run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]))


def collect_strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result = []
        for child in value.values():
            result.extend(collect_strings(child))
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            result.extend(collect_strings(child))
        return result
    return []


def pipeline_id_from_item(item):
    if not isinstance(item, dict):
        return ""
    for key in ("pipelineId", "pipeline_id", "pipelineID", "id"):
        value = item.get(key)
        if value:
            return str(value)
    return ""


def pipeline_display_name(item):
    if not isinstance(item, dict):
        return ""
    for key in ("name", "pipelineName", "displayName"):
        if item.get(key):
            return str(item.get(key))
    return ""


def collect_pipeline_items(payload):
    items = []
    if isinstance(payload, dict):
        if pipeline_id_from_item(payload):
            items.append(payload)
        for key in ("data", "result", "items", "list", "pipelines", "records", "content"):
            if key in payload:
                items.extend(collect_pipeline_items(payload[key]))
        return items
    if isinstance(payload, list):
        for value in payload:
            items.extend(collect_pipeline_items(value))
    return items


def extract_repo_refs(item):
    refs = []
    for text in collect_strings(item):
        text = text.strip()
        if not text:
            continue
        found = re.findall(r"(?:https?://|ssh://git@|git@)[^\s'\"<>]+?\.git", text)
        if found:
            refs.extend(found)
        elif "/codeup/" in text and "/" in text:
            refs.append(text)
    cleaned = []
    for ref in refs:
        ref = normalize_remote_url(ref.rstrip(".,;)'\"]"))
        if ref not in cleaned:
            cleaned.append(ref)
    return cleaned


def mapping_from_pipeline_item(item):
    pipeline_id = pipeline_id_from_item(item)
    if not pipeline_id:
        return []
    pipeline_name = pipeline_display_name(item)
    mappings = []
    for repo_ref in extract_repo_refs(item):
        mappings.append(
            {
                "key": repo_ref,
                "repo_name": repo_name_from_text(repo_ref),
                "pipeline_id": pipeline_id,
                "pipeline_name": pipeline_name,
            }
        )
    return mappings


def mapping_matches_remote_exact(mapping, remote_url):
    return mapping_matches_repo(mapping, remote_url, repo_name_from_text(remote_url))


def pipeline_item_contains_remote(item, remote_url):
    for mapping in mapping_from_pipeline_item(item):
        if mapping_matches_remote_exact(mapping, remote_url):
            return True
    return False


def collect_local_repositories(roots):
    repositories = []
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        for current, dirs, _files in os.walk(root):
            if ".git" not in dirs:
                if current.count(os.sep) - root.count(os.sep) >= 2:
                    dirs[:] = []
                continue
            repo = current
            dirs[:] = []
            try:
                remote_url = normalize_remote_url(run_git(repo, ["remote", "get-url", "origin"]))
                repo_name = os.path.basename(repo)
                key = normalize_for_match(remote_url)
                if key in seen:
                    continue
                seen.add(key)
                repositories.append({"repo_name": repo_name, "remote_url": remote_url})
            except Exception as exc:
                LogPage.log(f"[云效] 读取本地仓库失败 {repo}: {exc}")
    return repositories


def first_pipeline_mapping_for_repo(session, org_url, headers, repo, timeout):
    repo_name = repo.get("repo_name", "")
    remote_url = repo.get("remote_url", "")
    candidates = [
        {"repositoryUrl": remote_url},
        {"repoUrl": remote_url},
        {"sources": remote_url},
    ]
    for params in candidates:
        try:
            response = session.get(f"{org_url}/oapi/v1/flow/pipelines", headers=headers, params=params, timeout=timeout)
            if not (200 <= response.status_code < 300):
                continue
            items = collect_pipeline_items(response.json())
            matched_items = [item for item in items if pipeline_item_contains_remote(item, remote_url)]
            if not matched_items:
                matched_items = []
                for item in items:
                    pipeline_id = pipeline_id_from_item(item)
                    if not pipeline_id:
                        continue
                    for detail_url in (
                        f"{org_url}/oapi/v1/flow/pipelines/{pipeline_id}",
                        f"{org_url}/oapi/v1/flow/pipelines/{pipeline_id}/sources",
                    ):
                        detail_response = session.get(detail_url, headers=headers, timeout=timeout)
                        if 200 <= detail_response.status_code < 300 and pipeline_item_contains_remote(detail_response.json(), remote_url):
                            matched_items.append(item)
                            break
            for item in matched_items:
                pipeline_id = pipeline_id_from_item(item)
                if pipeline_id:
                    return {
                        "key": remote_url,
                        "repo_name": repo_name,
                        "pipeline_id": pipeline_id,
                        "pipeline_name": pipeline_display_name(item),
                    }
        except Exception:
            continue
    return None


def fetch_pipeline_mappings_from_openapi(org_url, token, roots=None, timeout=15):
    if not token:
        raise RuntimeError(f"请输入 YUNXIAO_TOKEN，或在 {TOKEN_PATH} 写入 token")

    session = requests.Session()
    session.trust_env = False
    headers = {"x-yunxiao-token": token}
    org_url = org_url.rstrip("/")
    url = f"{org_url}/oapi/v1/flow/pipelines"
    errors = []
    mappings = []
    seen = set()
    pipeline_items = []
    pipeline_ids = []

    def append_payload_mappings(payload):
        for item in collect_pipeline_items(payload):
            pipeline_items.append(item)
            pipeline_id = pipeline_id_from_item(item)
            if pipeline_id and pipeline_id not in pipeline_ids:
                pipeline_ids.append(pipeline_id)
            for mapping in mapping_from_pipeline_item(item):
                key = (normalize_for_match(mapping["key"]), mapping["pipeline_id"])
                if key in seen:
                    continue
                seen.add(key)
                mappings.append(mapping)

    try:
        response = session.get(url, headers=headers, timeout=timeout)
        if 200 <= response.status_code < 300:
            append_payload_mappings(response.json())
        else:
            errors.append(f"HTTP {response.status_code} params={{}}")
    except Exception as exc:
        errors.append(f"{{}}: {exc}")

    page_shapes = [
        ("page", "pageSize"),
        ("pageNo", "pageSize"),
        ("current", "pageSize"),
    ]
    for page_key, size_key in page_shapes:
        unchanged_pages = 0
        for page in range(1, 21):
            before = len(pipeline_ids)
            params = {page_key: page, size_key: 100}
            try:
                response = session.get(url, headers=headers, params=params, timeout=timeout)
                if not (200 <= response.status_code < 300):
                    errors.append(f"HTTP {response.status_code} params={params}")
                    break
                payload = response.json()
                append_payload_mappings(payload)
                if len(pipeline_ids) == before:
                    unchanged_pages += 1
                else:
                    unchanged_pages = 0
                if unchanged_pages >= 2:
                    break
            except Exception as exc:
                errors.append(f"{params}: {exc}")
                break

    for pipeline_id in pipeline_ids[:300]:
        before = len(seen)
        detail_urls = [
            f"{org_url}/oapi/v1/flow/pipelines/{pipeline_id}",
            f"{org_url}/oapi/v1/flow/pipelines/{pipeline_id}/sources",
        ]
        for detail_url in detail_urls:
            try:
                response = session.get(detail_url, headers=headers, timeout=timeout)
                if not (200 <= response.status_code < 300):
                    continue
                append_payload_mappings(response.json())
                if len(seen) > before:
                    break
            except Exception:
                continue

    for repo in collect_local_repositories(roots or []):
        mapping = first_pipeline_mapping_for_repo(session, org_url, headers, repo, timeout)
        if not mapping:
            continue
        key = (normalize_for_match(mapping["key"]), mapping["pipeline_id"])
        if key in seen:
            continue
        seen.add(key)
        mappings.append(mapping)

    if not mappings and errors:
        raise RuntimeError("; ".join(errors[-3:]))
    if not mappings and pipeline_items:
        raise RuntimeError(
            f"OpenAPI 返回了 {len(pipeline_items)} 条流水线，但返回内容里没有解析到仓库地址。"
            "需要确认流水线详情接口里的仓库字段名。"
        )
    return mappings


def extract_image_addresses(payload):
    text = "\n".join(collect_strings(payload))
    patterns = [
        r"[\w.-]+(?:-registry)?\.[\w.-]+\.aliyuncs\.com/[A-Za-z0-9._/@:-]+",
        r"registry(?:\.[\w.-]+)+/[A-Za-z0-9._/@:-]+",
        r"docker\.io/[A-Za-z0-9._/@:-]+",
        r"harbor(?:\.[\w.-]+)+/[A-Za-z0-9._/@:-]+",
    ]
    images = []
    for pattern in patterns:
        images.extend(re.findall(pattern, text))
    cleaned = []
    for image in images:
        image = image.rstrip(".,;)'\"]")
        if image not in cleaned:
            cleaned.append(image)
    return cleaned


class YunxiaoSignals(QtCore.QObject):
    scan_finished = QtCore.pyqtSignal(list, str)
    run_finished = QtCore.pyqtSignal(int, int, bool, str, list, str)
    mappings_finished = QtCore.pyqtSignal(list, str)


class CopyableTableWidget(QtWidgets.QTableWidget):
    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.Copy):
            self.copy_selection()
            return
        super().keyPressEvent(event)

    def copy_selection(self):
        ranges = self.selectedRanges()
        if not ranges:
            current = self.currentItem()
            if current:
                QtWidgets.QApplication.clipboard().setText(current.text())
            return

        lines = []
        for selected_range in ranges:
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                values = []
                for col in range(selected_range.leftColumn(), selected_range.rightColumn() + 1):
                    item = self.item(row, col)
                    values.append(item.text() if item else "")
                lines.append("\t".join(values))
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))


def table_item_text(item):
    if not item:
        return ""
    return item.text().strip()


def build_url_item(url):
    item = QtWidgets.QTableWidgetItem(url)
    if url:
        item.setForeground(QtGui.QBrush(QtGui.QColor("#0969da")))
        font = item.font()
        font.setUnderline(True)
        item.setFont(font)
        item.setToolTip("双击打开构建地址")
    return item


def open_url_from_table_item(item):
    if not item:
        return
    url = table_item_text(item)
    if url.startswith(("http://", "https://")):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


class FetchPipelineMappingsWorker(QtCore.QRunnable):
    def __init__(self, org_url, token, roots):
        super().__init__()
        self.org_url = org_url
        self.token = token
        self.roots = roots
        self.signals = YunxiaoSignals()

    def run(self):
        try:
            mappings = fetch_pipeline_mappings_from_openapi(self.org_url, self.token, self.roots)
            self.signals.mappings_finished.emit(mappings, "")
        except Exception as exc:
            self.signals.mappings_finished.emit([], str(exc))


class ScanCommitsWorker(QtCore.QRunnable):
    def __init__(self, roots, author, since, manual_mappings, automatic_mappings):
        super().__init__()
        self.roots = roots
        self.author = author
        self.since = since
        self.manual_mappings = manual_mappings
        self.automatic_mappings = automatic_mappings
        self.signals = YunxiaoSignals()

    def run(self):
        rows = []
        errors = []
        for root in self.roots:
            if not os.path.isdir(root):
                errors.append(f"目录不存在: {root}")
                continue
            for current, dirs, _files in os.walk(root):
                if ".git" not in dirs:
                    if current.count(os.sep) - root.count(os.sep) >= 2:
                        dirs[:] = []
                    continue
                repo = current
                dirs[:] = []
                try:
                    repo_name = os.path.basename(repo)
                    workspace = os.path.basename(os.path.dirname(repo))
                    remote_url = normalize_remote_url(run_git(repo, ["remote", "get-url", "origin"]))
                    pipeline_id, pipeline_source = match_pipeline(
                        remote_url,
                        repo_name,
                        self.manual_mappings,
                        self.automatic_mappings,
                    )
                    log_format = "%ci%x1f%h%x1f%an%x1f%s"
                    output = run_git(
                        repo,
                        ["log", "--all", f"--since={self.since}", f"--author={self.author}", f"--pretty=format:{log_format}"],
                        timeout=20,
                    )
                    for line in output.splitlines():
                        parts = line.split("\x1f", 3)
                        if len(parts) != 4:
                            continue
                        committed_at, short_hash, commit_author, subject = parts
                        branch = branch_for_commit(repo, short_hash)
                        rows.append(
                            {
                                "committed_at": committed_at,
                                "workspace": workspace,
                                "repo_name": repo_name,
                                "repo_path": repo,
                                "remote_url": remote_url,
                                "branch": branch,
                                "short_hash": short_hash,
                                "author": commit_author,
                                "subject": subject,
                                "pipeline_id": pipeline_id,
                                "pipeline_source": pipeline_source,
                            }
                        )
                except Exception as exc:
                    errors.append(f"{repo}: {exc}")

        rows.sort(key=lambda row: row.get("committed_at", ""), reverse=True)
        self.signals.scan_finished.emit(rows[:50], "\n".join(errors))


class RunPipelineWorker(QtCore.QRunnable):
    def __init__(self, row_index, history_row, org_url, token, pipeline_id, remote_url, branch, timeout=20):
        super().__init__()
        self.row_index = row_index
        self.history_row = history_row
        self.org_url = org_url.rstrip("/")
        self.token = token
        self.pipeline_id = pipeline_id
        self.remote_url = remote_url
        self.branch = normalize_branch_name(branch)
        self.timeout = timeout
        self.signals = YunxiaoSignals()

    def run(self):
        try:
            session = requests.Session()
            session.trust_env = False
            params = {
                "runningBranchs": {self.remote_url: self.branch},
                "comment": f"run {self.branch}",
            }
            url = f"{self.org_url}/oapi/v1/flow/pipelines/{self.pipeline_id}/runs"
            response = session.post(
                url,
                headers={"Content-Type": "application/json", "x-yunxiao-token": self.token},
                json={"params": json.dumps(params, ensure_ascii=False)},
                timeout=self.timeout,
            )
            payload = self._read_payload(response)
            if not (200 <= response.status_code < 300):
                detail = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
                self.signals.run_finished.emit(
                    self.row_index,
                    self.history_row,
                    False,
                    f"触发失败 HTTP {response.status_code}: {detail[:1200]}",
                    [],
                    "",
                )
                return

            images = extract_image_addresses(payload)
            run_id = self._find_run_id(payload)
            build_url = self._build_history_url(run_id) if run_id else ""
            if run_id:
                detail_payloads = self._fetch_run_details(session, run_id)
                for item in detail_payloads:
                    images.extend(img for img in extract_image_addresses(item) if img not in images)

            summary = json.dumps(payload, ensure_ascii=False)
            if run_id:
                summary = f"已触发 runId={run_id}; {summary}"
            self.signals.run_finished.emit(self.row_index, self.history_row, True, summary[:1500], images, build_url)
        except Exception as exc:
            self.signals.run_finished.emit(self.row_index, self.history_row, False, f"执行异常: {exc}", [], "")

    @staticmethod
    def _read_payload(response):
        try:
            return response.json()
        except Exception:
            return response.text

    @staticmethod
    def _find_run_id(payload):
        if isinstance(payload, int):
            return str(payload)
        if isinstance(payload, float) and payload.is_integer():
            return str(int(payload))
        if isinstance(payload, str) and payload.strip().isdigit():
            return payload.strip()
        if isinstance(payload, dict):
            for key in ("runId", "run_id", "pipelineRunId", "buildId", "build_id", "id"):
                value = payload.get(key)
                if value:
                    return str(value)
            for value in payload.values():
                found = RunPipelineWorker._find_run_id(value)
                if found:
                    return found
        if isinstance(payload, list):
            for value in payload:
                found = RunPipelineWorker._find_run_id(value)
                if found:
                    return found
        return ""

    def _build_history_url(self, run_id):
        public_org_url = self.org_url.replace("/oapi/v1", "").rstrip("/")
        return f"{public_org_url}/flow/pipelines/{self.pipeline_id}/builds/{run_id}"

    def _fetch_run_details(self, session, run_id):
        headers = {"x-yunxiao-token": self.token}
        candidates = [
            f"{self.org_url}/oapi/v1/flow/pipelines/{self.pipeline_id}/runs/{run_id}",
            f"{self.org_url}/oapi/v1/flow/pipelines/{self.pipeline_id}/runs/{run_id}/jobs",
            f"{self.org_url}/oapi/v1/flow/pipelines/{self.pipeline_id}/runs/{run_id}/logs",
        ]
        payloads = []
        for url in candidates:
            try:
                response = session.get(url, headers=headers, timeout=self.timeout)
                if 200 <= response.status_code < 300:
                    payloads.append(self._read_payload(response))
            except Exception:
                continue
        return payloads


class YunxiaoPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.thread_pool = QtCore.QThreadPool.globalInstance()
        self.rows = []
        self._build_ui()
        self.load_config()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self.config_tab = QtWidgets.QWidget()
        self.execute_tab = QtWidgets.QWidget()
        self.history_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.config_tab, "云效流水线配置")
        self.tabs.addTab(self.execute_tab, "云效流水线执行")
        self.tabs.addTab(self.history_tab, "云效流水线执行历史")

        self._build_config_tab()
        self._build_execute_tab()
        self._build_history_tab()

    def _build_config_tab(self):
        layout = QtWidgets.QVBoxLayout(self.config_tab)

        form = QtWidgets.QFormLayout()
        self.org_url_input = QtWidgets.QLineEdit(DEFAULT_ORG_URL)
        self.token_input = QtWidgets.QLineEdit(load_yunxiao_token())
        self.token_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.author_input = QtWidgets.QLineEdit("宇盛")
        self.since_input = QtWidgets.QLineEdit(datetime.now().strftime("%Y-%m-%d 00:00"))
        self.roots_input = QtWidgets.QPlainTextEdit("\n".join(DEFAULT_ROOTS))
        self.roots_input.setFixedHeight(78)
        form.addRow("云效组织地址:", self.org_url_input)
        form.addRow("YUNXIAO_TOKEN:", self.token_input)
        form.addRow("提交作者:", self.author_input)
        form.addRow("提交起始时间:", self.since_input)
        form.addRow("仓库根目录(每行一个):", self.roots_input)
        layout.addLayout(form)

        top_buttons = QtWidgets.QHBoxLayout()
        self.update_pipeline_btn = QtWidgets.QPushButton("更新流水线")
        self.save_config_btn = QtWidgets.QPushButton("保存配置")
        top_buttons.addWidget(self.update_pipeline_btn)
        top_buttons.addWidget(self.save_config_btn)
        layout.addLayout(top_buttons)

        layout.addWidget(QtWidgets.QLabel("OpenAPI 自动映射关系:"))
        self.auto_mapping_table = CopyableTableWidget(0, 4)
        self.auto_mapping_table.setHorizontalHeaderLabels(["仓库/远程地址", "仓库名", "流水线 ID", "流水线名称"])
        self.auto_mapping_table.setColumnWidth(0, 520)
        self.auto_mapping_table.setColumnWidth(1, 170)
        self.auto_mapping_table.setColumnWidth(2, 120)
        self.auto_mapping_table.horizontalHeader().setStretchLastSection(True)
        self.auto_mapping_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.auto_mapping_table)

        layout.addWidget(QtWidgets.QLabel("手动映射关系（优先级最高）:"))
        self.manual_mapping_table = CopyableTableWidget(0, 2)
        self.manual_mapping_table.setHorizontalHeaderLabels(["仓库名或远程地址关键字", "流水线 ID"])
        self.manual_mapping_table.setColumnWidth(0, 560)
        self.manual_mapping_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.manual_mapping_table)

        manual_buttons = QtWidgets.QHBoxLayout()
        self.add_manual_btn = QtWidgets.QPushButton("新增手动映射")
        self.remove_manual_btn = QtWidgets.QPushButton("删除选中手动映射")
        manual_buttons.addWidget(self.add_manual_btn)
        manual_buttons.addWidget(self.remove_manual_btn)
        layout.addLayout(manual_buttons)

        self.update_pipeline_btn.clicked.connect(self.update_pipeline_mappings)
        self.save_config_btn.clicked.connect(self.save_config)
        self.add_manual_btn.clicked.connect(self.add_manual_mapping_row)
        self.remove_manual_btn.clicked.connect(self.remove_selected_manual_rows)

    def _build_execute_tab(self):
        layout = QtWidgets.QVBoxLayout(self.execute_tab)

        action_buttons = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton("扫描最近提交")
        self.run_selected_btn = QtWidgets.QPushButton("执行选中流水线")
        self.run_all_btn = QtWidgets.QPushButton("执行全部已匹配流水线")
        action_buttons.addWidget(self.scan_btn)
        action_buttons.addWidget(self.run_selected_btn)
        action_buttons.addWidget(self.run_all_btn)
        layout.addLayout(action_buttons)

        self.commit_table = CopyableTableWidget(0, 10)
        self.commit_table.setHorizontalHeaderLabels(["时间", "工作区", "仓库", "分支", "提交", "作者", "流水线", "来源", "状态", "构建地址"])
        self.commit_table.setColumnWidth(0, 170)
        self.commit_table.setColumnWidth(2, 170)
        self.commit_table.setColumnWidth(8, 110)
        self.commit_table.setColumnWidth(9, 360)
        self.commit_table.horizontalHeader().setStretchLastSection(True)
        self.commit_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.commit_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.commit_table)

        self.scan_btn.clicked.connect(self.scan_commits)
        self.run_selected_btn.clicked.connect(self.run_selected)
        self.run_all_btn.clicked.connect(self.run_all_matched)
        self.commit_table.itemDoubleClicked.connect(self.open_commit_build_url)

    def _build_history_tab(self):
        layout = QtWidgets.QVBoxLayout(self.history_tab)

        button_layout = QtWidgets.QHBoxLayout()
        self.clear_history_btn = QtWidgets.QPushButton("清空历史")
        button_layout.addWidget(self.clear_history_btn)
        layout.addLayout(button_layout)

        self.history_table = CopyableTableWidget(0, 9)
        self.history_table.setHorizontalHeaderLabels(["执行时间", "仓库", "分支", "提交", "流水线", "来源", "状态", "构建地址", "返回信息"])
        self.history_table.setColumnWidth(0, 170)
        self.history_table.setColumnWidth(1, 190)
        self.history_table.setColumnWidth(3, 220)
        self.history_table.setColumnWidth(7, 360)
        self.history_table.setColumnWidth(8, 420)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.history_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.history_table)

        self.clear_history_btn.clicked.connect(lambda: self.history_table.setRowCount(0))
        self.history_table.itemDoubleClicked.connect(self.open_history_build_url)

    def load_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        if not os.path.exists(CONFIG_PATH):
            self.add_manual_mapping_row("sovell-demeter.git", "1397922")
            return
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
        self.org_url_input.setText(data.get("org_url", DEFAULT_ORG_URL))
        self.author_input.setText(data.get("author", "宇盛"))
        self.since_input.setText(data.get("since", datetime.now().strftime("%Y-%m-%d 00:00")))
        self.roots_input.setPlainText("\n".join(data.get("roots", DEFAULT_ROOTS)))

        manual_mappings = data.get("manual_mappings", data.get("mappings", []))
        self.manual_mapping_table.setRowCount(0)
        for item in manual_mappings:
            self.add_manual_mapping_row(item.get("key", ""), item.get("pipeline_id", ""))

        self.auto_mapping_table.setRowCount(0)
        for item in data.get("automatic_mappings", []):
            self.add_auto_mapping_row(item)

    def save_config(self):
        data = {
            "org_url": self.org_url_input.text().strip(),
            "author": self.author_input.text().strip(),
            "since": self.since_input.text().strip(),
            "roots": self.roots(),
            "manual_mappings": self.manual_mappings(),
            "automatic_mappings": self.automatic_mappings(),
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        QtWidgets.QMessageBox.information(self, "保存", f"配置已保存到 {CONFIG_PATH}\nToken 不会写入配置文件。")

    def update_pipeline_mappings(self):
        token = self.token_input.text().strip() or load_yunxiao_token()
        self.update_pipeline_btn.setEnabled(False)
        LogPage.log("[云效] 开始通过 OpenAPI 更新流水线映射")
        worker = FetchPipelineMappingsWorker(self.org_url_input.text().strip() or DEFAULT_ORG_URL, token, self.roots())
        worker.signals.mappings_finished.connect(self.on_pipeline_mappings_finished)
        self.thread_pool.start(worker)

    @QtCore.pyqtSlot(list, str)
    def on_pipeline_mappings_finished(self, mappings, error):
        self.update_pipeline_btn.setEnabled(True)
        if error:
            LogPage.log(f"[云效] 更新流水线映射失败: {error}")
            QtWidgets.QMessageBox.warning(self, "云效", f"更新流水线映射失败:\n{error}")
            return
        self.auto_mapping_table.setRowCount(0)
        for mapping in mappings:
            self.add_auto_mapping_row(mapping)
        self.save_config_silently()
        LogPage.log(f"[云效] 更新流水线映射完成，共 {len(mappings)} 条")
        QtWidgets.QMessageBox.information(self, "云效", f"已更新 {len(mappings)} 条 OpenAPI 映射")

    def save_config_silently(self):
        data = {
            "org_url": self.org_url_input.text().strip(),
            "author": self.author_input.text().strip(),
            "since": self.since_input.text().strip(),
            "roots": self.roots(),
            "manual_mappings": self.manual_mappings(),
            "automatic_mappings": self.automatic_mappings(),
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def add_auto_mapping_row(self, mapping):
        row = self.auto_mapping_table.rowCount()
        self.auto_mapping_table.insertRow(row)
        values = [
            mapping.get("key", ""),
            mapping.get("repo_name", ""),
            mapping.get("pipeline_id", ""),
            mapping.get("pipeline_name", ""),
        ]
        for col, value in enumerate(values):
            self.auto_mapping_table.setItem(row, col, QtWidgets.QTableWidgetItem(value))

    def add_manual_mapping_row(self, key="", pipeline_id=""):
        row = self.manual_mapping_table.rowCount()
        self.manual_mapping_table.insertRow(row)
        self.manual_mapping_table.setItem(row, 0, QtWidgets.QTableWidgetItem(key))
        self.manual_mapping_table.setItem(row, 1, QtWidgets.QTableWidgetItem(pipeline_id))

    def remove_selected_manual_rows(self):
        rows = sorted({index.row() for index in self.manual_mapping_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.manual_mapping_table.removeRow(row)

    def roots(self):
        return [line.strip() for line in self.roots_input.toPlainText().splitlines() if line.strip()]

    def manual_mappings(self):
        result = []
        for row in range(self.manual_mapping_table.rowCount()):
            key_item = self.manual_mapping_table.item(row, 0)
            pipeline_item = self.manual_mapping_table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            pipeline_id = pipeline_item.text().strip() if pipeline_item else ""
            if key and pipeline_id:
                result.append({"key": key, "pipeline_id": pipeline_id})
        return result

    def automatic_mappings(self):
        result = []
        for row in range(self.auto_mapping_table.rowCount()):
            key_item = self.auto_mapping_table.item(row, 0)
            repo_name_item = self.auto_mapping_table.item(row, 1)
            pipeline_item = self.auto_mapping_table.item(row, 2)
            name_item = self.auto_mapping_table.item(row, 3)
            key = key_item.text().strip() if key_item else ""
            pipeline_id = pipeline_item.text().strip() if pipeline_item else ""
            if key and pipeline_id:
                result.append(
                    {
                        "key": key,
                        "repo_name": repo_name_item.text().strip() if repo_name_item else "",
                        "pipeline_id": pipeline_id,
                        "pipeline_name": name_item.text().strip() if name_item else "",
                    }
                )
        return result

    def scan_commits(self):
        self.scan_btn.setEnabled(False)
        self.commit_table.setRowCount(0)
        self.rows = []
        LogPage.log("[云效] 开始扫描本地最近提交")
        worker = ScanCommitsWorker(
            self.roots(),
            self.author_input.text().strip(),
            self.since_input.text().strip(),
            self.manual_mappings(),
            self.automatic_mappings(),
        )
        worker.signals.scan_finished.connect(self.on_scan_finished)
        self.thread_pool.start(worker)

    @QtCore.pyqtSlot(list, str)
    def on_scan_finished(self, rows, errors):
        self.scan_btn.setEnabled(True)
        self.rows = rows
        self.commit_table.setRowCount(0)
        for row_data in rows:
            row = self.commit_table.rowCount()
            self.commit_table.insertRow(row)
            values = [
                row_data.get("committed_at", ""),
                row_data.get("workspace", ""),
                row_data.get("repo_name", ""),
                row_data.get("branch", ""),
                f"{row_data.get('short_hash', '')} {row_data.get('subject', '')}",
                row_data.get("author", ""),
                row_data.get("pipeline_id", "") or "未匹配",
                row_data.get("pipeline_source", ""),
                "待执行" if row_data.get("pipeline_id") else "缺少映射",
                "",
            ]
            for col, value in enumerate(values):
                self.commit_table.setItem(row, col, QtWidgets.QTableWidgetItem(value))

        LogPage.log(f"[云效] 扫描完成，共 {len(rows)} 条提交")
        if errors:
            LogPage.log(f"[云效] 扫描警告:\n{errors}")

    def run_selected(self):
        rows = sorted({index.row() for index in self.commit_table.selectedIndexes()})
        if not rows:
            QtWidgets.QMessageBox.warning(self, "云效", "请先选择要执行的提交行")
            return
        self.run_rows(rows)

    def open_commit_build_url(self, item):
        if item.column() == 9:
            open_url_from_table_item(item)

    def open_history_build_url(self, item):
        if item.column() == 7:
            open_url_from_table_item(item)

    def run_all_matched(self):
        rows = []
        seen = set()
        for index, row in enumerate(self.rows):
            key = (row.get("pipeline_id"), row.get("remote_url"), row.get("branch"))
            if row.get("pipeline_id") and key not in seen:
                rows.append(index)
                seen.add(key)
        if not rows:
            QtWidgets.QMessageBox.warning(self, "云效", "没有已匹配流水线的提交")
            return
        self.run_rows(rows)

    def run_rows(self, row_indexes):
        token = self.token_input.text().strip() or load_yunxiao_token()
        if not token:
            QtWidgets.QMessageBox.warning(self, "云效", f"请输入 YUNXIAO_TOKEN，或在 {TOKEN_PATH} 写入 token")
            return

        for row_index in row_indexes:
            row_data = self.rows[row_index]
            pipeline_id = row_data.get("pipeline_id")
            if not pipeline_id:
                self.set_commit_status(row_index, "缺少流水线映射", False)
                continue
            self.set_commit_status(row_index, "执行中...", None)
            history_row = self.add_history_row(row_data, "执行中", "", "")
            LogPage.log(
                f"[云效] 触发流水线 pipeline={pipeline_id} repo={row_data.get('repo_name')} branch={row_data.get('branch')}"
            )
            worker = RunPipelineWorker(
                row_index,
                history_row,
                self.org_url_input.text().strip() or DEFAULT_ORG_URL,
                token,
                pipeline_id,
                row_data.get("remote_url", ""),
                row_data.get("branch", ""),
            )
            worker.signals.run_finished.connect(self.on_run_finished)
            self.thread_pool.start(worker)

    @QtCore.pyqtSlot(int, int, bool, str, list, str)
    def on_run_finished(self, row_index, history_row, success, message, images, build_url):
        self.set_commit_status(row_index, "已触发" if success else "失败", success)
        self.commit_table.setItem(row_index, 9, build_url_item(build_url))
        self.update_history_row(history_row, "已触发" if success else "失败", build_url, message)
        if success:
            LogPage.log(f"[云效] 执行成功: {message}")
            if build_url:
                LogPage.log(f"[云效] 构建地址: {build_url}")
        else:
            LogPage.log(f"[云效] 执行失败: {message}")

    def add_history_row(self, row_data, status, build_url, message):
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        values = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            row_data.get("repo_name", ""),
            row_data.get("branch", ""),
            f"{row_data.get('short_hash', '')} {row_data.get('subject', '')}",
            row_data.get("pipeline_id", ""),
            row_data.get("pipeline_source", ""),
            status,
            build_url,
            message,
        ]
        for col, value in enumerate(values):
            if col == 7:
                self.history_table.setItem(row, col, build_url_item(value))
            else:
                self.history_table.setItem(row, col, QtWidgets.QTableWidgetItem(value))
        return row

    def update_history_row(self, row, status, build_url, message):
        if row < 0 or row >= self.history_table.rowCount():
            return
        self.history_table.setItem(row, 6, QtWidgets.QTableWidgetItem(status))
        self.history_table.setItem(row, 7, build_url_item(build_url))
        self.history_table.setItem(row, 8, QtWidgets.QTableWidgetItem(message))

    def set_commit_status(self, row_index, text, success):
        item = QtWidgets.QTableWidgetItem(text)
        if success is True:
            item.setForeground(QtCore.Qt.darkGreen)
        elif success is False:
            item.setForeground(QtCore.Qt.red)
        self.commit_table.setItem(row_index, 8, item)
