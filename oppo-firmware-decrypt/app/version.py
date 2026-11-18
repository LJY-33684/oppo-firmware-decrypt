# -*- coding: utf-8 -*-
"""version.py — 工具版本号（唯一真源，CLI/GUI/更新检查统一读取）

版本规则沿用 mtk-garbage-porttool：x.y.z.ppp
  x.y.z = 主版本（大版本 / 常规 / 小版本）
  ppp   = 三位数补丁号，修补 N 个模块则升 N
首版：1.0.0.001
Linux 适配：1.0.0.002
Linux OpenSSL 内置：1.0.0.005
OZIP 小块性能 / ARM64 vendor / 打包断言：1.0.0.008
ARM64 cp315 自编 wheel：1.0.0.009
高通 QC OFP 分支：1.0.1.001
密钥表报错文案 / OFP 结构兜底：1.0.1.003
"""
__version__ = '1.0.1.003'
