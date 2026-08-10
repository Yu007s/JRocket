#!/usr/bin/env bash
set -euo pipefail

GITHUB_OWNER="${GITHUB_OWNER:-yjjwnwmzzjc-commits}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
API="https://api.github.com"
OWNER_TYPE=""

if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "Please export GITHUB_TOKEN before running."
  exit 1
fi

detect_owner_type() {
  OWNER_TYPE="$(curl -fsS \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H 'Accept: application/vnd.github+json' \
    "$API/users/$GITHUB_OWNER" | jq -r '.type')"

  if [[ "$OWNER_TYPE" != "User" && "$OWNER_TYPE" != "Organization" ]]; then
    echo "Unable to determine GitHub owner type for $GITHUB_OWNER"
    exit 1
  fi
}

list_repos() {
  local page="$1"

  if [[ "$OWNER_TYPE" == "Organization" ]]; then
    curl -fsS \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H 'Accept: application/vnd.github+json' \
      "$API/orgs/$GITHUB_OWNER/repos?type=all&per_page=100&page=$page"
  else
    curl -fsS \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H 'Accept: application/vnd.github+json' \
      "$API/user/repos?affiliation=owner&visibility=all&per_page=100&page=$page"
  fi
}

detect_owner_type
echo "Deleting repositories for $GITHUB_OWNER ($OWNER_TYPE)"

page=1
while :; do
  repos="$(list_repos "$page")"

  if [[ "$OWNER_TYPE" == "Organization" ]]; then
    names="$(printf '%s' "$repos" | jq -r '.[].name')"
  else
    names="$(printf '%s' "$repos" | jq -r --arg owner "$GITHUB_OWNER" '.[] | select(.owner.login == $owner) | .name')"
  fi
  [[ -n "$names" ]] || break

  while IFS= read -r repo; do
    [[ -n "$repo" ]] || continue
    echo "Deleting $GITHUB_OWNER/$repo"
    curl -fsS -X DELETE \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H 'Accept: application/vnd.github+json' \
      "$API/repos/$GITHUB_OWNER/$repo" >/dev/null
  done <<< "$names"

  page=$((page + 1))
done

echo "Done."
