#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_zip.py — 生成发行用 zip（放在仓库上一级，arcname 根为源码目录名）

用法：python app/tools/build_zip.py
输出：<仓库上一级>/oppo-firmware-decrypt-<版本>.zip

排除：__pycache__、*.pyc/*.pyo、.git、dist、out、tmp、.oppo_decrypt_tmp、*.log
"""
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # app/tools → app → 源码根
sys.path.insert(0, str(ROOT))
from app.version import __version__  # noqa: E402

EXCLUDE_DIRS = {'__pycache__', '.git', 'dist', 'out', 'tmp', '.oppo_decrypt_tmp',
                '.idea', '.vscode', '.venv', 'venv'}
EXCLUDE_FILES = {'.oppo_firmware_decrypt.lock'}
EXCLUDE_SUFFIX = ('.pyc', '.pyo', '.log')
ARC_ROOT = ROOT.name

# 发行包 must 清单：缺一项就中止打包，避免“文件数对但关键件缺失”。
MUST_FILES = [
    'run.bat', 'run.sh', 'main.py', 'decrypt_cli.py',
    'README.md', 'LICENSE', 'docs/INTERFACE.md',
    'app/version.py', 'app/gui.py', 'app/core/oppo_decrypt.py',
    'app/core/brotli.py', 'app/core/_vendor_brotli',
    'app/icons/app.ico', 'app/icons/app.png', 'app/icons/app_header.png',
    'app/bin/win/x86_64/openssl.exe', 'app/bin/win/x86_64/brotli.exe',
    'app/bin/win/x86_64/libeay32.dll', 'app/bin/win/x86_64/ssleay32.dll',
    'app/bin/linux/x86_64/openssl', 'app/bin/linux/x86_64/brotli',
    'app/bin/linux/arm64/openssl', 'app/bin/linux/arm64/brotli',
]
MUST_MIN_BYTES = {
    'app/bin/win/x86_64/openssl.exe': 400 * 1024,
    'app/bin/win/x86_64/brotli.exe': 400 * 1024,
    'app/bin/win/x86_64/libeay32.dll': 1024 * 1024,
    'app/bin/win/x86_64/ssleay32.dll': 300 * 1024,
    'app/bin/linux/x86_64/openssl': 5 * 1024 * 1024,
    'app/bin/linux/x86_64/brotli': 500 * 1024,
    'app/bin/linux/arm64/openssl': 5 * 1024 * 1024,
    'app/bin/linux/arm64/brotli': 500 * 1024,
}
MIN_FILES = 100
MIN_ZIP_BYTES = 15 * 1024 * 1024


def fail(msg):
    raise SystemExit(f'【打包预检失败】{msg}')


def preflight():
    """打包前检查版本号、must 清单、ARM64 vendor 与关键二进制体积。"""
    for rel in MUST_FILES:
        p = ROOT / rel
        if not p.exists():
            fail(f'缺少 must 文件：{rel}')
    for rel, min_size in MUST_MIN_BYTES.items():
        size = (ROOT / rel).stat().st_size
        if size < min_size:
            fail(f'{rel} 体积异常：{size} bytes < {min_size} bytes')
    version_text = (ROOT / 'app/version.py').read_text(encoding='utf-8')
    if f'__version__ = {__version__!r}' not in version_text:
        fail(f'app/version.py 与导入版本不一致：{__version__}')
    # ARM64 vendor 兜底：至少要有 cp312/313/314 的 aarch64 wheel 解包目录。
    vendor = ROOT / 'app/core/_vendor_brotli'
    arm_dirs = [p for p in vendor.iterdir() if p.is_dir() and 'aarch64' in p.name]
    if not any((p / 'brotli.py').exists() and any(p.glob('_brotli*.so')) for p in arm_dirs):
        fail('app/core/_vendor_brotli 缺少 aarch64 wheel 解包目录')
    print(f'预检通过：{len(MUST_FILES)} 项 must 清单，版本 {__version__}')


def iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIX):
                continue
            p = Path(dirpath) / name
            yield p, p.relative_to(ROOT)


def verify_zip(out):
    """打包后再按 zip 内容核对，防止遍历过程中漏文件或丢执行位。"""
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        for rel in MUST_FILES:
            arc = f'{ARC_ROOT}/{rel}'
            if (ROOT / rel).is_dir():
                if not any(n.startswith(arc + '/') for n in names):
                    fail(f'zip 内缺少 must 目录：{rel}')
            elif arc not in names:
                fail(f'zip 内缺少 must 文件：{rel}')
        for rel in ('app/bin/linux/x86_64/openssl', 'app/bin/linux/x86_64/brotli',
                    'app/bin/linux/arm64/openssl', 'app/bin/linux/arm64/brotli',
                    'run.sh'):
            info = z.getinfo(f'{ARC_ROOT}/{rel}')
            if (info.external_attr >> 16) & 0o777 != 0o755:
                fail(f'{rel} 未写入 755 可执行位')
        if len(names) < MIN_FILES:
            fail(f'zip 文件数 {len(names)} < {MIN_FILES}')
    size = out.stat().st_size
    if size < MIN_ZIP_BYTES:
        fail(f'zip 体积 {size} bytes < {MIN_ZIP_BYTES} bytes')


def main():
    preflight()
    # 仓库采用「根目录 4 文件 + 同名源码子目录」结构：
    #   <repo>/oppo-firmware-decrypt/tools/build_zip.py
    # 发行 zip 放到仓库上一级目录（与 MTK 发行包惯例一致）。
    repo_dir = ROOT.parent
    out_dir = repo_dir.parent if repo_dir.name == ROOT.name else repo_dir
    out = out_dir / f'{ROOT.name}-{__version__}.zip'
    if out.exists():
        out.unlink()
    count = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path, rel in iter_files():
            arcname = f'{ARC_ROOT}/{rel.as_posix()}'
            info = zipfile.ZipInfo.from_file(path, arcname)
            data = path.read_bytes()
            # Windows 上创建的 zip 不会自动保留 Linux 可执行位；显式写入 755，
            # 并把创建者标记为 Unix，Linux 的 unzip 才会恢复权限。
            if rel.as_posix() == 'run.sh' or rel.as_posix().startswith('app/bin/linux/'):
                info.create_system = 3
                info.external_attr = (0o100755 << 16) | (info.external_attr & 0xFFFF)
            # Windows 检出可能把 run.sh 转成 CRLF；打包时统一回 LF，避免 bad interpreter。
            if rel.as_posix().endswith('.sh'):
                data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED,
                       compresslevel=6)
            count += 1
    verify_zip(out)
    size = out.stat().st_size
    print(f'已生成：{out}')
    print(f'文件数：{count}，体积：{size / 1048576:.2f} MB')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
