#!/bin/sh
[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
set -u -o pipefail

GITEE_OWNER="${GITEE_OWNER:-yu007sheng}"
GITEE_TOKEN="${GITEE_TOKEN:-992e80a25c2a7fc270ac2a02e05a0064}"
GITEE_OWNER_TYPE="${GITEE_OWNER_TYPE:-user}"
GITEE_API="${GITEE_API:-https://gitee.com/api/v5}"
GITEE_HOST="${GITEE_HOST:-https://gitee.com}"
MIRROR_ROOT="${MIRROR_ROOT:-/Users/devjys/Documents/雄伟科技/全部代码全量git}"
REPO_NAME_MODE="${REPO_NAME_MODE:-path}"
JOBS="${JOBS:-10}"
PROJECT_LABEL="${PROJECT_LABEL:-sovell}"
PROJECT_LABEL_COLOR="${PROJECT_LABEL_COLOR:-108ee9}"
REPO_PRIVATE="${REPO_PRIVATE:-1}"
DELETE_ON_FAILURE="${DELETE_ON_FAILURE:-0}"
RESULTS_FILE="${RESULTS_FILE:-$MIRROR_ROOT/gitee_import_results.tsv}"
TOKEN_FILE="${TOKEN_FILE:-/Users/devjys/Desktop/WorkSpaces/JRocket/scripts/yunxiao-repo-export/gitee token}"

if [[ -z "$GITEE_TOKEN" && -f "$TOKEN_FILE" ]]; then
  GITEE_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi

if [[ -z "$GITEE_OWNER" || -z "$GITEE_TOKEN" ]]; then
  echo "Please export GITEE_OWNER and GITEE_TOKEN before running."
  exit 1
fi
if [[ ! -d "$MIRROR_ROOT" ]]; then
  echo "Mirror directory not found: $MIRROR_ROOT"
  exit 1
fi
if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  echo "curl and jq are required."
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo "git is required."
  exit 1
fi
if ! [[ "$JOBS" =~ ^[0-9]+$ ]] || [[ "$JOBS" -lt 1 ]]; then
  echo "JOBS must be a positive integer."
  exit 1
fi
if [[ "$GITEE_OWNER_TYPE" != "user" && "$GITEE_OWNER_TYPE" != "org" ]]; then
  echo "GITEE_OWNER_TYPE must be user or org."
  exit 1
fi

ASKPASS="$(mktemp)"
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -f "$ASKPASS"
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

chmod 700 "$ASKPASS"
cat > "$ASKPASS" <<'EOF'
#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' "$GITEE_OWNER" ;;
  *) printf '%s\n' "$GITEE_TOKEN" ;;
esac
EOF

export GITEE_OWNER GITEE_TOKEN GITEE_OWNER_TYPE GITEE_API GITEE_HOST
export MIRROR_ROOT REPO_NAME_MODE PROJECT_LABEL PROJECT_LABEL_COLOR
export REPO_PRIVATE DELETE_ON_FAILURE TMP_DIR
export GIT_ASKPASS="$ASKPASS"
export GIT_TERMINAL_PROMPT=0
export GIT_HTTP_VERSION=HTTP/1.1

printf 'path\trepository\tstatus\tmessage\n' > "$RESULTS_FILE"

api_call() {
  curl -sS \
    --retry 3 \
    --retry-delay 2 \
    --retry-connrefused \
    -H 'Accept: application/json' \
    "$@"
}

target_repo_name() {
  local relative_path="$1"
  local trimmed_path="${relative_path%.git}"

  case "$REPO_NAME_MODE" in
    leaf)
      basename "$trimmed_path"
      ;;
    path)
      printf '%s\n' "${trimmed_path//\//-}"
      ;;
    *)
      echo "Unsupported REPO_NAME_MODE: $REPO_NAME_MODE"
      return 1
      ;;
  esac
}

repo_exists() {
  local name="$1"
  local status

  status="$(curl -sS -o /dev/null -w '%{http_code}' \
    "$GITEE_API/repos/$GITEE_OWNER/$name?access_token=$GITEE_TOKEN")"
  [[ "$status" == "200" ]]
}

create_repository() {
  local name="$1"
  local private_value create_url status
  private_value=0
  [[ "$REPO_PRIVATE" == "1" ]] && private_value=1

  if repo_exists "$name"; then
    return 0
  fi

  if [[ "$GITEE_OWNER_TYPE" == "org" ]]; then
    create_url="$GITEE_API/orgs/$GITEE_OWNER/repos"
  else
    create_url="$GITEE_API/user/repos"
  fi

  status="$(curl -sS -o /dev/null -w '%{http_code}' \
    -X POST "$create_url" \
    --data-urlencode "access_token=$GITEE_TOKEN" \
    --data-urlencode "name=$name" \
    --data-urlencode "path=$name" \
    --data-urlencode "private=$private_value" \
    --data-urlencode 'has_issues=true' \
    --data-urlencode 'has_wiki=false' \
    --data-urlencode 'can_comment=true')"

  [[ "$status" == "201" || "$status" == "422" ]]
}

ensure_label() {
  local name="$1"
  local labels status

  labels="$(api_call "$GITEE_API/repos/$GITEE_OWNER/$name/labels?access_token=$GITEE_TOKEN")" || return 1
  if printf '%s' "$labels" | jq -e --arg label "$PROJECT_LABEL" '.[] | select(.name == $label)' >/dev/null 2>&1; then
    return 0
  fi

  status="$(curl -sS -o /dev/null -w '%{http_code}' \
    -X POST "$GITEE_API/repos/$GITEE_OWNER/$name/labels" \
    --data-urlencode "access_token=$GITEE_TOKEN" \
    --data-urlencode "name=$PROJECT_LABEL" \
    --data-urlencode "color=$PROJECT_LABEL_COLOR")"

  [[ "$status" == "201" || "$status" == "422" ]]
}

delete_repository() {
  local name="$1"
  local status

  status="$(curl -sS -o /dev/null -w '%{http_code}' \
    -X DELETE \
    "$GITEE_API/repos/$GITEE_OWNER/$name?access_token=$GITEE_TOKEN")"
  [[ "$status" == "204" || "$status" == "404" ]]
}

process_mirror() {
  local mirror="$1"
  local result_file="$2"
  local path name remote_url

  path="${mirror#"$MIRROR_ROOT"/}"
  if ! name="$(target_repo_name "$path")"; then
    printf '%s\t%s\tfailed\tinvalid repository name\n' "$path" "unknown" >> "$result_file"
    return 0
  fi

  remote_url="$GITEE_HOST/$GITEE_OWNER/$name.git"
  echo "Migrating $path -> $GITEE_OWNER/$name"

  if ! create_repository "$name"; then
    printf '%s\t%s\tfailed\tcreate repository\n' "$path" "$name" >> "$result_file"
    return 0
  fi

  if ! ensure_label "$name"; then
    printf '%s\t%s\tfailed\tensure label %s\n' "$path" "$name" "$PROJECT_LABEL" >> "$result_file"
    return 0
  fi

  if ! git -C "$mirror" remote get-url gitee >/dev/null 2>&1; then
    git -C "$mirror" remote add gitee "$remote_url"
  else
    git -C "$mirror" remote set-url gitee "$remote_url"
  fi

  if ! git -C "$mirror" push gitee 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'; then
    if [[ "$DELETE_ON_FAILURE" == "1" ]]; then
      delete_repository "$name"
    fi
    printf '%s\t%s\tfailed\tgit push\n' "$path" "$name" >> "$result_file"
    return 0
  fi

  if command -v git-lfs >/dev/null 2>&1; then
    if ! git -C "$mirror" lfs push --all gitee; then
      if [[ "$DELETE_ON_FAILURE" == "1" ]]; then
        delete_repository "$name"
      fi
      printf '%s\t%s\tfailed\tgit lfs push\n' "$path" "$name" >> "$result_file"
      return 0
    fi
  fi

  printf '%s\t%s\tok\tlabel=%s\n' "$path" "$name" "$PROJECT_LABEL" >> "$result_file"
}

declare -a mirrors=()
while IFS= read -r -d '' mirror; do
  mirrors+=("$mirror")
done < <(find "$MIRROR_ROOT" -type d -name '*.git' -print0)

echo "Gitee owner: $GITEE_OWNER ($GITEE_OWNER_TYPE), repo naming mode: $REPO_NAME_MODE, jobs: $JOBS, label: $PROJECT_LABEL"
echo "Mirror root: $MIRROR_ROOT"
echo "Found ${#mirrors[@]} mirror repositories."

active_jobs=0
declare -a pids=()
for mirror in "${mirrors[@]}"; do
  result_file="$TMP_DIR/$(printf '%s' "$mirror" | shasum | awk '{print $1}').tsv"
  process_mirror "$mirror" "$result_file" &
  pids+=("$!")
  active_jobs=$((active_jobs + 1))
  if [[ "$active_jobs" -ge "$JOBS" ]]; then
    wait "${pids[0]}"
    pids=("${pids[@]:1}")
    active_jobs=$((active_jobs - 1))
  fi
done

for pid in "${pids[@]}"; do
  wait "$pid"
done

for result_file in "$TMP_DIR"/*.tsv; do
  [[ -e "$result_file" ]] || continue
  cat "$result_file" >> "$RESULTS_FILE"
done

echo "Finished. Results: $RESULTS_FILE"
