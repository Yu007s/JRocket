#!/usr/bin/env python3
"""导出 Region 版自建云效 Codeup 仓库的 HTTP 克隆地址。"""

import csv
import sys
from pathlib import Path

import requests

# 复用 JRocket 现有的云效个人访问令牌（PAT）。
TOKEN_FILE = Path(__file__).parents[2] / "ui" / "yunxiao" / "yunxiaotoken.txt"
ACCESS_TOKEN = TOKEN_FILE.read_text(encoding="utf-8").strip()
API_BASE_URL = "https://sovell-cn-shanghai.devops.aliyuncs.com"

OUTPUT_FILE = Path(__file__).with_name("repositories.csv")
PER_PAGE = 100


def list_repositories(session: requests.Session) -> list[dict]:
    repositories: list[dict] = []
    page = 1

    while True:
        response = session.get(
            f"{API_BASE_URL}/oapi/v1/codeup/repositories",
            headers={
                "Content-Type": "application/json",
                "x-yunxiao-token": ACCESS_TOKEN,
            },
            params={
                "page": page,
                "perPage": PER_PAGE,
                "orderBy": "path",
                "sort": "asc",
                "archived": "false",
            },
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json()
        repositories.extend(batch)

        next_page = response.headers.get("X-Next-Page")
        current_page = int(response.headers.get("X-Page", page))
        total_pages = int(response.headers.get("X-Total-Pages", current_page))
        if (
            not next_page
            or next_page == "0"
            or current_page >= total_pages
            or int(next_page) <= current_page
        ):
            return repositories
        page = int(next_page)


def export_repositories() -> None:
    if not ACCESS_TOKEN:
        sys.exit("请先在脚本顶部填写 ACCESS_TOKEN。")

    with requests.Session() as session:
        repositories = list_repositories(session)

    rows = [
        {
            "id": repository["id"],
            "path": repository["pathWithNamespace"],
            "http_clone_url": repository["httpUrlToRepo"],
            "web_url": repository["webUrl"],
            "archived": repository["archived"],
        }
        for repository in repositories
    ]

    fieldnames = ["id", "path", "http_clone_url", "web_url", "archived"]
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"已导出 {len(rows)} 个仓库: {OUTPUT_FILE}")


if __name__ == "__main__":
    export_repositories()
