# CLI 接口契约（decrypt_cli.py）

面向外部 UI 壳（Java / C# / C++ / Rust / Python…）的稳定接口。壳只需启动进程、喂参数、读 stdout。
GUI 与 CLI 走同一个核心入口 `app.core.oppo_decrypt.decrypt()`，行为一致。

## 1. 调用方式

```text
python decrypt_cli.py decrypt --input <固件> [--outdir <目录>] [--out-type img|zip] [--log-file <文件>]
python decrypt_cli.py --version
python decrypt_cli.py -h | --help
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `--input` | 是 | 固件路径，`.ofp` / `.ozip` / `.ops`；不存在返回退出码 1 |
| `--outdir` | 否 | 输出目录。缺省为固件同目录 `<固件名>_decrypted/`；若该目录已存在且非空，自动追加 `_YYYYMMDD-HHMMSS` |
| `--out-type` | 否 | `img`（默认）展开并转换分区镜像；`zip` 输出解密后的卡刷包（OZIP 重建；高通 QC zip 型解压后重打包；其余 OFP / OPS 会提示后仍按 img 输出） |
| `--log-file` | 否 | 额外日志文件（UTF-8），stdout 照常输出 |
| `--version` | 否 | 打印版本号（如 `1.0.1.001`）后退出 0 |

## 2. 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功（含「部分分区格式转换失败但解密本身成功」的情况，日志会提示） |
| 1 | 参数 / 校验错误：固件不存在、输出目录无法创建、未知子命令、缺参数 |
| 2 | 解密失败：格式无法识别、密钥不匹配、包结构损坏、写盘异常等 |

## 3. stdout 协议

- 全部日志走 stdout，`print(msg, file=log)` 风格，逐行输出；不写 stderr（除非 Python 解释器自身报错）。
- 日志行以 `【】` 前缀分类，便于壳做进度/告警着色：

| 前缀 | 含义 |
|---|---|
| `【解密】` | 开始信息：固件路径、识别格式、AES 后端、输出类型 |
| `【解压】` / `【格式转换】` / `【清理】` | img 模式的分步进度 |
| `【提示】` | 非致命说明（如明文 OZIP、降级 pyaes、部分分区未转换） |
| `【警告】` | 可继续的异常（如 OPS 分区 SHA256 校验不一致） |
| `【错误】` | 失败原因；出现即代表本次退出码为 2 |
| `【完成】` | 成功收尾，附输出目录 |
| `【CLI】` | 壳可解析的最终输出目录一行 |

- 无进度百分比，壳可按行追加显示，或用「最近一行」做状态文本。

## 4. 输出约定

- 原始固件只读，不会被修改、移动或删除。
- 临时目录固定为 `<outdir>/.oppo_decrypt_tmp/`，结束时自动删除；异常中断时下次运行会先清理。
- `img` 模式：MTK OFP / 高通 QC OFP / OPS 直接写分区镜像；OZIP 先解密重建 zip，再展开并把 `*.new.dat[.br]` 转成 `*.img`，
  转换成功后删除中间文件；若 brotli / sdat2img 不可用，`.new.dat[.br]` 原样保留并提示。
- `zip` 模式：OZIP 输出 `<固件名>.zip`；高通 QC zip 型解压后重打包为 `<固件名>.zip`；
  MTK OFP / OPS / 加密型 QC OFP 无此形态，按 img 处理。
- 路径穿越防护：ZIP 内条目若解析到输出目录之外会被跳过并告警。

## 5. 外部壳集成示例（Java 片段）

```java
ProcessBuilder pb = new ProcessBuilder(
        "python", "decrypt_cli.py", "decrypt",
        "--input", fwPath,
        "--out-type", useZip ? "zip" : "img",
        "--outdir", outDir);
pb.redirectErrorStream(true);
Process p = pb.start();
try (BufferedReader r = new BufferedReader(
        new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
    String line;
    while ((line = r.readLine()) != null) {
        ui.appendLog(line);
        if (line.startsWith("【CLI】")) ui.setOutDir(line.substring(5).trim());
    }
}
int code = p.waitFor();   // 0/1/2 按上表判断
```

注意：Windows 下若壳自身是 UTF-8 环境，请给 Python 进程设置 `PYTHONIOENCODING=utf-8`，
或直接使用 `pythonw`/打包后的可执行文件；CLI 已在入口处 `reconfigure(encoding='utf-8')`。

## 6. 版本与稳定性

- 版本号唯一真源为 `app/version.py`，`--version` 与 GUI 标题一致。
- 本接口为对外契约：新增功能优先以可选参数加入，不改变既有参数名、语义与退出码含义。
- 更新检查不在 CLI 契约内（GUI 专用；GitHub / Gitee 双源，两个仓库与发行版均已创建）。
