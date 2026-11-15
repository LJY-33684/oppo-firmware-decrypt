# -*- coding: utf-8 -*-
"""
gui.py — OPPO / Realme / OnePlus 固件解密工具 轻量图形界面

设计原则（相对 mtk-garbage-porttool 的 ui.py）：
  1. 只保留解密所需控件：选固件 / 选输出类型 / 选输出目录 / 开始解密 / 日志；
  2. 不依赖移植方案表、方案切换等移植工具体系；
  3. 解密在后台线程执行，日志经 queue 回主线程刷新（子线程不碰任何 tkinter API）；
  4. main() 入口带单实例锁；底部版本号旁提供 GitHub / Gitee 图标跳转。
"""
import ctypes
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from .version import __version__                       # noqa: E402
from .common import default_outdir, FORMAT_LABELS      # noqa: E402
from . import updater                                  # noqa: E402
from .core import oppo_decrypt                        # noqa: E402

APP_TITLE = 'OPPO / Realme / OnePlus 固件解密工具'
UI_FONT = ('Microsoft YaHei', 9)
MONO_FONT = ('Consolas', 9)

# 仓库尚未创建；建仓后这两个地址即为有效仓库主页。图标文件在 app/icons/。
REPO_LINKS = (
    ('icon_github.png', 'https://github.com/LJY-33684/oppo-firmware-decrypt'),
    ('icon_gitee.png', 'https://gitee.com/Q3368436451/oppo-firmware-decrypt'),
)


def _enable_dpi_awareness():
    """Windows 高 DPI 感知：必须在创建 Tk 根窗口之前调用。

    未声明时进程按 96 DPI 渲染，再被系统位图拉伸到 125%/150%，文字发糊、
    控件尺寸也会按缩放倍数失真。优先 Per-Monitor V2，其次系统级 DPI 感知。
    """
    if sys.platform != 'win32':
        return
    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, 'SetProcessDpiAwarenessContext'):
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()        # 系统级兜底
    except Exception:
        pass


_enable_dpi_awareness()


class QueueLog:
    """把 decrypt() 的 log 输出投进队列，由主线程写入文本框。"""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(('log', s))

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self._icon_photo = None
        self._icon_ready = False
        self._set_window_icon()
        self.title(f"{APP_TITLE} {__version__}")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1320, sw - 80), min(720, sh - 120)
        self.geometry(f'{w}x{h}')
        self.minsize(min(1120, w), min(620, h))

        self.q = queue.Queue()
        self.qlog = QueueLog(self.q)
        self._running = False
        self._auto_outdir = ''
        self._poll_id = None
        self.repo_icons = []

        self.fw_var = tk.StringVar()
        self.outdir_var = tk.StringVar()
        self.out_type_var = tk.StringVar(value='img')
        self.status_var = tk.StringVar(value='就绪：选择固件文件后点击「开始解密」')
        self.format_var = tk.StringVar(value='识别格式：—')
        self.backend_var = tk.StringVar(value='AES 后端：检测中… | brotli 后端：检测中…')
        self.open_after_var = tk.BooleanVar(value=True)

        self._build_ui()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self._poll_id = self.after(80, self._poll_queue)
        threading.Thread(target=self._probe_backends, daemon=True).start()

    def _set_window_icon(self):
        """设置窗口左上角图标：Windows 用多尺寸 ICO，其它平台用 PNG 回退。"""
        icon_dir = Path(__file__).resolve().parent / 'icons'
        ico_path = icon_dir / 'app.ico'
        png_path = icon_dir / 'app.png'
        if sys.platform == 'win32':
            try:
                self.iconbitmap(str(ico_path))
                self.iconbitmap(default=str(ico_path))   # 更新弹窗等 Toplevel 也继承
                self._icon_ready = True
                return
            except Exception:
                pass
        try:
            img = tk.PhotoImage(file=str(png_path))
            self.iconphoto(True, img)
            self._icon_photo = img                         # 防止被垃圾回收
            self._icon_ready = True
        except Exception:
            pass

    # ---------------- UI ----------------
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use('vista')
        except tk.TclError:
            pass

        outer = ttk.Frame(self, padding=(8, 8))
        outer.pack(fill='both', expand=True)

        # ---- 左侧操作区 ----
        left = ttk.Frame(outer)
        left.pack(side='left', fill='y', padx=(0, 8))

        title = ttk.Label(left, text=APP_TITLE,
                          font=('Microsoft YaHei', 10, 'bold'))
        title.pack(anchor='w', pady=(2, 2))
        ttk.Label(left, text='支持 OFP（MTK）/ OZIP / OPS；原始固件只读不动，产物写入输出目录。',
                  foreground='#666666', wraplength=410).pack(anchor='w', pady=(0, 10))

        # 固件文件
        fw_box = ttk.Labelframe(left, text='固件文件')
        fw_box.pack(fill='x', pady=(0, 8))
        row = ttk.Frame(fw_box)
        row.pack(fill='x', padx=8, pady=(8, 3))
        self.fw_entry = ttk.Entry(row, textvariable=self.fw_var)
        self.fw_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='选择', width=7, command=self._choose_fw).pack(side='left', padx=(5, 0))
        ttk.Label(fw_box, textvariable=self.format_var, foreground='#0070c0').pack(
            anchor='w', padx=10, pady=(0, 8))

        # 输出类型
        type_box = ttk.Labelframe(left, text='输出类型')
        type_box.pack(fill='x', pady=(0, 8))
        ttk.Radiobutton(type_box, text='img：展开固件并转换成分区镜像（默认）',
                        value='img', variable=self.out_type_var).pack(anchor='w', padx=10, pady=(8, 0))
        ttk.Radiobutton(type_box, text='zip：直接输出解密后的卡刷包（仅 OZIP 有效）',
                        value='zip', variable=self.out_type_var).pack(anchor='w', padx=10, pady=(2, 8))

        # 输出目录
        out_box = ttk.Labelframe(left, text='输出目录')
        out_box.pack(fill='x', pady=(0, 8))
        row2 = ttk.Frame(out_box)
        row2.pack(fill='x', padx=8, pady=(8, 3))
        self.outdir_entry = ttk.Entry(row2, textvariable=self.outdir_var)
        self.outdir_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(row2, text='选择', width=7, command=self._choose_outdir).pack(side='left', padx=(5, 0))
        ttk.Label(out_box, text='留空 = 固件同目录 <固件名>_decrypted/',
                  foreground='#888888', font=('Microsoft YaHei', 8)).pack(
            anchor='w', padx=10, pady=(0, 6))
        ttk.Checkbutton(out_box, text='完成后自动打开输出目录',
                        variable=self.open_after_var).pack(anchor='w', padx=10, pady=(0, 8))

        # 开始按钮 / 进度 / 状态
        self.start_btn = ttk.Button(left, text='开始解密', command=self._start)
        self.start_btn.pack(fill='x', pady=(2, 6), ipady=4)

        self.progress = ttk.Progressbar(left, mode='indeterminate')
        self.progress.pack(fill='x', pady=(0, 6))

        ttk.Label(left, textvariable=self.status_var, foreground='#333333',
                  wraplength=410).pack(anchor='w', pady=(0, 8))

        # 后端信息
        ttk.Label(left, textvariable=self.backend_var, foreground='#666666',
                  font=('Microsoft YaHei', 8), wraplength=410).pack(anchor='w', pady=(0, 6))

        # 底部：版本 / 更新 / 打开目录
        bottom = ttk.Frame(left)
        bottom.pack(side='bottom', fill='x', pady=(8, 0))
        ttk.Label(bottom, text=f'版本号：{__version__}',
                  foreground='#888888', font=('Microsoft YaHei', 8)).pack(side='left')

        # GitHub / Gitee 仓库图标：点击用系统浏览器打开对应页面
        icon_dir = Path(__file__).resolve().parent / 'icons'
        for icon_name, repo_url in REPO_LINKS:
            try:
                img = tk.PhotoImage(file=str(icon_dir / icon_name))
                lbl = ttk.Label(bottom, image=img, cursor='hand2')
                lbl.image = img          # 防止被垃圾回收
                lbl.pack(side='left', padx=(8, 0))
                lbl.bind('<Button-1>', lambda e, url=repo_url: webbrowser.open(url))
                self.repo_icons.append((lbl, img))
            except Exception:
                pass                      # 图标缺失时静默跳过，不阻塞启动

        ttk.Button(bottom, text='打开输出目录', width=12,
                   command=self._open_outdir).pack(side='right')
        self.update_btn = ttk.Button(bottom, text='检查更新', width=9,
                                     command=self._check_update)
        self.update_btn.pack(side='right', padx=(0, 5))

        # 风险提示（移植工具同款橙色提示，放在底部按钮上方）
        self.risk_label = ttk.Label(
            left,
            text='刷机有风险，操作前务必备份原系统；请保留原厂固件以备恢复。',
            font=('Microsoft YaHei', 8), foreground='#b06000',
            wraplength=470, justify='left')
        self.risk_label.pack(side='bottom', anchor='w', fill='x', pady=(6, 2))

        # ---- 右侧日志区 ----
        log_box = ttk.Labelframe(outer, text='日志输出')
        log_box.pack(side='left', fill='both', expand=True)

        toolbar = ttk.Frame(log_box)
        toolbar.pack(fill='x', padx=6, pady=(6, 0))
        ttk.Button(toolbar, text='清空日志', width=9,
                   command=self._clear_log).pack(side='right')

        self.log_text = ScrolledText(log_box, wrap='char', font=MONO_FONT,
                                     background='#1e1e1e', foreground='#dcdcdc',
                                     insertbackground='#ffffff', borderwidth=0)
        self.log_text.pack(fill='both', expand=True, padx=6, pady=6)
        self.log_text.configure(state='disabled')
        for tag, color in (('err', '#ff6b6b'), ('warn', '#f0c674'),
                           ('ok', '#7ec699'), ('info', '#6cb6ff')):
            self.log_text.tag_configure(tag, foreground=color)

        self._append_log(f'OPPO 固件解密工具 {__version__} 已启动 | '
                         f'Python {sys.version.split()[0]} | {sys.platform}\n')

    # ---------------- 日志 ----------------
    def _append_log(self, text):
        """主线程写入日志（超长日志自动截断，避免内存膨胀）。"""
        self.log_text.configure(state='normal')
        tag = None
        if '【错误】' in text or '失败' in text:
            tag = 'err'
        elif '【警告】' in text or '【提示】' in text:
            tag = 'warn'
        elif '【完成】' in text:
            tag = 'ok'
        elif '【解密】' in text or '【CLI】' in text:
            tag = 'info'
        self.log_text.insert('end', text, tag)
        # 行数过多时丢弃最前面的 5000 行
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 30000:
            self.log_text.delete('1.0', '5000.0')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    def _poll_queue(self):
        chunks = []
        done = None
        backend = None
        update = None
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                chunks.append(payload)
            elif kind == 'done':
                done = payload
            elif kind == 'backend':
                backend = payload
            elif kind == 'update':
                update = payload
        if chunks:
            self._append_log(''.join(chunks))
        if backend:
            self.backend_var.set(backend)
        if done:
            self._on_done(*done)
        if update:
            self._on_update_result(update)
        self._poll_id = self.after(80, self._poll_queue)

    # ---------------- 选择文件 ----------------
    def _choose_fw(self):
        f = filedialog.askopenfilename(
            title='选择固件文件',
            filetypes=[('OPPO 系固件', '*.ofp *.ozip *.ops'), ('所有文件', '*.*')])
        if f:
            self._set_fw(f)

    def _set_fw(self, path):
        self.fw_var.set(path)
        fmt = oppo_decrypt.detect_format(path)
        self.format_var.set('识别格式：' + (FORMAT_LABELS.get(fmt, '无法识别（非 OFP/OZIP/OPS）')))
        current = self.outdir_var.get().strip()
        if (not current) or current == self._auto_outdir:
            self._auto_outdir = default_outdir(path)
            self.outdir_var.set(self._auto_outdir)
        self._append_log(f'【选择】固件：{path}\n')

    def _choose_outdir(self):
        d = filedialog.askdirectory(title='选择输出目录')
        if d:
            self._auto_outdir = ''
            self.outdir_var.set(d)

    def _probe_backends(self):
        try:
            aes = oppo_decrypt.backend_name()
        except Exception as e:
            aes = f'检测失败（{e}）'
        try:
            from .core import brotli
            br = brotli.backend_name() or '无可用后端'
        except Exception as e:
            br = f'检测失败（{e}）'
        self.q.put(('backend', f'AES 后端：{aes} | brotli 后端：{br}'))

    # ---------------- 解密流程 ----------------
    def _start(self):
        if self._running:
            return
        fw = self.fw_var.get().strip().strip('"')
        if not fw or not Path(fw).is_file():
            messagebox.showwarning('未选择固件', '请先选择固件文件（.ofp / .ozip / .ops）。')
            return
        fmt = oppo_decrypt.detect_format(fw)
        if fmt is None:
            messagebox.showerror('格式无法识别',
                                 '该文件不是可识别的 OPPO 系固件（OFP / OZIP / OPS）。\n'
                                 '请确认文件完整且扩展名正确。')
            return
        outdir = self.outdir_var.get().strip().strip('"') or default_outdir(fw)
        out_type = self.out_type_var.get()
        if out_type == 'zip' and fmt != 'ozip':
            messagebox.showinfo('提示', 'zip 输出仅对 OZIP 生效：\n'
                                        'OFP/OPS 为分区镜像流，本次仍按 img 输出。')

        self._running = True
        self.start_btn.configure(state='disabled', text='解密中…')
        self.progress.start(12)
        self.status_var.set(f'正在解密（{FORMAT_LABELS.get(fmt, fmt)}），请稍候…')
        self._append_log('\n' + '=' * 60 + '\n')

        threading.Thread(target=self._worker, args=(fw, outdir, out_type),
                         daemon=True).start()

    def _worker(self, fw, outdir, out_type):
        try:
            ok = oppo_decrypt.decrypt(fw, outdir, self.qlog, out_type=out_type)
            self.q.put(('done', (ok, outdir, None)))
        except Exception as e:
            self.q.put(('done', (False, outdir, str(e))))

    def _on_done(self, ok, outdir, err):
        self._running = False
        self.start_btn.configure(state='normal', text='开始解密')
        self.progress.stop()
        if err:
            self.status_var.set(f'解密异常：{err}')
            self._append_log(f'【错误】解密异常：{err}\n')
            messagebox.showerror('解密异常', f'{err}')
            return
        if ok:
            self.status_var.set('解密完成：' + outdir)
            messagebox.showinfo('完成', f'解密完成，产物目录：\n{outdir}')
            if self.open_after_var.get():
                self._open_outdir(outdir)
        else:
            self.status_var.set('解密失败，请查看日志中的【错误】行')
            messagebox.showerror('解密失败', '解密失败，请查看日志中的【错误】行排查原因。')

    def _open_outdir(self, outdir=None):
        d = outdir or self.outdir_var.get().strip().strip('"')
        if not d:
            messagebox.showinfo('无输出目录', '尚未设置输出目录。')
            return
        if not os.path.isdir(d):
            messagebox.showinfo('目录不存在', f'输出目录还不存在：\n{d}')
            return
        try:
            os.startfile(d)  # noqa: S606  (Windows)
        except Exception as e:
            messagebox.showerror('打开失败', f'无法打开输出目录：{e}')

    # ---------------- 检查更新 ----------------
    def _check_update(self):
        self.update_btn.configure(text='检查更新中…', state='disabled')
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self):
        result = updater.fetch_update_info(updater.DEFAULT_SOURCE)
        self.q.put(('update', result))

    def _on_update_result(self, result):
        self.update_btn.configure(text='检查更新', state='normal')
        if not result.ok:
            messagebox.showinfo('检查更新', f'{result.reason}')
            return
        self._show_update_dialog(result.tag, result.body, result.download_url)

    def _show_update_dialog(self, tag, body, download_url):
        win = tk.Toplevel(self)
        win.title(('当前已是最新版本 - ' if tag == __version__ else '发现新版本 - ') + str(tag))
        win.geometry('660x500')
        win.transient(self)
        win.grab_set()

        header = ttk.Frame(win)
        header.pack(fill='x', padx=12, pady=(10, 5))
        ttk.Label(header, text=(f'当前已是最新版本：{tag}' if tag == __version__
                                else f'发现新版本：{tag}'),
                  font=('Microsoft YaHei', 10, 'bold')).pack(side='left')

        def open_download():
            if download_url:
                import webbrowser
                webbrowser.open(download_url)

        ttk.Button(header, text='前往下载', command=open_download).pack(side='right')

        content = ttk.Frame(win)
        content.pack(fill='both', expand=True, padx=12, pady=(0, 10))
        text = tk.Text(content, wrap='word', font=('Microsoft YaHei', 10), padx=8, pady=8)
        bar = ttk.Scrollbar(content, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        updater.render_markdown(text, body)
        text.configure(state='disabled')

    # ---------------- 关闭 ----------------
    def destroy(self):
        """销毁窗口前取消日志轮询定时器，避免 Tcl 残留回调报 invalid command name。"""
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        super().destroy()

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno('正在解密',
                                       '解密任务仍在进行，退出会中断本次解密（原固件不会受影响）。\n'
                                       '确定退出吗？'):
                return
        self.destroy()


def _show_already_running(pid, singleton):
    """同目录已有实例在运行：弹出提示窗口。

    可选：跳转至已运行窗口 / 清除残留状态锁后继续 / 直接退出。
    返回 True=用户已清除状态锁且本进程已重新上锁，可继续启动；False=关闭退出。
    """
    root = tk.Tk()
    root.title(APP_TITLE)
    root.resizable(False, False)
    root.attributes('-topmost', True)

    msg = ("检测到本工具已有一个正在运行的实例。\n"
           "同一目录仅允许运行一个实例，以免同时解密写入同一输出目录造成冲突。\n"
           "如需同时运行多个实例，请将本工具所在目录复制到其他位置后再打开运行。\n\n"
           "提示：若你确认当前并没有其他实例在运行、但仍弹出此窗口，\n"
           "说明上次进程被强制结束后残留了状态锁，请点击「清除状态锁」按钮后重试。")
    ttk.Label(root, text=msg, justify='left', wraplength=430).pack(padx=20, pady=(16, 6))

    result = {'clear': False}
    tip = ttk.Label(root, text='', foreground='#cc0000')
    btns = ttk.Frame(root)

    def _jump():
        # 只有跳转成功才关闭提示窗并退出本实例；失败时留在窗口里给出提示，
        # 避免「点了跳转、本实例直接退出、已有窗口也没出来」的静默失效。
        try:
            moved = bool(singleton.focus_window(pid))
        except Exception:
            moved = False
        if moved:
            root.destroy()
        else:
            tip.config(text='未能定位到正在运行的窗口（可能已最小化或已退出）。\n'
                            '可先手动切换过去，或点击「清除状态锁」后继续。')
            tip.pack(pady=(0, 4))

    def _clear():
        # 若检测到仍有实例在运行：二次弹窗让用户确认是否强制清除
        if singleton.pid_alive(pid):
            ans = messagebox.askyesno(
                '确认清除状态锁',
                '检测到仍有一个实例可能在运行（PID：%s）。\n\n'
                '强制清除状态锁后，该实例将失去本工具的单实例保护，\n'
                '若两实例同时操作可能造成文件冲突。\n\n'
                '确认强制清除并继续启动吗？\n'
                '（若该实例仍在使用，建议先关闭它，或点击「跳转至正在运行的程序」切换过去）' % pid,
                parent=root)
            if not ans:
                return
        # 实例已确认退出 / 用户确认强制清除：删除状态锁并重新上锁
        singleton.clear_lock()
        ok, _ = singleton.acquire()
        if ok:
            result['clear'] = True
            root.destroy()
        else:
            tip.config(text='清除后仍检测到其他实例在运行，请先确认是否已有程序打开。')
            tip.pack(pady=(0, 4))

    ttk.Button(btns, text='跳转至正在运行的程序', command=_jump).pack(side='left', padx=6)
    ttk.Button(btns, text='清除状态锁', command=_clear).pack(side='left', padx=6)
    ttk.Button(btns, text='好的', command=root.destroy).pack(side='left', padx=6)
    btns.pack(pady=(6, 14))

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f'+{x}+{y}')
    root.mainloop()
    return result['clear']


def main():
    from . import singleton
    import atexit

    # 单实例检查：同一目录只允许一个 GUI 实例
    ok, pid = singleton.acquire()
    if not ok:
        # 用户清除状态锁成功时（_show_already_running 返回 True）已在本进程重新上锁，继续启动
        if not _show_already_running(pid, singleton):
            return
    atexit.register(singleton.release)

    app = App()
    app.mainloop()
