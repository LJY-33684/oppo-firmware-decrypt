# -*- coding: utf-8 -*-
"""main.py — GUI 启动入口（双击 run.bat 或 python main.py）

命令行用法请走 decrypt_cli.py（接口见 docs/INTERFACE.md）。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if __name__ == '__main__':
    from app.gui import main
    main()
