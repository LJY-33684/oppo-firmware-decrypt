# -*- coding: utf-8 -*-
"""common.py — CLI 与 GUI 共用的小工具（默认输出目录、格式显示名）"""
import os
import time
from pathlib import Path

# 固件格式 → 界面显示名
FORMAT_LABELS = {
    'ofp_mtk': 'OFP（MTK）',
    'ozip': 'OZIP（Realme / OPPO）',
    'ops': 'OPS（OnePlus）',
}


def default_outdir(fw):
    """默认输出目录：与固件同级的 <固件名>_decrypted/

    该目录已存在且非空时，追加时间戳后缀，避免覆盖上一次的产物。
    """
    p = Path(os.path.abspath(fw))
    base = p.parent / f"{p.stem}_decrypted"
    if base.exists():
        try:
            non_empty = any(base.iterdir())
        except OSError:
            non_empty = True
        if non_empty:
            base = p.parent / f"{p.stem}_decrypted_{time.strftime('%Y%m%d-%H%M%S')}"
    return str(base)


def human_size(num):
    """字节数 → 人类可读（用于日志提示）"""
    num = float(num)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if num < 1024 or unit == 'TB':
            return f"{num:.1f} {unit}" if unit != 'B' else f"{int(num)} B"
        num /= 1024
