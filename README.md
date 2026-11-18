# OPPO 固件解密工具 / OPPO Firmware Decrypt Tool

> 当前版本 / Current version：**1.0.1.003**

> **仓库地址 / Repository：**
> - **GitHub**：https://github.com/LJY-33684/oppo-firmware-decrypt
> - **Gitee 镜像**：https://gitee.com/Q3368436451/oppo-firmware-decrypt
> - **Gitee 发行版**：https://gitee.com/Q3368436451/oppo-firmware-decrypt/releases/tag/1.0.1.003

## 目录 / Table of Contents

- [项目介绍 / Introduction](#intro)
- [致谢 / Credits](#credits)
- [功能特点 / Features](#features)
- [支持格式 / Supported Formats](#formats)
- [仓库结构 / Repository Layout](#layout)
- [环境要求 / Requirements](#env)
- [图形界面 / GUI](#gui)
- [命令行 / CLI](#cli)
- [输出约定 / Output Rules](#output)
- [解密后端 / Decryption Backends](#backends)
- [单实例与界面细节 / Single Instance & UI](#singleton)
- [更新检查 / Update Check](#update)
- [发行包 / Release Package](#release)
- [已知边界 / Known Limits](#limits)
- [常见问题 / FAQ](#faq)
- [免责声明 / Disclaimer](#disclaimer)
- [版本记录 / Version History](#history)
- [联系 / Contact](#contact)

<a name="intro"></a>
## 项目介绍 / Introduction

本工具从 [mtk-garbage-porttool](https://github.com/LJY-33684/mtk-garbage-porttool-master) 的
OPPO 固件解密模块中抽出，独立成一个只做一件事的工具：**把 OPPO 系官方固件解开，
得到分区镜像或标准卡刷包**。核心解密逻辑与上游保持一致，去掉了移植工具的方案表、
移植条目与设备状态体系，保留 GUI、CLI、随包加速组件与更新检查框架。

支持 **OFP（OPPO MTK / 高通 QC）/ OZIP（Realme / OPPO）/ OPS（OnePlus）** 三种格式；
原始固件全程只读，输出目录可自定义，临时文件在输出目录内自动清理。

This tool is extracted from the OPPO firmware decryption module of
[mtk-garbage-porttool](https://github.com/LJY-33684/mtk-garbage-porttool-master).
It does one thing only: decrypt OPPO-family official firmware and produce partition
images or a standard flashable ZIP. It supports **OFP (MTK / Qualcomm QC), OZIP and
OPS**, provides both GUI and CLI, and never modifies the source firmware.

<a name="credits"></a>
## 致谢 / Credits

- 解密算法来自 [@bkerler/OPPO_Decrypt_Tools](https://github.com/bkerler/OPPO_Decrypt_Tools)
  （MIT License），其中高通 QC OFP 部分来自 `ofp_qc_decrypt.py`；
  经 [@ColdWindScholar/TIK](https://github.com/ColdWindScholar/TIK) 集成，
  再经 mtk-garbage-porttool 合并为多格式模块。
- 单实例锁、更新检查框架与底部风险提示复用了 mtk-garbage-porttool 的实现。
- 内置 OpenSSL：Windows 为 1.0.2u x64 构建（Shining Light Productions）；
  Linux x86_64 / ARM64 为 OpenSSL 3.5.5 静态构建（随包，均只用于 AES 加速）；
  缺失时自动回落到纯 Python `pyaes`。
- 内置 Brotli 二进制与 Python wheel 来自 Google Brotli 官方发布。
- GitHub / Gitee 徽标仅作为界面入口标识，商标归各自所有者。

<a name="features"></a>
## 功能特点 / Features

- **1. 多格式识别 / Multi-format detection**
  - 自动识别 `.ofp` / `.ozip` / `.ops`，无需手动选择格式
  - OFP 按文件结构区分 MTK（`MMM` + 分区表）与高通 QC（`0x7CEF` 尾页 / PK zip）
  - OZIP 支持 PK 型加密包、OPPOENCRYPT 头和明文旧包
  - OPS 解析尾部 XML 与加密分区

- **2. 两种输出形态 / Two output modes**
  - `img`：展开固件并转换成分区镜像（OFP / OZIP / OPS 通用）
  - `zip`：OZIP 重建卡刷包；高通 QC zip 型解压后重打包（加密型 QC OFP 无卡刷包形态，自动按 img 处理）

- **3. 随包组件 / Bundled backends**
  - Windows 自带 `openssl.exe`（AES 加速）与 `brotli.exe`（`.new.dat.br` 解压）
  - Linux x86_64 自带 `app/bin/linux/x86_64/openssl`（OpenSSL 3.5.5 静态 x86_64，单文件约 8.1 MB）与 `app/bin/linux/x86_64/brotli`（brotli 1.1.0，动态链接 glibc/libc/libm，需兼容 glibc）
  - Linux ARM64 自带 `app/bin/linux/arm64/openssl`（OpenSSL 3.5.5 aarch64，静态库链接，仅依赖 glibc）与 `app/bin/linux/arm64/brotli`（brotli 1.1.0 aarch64，动态链接 glibc/libc/libm）
  - openssl 缺失时自动降级 `pyaes`；brotli 缺失时回落到 vendored Python 库（Windows / Linux x86_64 覆盖 cp312–cp315，Linux ARM64 覆盖 cp312–cp315，其中 cp315 为自编 wheel）
  - Windows 通常无需额外安装依赖；Linux 双架构均自带 OpenSSL，不再要求系统 PATH 中有 `openssl`（系统命令仍作为后备）

- **4. 图形界面 / GUI**
  - 选固件 → 选输出类型 → 选输出目录 → 开始解密，四步操作
  - Per-Monitor V2 DPI 感知，125% / 150% / 200% 缩放下文字不发糊
  - 后台线程解密 + 队列刷新日志，界面不卡死
  - 完成后可自动打开输出目录

- **5. 单实例保护 / Single-instance guard**
  - 同一源码目录只允许运行一个 GUI 实例
  - 重复启动可跳转至已运行窗口，或清除残留状态锁
  - 进程被强杀留下的锁会自动识别并接管，不再误锁死

- **6. 稳定 CLI / Stable CLI**
  - `decrypt_cli.py` 面向外部 UI 壳，参数 / 日志 / 退出码契约固定
  - stdout 逐行输出，`【解密】/【警告】/【错误】/【完成】/【CLI】` 分类
  - 支持 `--log-file` 双写日志文件

- **7. 界面细节 / UI details**
  - 底部版本号旁提供 GitHub / Gitee 图标，点击用系统浏览器打开
  - 底部「更新源」下拉框支持 GitHub / Gitee 双源切换，默认 GitHub
  - 保留移植工具同款橙色刷机风险提示
  - 圆形蒙板窗口图标（多尺寸 ICO，圆外透明）

- **8. 自检 / Self-test**
  - 18 项合成样本自检：AES 双后端、brotli、sdat2img、fsutil、单实例锁、
    格式识别、OZIP / MTK OFP / 高通 QC OFP / OPS 解密、CLI 契约、更新源配置、GUI 冒烟与端到端
  - Linux 默认跳过 GUI 两项（避免远程 X 的 xcb 进程级 abort）；确认真实桌面后设 `OPPO_TEST_GUI=1` 启用
  - 无 7-Zip 时跳过“加密 QC zip 重打包”合成样本，其余核心用例仍会执行

<a name="formats"></a>
## 支持格式 / Supported Formats

| 格式 / Format | 适用设备 / Devices | 识别方式 / Detection | 输出 / Output |
|---|---|---|---|
| **OFP（MTK）** | OPPO MTK 平台 | 文件头 `MMM` + MTK 分区表 | 分区镜像（img） |
| **OFP（QC）** | OPPO / Realme 高通平台 | 尾部 `0x7CEF` 页索引，或文件头 `PK`（固定密码 zip） | 分区镜像（img）或 QC zip 解压后重打包 |
| **OZIP** | Realme / OPPO | `OPPOENCRYPT!` 头 / PK 型加密包 / 明文 ZIP | 卡刷包（zip）或分区镜像（img） |
| **OPS** | OnePlus MSM/EDL 包 | 尾部 0x200 头 + XML 索引 | 分区镜像（img） |

> 说明：MTK OFP / OPS / 加密型 QC OFP 没有“卡刷包”形态，选择 `zip` 时会提示并仍按 `img` 输出；
> 高通 QC zip 型在 `zip` 下会先解压、再重新打包为卡刷 zip。

<a name="layout"></a>
## 仓库结构 / Repository Layout

仓库根目录只放仓库级文件，源码全部在同名子目录内，与 mtk-garbage-porttool 的仓库层级一致。

```text
oppo-firmware-decrypt/
├─ README.md                 本文件（仓库说明）
├─ LICENSE                   GPL-3.0 全文
├─ .gitignore                运行产物 / 缓存忽略规则
├─ latest_version.txt        更新检查版本文件（GitHub Release 下载地址）
└─ oppo-firmware-decrypt/    源码本体（发行 zip 的根目录即此目录）
   ├─ main.py                GUI 入口
   ├─ decrypt_cli.py         CLI 入口（外部壳调用）
   ├─ run.bat                Windows 启动脚本（自动挑选带 Tcl/Tk 的 Python）
   ├─ run.sh                 Linux 启动脚本（自动检测 Python / Tk，支持 --cli）
   ├─ app/                   全部实现与随包资源（一个包收口）
   │  ├─ gui.py              轻量 Tk 界面（Per-Monitor V2 DPI 感知）
   │  ├─ singleton.py        单实例锁（跳转已运行窗口 / 清除残留锁）
   │  ├─ icons/              窗口图标 app.ico/app.png + GitHub / Gitee 图标
   │  ├─ updater.py          更新检查（GitHub / Gitee 双源，均已配置）
   │  ├─ common.py           CLI / GUI 共用逻辑
   │  ├─ version.py          版本号唯一真源
   │  ├─ core/               解密核心（MTK OFP / 高通 QC OFP / OZIP / OPS、brotli、sdat2img、pyaes）
   │  ├─ bin/win/x86_64/     Windows openssl / brotli 加速组件
   │  ├─ bin/linux/x86_64/   Linux x86_64 OpenSSL 静态版 + brotli
   │  ├─ bin/linux/arm64/    Linux ARM64 OpenSSL 静态库链接版 + brotli
   │  ├─ licenses/          OpenSSL / Brotli 许可原文
   │  ├─ tests/selftest.py   合成样本自检（18 项）
   │  └─ tools/              build_zip.py + 获取 openssl/brotli 组件脚本
   ├─ docs/                  INTERFACE.md / THIRD_PARTY_NOTICES.md / 界面截图
   ├─ README.md              使用说明、输出约定、已知边界
   └─ LICENSE                GPL-3.0 全文
```

<a name="env"></a>
## 环境要求 / Requirements

- **Windows x64**：主支持平台，Python 3.10+，需带 Tcl/Tk（官方 Python 默认包含）
- **Linux x86_64**：支持 GUI / CLI，Python 3.10+，需带 Tcl/Tk（Debian/Ubuntu 装 `python3-tk`）；AES 使用随包 `app/bin/linux/x86_64/openssl`（OpenSSL 3.5.5 静态版），brotli 使用随包 `app/bin/linux/x86_64/brotli`（动态链接，需 glibc）
- **Linux ARM64**：支持 GUI / CLI，Python 3.10+，需带 Tcl/Tk（Debian/Ubuntu 装 `python3-tk`）；AES 使用随包 `app/bin/linux/arm64/openssl`（OpenSSL 3.5.5 静态库链接），brotli 使用随包 `app/bin/linux/arm64/brotli`（动态链接 glibc/libc/libm）
- Linux 桌面用 `./run.sh`；无图形环境时用 `./run.sh --cli` 或直接调用 `decrypt_cli.py`
- 已在 Python 3.15 上完成源自检（GUI 默认跳过）；Linux Python 3.14 与 WSLg 真实显示下的 GUI 自检结果见版本记录；GitHub Actions `ubuntu-24.04-arm` 上 ARM64 核心用例通过（随包 ARM64 组件，GUI 两项跳过）
- 若默认 `python` 是精简运行时（缺 `init.tcl`），`run.bat` 会自动尝试 `py -3` 与官方 Python 3.15

<a name="gui"></a>
## 图形界面 / GUI

```bash
cd oppo-firmware-decrypt
run.bat          # Windows：或 python main.py
./run.sh         # Linux：GUI；无显示环境用 ./run.sh --cli
```

操作顺序：

1. 选择固件（`.ofp` / `.ozip` / `.ops`），界面即时显示识别格式
2. 选择输出类型：img（默认）或 zip（OZIP / 高通 QC zip 型）
3. 选择输出目录；留空则输出到固件同级 `<固件名>_decrypted/`
4. 点击「开始解密」，右侧日志实时显示进度

底部「检查更新」支持 GitHub / Gitee 双源切换（「更新源」下拉框，默认 GitHub）；
两个镜像均已创建，双源均可使用。

![主界面](oppo-firmware-decrypt/docs/gui-main.png)

<a name="cli"></a>
## 命令行 / CLI

```bash
# 默认：展开成分区镜像
python decrypt_cli.py decrypt --input RMX1901_11.A.20_OTA.ozip

# 输出解密后的卡刷包（OZIP / 高通 QC zip 型）
python decrypt_cli.py decrypt --input RMX1901_11.A.20_OTA.ozip --out-type zip

# 指定输出目录 + 落盘日志
python decrypt_cli.py decrypt --input firmware.ofp --outdir D:\out\op7 --log-file D:\out\op7.log

# 版本号
python decrypt_cli.py --version
```

退出码 / Exit codes：

| 码 | 含义 |
|---|---|
| 0 | 成功（含部分分区格式转换失败但解密本身成功） |
| 1 | 参数 / 校验错误：固件不存在、目录无法创建、未知子命令、缺参数 |
| 2 | 解密失败：格式无法识别、密钥不匹配、包结构损坏、写盘异常 |

完整参数、stdout 协议与 Java 壳示例见
[`oppo-firmware-decrypt/docs/INTERFACE.md`](oppo-firmware-decrypt/docs/INTERFACE.md)。

<a name="output"></a>
## 输出约定 / Output Rules

| 项 | 规则 |
|---|---|
| 默认输出目录 | 固件同级 `<固件名>_decrypted/`；已存在且非空时追加 `_YYYYMMDD-HHMMSS`，不覆盖旧产物 |
| 临时目录 | `<输出目录>/.oppo_decrypt_tmp/`，结束（成功或失败）自动清理 |
| 原始固件 | 只读不动，任何情况下都不修改源文件 |
| MTK OFP / OPS | 始终输出分区镜像 |
| 高通 QC OFP（加密型） | 输出分区镜像；选择 zip 时提示后仍按 img |
| 高通 QC OFP（zip 型）+ zip | 解压到临时目录，再重打包为 `<原文件名>.zip`；不保留解压目录 |
| OZIP + img | 解密 → 展开 → `*.new.dat[.br]` 转 `*.img`，中间文件转换成功后清理 |
| OZIP + zip | 只重建卡刷包，不展开、不转换 |
| 路径安全 | ZIP 条目解析到输出目录之外时跳过并告警 |

<a name="backends"></a>
## 解密后端 / Decryption Backends

| 用途 | 优先顺序 | 说明 |
|---|---|---|
| AES | Windows：`app/bin/win/x86_64/openssl.exe` → 系统 `openssl` → 内置 `pyaes`；Linux x86_64：`app/bin/linux/x86_64/openssl`（随包静态版）→ 系统 `openssl` → 内置 `pyaes`；Linux ARM64：`app/bin/linux/arm64/openssl`（随包静态库链接版）→ 系统 `openssl` → 内置 `pyaes` | openssl 快很多；Linux 双架构均优先随包组件 |
| Brotli | 自带 `brotli`（Windows / Linux x86_64 / Linux ARM64 按架构取）→ 系统 PATH `brotli` → vendored Python 库（Windows / x86_64 cp312–cp315；ARM64 cp312–cp315，cp315 为自编）→ `pip install brotli` / `brotlicffi` | `.new.dat.br` 解压；缺失时原样保留并提示 |
| sdat2img | 内置 `app/core/sdat2img.py` | `new.dat + transfer.list → img` |

<a name="singleton"></a>
## 单实例与界面细节 / Single Instance & UI

- 单实例锁文件为源码根目录 `.oppo_firmware_decrypt.lock`，只允许同一目录运行一个 GUI。
- 重复启动时弹窗提供「跳转至正在运行的程序」「清除状态锁」「好的」三个选项。
- 上次进程被强杀留下的残留锁，会检测 PID 是否存活；进程已退出则自动接管。
- 窗口图标为圆形蒙板图片生成的多尺寸 ICO（16/24/32/48/64/128/256），圆外透明。
- 底部 GitHub / Gitee 图标点击后调用系统默认浏览器；两个仓库均已创建，地址可用。
- 底部橙色提示：刷机有风险，操作前务必备份原系统，并保留原厂固件以备恢复。

<a name="update"></a>
## 更新检查 / Update Check

更新模块复用自 mtk-garbage-porttool：网络请求、`latest_version.txt` 解析、发行说明 markdown
渲染与 GUI 弹窗全部保留。当前 **`UPDATE_ENABLED = True`，GitHub 更新源已配置**：
`raw` 指向仓库 `main` 分支的 `latest_version.txt`，`api` 指向 Releases API，
`contents_api` 用于绕过 CDN 缓存；`latest_version.txt` 的 `update_url_1` 指向
GitHub `1.0.1.003` Release 资产，`update_url_2` 指向 Gitee 同版本资产。GUI 底部
「更新源」下拉框可在 GitHub / Gitee 间切换，默认 GitHub；`1.0.1.003` 已双源发布。

<a name="release"></a>
## 发行包 / Release Package

发行资产命名：`oppo-firmware-decrypt-1.0.1.003.zip`，zip 内根目录为 `oppo-firmware-decrypt/`，
解压后 Windows 可直接 `run.bat`、Linux 可直接 `./run.sh` 启动。上一版发布页：
- GitHub：[`1.0.0.009`](https://github.com/LJY-33684/oppo-firmware-decrypt/releases/tag/1.0.0.009)
- Gitee：[`1.0.0.009`](https://gitee.com/Q3368436451/oppo-firmware-decrypt/releases/tag/1.0.0.009)

打包命令：

```bash
cd oppo-firmware-decrypt
python app/tools/build_zip.py
```

打包脚本会自动排除 `__pycache__`、`*.pyc`、`out/`、`tmp/`、`.oppo_decrypt_tmp/`、
`.oppo_firmware_decrypt.lock` 与日志文件；并在打包前后执行 must 清单、关键二进制体积、
ARM64 vendor、文件数与 Linux 755 执行位断言，缺项直接中止。

<a name="limits"></a>
## 已知边界 / Known Limits

- 仓库不带真实固件样本（体积与版权原因）；发布前建议用真实 OFP / OZIP / OPS 各跑一遍。
- 合成样本只能证明算法链路，不能覆盖各家机型密钥表差异；真实 OPS 大包尚未做端到端验证。
- OFP 沿用上游实现：MTK 按「加密首块（`enclength > 0`）+ 明文余下部分」读取；
  高通 QC 按「前 0x40000 加密 + 余下明文」读取，私有打包布局可能需适配。
- 高通 QC 内置 6 组密钥，覆盖机型有限；2021 年的 `RMX1851EX_11_C.18` 实测命中第 4 组，
  不能按年份判断支持范围；未命中时会报“未命中内置密钥表”。
- QC zip 型使用固定密码 `flash@realme$50E7F7D847732396F1582CD62DD385ED7ABB0897`；
  当前仅接受带加密位的 QC zip，未加密型因暂无真实样本保持保守拒绝。
- 内置 Windows `openssl.exe` 为 1.0.2u，仅用于加速；其许可与 GPL-3.0 存在历史争议，可删除并回落到 pyaes。
- 内置 Linux x86_64 / ARM64 `openssl` 均为 OpenSSL 3.5.5 构建（Apache-2.0），许可原文见 `app/licenses/OpenSSL-3-LICENSE.txt`；ARM64 静态链接 OpenSSL 库，仅依赖 glibc。
- Windows `brotli.exe` 来自 `brotli-x64-windows-static.zip`，但 PE 导入表仍含 `VCRUNTIME140.dll` 与 Universal CRT API-set，仍需系统 VC 运行库；缺失时会回落到内置 Python 库。
- Linux x86_64 下 `app/bin/win` 不可用：AES 优先使用随包 `app/bin/linux/x86_64/openssl`（静态版），brotli 使用随包 `app/bin/linux/x86_64/brotli`（动态链接 glibc）。
- Linux ARM64 优先使用 `app/bin/linux/arm64/openssl` 与 `brotli`；未安装/被删除时才回退系统 `openssl` / `brotli` 或 Python 库。
- Linux 无图形环境时不能启动 GUI；请用 `./run.sh --cli` 或 `decrypt_cli.py`，并安装 `python3-tk` 后使用桌面。
- GUI 只暴露解密必需项，不含移植方案表、自动更新弹窗；单实例锁、仓库图标与风险提示已保留。

<a name="faq"></a>
## 常见问题 / FAQ

**Q：启动时报 `Tcl wasn't installed properly` / `Can't find a usable init.tcl`？**
A：当前 `python` 是无 Tk 数据的精简运行时。双击 `run.bat`，它会自动尝试 `py -3` 与官方 Python；
也可以手动用官方 Python 3.10+ 执行 `python main.py`。

**Q：输出目录在哪里？**
A：未指定时在固件同目录 `<固件名>_decrypted/`；目录已存在且非空会追加时间戳，不会覆盖旧结果。

**Q：为什么选择 zip 但 MTK OFP / OPS / 加密型 QC OFP 仍输出 img？**
A：这些格式是分区镜像包，没有卡刷 zip 形态；选择 zip 会提示后按 img 处理。
高通 QC zip 型例外：会先解压再重打包为卡刷 zip。

**Q：检查更新提示网络错误 / 超时？**
A：更新检查现在支持 GitHub / Gitee 双源，默认 GitHub。若网络无法访问对应站点，会提示网络错误或超时；
两个镜像均已创建，可切换另一个源重试。

**Q：重复启动提示已有实例，但我确认没开？**
A：上次进程可能被强制结束留下状态锁。点「清除状态锁」继续，或直接删除源码根目录
`.oppo_firmware_decrypt.lock`。若 PID 已退出，下一次启动也会自动接管。

<a name="disclaimer"></a>
## 免责声明 / Disclaimer

本工具仅用于个人设备恢复、固件研究与技术交流。请勿用于侵犯他人知识产权、绕过设备授权、
商业刷机服务或任何违法用途。固件与设备操作存在风险，因使用本工具导致的设备损坏、数据丢失、
保修失效等问题，开发者不承担任何责任。

This tool is intended only for personal device recovery, firmware research and technical
exchange. Do not use it to infringe intellectual property, bypass device authorization,
provide commercial flashing services, or violate any law. Firmware/device operations carry
risk; the developers assume no responsibility for damage, data loss, or warranty issues.

<a name="history"></a>
## 版本记录 / Version History

- **1.0.1.003**（QC 报错文案 / OFP 结构兜底修正）
  - QC 密钥未命中时改为明确提示“未命中内置密钥表”，不再按 2020 年份推断支持范围
  - `detect_format` 增加 OFP 结构兜底：`.ofp` 改名为 `.bin` 后仍可通过 PK 头 /
    `0x7CEF` 尾页识别为 `ofp_qc_zip` / `ofp_qc`
  - QC zip 未加密条目仍按保守策略拒绝，但错误文案明确说明暂无真实样本
- **1.0.1.001**（高通 QC OFP 分支 / Qualcomm QC OFP branch）
  - `.ofp` 不再一律按 MTK 处理：按文件结构区分 `ofp_qc_zip` / `ofp_qc` / `ofp_mtk`
  - QC zip 型：固定密码解压分区；`--out-type zip` 下解压后重新打包
  - QC 加密型：`0x200` / `0x1000` 页 + `0x7CEF` 尾页，6 组密钥派生 AES-CFB128 解密 XML
  - 分区按 XML 节点导出：前 `0x40000` 字节解密、其余明文；`Sahara` 整段解密；
    `Firmware` / `DigestsToSign` / `ChainedTableOfDigests` 直接 copy
  - 新增输出路径安全映射、md5/sha256 校验、嵌套目录创建与同名覆盖提示
  - `ChainedTableOfDigests` / `DigestsToSign` / `Firmware` 按 `SizeInByteInSrc`
    截断后再 copy，避免整扇区补齐数据写进产物
  - 已在 `RMX1851EX_11_C.18_210724` 真实 `.ofp`（9.27 GB，密钥组 #4）完成全量导出：
    58 个文件、9.72 GB，`boot.img` / `recovery.img` 为 `ANDROID!`，`system.img` /
    `vendor.img` / `userdata.img` 为 Android sparse，`xbl.elf` 为 ELF
- **1.0.0.009**（ARM64 cp315 自编 wheel）
  - 新增 `build_brotli_arm64_wheel.sh` 与 `build-brotli-arm64-wheel.yml`，在 `ubuntu-24.04-arm` 上构建 cp315 aarch64 wheel
  - `_vendor_brotli` 补入自编 `brotli-1.2.0-cp315-cp315-linux_aarch64`，ARM64 vendor 覆盖 cp312–cp315
  - `build_zip.py` 的 ARM64 vendor 断言改为逐一要求 cp312 / cp313 / cp314 / cp315
- **1.0.0.008**（OZIP 小块性能 / ARM64 vendor / 打包断言）
  - OZIP 小块 ECB 头直接走 pyaes，不再为每个 16 字节块 spawn openssl；大块仍走 openssl
  - `_vendor_brotli` 补充 cp312 / cp313 / cp314 的 `manylinux2014_aarch64` wheel；
    cp315 ARM64 暂无官方 wheel，由随包 `brotli` 命令优先兜底
  - `build_zip.py` 新增 must 清单、体积/文件数断言、ARM64 vendor 检查与 zip 执行位复核
- **1.0.0.005**（ARM64 随包组件与界面细节 / ARM64 bundled backends & UI）
  - 新增 Linux ARM64 OpenSSL 3.5.5 与 brotli 1.1.0 随包组件（`app/bin/linux/arm64/`），由 `ubuntu-24.04-arm` 构建
  - 新增 `.github/workflows/build-arm64-bins.yml`，可重复生成 ARM64 组件并核对版本、架构与 SHA256
  - ARM64 自检改为强制使用随包组件，不再依赖系统 `openssl` / `brotli`
  - GUI 左上角品牌图标改为 64×64 圆形图标，点击打开 GitHub 主页；标题栏小图标做同底色视觉隐藏
- **1.0.0.003**（Linux OpenSSL 内置 / bundled Linux OpenSSL）
  - 新增 Linux x86_64 OpenSSL 3.5.5 **静态单文件** `app/bin/linux/x86_64/openssl`，不再依赖系统 `openssl` 或 `libcrypto/libssl`
  - AES 后端顺序：随包 Linux OpenSSL → 系统 `openssl` → `pyaes`；缺失时才回退纯 Python
  - 补充 OpenSSL 3 Apache-2.0 许可与第三方声明；打包脚本继续为 Linux bin 写入 755
  - Linux GUI 自检默认跳过策略保留；可用 `OPPO_TEST_GUI=1` 在真实桌面显式启用
- **1.0.0.002**（Linux 适配 / Linux support）
  - 新增 Linux `run.sh` 启动脚本：自动选择 Python 3.10+、检测 Tk，无显示环境时引导 CLI
  - 新增 Linux x86_64 `brotli` 1.1.0（随包，动态链接 glibc/libc/libm，需兼容 glibc），覆盖 Python 3.10/3.11 等无 vendor 库的解释器
  - Linux GUI：`xdg-open` / `gio` / `kde-open` 打开输出目录，Windows 字体硬编码改为平台回退
  - 打包脚本为 `run.sh` 与 Linux `brotli` 写入 755 可执行位，解压即用
  - Linux 实测核心 13/13 通过；GUI 自检在 Linux 默认跳过（确认真实桌面后设 `OPPO_TEST_GUI=1`），`OPPO_SKIP_GUI=1` 可强制跳过
- **1.0.0.001**（首个独立版本 / initial standalone release）
  - 从 mtk-garbage-porttool 抽出 OPPO 解密模块，保留 OFP / OZIP / OPS 三格式
  - 新增独立 GUI、稳定 CLI 与 15 项合成样本自检
  - 输出目录跟随固件、临时目录收进输出目录并自动清理
  - Per-Monitor V2 DPI 修复，窗口按屏幕自适应
  - 单实例锁：跳转已运行窗口 / 清除残留锁 / 强杀残留自动接管
  - 底部 GitHub / Gitee 图标与橙色刷机风险提示
  - 圆形蒙板多尺寸窗口 ICO
  - 更新检查接入 GitHub / Gitee 双发行版，GUI 支持双源切换

<a name="contact"></a>
## 联系 / Contact

- GitHub Issues：https://github.com/LJY-33684/oppo-firmware-decrypt/issues
- 邮箱 / Email：3368436451@qq.com
- 上游工具：https://github.com/LJY-33684/mtk-garbage-porttool-master

---

如果这个工具对你有帮助，欢迎 Star / Issue 反馈。  
If this tool helps you, a Star or an issue report is welcome.
