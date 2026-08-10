#!/usr/bin/env python3
"""Create or update complete Git mirrors from repositories.csv."""

import argparse
import csv
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = SCRIPT_DIR / "repositories.csv"


def mirror_path(destination: Path, repository_path: str) -> Path:
    parts = [part for part in repository_path.split("/") if part not in ("", ".", "..")]
    if not parts:
        raise ValueError(f"Invalid repository path: {repository_path!r}")
    name = parts[-1] if parts[-1].endswith(".git") else f"{parts[-1]}.git"
    return destination.joinpath(*parts[:-1], name)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def mirror_one(row: dict[str, str], destination: Path, include_lfs: bool) -> dict[str, str]:
    repository_path = row["path"]
    clone_url = row["http_clone_url"]
    target = mirror_path(destination, repository_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_dir():
        command = ["git", "-C", str(target), "remote", "update", "--prune"]
        action = "updated"
    else:
        command = ["git", "clone", "--mirror", clone_url, str(target)]
        action = "cloned"

    result = run(command)
    if result.returncode != 0:
        return {
            "path": repository_path,
            "status": "failed",
            "action": action,
            "target": str(target),
            "message": (result.stderr or result.stdout).strip(),
        }

    if include_lfs:
        result = run(["git", "-C", str(target), "lfs", "fetch", "--all"])
        if result.returncode != 0:
            return {
                "path": repository_path,
                "status": "failed",
                "action": action,
                "target": str(target),
                "message": f"Git mirror succeeded; LFS failed: {(result.stderr or result.stdout).strip()}",
            }

    return {
        "path": repository_path,
        "status": "ok",
        "action": action,
        "target": str(target),
        "message": "",
    }


def load_repositories(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    required = {"path", "http_clone_url"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"{csv_path} must contain columns: {', '.join(sorted(required))}")
    return [row for row in rows if row["path"] and row["http_clone_url"]]


def write_results(path: Path, results: list[dict[str, str]]) -> None:
    fields = ["path", "status", "action", "target", "message"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror all Codeup repositories concurrently.")
    parser.add_argument("destination", type=Path, help="Directory that will contain the .git mirrors")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help=f"Source CSV (default: {DEFAULT_CSV})")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent Git operations (default: 4)")
    parser.add_argument("--include-lfs", action="store_true", help="Also fetch every Git LFS object")
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if not args.csv.is_file():
        parser.error(f"CSV not found: {args.csv}")

    repositories = load_repositories(args.csv)
    args.destination.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(mirror_one, row, args.destination, args.include_lfs): row["path"]
            for row in repositories
        }
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(f"[{index}/{len(repositories)}] {result['status']}: {result['path']}", flush=True)

    results.sort(key=lambda item: item["path"])
    results_path = args.destination / "mirror_results.csv"
    write_results(results_path, results)
    failures = sum(item["status"] != "ok" for item in results)
    print(f"Finished: {len(results) - failures} succeeded, {failures} failed.")
    print(f"Results: {results_path}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
