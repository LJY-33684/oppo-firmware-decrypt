#!/usr/bin/env bash
# 构建 Linux ARM64 随包组件：静态 OpenSSL 3.5.5 + brotli 1.1.0。
# 必须在 aarch64 Linux 上运行；Windows / x86_64 上仅用于交叉检查会直接失败。
# 用法：bash app/tools/build_linux_arm64_bins.sh [输出目录]
# 默认输出：app/bin/linux/arm64
set -euo pipefail

OPENSSL_VERSION="${OPENSSL_VERSION:-3.5.5}"
BROTLI_VERSION="${BROTLI_VERSION:-1.1.0}"
OPENSSL_URL="${OPENSSL_URL:-https://github.com/openssl/openssl/releases/download/openssl-${OPENSSL_VERSION}/openssl-${OPENSSL_VERSION}.tar.gz}"
BROTLI_URL="${BROTLI_URL:-https://github.com/google/brotli/archive/refs/tags/v${BROTLI_VERSION}.tar.gz}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "aarch64" ]]; then
  echo "[错误] 本脚本只能在 Linux ARM64（aarch64）上构建，当前：$(uname -s) $(uname -m)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${1:-$SCRIPT_DIR/../bin/linux/arm64}"
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

for cmd in curl tar make perl gcc strip cmake sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "[错误] 缺少构建命令：$cmd" >&2
    exit 1
  }
done

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "[1/4] 下载 OpenSSL ${OPENSSL_VERSION}"
curl -fL --retry 3 --retry-delay 5 -o "$WORK/openssl.tar.gz" "$OPENSSL_URL"
echo "[2/4] 编译 OpenSSL（no-shared, no-tests, 静态单文件）"
tar -xzf "$WORK/openssl.tar.gz" -C "$WORK"
openssl_src="$WORK/openssl-${OPENSSL_VERSION}"
(
  cd "$openssl_src"
  ./Configure linux-aarch64 no-shared no-tests \
    --prefix="$WORK/openssl-install" --openssldir="$WORK/openssl-install/ssl"
  make -j"$(nproc)" build_sw
)

echo "[3/4] 下载并编译 brotli ${BROTLI_VERSION}"
curl -fL --retry 3 --retry-delay 5 -o "$WORK/brotli.tar.gz" "$BROTLI_URL"
tar -xzf "$WORK/brotli.tar.gz" -C "$WORK"
brotli_src="$WORK/brotli-${BROTLI_VERSION}"
cmake -S "$brotli_src" -B "$WORK/brotli-build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DBROTLI_DISABLE_TESTS=ON
cmake --build "$WORK/brotli-build" --target brotli -j"$(nproc)"
brotli_bin="$WORK/brotli-build/brotli"
if [[ ! -x "$brotli_bin" ]]; then
  echo "[错误] 未找到 CMake 生成的 brotli 可执行文件：$brotli_bin" >&2
  find "$WORK/brotli-build" -maxdepth 3 -name 'brotli*' -ls >&2 || true
  exit 1
fi

echo "[4/4] 安装到 $OUT_DIR"
install -m 0755 "$openssl_src/apps/openssl" "$OUT_DIR/openssl"
install -m 0755 "$brotli_bin" "$OUT_DIR/brotli"
strip --strip-all "$OUT_DIR/openssl" "$OUT_DIR/brotli"

file "$OUT_DIR/openssl" "$OUT_DIR/brotli"
if ! file "$OUT_DIR/openssl" | grep -q 'aarch64'; then
  echo "[错误] openssl 不是 aarch64 可执行文件" >&2
  exit 1
fi
if ! file "$OUT_DIR/brotli" | grep -q 'aarch64'; then
  echo "[错误] brotli 不是 aarch64 可执行文件" >&2
  exit 1
fi
if ldd "$OUT_DIR/openssl" 2>&1 | grep -qE 'libcrypto|libssl'; then
  echo "[错误] openssl 仍动态依赖 OpenSSL 库，不是静态构建" >&2
  exit 1
fi
"$OUT_DIR/openssl" version
"$OUT_DIR/brotli" --version
sha256sum "$OUT_DIR/openssl" "$OUT_DIR/brotli"
echo "[完成] ARM64 组件已生成"
