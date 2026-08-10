#!/usr/bin/env bash
set -u

# Connection settings. Fill these values before running.
MYSQL_HOST="192.168.0.138"
MYSQL_PORT="3306"
MYSQL_USER="root"
MYSQL_PASSWORD="ZN838ft6iqs3a68R748WnfMQKbHGiU"

MYSQL_BIN="/usr/local/mysql-8.0.29-macos12-arm64/bin"
MYSQLDUMP="$MYSQL_BIN/mysqldump"
OUTPUT_DIR="${OUTPUT_DIR:-/Users/devjys/Documents/雄伟科技/离职时中石油数据备份/$(date +%Y%m%d_%H%M%S)}"
WORKERS=20

DATABASES=(
  "antiantis-medical"
  "atlantis-cloud"
  "atlantis-cloud-devops"
  "atlantis-cloud-navi"
  "chaos-face"
  "chaos-upms"
  "default_db"
  "food_safe"
  "information-publish"
  "information_schema"
  "mysql"
  "navi"
  "performance_schema"
  "platform"
  "report"
  "restaurant-base-core"
  "restaurant-policy-custom"
  "restaurant_order"
  "shopdish"
  "single-inventory-manage"
  "sovell-autotest"
  "sovell_demeter_docking"
  "super_market"
  "super_market2"
  "sys"
)

if [[ "${1:-}" == "--dump-one" ]]; then
  database="$2"
  output_file="$OUTPUT_DIR/${database}.sql"
  temp_file="$output_file.tmp"
  log_file="$OUTPUT_DIR/${database}.log"

  # These schemas are virtual and do not contain restorable user data.
  if [[ "$database" == "information_schema" || "$database" == "performance_schema" ]]; then
    printf 'SKIPPED: virtual MySQL schema; no full dump is available.\n' > "$log_file"
    printf '[SKIP] %s (virtual schema)\n' "$database"
    exit 0
  fi

  rm -f "$temp_file"
  if MYSQL_PWD="$MYSQL_PASSWORD" "$MYSQLDUMP" \
      --host="$MYSQL_HOST" \
      --port="$MYSQL_PORT" \
      --user="$MYSQL_USER" \
      --single-transaction \
      --quick \
      --routines \
      --events \
      --triggers \
      --hex-blob \
      --set-gtid-purged=OFF \
      --column-statistics=0 \
      --databases "$database" > "$temp_file" 2> "$log_file"; then
    mv "$temp_file" "$output_file"
    printf '[OK] %s -> %s\n' "$database" "$output_file"
    exit 0
  fi

  rm -f "$temp_file"
  printf '[FAILED] %s (see %s)\n' "$database" "$log_file" >&2
  exit 1
fi

if [[ ! -x "$MYSQLDUMP" ]]; then
  echo "mysqldump not found or not executable: $MYSQLDUMP" >&2
  exit 1
fi
if [[ "$WORKERS" -lt 1 ]]; then
  echo "WORKERS must be at least 1" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

if [[ -z "$MYSQL_PASSWORD" ]]; then
  read -r -s -p "MySQL password for ${MYSQL_USER}: " MYSQL_PASSWORD
  printf '\n'
fi

export MYSQL_HOST MYSQL_PORT MYSQL_USER MYSQL_PASSWORD MYSQL_BIN MYSQLDUMP OUTPUT_DIR

printf 'MySQL export started. Output: %s\n' "$OUTPUT_DIR"
printf 'Concurrency: %s\n' "$WORKERS"

printf '%s\n' "${DATABASES[@]}" |
  xargs -P "$WORKERS" -I {} bash "$0" --dump-one "{}"
xargs_status=$?

if [[ "$xargs_status" -eq 0 ]]; then
  printf 'All export tasks completed.\n'
else
  printf 'Some export tasks failed. Check *.log under: %s\n' "$OUTPUT_DIR" >&2
  exit 1
fi
