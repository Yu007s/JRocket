#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

import requests


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(os.path.expanduser("~"), "JRocket", "yunxiao_config.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, "ui", "yunxiao", "yunxiaotoken.txt")
DEFAULT_ORG_URL = "https://sovell-cn-shanghai.devops.aliyuncs.com"
DEFAULT_ROOTS = [
    "/Users/devjys/Desktop/WorkSpaces/sovell/sovell15~20",
    "/Users/devjys/Desktop/WorkSpaces/sovell/sovell11~14",
    "/Users/devjys/Desktop/WorkSpaces/sovell/sovell21~",
]


def usage():
    print(
        """Usage:
  scripts/push_branch_if_exists.sh <branch> [root_dir...]

Examples:
  scripts/push_branch_if_exists.sh stable-v5.0.20-chongqingluqin
  scripts/push_branch_if_exists.sh stable-v5.0.20-chongqingluqin /Users/devjys/Desktop/WorkSpaces/sovell/sovell15~20

Behavior:
  - Reads JRocket Yunxiao config from ~/JRocket/yunxiao_config.json.
  - Reads Yunxiao token from ui/yunxiao/yunxiaotoken.txt or YUNXIAO_TOKEN.
  - Scans local git repositories under configured roots or passed roots.
  - If a repository has the branch locally or under origin, triggers its matched Yunxiao pipeline.
"""
    )


def run_git(repo_path, args, timeout=10):
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


def load_token():
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as file:
            token = file.read().strip()
            if token:
                return token
    except FileNotFoundError:
        pass
    return os.environ.get("YUNXIAO_TOKEN", "").strip()


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_remote_url(remote_url):
    remote_url = (remote_url or "").strip()
    if remote_url.startswith("git@"):
        match = re.match(r"git@([^:]+):(.+)", remote_url)
        if match:
            return f"https://{match.group(1)}/{match.group(2)}"
    if remote_url.startswith("ssh://git@"):
        parsed = urlparse(remote_url)
        return f"https://{parsed.hostname}/{parsed.path.lstrip('/')}"
    return remote_url


def normalize_yunxiao_codeup_url(remote_url):
    remote_url = normalize_remote_url(remote_url)
    parsed = urlparse(remote_url)
    if not parsed.scheme or not parsed.netloc:
        return remote_url
    path = parsed.path
    if "devops.aliyuncs.com" in parsed.netloc and path.startswith("/codeup/sovell/"):
        path = path.replace("/codeup/sovell/", "/codeup/", 1)
        return parsed._replace(path=path).geturl()
    return remote_url


def normalize_for_match(value):
    value = normalize_yunxiao_codeup_url(value or "").lower().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value


def repo_path_from_remote(remote_url):
    normalized = normalize_yunxiao_codeup_url(remote_url)
    parsed = urlparse(normalized)
    path = parsed.path.lstrip("/") if parsed.path else normalized
    path = path.lower().rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def repo_name_from_text(value):
    normalized = normalize_for_match(value)
    return normalized.split("/")[-1] if normalized else ""


def mapping_matches_repo(mapping, remote_url, repo_name, allow_repo_name=False):
    key = (mapping.get("key") or "").strip()
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


def mapping_repo_url(mapping, fallback_url):
    key = (mapping.get("key") or "").strip()
    if key.startswith(("http://", "https://", "git@", "ssh://")) or "/codeup/" in key:
        return normalize_yunxiao_codeup_url(key)
    return normalize_yunxiao_codeup_url(fallback_url)


def match_pipeline(remote_url, repo_name, manual_mappings, automatic_mappings):
    for mapping in manual_mappings:
        pipeline_id = (mapping.get("pipeline_id") or "").strip()
        if pipeline_id and mapping_matches_repo(mapping, remote_url, repo_name, allow_repo_name=True):
            return pipeline_id, "manual", mapping_repo_url(mapping, remote_url)

    for mapping in automatic_mappings:
        pipeline_id = (mapping.get("pipeline_id") or "").strip()
        if pipeline_id and mapping_matches_repo(mapping, remote_url, repo_name):
            return pipeline_id, "openapi", mapping_repo_url(mapping, remote_url)

    exact_name_mappings = []
    repo_short_key = normalize_for_match(repo_name)
    for mapping in automatic_mappings:
        pipeline_id = (mapping.get("pipeline_id") or "").strip()
        mapping_repo_name = normalize_for_match(mapping.get("repo_name", ""))
        mapping_key_name = repo_name_from_text(mapping.get("key", ""))
        if pipeline_id and repo_short_key and repo_short_key in (mapping_repo_name, mapping_key_name):
            exact_name_mappings.append(mapping)
    if len(exact_name_mappings) == 1:
        mapping = exact_name_mappings[0]
        return (mapping.get("pipeline_id") or "").strip(), "openapi-name", mapping_repo_url(mapping, remote_url)

    return "", "", normalize_yunxiao_codeup_url(remote_url)


def branch_exists(repo_path, branch):
    checks = [
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
    ]
    for args in checks:
        process = subprocess.run(["git", "-C", repo_path] + args)
        if process.returncode == 0:
            return True
    return False


def collect_repositories(roots):
    repos = []
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            print(f"[skip-root] not found: {root}")
            continue
        for current, dirs, _files in os.walk(root):
            if ".git" not in dirs:
                if current.count(os.sep) - root.count(os.sep) >= 2:
                    dirs[:] = []
                continue
            dirs[:] = []
            try:
                remote_url = normalize_yunxiao_codeup_url(run_git(current, ["remote", "get-url", "origin"]))
            except Exception as exc:
                print(f"[skip] {current}: cannot read origin remote: {exc}")
                continue
            key = normalize_for_match(remote_url)
            if key in seen:
                continue
            seen.add(key)
            repos.append(
                {
                    "path": current,
                    "repo_name": os.path.basename(current),
                    "remote_url": remote_url,
                }
            )
    return repos


def trigger_pipeline(session, org_url, token, pipeline_id, repo_url, branch):
    params = {
        "runningBranchs": {repo_url: branch},
        "comment": f"run {branch}",
    }
    url = f"{org_url}/oapi/v1/flow/pipelines/{pipeline_id}/runs"
    response = session.post(
        url,
        headers={"Content-Type": "application/json", "x-yunxiao-token": token},
        json={"params": json.dumps(params, ensure_ascii=False)},
        timeout=20,
    )
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return response.status_code, payload


def find_run_id(payload):
    if isinstance(payload, int):
        return str(payload)
    if isinstance(payload, str) and payload.strip().isdigit():
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("runId", "run_id", "pipelineRunId", "buildId", "build_id", "id"):
            value = payload.get(key)
            if value:
                return str(value)
        for value in payload.values():
            found = find_run_id(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = find_run_id(value)
            if found:
                return found
    return ""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        usage()
        return 0

    branch = sys.argv[1].strip()
    if not branch:
        print("Branch name cannot be empty.", file=sys.stderr)
        return 1

    config = load_config()
    roots = sys.argv[2:] or config.get("roots") or DEFAULT_ROOTS
    org_url = (config.get("org_url") or DEFAULT_ORG_URL).rstrip("/")
    token = load_token()
    if not token:
        print(f"Missing Yunxiao token. Put it in {TOKEN_PATH} or export YUNXIAO_TOKEN.", file=sys.stderr)
        return 1

    manual_mappings = config.get("manual_mappings", config.get("mappings", []))
    automatic_mappings = config.get("automatic_mappings", [])

    repos = collect_repositories(roots)
    session = requests.Session()
    session.trust_env = False

    total = 0
    triggered = 0
    skipped = 0
    failed = 0

    for repo in repos:
        total += 1
        repo_name = repo["repo_name"]
        if not branch_exists(repo["path"], branch):
            print(f"[skip] {repo_name}: branch not found: {branch}")
            skipped += 1
            continue

        pipeline_id, source, pipeline_repo_url = match_pipeline(
            repo["remote_url"],
            repo_name,
            manual_mappings,
            automatic_mappings,
        )
        if not pipeline_id:
            print(f"[skip] {repo_name}: no matched Yunxiao pipeline")
            skipped += 1
            continue

        print(f"[run] {repo_name}: pipeline={pipeline_id} source={source} branch={branch}")
        print(f"      runningBranchs={pipeline_repo_url}:{branch}")
        status_code, payload = trigger_pipeline(session, org_url, token, pipeline_id, pipeline_repo_url, branch)
        if not (200 <= status_code < 300):
            print(f"[fail] {repo_name}: HTTP {status_code} {json.dumps(payload, ensure_ascii=False)[:1000]}")
            failed += 1
            continue

        run_id = find_run_id(payload)
        build_url = f"{org_url}/flow/pipelines/{pipeline_id}/builds/{run_id}" if run_id else ""
        print(f"[ok] {repo_name}: runId={run_id or '-'} {build_url}")
        triggered += 1

    print()
    print(f"Done. total={total} triggered={triggered} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
