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


def iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIX):
                continue
            p = Path(dirpath) / name
            yield p, p.relative_to(ROOT)


def main():
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
            # Windows 上创建的 zip 不会自动保留 Linux 可执行位；显式写入 755，
            # 保证解压后 run.sh / app/bin/linux/x86_64/brotli 可直接执行。
            if rel.as_posix() == 'run.sh' or rel.as_posix().startswith('app/bin/linux/'):
                info.external_attr = (0o100755 << 16) | (info.external_attr & 0xFFFF)
            z.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                       compresslevel=6)
            count += 1
    size = out.stat().st_size
    print(f'已生成：{out}')
    print(f'文件数：{count}，体积：{size / 1048576:.2f} MB')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
