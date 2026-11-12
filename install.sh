#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if (( EUID != 0 )); then
    printf '请使用 sudo bash %q 安装到 /usr/local/bin。\n' "${BASH_SOURCE[0]}" >&2
    exit 1
fi
install -d -m 0755 /usr/local/bin
install -m 0755 -- "$script_dir/check" /usr/local/bin/check
printf '已安装到 /usr/local/bin/check。运行 check 或 check <主机别名>。\n'
