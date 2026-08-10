#!/usr/bin/env bash
set -u

# Set these through the environment before running.
GITHUB_OWNER="${GITHUB_OWNER:-yjjwnwmzzjc-commits}"
GITHUB_TOKEN="${GITHUB_TOKEN:-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}"
MIRROR_ROOT="/Users/devjys/Documents/雄伟科技/全部代码全量git"
REPO_NAME_MODE="${REPO_NAME_MODE:-path}"
JOBS="${JOBS:-20}"

API="https://api.github.com"
RESULTS_FILE="$MIRROR_ROOT/github_import_results.tsv"
OWNER_TYPE=""
DELETE_ON_FAILURE="${DELETE_ON_FAILURE:-0}"

if [[ -z "$GITHUB_OWNER" || -z "$GITHUB_TOKEN" ]]; then
  echo "Please export GITHUB_OWNER and GITHUB_TOKEN before running."
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
if ! command -v git-lfs >/dev/null 2>&1; then
  echo "git-lfs is required because this migration includes Git LFS objects."
  exit 1
fi
if ! [[ "$JOBS" =~ ^[0-9]+$ ]] || [[ "$JOBS" -lt 1 ]]; then
  echo "JOBS must be a positive integer."
  exit 1
fi

ASKPASS="$(mktemp)"
chmod 700 "$ASKPASS"
cat > "$ASKPASS" <<'EOF'
#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' 'x-access-token' ;;
  *) printf '%s\n' "$GITHUB_TOKEN" ;;
esac
EOF
trap 'rm -f "$ASKPASS"' EXIT

export GITHUB_TOKEN
export GIT_ASKPASS="$ASKPASS"
export GIT_TERMINAL_PROMPT=0
export GITHUB_OWNER OWNER_TYPE REPO_NAME_MODE DELETE_ON_FAILURE API

printf 'path\trepository\tstatus\tmessage\n' > "$RESULTS_FILE"

detect_owner_type() {
  local status response_file owner_type
  response_file="$(mktemp)"

  status="$(curl -sS -o "$response_file" -w '%{http_code}' \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H 'Accept: application/vnd.github+json' \
    "$API/users/$GITHUB_OWNER")"
  if [[ "$status" != "200" ]]; then
    echo "GitHub owner lookup failed for $GITHUB_OWNER (HTTP $status)"
    rm -f "$response_file"
    return 1
  fi

  owner_type="$(jq -r '.type // empty' "$response_file")"
  rm -f "$response_file"
  if [[ "$owner_type" != "User" && "$owner_type" != "Organization" ]]; then
    echo "Unable to determine GitHub owner type for $GITHUB_OWNER"
    return 1
  fi

  OWNER_TYPE="$owner_type"
}

target_repo_name() {
  local relative_path="$1"
  local trimmed_path
  trimmed_path="${relative_path%.git}"

  case "$REPO_NAME_MODE" in
    leaf)
      basename "$trimmed_path"
      ;;
    path)
      # Keep path context to avoid collisions across groups with the same leaf name.
      printf '%s\n' "${trimmed_path//\//-}"
      ;;
    *)
      echo "Unsupported REPO_NAME_MODE: $REPO_NAME_MODE"
      return 1
      ;;
  esac
}

create_repository() {
  local name="$1"
  local status response_file
  response_file="$(mktemp)"

  status="$(curl -sS -o "$response_file" -w '%{http_code}' \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H 'Accept: application/vnd.github+json' \
    "$API/repos/$GITHUB_OWNER/$name")"
  if [[ "$status" == "200" ]]; then
    rm -f "$response_file"
    return 0
  fi
  if [[ "$status" != "404" ]]; then
    echo "GitHub API lookup failed for $name (HTTP $status)"
    rm -f "$response_file"
    return 1
  fi

  local create_url
  if [[ "$OWNER_TYPE" == "Organization" ]]; then
    create_url="$API/orgs/$GITHUB_OWNER/repos"
  else
    create_url="$API/user/repos"
  fi

  status="$(curl -sS -o "$response_file" -w '%{http_code}' \
    -X POST \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H 'Accept: application/vnd.github+json' \
    -H 'Content-Type: application/json' \
    "$create_url" \
    --data "$(jq -cn --arg name "$name" '{name:$name, private:true, has_issues:false, has_projects:false, has_wiki:false}')")"
  rm -f "$response_file"
  [[ "$status" == "201" || "$status" == "422" ]]
}

delete_repository() {
  local name="$1"
  local status

  status="$(curl -sS -o /dev/null -w '%{http_code}' \
    -X DELETE \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H 'Accept: application/vnd.github+json' \
    "$API/repos/$GITHUB_OWNER/$name")"
  [[ "$status" == "204" || "$status" == "404" ]]
}

process_mirror() {
  local mirror="$1"
  local path name github_url result_file
  result_file="$2"

  path="${mirror#"$MIRROR_ROOT"/}"
  if ! name="$(target_repo_name "$path")"; then
    printf '%s\t%s\tfailed\tinvalid repository name\n' "$path" "unknown" >> "$result_file"
    return 0
  fi
  github_url="https://github.com/$GITHUB_OWNER/$name.git"

  echo "Migrating $path -> $GITHUB_OWNER/$name"
  if ! create_repository "$name"; then
    printf '%s\t%s\tfailed\tcreate repository\n' "$path" "$name" >> "$result_file"
    return 0
  fi

  if ! git -C "$mirror" remote get-url github >/dev/null 2>&1; then
    git -C "$mirror" remote add github "$github_url"
  else
    git -C "$mirror" remote set-url github "$github_url"
  fi

  # GitHub rejects Gerrit review refs like refs/changes/*, so only push branches and tags.
  if ! git -C "$mirror" push github 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'; then
    if [[ "$DELETE_ON_FAILURE" == "1" ]]; then
      delete_repository "$name"
    fi
    printf '%s\t%s\tfailed\tgit push\n' "$path" "$name" >> "$result_file"
    return 0
  fi
  if ! git -C "$mirror" lfs push --all github; then
    if [[ "$DELETE_ON_FAILURE" == "1" ]]; then
      delete_repository "$name"
    fi
    printf '%s\t%s\tfailed\tgit lfs push\n' "$path" "$name" >> "$result_file"
    return 0
  fi

  printf '%s\t%s\tok\t\n' "$path" "$name" >> "$result_file"
}

if ! detect_owner_type; then
  exit 1
fi

echo "GitHub owner: $GITHUB_OWNER ($OWNER_TYPE), repo naming mode: $REPO_NAME_MODE"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

declare -a mirrors=()
while IFS= read -r -d '' mirror; do
  mirrors+=("$mirror")
done < <(find "$MIRROR_ROOT" -type d -name '*.git' -print0)

active_jobs=0
declare -a pids=()
for mirror in "${mirrors[@]}"; do
  result_file="$tmp_dir/$(printf '%s' "$mirror" | shasum | awk '{print $1}').tsv"
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

for result_file in "$tmp_dir"/*.tsv; do
  [[ -e "$result_file" ]] || continue
  cat "$result_file" >> "$RESULTS_FILE"
done

echo "Finished. Results: $RESULTS_FILE"
