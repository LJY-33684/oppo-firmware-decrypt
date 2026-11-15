# -*- coding: utf-8 -*-
"""core — OPPO / Realme / OnePlus 固件解密核心包。

模块：
  oppo_decrypt.py  解密统一入口（OFP / OZIP / OPS）
  fsutil.py        文件系统小工具（_clear_attrs / _rmtree）
  brotli.py        new.dat.br 解压（多后端探测）
  sdat2img.py      new.dat + transfer.list → 分区 img
  pyaes/           纯 Python AES 兜底后端
  _vendor_brotli/  内置 brotli Python 库（按解释器 ABI 自动匹配）
"""
