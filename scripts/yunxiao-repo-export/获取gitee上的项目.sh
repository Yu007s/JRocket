GITEE_TOKEN='992e80a25c2a7fc270ac2a02e05a0064'

SEARCH='collect'

page=1
while :; do
  repos="$(curl -fsSL "https://gitee.com/api/v5/user/repos?access_token=$GITEE_TOKEN&per_page=100&page=$page")"
  urls="$(printf '%s' "$repos" | jq -r '.[] | select(.path | test("collect"; "i")) | .html_url + ".git"')"
  [ -n "$urls" ] && printf '%s\n' "$urls"
  count="$(printf '%s' "$repos" | jq 'length')"
  [ "$count" -lt 100 ] && break
  page=$((page + 1))
done