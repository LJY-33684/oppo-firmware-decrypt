#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPPO / Realme / OnePlus 固件解密工具 —— 命令行入口 (CLI Bridge)

给其它平台（Java / C / C++ / Rust ...）的 UI 壳调用用的纯命令行接口：
参数传入（固件路径、输出类型、输出目录），日志/结果经 stdout 传出
（可选 --log-file 同时落盘）。壳只需要启动本进程、喂参数、读输出。

接口规范详见 docs/INTERFACE.md。

子命令：
  decrypt       固件解密（OFP / OZIP / OPS；img 展开转镜像 / zip 直出卡刷包）

顶层查询：
  --version     输出版本号

退出码：
  0 = 成功
  1 = 参数/校验错误（用法错误、文件缺失、非法组合）
  2 = 解密失败（流程跑完但出错）
"""
import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.version import __version__       # noqa: E402
from app.common import default_outdir     # noqa: E402


# ============================================================
# 日志接口：stdout + 可选文件 双写（Tee），供 decrypt() 的 log 参数使用
# 约定：所有日志行带【】前缀标记，与 GUI 日志完全一致；
#       print(..., file=log) 接口即 stdlog 协议（需 write/flush）
# ============================================================
class TeeLog:
    """同时写 stdout 与（可选）日志文件。"""

    def __init__(self, logfile=None):
        self.logfile = None
        if logfile:
            try:
                self.logfile = open(logfile, 'w', encoding='utf-8')
            except OSError as e:
                sys.stdout.write(
                    f"【参数错误】日志文件无法写入：{logfile}（{e}），本次仅输出到 stdout\n")
                sys.stdout.flush()
                self.logfile = None

    def write(self, s):
        sys.stdout.write(s)
        if self.logfile:
            self.logfile.write(s)

    def flush(self):
        sys.stdout.flush()
        if self.logfile:
            self.logfile.flush()

    def close(self):
        if self.logfile:
            self.logfile.flush()
            self.logfile.close()
            self.logfile = None


# ============================================================
# decrypt 子命令：OPPO/Realme/OnePlus 固件解密（OFP/OZIP/OPS）
# ============================================================
def cmd_decrypt(a, log):
    from app.core import oppo_decrypt

    fw = a.input
    if not fw or not os.path.isfile(fw):
        print(f"【参数错误】固件不存在：{fw}", file=log)
        return 1

    outdir = a.outdir or default_outdir(fw)
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError as e:
        print(f"【参数错误】输出目录无法创建：{outdir}（{e}）", file=log)
        return 1

    print(file=log)
    print("=" * 60, file=log)
    ok = oppo_decrypt.decrypt(fw, outdir, log, out_type=getattr(a, 'out_type', 'img'))
    print(f"【CLI】输出目录：{outdir}", file=log)
    return 0 if ok else 2


# ============================================================
# 参数解析
# ============================================================
def build_parser():
    p = argparse.ArgumentParser(
        prog='decrypt_cli.py',
        description='OPPO / Realme / OnePlus 固件解密工具（命令行）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='退出码：0 成功 / 1 参数错误 / 2 解密失败')
    p.add_argument('--version', action='store_true', help='输出版本号后退出')

    sub = p.add_subparsers(dest='cmd')

    # decrypt
    sd = sub.add_parser('decrypt', help='OPPO/Realme/OnePlus 固件解密（OFP/OZIP/OPS）')
    sd.add_argument('--input', required=True, help='固件路径（.ofp/.ozip/.ops）')
    sd.add_argument('--outdir', default='',
                    help='输出目录（默认：固件同目录 <固件名>_decrypted/）')
    sd.add_argument('--out-type', choices=['img', 'zip'], default='img',
                    help='输出类型：img（默认，展开并转换成分区镜像）'
                         '| zip（OZIP 直接输出解密后的卡刷包，不展开）')
    sd.add_argument('--log-file', default='', help='额外日志文件（stdout 照常输出）')
    return p


def main(argv=None):
    p = build_parser()
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        # argparse 内建错误（未知子命令/缺参数）默认退出码 2，统一为 1=参数错误
        if e.code == 2:
            return 1
        raise

    if a.version:
        print(__version__)
        return 0

    if a.cmd is None:
        p.print_help()
        return 1

    log = TeeLog(getattr(a, 'log_file', ''))
    try:
        if a.cmd == 'decrypt':
            rc = cmd_decrypt(a, log)
        else:
            rc = 1
    finally:
        log.close()
    return rc


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
