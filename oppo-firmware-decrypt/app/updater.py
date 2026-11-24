# -*- coding: utf-8 -*-
"""updater.py — 更新检查 / 下载 / 自更新模块

移植自 mtk-garbage-porttool 的 porttool/update.py，并按独立工具裁剪：
  1. GitHub / Gitee 双更新源，latest_version.txt 带 update_sha256 时强制校验；
  2. 下载只接受 http/https，限制 300 MiB，边下边算 SHA256；
  3. stage_update() 拒绝绝对路径、.. 穿越和错误顶层目录；
  4. 自更新前备份程序目录，但跳过 out/ 等运行时产物；覆盖失败只回滚代码，
     不删除用户输出；
  5. 去掉了模块级 tkinter 依赖，CLI 在无 tkinter 环境也能 import。
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

# tkinter.END 的等价常量（避免模块级依赖 tkinter）
END = 'end'
if sys.platform == 'win32':
    _UI_FAMILY, _MONO_FAMILY = 'Microsoft YaHei', 'Consolas'
elif sys.platform == 'darwin':
    _UI_FAMILY, _MONO_FAMILY = 'PingFang SC', 'Menlo'
else:
    _UI_FAMILY, _MONO_FAMILY = 'Noto Sans CJK SC', 'DejaVu Sans Mono'

# 更新检查总开关：GitHub / Gitee 地址均已配置；两个仓库与发行版均已创建
UPDATE_ENABLED = True

# ============================================================
# 更新源配置（GitHub / Gitee 均已启用）
#   raw           latest_version.txt 的原始文件地址
#   api           发行版 API 模板（{tag} 会被替换为版本号）
#   contents_api  GitHub contents API（可选，绕过 CDN 缓存）
#   url_key       latest_version.txt 中对应的下载地址键名
# ============================================================
UPDATE_SOURCES = {
    'GitHub': {
        'raw': 'https://raw.githubusercontent.com/LJY-33684/oppo-firmware-decrypt/main/latest_version.txt',
        'api': 'https://api.github.com/repos/LJY-33684/oppo-firmware-decrypt/releases/tags/{tag}',
        'contents_api': 'https://api.github.com/repos/LJY-33684/oppo-firmware-decrypt/contents/latest_version.txt?ref=main',
        'url_key': 'update_url_1',
    },
    'Gitee': {
        'raw': 'https://gitee.com/Q3368436451/oppo-firmware-decrypt/raw/main/latest_version.txt',
        'api': 'https://gitee.com/api/v5/repos/Q3368436451/oppo-firmware-decrypt/releases/tags/{tag}',
        'url_key': 'update_url_2',
    },
}
DEFAULT_SOURCE = 'GitHub'
UPDATE_TIMEOUT = 30  # 秒
UPDATE_MAX_BYTES = 300 * 1024 * 1024
_UA = 'OPPO-Firmware-Decrypt'


def parse_version(value):
    """把 1.0.1.006 / v1.0-beta6p1 等版本串转成可比较的数字元组。"""
    if not value:
        return ()
    return tuple(int(x) for x in re.findall(r'\d+', str(value)))


def compare_versions(left, right):
    """返回 -1 / 0 / 1；缺位按 0 补齐，无法解析时返回 None。"""
    a, b = parse_version(left), parse_version(right)
    if not a or not b:
        return None
    width = max(len(a), len(b))
    a = a + (0,) * (width - len(a))
    b = b + (0,) * (width - len(b))
    return (a > b) - (a < b)


def version_status(remote, local):
    """返回 newer / same / older / unknown。"""
    cmp_result = compare_versions(remote, local)
    if cmp_result is None:
        return 'unknown'
    return {1: 'newer', 0: 'same', -1: 'older'}[cmp_result]


class UpdateResult:
    """更新检查结果对象（线程安全，只读数据）"""
    __slots__ = ('ok', 'tag', 'body', 'download_url', 'sha256', 'reason')

    def __init__(self, ok=False, tag=None, body='', download_url=None, sha256=None, reason=''):
        self.ok = ok
        self.tag = tag
        self.body = body
        self.download_url = download_url
        self.sha256 = sha256
        self.reason = reason


def is_configured(source=DEFAULT_SOURCE):
    """更新源是否已配置（地址留空视为未配置）。"""
    cfg = UPDATE_SOURCES.get(source) or {}
    return bool(UPDATE_ENABLED and cfg.get('raw') and cfg.get('api'))


def fetch_update_info(source=DEFAULT_SOURCE, timeout=UPDATE_TIMEOUT):
    """线程安全：请求对应源 latest_version.txt + 更新内容（markdown）。

    返回 UpdateResult：
      ok=True  时 tag/body/download_url/sha256 有效
      ok=False 时 reason 为失败原因
    """
    src_cfg = UPDATE_SOURCES.get(source, UPDATE_SOURCES[DEFAULT_SOURCE])
    result = UpdateResult()
    if not is_configured(source):
        result.reason = '更新源尚未配置（仓库创建后填入更新地址即可启用）'
        return result
    try:
        # 1. 请求对应源的 latest_version.txt
        # GitHub 优先用 contents API（无 CDN 缓存，修改后立即可见），失败降级 raw
        raw = None
        if source == 'GitHub' and src_cfg.get('contents_api'):
            try:
                req_c = urllib.request.Request(
                    src_cfg['contents_api'],
                    headers={'User-Agent': _UA, 'Accept': 'application/vnd.github+json'})
                with urllib.request.urlopen(req_c, timeout=timeout) as resp_c:
                    file_data = json.loads(resp_c.read().decode('utf-8'))
                    raw = base64.b64decode(file_data['content']).decode('utf-8-sig')
            except Exception:
                raw = None
        if raw is None:
            req = urllib.request.Request(src_cfg['raw'], headers={'User-Agent': _UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8-sig')

        # 2. 解析 latest_version.txt（有/无引号、update_url/update_url_1/update_url_2）
        tag = None
        sha256 = None
        all_urls = {}
        for line in raw.splitlines():
            line = line.strip()
            m = re.match(r'latest_version\s*=\s*(.+?)\s*$', line)
            if m:
                tag = m.group(1).strip().strip('"').strip("'")
            m = re.match(r'(update_url(?:_\d+)?)\s*=\s*(.+?)\s*$', line)
            if m:
                all_urls[m.group(1)] = m.group(2).strip().strip('"').strip("'")
            m = re.match(r'update_sha256\s*=\s*(.+?)\s*$', line)
            if m:
                sha256 = m.group(1).strip().strip('"').strip("'").lower()

        if not tag:
            result.reason = '版本信息格式错误'
        else:
            download_url = all_urls.get(src_cfg['url_key']) or all_urls.get('update_url')
            body = fetch_release_body(src_cfg, tag, timeout)
            result.ok = True
            result.tag = tag
            result.body = body
            result.download_url = download_url
            result.sha256 = sha256
    except Exception as e:
        err_str = str(e).lower()
        if 'timed out' in err_str or 'timeout' in err_str:
            result.reason = '网络超时'
        else:
            result.reason = f'网络错误: {e}'
    return result


def fetch_release_body(src_cfg, tag, timeout=UPDATE_TIMEOUT):
    """获取更新内容（markdown）：直接走 releases API。"""
    body = ''
    try:
        api_url = src_cfg['api'].format(tag=tag)
        req2 = urllib.request.Request(
            api_url, headers={'User-Agent': _UA, 'Accept': 'application/json'})
        with urllib.request.urlopen(req2, timeout=timeout) as resp2:
            release_data = json.loads(resp2.read().decode('utf-8'))
            body = release_data.get('body', '') or ''
    except Exception:
        pass
    if not body:
        body = f'## {tag}\n\n更新内容获取失败，请前往下载页面查看详情。'
    return body


def download_update(url, dest_path, progress=None, timeout=180, expected_sha256=None):
    """下载更新 zip 到 dest_path；progress(got, total) 用于 UI 进度回调。

    只接受 http/https，限制最大 300 MiB；下载时同步计算 SHA256，若远端
    latest_version.txt 带 update_sha256 则必须一致，否则删除下载文件并报错。
    """
    if not url or not str(url).lower().startswith(('http://', 'https://')):
        raise ValueError('更新地址不是有效的 http/https 链接')
    expected_sha256 = (expected_sha256 or '').strip().lower() or None
    if expected_sha256 is not None and not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('更新包 SHA256 格式不合法')
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(str(url), headers={'User-Agent': _UA})
    digest = hashlib.sha256()
    total = got = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get('Content-Length') or 0)
            if total > UPDATE_MAX_BYTES:
                raise ValueError(f'更新包过大（{total / (1024 ** 2):.1f} MiB），已拒绝下载')
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > UPDATE_MAX_BYTES:
                        raise ValueError('更新包超过 300 MiB，已中止下载')
                    f.write(chunk)
                    digest.update(chunk)
                    if progress:
                        progress(got, total)
        if total and got != total:
            raise IOError(f'更新包不完整：应为 {total} 字节，实际 {got} 字节')
        actual_sha256 = digest.hexdigest()
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise ValueError(
                f'更新包 SHA256 不匹配：期望 {expected_sha256}，实际 {actual_sha256}')
    except Exception:
        try:
            if dest_path.exists():
                dest_path.unlink()
        except OSError:
            pass
        raise
    return str(dest_path)


def stage_update(zip_path):
    """校验并解压更新包到临时目录，返回解压后的源码根目录。

    安全约束：拒绝绝对路径、.. 路径穿越和非预期顶层目录；必须包含
    main.py、run.bat、run.sh、app/core/oppo_decrypt.py，避免错包覆盖。
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError('更新包不存在')
    stage_root = Path(tempfile.mkdtemp(prefix='oppo_firmware_decrypt_update_'))
    expected_prefix = 'oppo-firmware-decrypt/'
    try:
        with zipfile.ZipFile(zip_path) as z:
            bad = z.testzip()
            if bad:
                raise ValueError(f'更新包损坏：{bad}')
            for info in z.infolist():
                name = info.filename.replace('\\', '/')
                if not name or name.endswith('/'):
                    continue
                if name.startswith('/') or re.match(r'^[A-Za-z]:', name) or '..' in Path(name).parts:
                    raise ValueError(f'更新包含非法路径：{name}')
                if not name.startswith(expected_prefix):
                    raise ValueError(f'更新包顶层目录不符合预期：{name}')
                rel = name[len(expected_prefix):]
                target = stage_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(target, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                mode = (info.external_attr >> 16) & 0o777
                if mode:
                    try:
                        os.chmod(target, mode)
                    except OSError:
                        pass
    except Exception:
        shutil.rmtree(stage_root, ignore_errors=True)
        raise

    for required in ('main.py', 'run.bat', 'run.sh', 'app/core/oppo_decrypt.py'):
        if not (stage_root / required).is_file():
            shutil.rmtree(stage_root, ignore_errors=True)
            raise ValueError(f'更新包缺少必要文件：{required}')
    return str(stage_root)


UPDATE_BACKUP_IGNORE = (
    'out',
    'tmp',
    '.oppo_decrypt_tmp',
    'dist',
    'build',
    '__pycache__',
    '.git',
    '*.log',
)


def prepare_update_backup(app_root, backup_root):
    """备份程序目录，但跳过可再生成的运行时产物和构建缓存。"""
    app_root = Path(app_root)
    backup_root = Path(backup_root)
    if backup_root.exists():
        shutil.rmtree(backup_root, ignore_errors=True)
    shutil.copytree(
        app_root,
        backup_root,
        symlinks=True,
        ignore=shutil.ignore_patterns(*UPDATE_BACKUP_IGNORE),
    )


def launch_update_installer(stage_root, zip_path=None):
    """生成并在后台启动替换脚本；调用方应立即退出程序。

    替换前先把当前程序目录备份到同级 ``<app>.backup``；复制失败时
    用备份回滚，避免“新 .py + 旧 .pyd”的半覆盖状态。备份阶段已跳过
    ``out/`` 等运行时产物；复制成功后再删除更新 zip 与解压暂存目录。
    """
    app_root = Path(__file__).resolve().parent.parent
    stage_root = Path(stage_root)
    backup_root = Path(str(app_root) + '.backup')
    prepare_update_backup(app_root, backup_root)
    zip_path = str(zip_path) if zip_path else ''
    if os.name == 'nt':
        script = Path(tempfile.gettempdir()) / 'oppo_firmware_decrypt_apply_update.bat'
        script.write_text(
            '@echo off\n'
            '"%SystemRoot%\\System32\\chcp.com" 65001 >nul 2>nul\n'
            f'set "SRC={stage_root}"\n'
            f'set "DST={app_root}"\n'
            f'set "BACKUP={backup_root}"\n'
            f'set "ZIP={zip_path}"\n'
            '"%SystemRoot%\\System32\\ping.exe" -n 4 127.0.0.1 >nul\n'
            'if not exist "%BACKUP%\\main.py" (\n'
            '  echo [ERROR] backup missing before update > "%TEMP%\\oppo_firmware_decrypt_update_error.log"\n'
            '  exit /b 1\n'
            ')\n'
            '"%SystemRoot%\\System32\\robocopy.exe" "%SRC%" "%DST%" /E /IS /IT /NFL /NDL /NJH /NJS /NP /R:2 /W:1 >nul\n'
            'if errorlevel 8 (\n'
            '  echo [ERROR] update copy failed, robocopy exit=%ERRORLEVEL% > "%TEMP%\\oppo_firmware_decrypt_update_error.log"\n'
            '  "%SystemRoot%\\System32\\robocopy.exe" "%BACKUP%" "%DST%" /E /IS /IT /NFL /NDL /NJH /NJS /NP /R:2 /W:1 >nul\n'
            '  if errorlevel 8 (\n'
            '    echo [ERROR] rollback failed, backup kept at "%BACKUP%" >> "%TEMP%\\oppo_firmware_decrypt_update_error.log"\n'
            '  ) else (\n'
            '    echo [INFO] rolled back to "%BACKUP%" >> "%TEMP%\\oppo_firmware_decrypt_update_error.log"\n'
            '  )\n'
            '  exit /b 1\n'
            ')\n'
            'if exist "%SRC%" rmdir /s /q "%SRC%"\n'
            'if exist "%ZIP%" del /f /q "%ZIP%"\n'
            'start "" cmd /c ""%DST%\\run.bat""\n'
            'exit /b 0\n',
            encoding='utf-8',
            newline='\r\n',
        )
        cmd_exe = os.environ.get('ComSpec') or r'C:\Windows\System32\cmd.exe'
        subprocess.Popen(
            [cmd_exe, '/c', str(script)],
            cwd=str(app_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    else:
        script = Path(tempfile.gettempdir()) / 'oppo_firmware_decrypt_apply_update.sh'
        zip_cleanup = f'rm -f "{zip_path}"' if zip_path else ':'
        script.write_text(
            '#!/bin/sh\n'
            'set -eu\n'
            'sleep 3\n'
            f'BACKUP="{backup_root}"\n'
            f'APP="{app_root}"\n'
            f'STAGE="{stage_root}"\n'
            'if [ ! -d "$BACKUP" ]; then\n'
            '  echo "[ERROR] backup missing before update" >&2\n'
            '  exit 1\n'
            'fi\n'
            'if ! cp -a "$STAGE"/. "$APP"/; then\n'
            '  echo "[ERROR] update copy failed; rolling back from $BACKUP" >&2\n'
            '  cp -a "$BACKUP"/. "$APP"/ || echo "[ERROR] rollback failed; backup kept at $BACKUP" >&2\n'
            '  exit 1\n'
            'fi\n'
            f'rm -rf "{stage_root}"\n'
            f'{zip_cleanup}\n'
            f'exec "{app_root}/run.sh"\n',
            encoding='utf-8',
        )
        script.chmod(0o755)
        subprocess.Popen(
            ['/bin/sh', str(script)],
            cwd=str(app_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    return str(script)


def render_markdown(text_widget, markdown_text):
    """简单 markdown 渲染：标题、粗体、列表、代码块、链接"""
    # 配置 tag 样式
    text_widget.tag_configure('h1', font=(_UI_FAMILY, 16, 'bold'), spacing1=8, spacing3=4)
    text_widget.tag_configure('h2', font=(_UI_FAMILY, 14, 'bold'), spacing1=6, spacing3=3)
    text_widget.tag_configure('h3', font=(_UI_FAMILY, 12, 'bold'), spacing1=4, spacing3=2)
    text_widget.tag_configure('bold', font=(_UI_FAMILY, 10, 'bold'))
    text_widget.tag_configure('code', font=(_MONO_FAMILY, 9), background='#f0f0f0')
    text_widget.tag_configure('link', foreground='#0066cc', underline=True)
    text_widget.tag_configure('list', lmargin1=20, lmargin2=20)
    text_widget.tag_configure('blockquote', lmargin1=16, lmargin2=16, foreground='#888888')

    in_code_block = False
    for line in markdown_text.splitlines():
        stripped = line.strip()

        # 代码块
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            text_widget.insert(END, line + '\n', 'code')
            continue

        # 标题（标题行也走内联解析，支持 [链接](url)、**粗体** 等行内格式）
        if stripped.startswith('### '):
            _insert_inline(text_widget, stripped[4:], style='h3')
            text_widget.insert(END, '\n', 'h3')
            continue
        if stripped.startswith('## '):
            _insert_inline(text_widget, stripped[3:], style='h2')
            text_widget.insert(END, '\n', 'h2')
            continue
        if stripped.startswith('# '):
            _insert_inline(text_widget, stripped[2:], style='h1')
            text_widget.insert(END, '\n', 'h1')
            continue

        # 列表项
        if re.match(r'^[-*]\s+', stripped):
            content = re.sub(r'^[-*]\s+', '', stripped)
            text_widget.insert(END, '• ', 'list')
            _insert_inline(text_widget, content)
            text_widget.insert(END, '\n')
            continue
        if re.match(r'^\d+\.\s+', stripped):
            content = re.sub(r'^\d+\.\s+', '', stripped)
            text_widget.insert(END, stripped.split('.')[0] + '. ', 'list')
            _insert_inline(text_widget, content)
            text_widget.insert(END, '\n')
            continue

        # 引用块（blockquote）
        if stripped.startswith('>'):
            content = re.sub(r'^>\s?', '', stripped)
            text_widget.insert(END, '  ', 'blockquote')
            _insert_inline(text_widget, content, style='blockquote')
            text_widget.insert(END, '\n')
            continue

        # 普通行（处理内联格式）
        if stripped:
            _insert_inline(text_widget, stripped)
        text_widget.insert(END, '\n')


def _insert_inline(text_widget, text, style=None):
    """处理行内 markdown：**粗体**、`代码`、[链接](url)
    style：可选标题样式名（h1/h2/h3），传入时普通文本与行内元素都继承该样式
    """
    pattern = r'(\*\*.+?\*\*|`.+?`|\[.+?\]\(.+?\))'
    parts = re.split(pattern, text)
    base = (style,) if style else ()
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            text_widget.insert(END, part[2:-2], base + ('bold',))
        elif part.startswith('`') and part.endswith('`'):
            text_widget.insert(END, part[1:-1], base + ('code',))
        elif part.startswith('[') and '](' in part:
            m = re.match(r'\[(.+?)\]\((.+?)\)', part)
            if m:
                label, url = m.group(1), m.group(2)
                tag_name = f'link_{id(url)}'
                text_widget.insert(END, label, base + ('link', tag_name))
                text_widget.tag_bind(tag_name, '<Button-1>', lambda e, u=url: webbrowser.open(u))
                text_widget.tag_bind(tag_name, '<Enter>', lambda e: text_widget.config(cursor='hand2'))
                text_widget.tag_bind(tag_name, '<Leave>', lambda e: text_widget.config(cursor=''))
            else:
                text_widget.insert(END, part, base)
        else:
            text_widget.insert(END, part, base)
