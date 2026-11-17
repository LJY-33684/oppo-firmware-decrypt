# 第三方版权声明 / Third-Party Notices

本工具（OPPO 固件解密工具）主体以 **GNU General Public License v3.0（GPL-3.0）** 发布。
在遵循 GPL-3.0 的前提下，本工具包含以下采用 **MIT License** 或其它兼容许可的第三方开源组件。

---

## 1. OPPO / Realme / OnePlus 固件解密逻辑

本工具的 `app/core/oppo_decrypt.py` 合并、修改自以下由 **B. Kerler** 编写的 MIT 许可组件
（合并文件头已保留原版权行，并注明 Modified by）：

| 原文件 | 功能 | 版权 |
|---|---|---|
| `ofp_mtk_decrypt.py` | OPPO MTK OFP 固件解密（AES-CFB128） | Copyright (c) 2022 B. Kerler |
| `ozipdecrypt.py` | Realme / OPPO OZIP 固件解密（AES-ECB） | Copyright (c) 2017-2020 B. Kerler |
| `opscrypto.py` | OnePlus OPS 固件解包（自定义流密码） | Copyright (c) 2019-2021 B. Kerler |

来源仓库：<https://github.com/bkerler/OPPO_Decrypt_Tools>
（经 <https://github.com/ColdWindScholar/TIK> 集成，再经 mtk-garbage-porttool 合并为三合一模块）。
本工具在抽取时仅改动了包内引用、临时目录位置与文件头说明，解密算法未改动。

## 2. pyaes（纯 Python AES 实现）

- 位置：`app/core/pyaes/`
- 版本：1.6.1（未改动，随附其 `LICENSE.txt`）
- 版权：Copyright (c) 2014 Richard Moore
- 用途：未检测到 openssl 时作为 AES 解密的内置兜底后端
- 来源：<https://github.com/ricmoo/pyaes>

## 3. Brotli（`.new.dat.br` 解压组件）

- 位置：
  - Windows 二进制：`app/bin/win/x86_64/brotli.exe`（Google 官方 Windows 静态版，随包分发）
  - Linux 二进制：`app/bin/linux/x86_64/brotli`、`app/bin/linux/arm64/brotli`（官方源码构建，随包分发）
  - Python 库：`app/core/_vendor_brotli/`（官方 PyPI wheel 解包 + 自编 cp315 aarch64 wheel，Windows / Linux x86_64 覆盖
    cp312 / cp313 / cp314 / cp315；Linux ARM64 覆盖 cp312 / cp313 / cp314 / cp315，按解释器 ABI 自动匹配；
    cp315 ARM64 使用本仓库 `build_brotli_arm64_wheel.sh` 在 `ubuntu-24.04-arm` 构建的 `linux_aarch64` wheel；
    各子目录保留 wheel 原始 `dist-info` 许可文件）
- 版本：Windows / Linux CLI 二进制 1.1.0；Python 库 1.2.0
- 版权：Copyright (c) 2009, 2010, 2013-2016 by the Brotli Authors（MIT License）
- 用途：OZIP 以 img 模式输出时解压 `system/vendor` 等分区的 `.new.dat.br`（Android 9+ 固件）
- 许可原文：`app/licenses/Brotli-LICENSE.txt`（`app/core/_vendor_brotli/*/dist-info/` 内亦随附 wheel 原始许可）
- 来源：<https://github.com/google/brotli> / <https://pypi.org/project/Brotli/>

## 4. OpenSSL（AES 解密加速组件）

- Windows 位置：`app/bin/win/x86_64/`：`openssl.exe` + `libeay32.dll` + `ssleay32.dll`
- Windows 版本：1.0.2u（20 Dec 2019，Windows x64 构建）
- Linux 位置：`app/bin/linux/x86_64/openssl`、`app/bin/linux/arm64/openssl`
- Linux 版本：OpenSSL 3.5.5（27 Jan 2026；x86_64 静态单文件 / aarch64 静态库链接，均来源于官方源码）
- 版权：Copyright (c) 1998-2026 The OpenSSL Project
- 许可：Windows 1.0.2u 为 OpenSSL License + SSLeay License 双许可；
  Linux 3.5.5 为 Apache License 2.0
- 用途：OFP / OZIP AES 解密的首选加速后端；未检测到时自动回落到内置纯 Python 的 `app/core/pyaes/`
- 许可原文：
  - `app/licenses/OpenSSL-LICENSE.txt`（Windows 1.0.2u 的 OpenSSL License + SSLeay License 全文）
  - `app/licenses/OpenSSL-3-LICENSE.txt`（Linux 3.5.5 的 Apache License 2.0 全文）
- 来源：<https://www.openssl.org/source/>（Windows 构建自 Shining Light Productions，
  <https://slproweb.com/products/Win32OpenSSL.html>；Linux x86_64 / ARM64 由本项目从官方 3.5.5 源码编译）
- 注 1：上游 mtk-garbage-porttool 把 `cygwin1.dll` 也算作本组件的一部分；本工具实测
  `openssl.exe` 的 PE 导入表只依赖 `SSLEAY32.dll`、`LIBEAY32.dll`、`WS2_32.dll`、`msvcrt.dll`、
  `KERNEL32.dll`，因此只随包分发上述三个文件，不再附带 `cygwin1.dll`。
- 注 2：Windows OpenSSL 1.0.2u 许可与本项目采用的 GPL-3.0 存在历史兼容性争议（广告条款），
  本组件随包分发仅为功能加速；因存在纯 Python 兜底（pyaes），使用方若需纯 GPL 合规分发可自行删除。
- 注 3：Linux 构建只启用 AES 相关基础算法，`enc` 子命令不依赖系统 `libcrypto/libssl`；
  OpenSSL 库为静态链接，但 ARM64 可执行文件仍依赖 glibc（与 x86_64 版一致）。
- 注 4：随包 Linux OpenSSL / brotli 同时提供 x86_64 与 ARM64 构建；ARM64 版本由
  GitHub Actions `ubuntu-24.04-arm` 构建。若组件被删除或不可执行，工具才回退系统
  `openssl` / `brotli` 或 Python 库。

## 5. 窗口图标与 GitHub / Gitee 图标

- 位置：`app/icons/`：`app.ico`、`app.png`、`app_header.png`、`app_blank.ico`、`icon_github.png`、`icon_gitee.png`
- `app.ico` / `app.png`：由使用方提供的图片经圆形蒙板裁切并转换为多尺寸 ICO，
  仅作为本工具窗口图标使用
- `icon_github.png`、`icon_gitee.png`：仅作为界面底部跳转仓库入口的标识，不改变图标本身
- GitHub 徽标为 GitHub, Inc. 的商标，Gitee 徽标为 Gitee（深圳奥思网络科技有限公司）的商标；
  此处仅作入口标识，不代表任何官方背书或隶属关系

---

## The MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## GPL-3.0

本工具整体适用 GNU General Public License v3.0，完整文本见仓库根目录 `LICENSE`。
