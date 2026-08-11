#!/usr/bin/env bash
set -euo pipefail

GITEE_OWNER="${GITEE_OWNER:-}"
GITEE_TOKEN="${GITEE_TOKEN:-}"
CSV_FILE="${CSV_FILE:-/Users/devjys/Desktop/WorkSpaces/JRocket/scripts/yunxiao-repo-export/repositories.csv}"
TOKEN_FILE="${TOKEN_FILE:-/Users/devjys/Desktop/WorkSpaces/JRocket/scripts/yunxiao-repo-export/gitee token}"
EXECUTE="${EXECUTE:-0}"
RESULTS_FILE="${RESULTS_FILE:-/Users/devjys/Desktop/WorkSpaces/JRocket/scripts/yunxiao-repo-export/gitee_rename_results.tsv}"

if [[ -z "$GITEE_TOKEN" && -f "$TOKEN_FILE" ]]; then
  GITEE_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi

if [[ -z "$GITEE_OWNER" || -z "$GITEE_TOKEN" ]]; then
  echo "Please export GITEE_OWNER and GITEE_TOKEN before running."
  exit 1
fi

if [[ ! -f "$CSV_FILE" ]]; then
  echo "CSV file not found: $CSV_FILE"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  echo "curl and python3 are required."
  exit 1
fi

TMP_MAP="$(mktemp)"
cleanup() {
  rm -f "$TMP_MAP"
}
trap cleanup EXIT

python3 - <<'PY' > "$TMP_MAP"
import csv
import os
import sys
from collections import Counter, defaultdict

csv_file = os.environ["CSV_FILE"]

rows = []
with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        path = (row.get("path") or "").strip().strip("/")
        if not path:
            continue
        parts = path.split("/")
        rows.append((path, parts))

last_counts = Counter(parts[-1] for _, parts in rows)
new_name_to_paths = defaultdict(list)
records = []

for path, parts in rows:
    last = parts[-1]
    if last_counts[last] > 1 and len(parts) >= 2:
      new_name = f"{parts[-2]}-{last}"
    else:
      new_name = last
    old_name = "-".join(parts)
    new_name_to_paths[new_name].append(path)
    records.append((path, old_name, new_name))

collisions = {name: paths for name, paths in new_name_to_paths.items() if len(paths) > 1}
if collisions:
    print("New naming rule still has collisions:", file=sys.stderr)
    for name, paths in sorted(collisions.items()):
        print(name, file=sys.stderr)
        for path in paths:
            print(f"  {path}", file=sys.stderr)
    sys.exit(1)

for path, old_name, new_name in records:
    print("\t".join([path, old_name, new_name]))
PY

printf 'path\told_repo\tnew_repo\tstatus\tmessage\n' > "$RESULTS_FILE"

echo "Owner: $GITEE_OWNER"
echo "CSV: $CSV_FILE"
echo "Results: $RESULTS_FILE"
echo

if [[ "$EXECUTE" != "1" ]]; then
  echo "Preview mode. Set EXECUTE=1 to actually rename repositories."
  echo
fi

while IFS=$'\t' read -r path old_repo new_repo; do
  [[ -n "$old_repo" ]] || continue

  if [[ "$old_repo" == "$new_repo" ]]; then
    echo "Skip $old_repo (already short enough)"
    printf '%s\t%s\t%s\tskipped\talready matches target rule\n' \
      "$path" "$old_repo" "$new_repo" >> "$RESULTS_FILE"
    continue
  fi

  echo "$old_repo -> $new_repo"

  if [[ "$EXECUTE" != "1" ]]; then
    printf '%s\t%s\t%s\tpreview\tno change applied\n' \
      "$path" "$old_repo" "$new_repo" >> "$RESULTS_FILE"
    continue
  fi

  status="$(curl -sS -o /tmp/gitee_rename_repo_body.$$ -w '%{http_code}' \
    -X PATCH "https://gitee.com/api/v5/repos/$GITEE_OWNER/$old_repo" \
    --data-urlencode "access_token=$GITEE_TOKEN" \
    --data-urlencode "name=$new_repo" \
    --data-urlencode "path=$new_repo")"

  if [[ "$status" == "200" ]]; then
    printf '%s\t%s\t%s\tok\trenamed\n' \
      "$path" "$old_repo" "$new_repo" >> "$RESULTS_FILE"
  else
    message="$(tr '\n' ' ' < /tmp/gitee_rename_repo_body.$$ | sed 's/[[:space:]]\\+/ /g')"
    printf '%s\t%s\t%s\tfailed\tHTTP %s %s\n' \
      "$path" "$old_repo" "$new_repo" "$status" "$message" >> "$RESULTS_FILE"
  fi
done < "$TMP_MAP"

rm -f /tmp/gitee_rename_repo_body.$$
echo
echo "Done. Results: $RESULTS_FILE"
