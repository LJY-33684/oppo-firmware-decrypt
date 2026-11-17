#!/usr/bin/env bash
# 构建 ARM64 Brotli Python wheel（用于 _vendor_brotli 的 cp315 补位）。
# 用法：bash app/tools/build_brotli_arm64_wheel.sh <输出目录>
# 需在 aarch64 Linux 上运行，Python 版本决定 wheel 的 cpXXX tag。
set -euo pipefail

OUT="${1:-dist}"
PY="${PYTHON:-python3}"

rm -rf "$OUT"
mkdir -p "$OUT"

"$PY" -m pip install --upgrade pip setuptools wheel
"$PY" -m pip wheel --no-deps --no-binary=:all: 'Brotli==1.2.0' -w "$OUT"

"$PY" - "$OUT" <<'PY'
import glob
import sys
import zipfile

out = sys.argv[1]
wheels = glob.glob(out + '/*.whl')
if len(wheels) != 1:
    raise SystemExit(f'期望生成 1 个 wheel，实际 {len(wheels)} 个：{wheels}')
wheel = wheels[0]
name = wheel.rsplit('/', 1)[-1]
if 'cp315' not in name or 'aarch64' not in name:
    raise SystemExit(f'wheel 不是 cp315/aarch64：{name}')
with zipfile.ZipFile(wheel) as z:
    members = z.namelist()
    if not any(m.endswith('.so') and 'aarch64' in m for m in members):
        raise SystemExit(f'wheel 内缺少 aarch64 扩展：{members}')
print(f'OK: {name}')
PY
