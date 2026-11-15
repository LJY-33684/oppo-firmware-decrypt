#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 环境与解密链路自检（不接触真实固件，全部用合成样本）

覆盖：
  1. AES 后端（openssl / pyaes）一致性：ECB、CFB128
  2. brotli 后端可用性与 .br 解压
  3. sdat2img：new.dat + transfer.list → img
  4. 单实例锁：首次上锁 / 重复获取拒绝 / 释放后重上锁
  5. detect_format 五个分支
  6. PK 型加密 OZIP 全链路（含真实 AES 解密 + 重建 zip + 展开转镜像）
  7. 明文 OZIP（无 oppo_metadata、boot.img 未加密）直出卡刷包
  8. CLI 契约：--version / 缺文件退出码 / 默认输出目录
  9. 更新模块的 GitHub / Gitee 双更新源配置
  10. GUI 控件构建、GitHub/Gitee 图标加载
  11. GUI 端到端解密

用法：python app/tests/selftest.py
退出码：0 全部通过；1 存在失败项
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # app/tests → app → 源码根
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import oppo_decrypt as od   # noqa: E402
from app.core import pyaes                # noqa: E402
from app.core import brotli               # noqa: E402
from app.core import sdat2img             # noqa: E402

RESULTS = []
TMP = Path(tempfile.mkdtemp(prefix='oppo_dec_selftest_'))
SKIP_GUI = os.environ.get('OPPO_SKIP_GUI') == '1'


class Skip(Exception):
    """当前环境缺少测试前提（如无 Tcl/Tk），跳过而非失败。"""


def check(name, fn):
    try:
        detail = fn() or ''
        RESULTS.append((True, name, detail))
        print(f'[PASS] {name}' + (f' — {detail}' if detail else ''))
    except Skip as e:
        RESULTS.append((None, name, str(e)))
        print(f'[SKIP] {name} — {e}')
    except Exception as e:
        RESULTS.append((False, name, str(e)))
        print(f'[FAIL] {name} — {e}')


def emit(msg):
    print('    ' + msg if msg.endswith('\n') else '    ' + msg)


# ---------------- 1. AES 后端 ----------------
def t_aes():
    key = bytes.fromhex('D6EECF0AE5ACD4E0E9FE522DE7CE381E')
    plain = bytearray(range(16))
    ecb = pyaes.AESModeOfOperationECB(key)
    ct = ecb.encrypt(bytes(plain))
    assert isinstance(ct, bytes) and len(ct) == 16, 'pyaes ECB 加密输出异常'

    # 解密通道（可能走 openssl，也可能走 pyaes；两条路径都验）
    dec = od.aes_ecb_decrypt(key, ct)
    assert dec == bytes(plain), 'aes_ecb_decrypt 与 pyaes 加密结果不一致'
    py_dec = pyaes.AESModeOfOperationECB(key).decrypt(ct)
    assert py_dec == bytes(plain), 'pyaes ECB 自身解密不一致'

    iv = bytes.fromhex('2bf515b3a9737835' * 2)
    enc = pyaes.Encrypter(pyaes.AESModeOfOperationCFB(key, iv, segment_size=16))
    cct = enc.feed(bytes(plain)) + enc.feed()
    cdec = od.aes_cfb128_decrypt(key, iv, cct)
    assert cdec == bytes(plain), 'aes_cfb128_decrypt 与 pyaes CFB 加密结果不一致'
    return f'后端={od.backend_name()}，ECB/CFB128 双通道一致'


# ---------------- 2. brotli ----------------
def t_brotli():
    brotli._probe()
    backend = brotli.backend_name()
    assert backend != 'none', '未找到任何 brotli 后端'
    data = (b'OPPO firmware decrypt selftest\n' * 4096)
    src = TMP / 'sample.txt'
    br = TMP / 'sample.txt.br'
    out = TMP / 'sample.out'
    src.write_bytes(data)

    if brotli._BIN:
        p = subprocess.run([brotli._BIN, '-f', '-o', str(br), str(src)],
                           capture_output=True)
        assert p.returncode == 0, f'brotli 压缩失败：{p.stderr[:200]}'
    else:
        br.write_bytes(brotli._MOD.compress(data))

    brotli.brotli_decompress(str(br), str(out), emit=lambda m: None)
    assert out.read_bytes() == data, '解压结果与原文不一致'
    out_size = br.stat().st_size
    return f'后端={backend}，{len(data)}B → {out_size}B → 还原一致'


# ---------------- 3. sdat2img ----------------
def t_sdat2img():
    tl = TMP / 'system.transfer.list'
    dat = TMP / 'system.new.dat'
    img = TMP / 'system.img'
    tl.write_text('4\n2\n0\n0\nnew 2,1,2\n', encoding='utf-8')
    block = bytes(range(256)) * 16  # 4096 字节
    dat.write_bytes(block)
    sdat2img.main(str(tl), str(dat), str(img), log=lambda m: None)
    assert img.exists(), '未生成 img'
    assert img.stat().st_size == 8192, f'img 大小异常：{img.stat().st_size}'
    return f'4096B new.dat → {img.stat().st_size}B img'


# ---------------- 3b. fsutil（只读文件删除） ----------------
def t_fsutil():
    from app.core import fsutil
    d = TMP / 'ro_dir'
    d.mkdir(exist_ok=True)
    f = d / 'readonly.bin'
    f.write_bytes(b'x')
    os.chmod(f, 0o444)          # Windows 下即置只读属性
    fsutil._rmtree(d)
    assert not d.exists(), '只读文件/目录未被删除'
    return '_rmtree 清除只读属性后删除成功'


def t_singleton():
    """单实例锁：首次获取成功，重复获取应被拒绝，释放后可再次获取。"""
    from app import singleton
    lp = singleton._lock_path()
    if lp.exists():
        raise Skip('工具当前正在运行，跳过单实例锁测试')
    ok, pid = singleton.acquire()
    assert ok and pid == os.getpid(), f'首次上锁失败：{ok}, {pid}'
    try:
        ok2, pid2 = singleton.acquire()
        assert not ok2, '同一进程第二次获取锁竟然成功'
        assert pid2 == os.getpid(), f'返回的持有者 PID 异常：{pid2}'
    finally:
        singleton.release()
    assert not lp.exists(), '释放后锁文件仍存在'
    ok3, _ = singleton.acquire()
    assert ok3, '释放后无法重新上锁'
    singleton.release()
    return '首次上锁 / 重复拒绝 / 释放后重上锁均正常'


# ---------------- 4. 格式识别 ----------------
def t_detect():
    cases = [
        ('a.ofp', b'MMM' + b'\0' * 9, 'ofp_mtk'),
        ('b.ops', b'\0' * 12, 'ops'),
        ('c.ozip', b'OPPOENCRYPT!' + b'\0' * 12, 'ozip'),
        ('d.ozip', b'PK\x03\x04' + b'\0' * 8, 'ozip'),
        ('e.bin', b'hello world!', None),
    ]
    got = []
    for name, head, expect in cases:
        p = TMP / name
        p.write_bytes(head)
        actual = od.detect_format(str(p))
        assert actual == expect, f'{name}: 期望 {expect}，实际 {actual}'
        got.append(f'{name}→{actual}')
    return '，'.join(got)


# ---------------- 5. PK 型加密 OZIP 全链路 ----------------
OZIP_KEY = bytes.fromhex('D6EECF0AE5ACD4E0E9FE522DE7CE381E')


def _ozip_encrypted_file(plain_block18: bytes) -> bytes:
    """构造 _ozip_decryptfile 认识的加密文件：0x10 处写长度，0x1050 起写密文块。"""
    assert len(plain_block18) == 16
    buf = bytearray(b'\0' * (0x1050 + 16))
    buf[0x10:0x20] = b'16' + b'\0' * 14
    ct = pyaes.AESModeOfOperationECB(OZIP_KEY).encrypt(plain_block18)
    buf[0x1050:0x1060] = ct
    return bytes(buf)


def _build_pk_ozip(path: Path):
    vbmeta = _ozip_encrypted_file(b'AVB0' + b'\0' * 12)
    boot = _ozip_encrypted_file(b'\0' * 16)
    meta = 'vbmeta.img\nboot.img\n'
    payload = TMP / 'meta.bin'
    payload.write_bytes(b'not important')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('oppo_metadata', meta)
        z.writestr('vbmeta.img', vbmeta)
        z.writestr('boot.img', boot)
        z.writestr('META-INF/com/google/android/update-binary', payload.read_bytes())


def t_ozip_encrypted():
    pkg = TMP / 'enc_test.ozip'
    _build_pk_ozip(pkg)
    outdir = TMP / 'out_zip'
    logs = []
    ok = od.decrypt(str(pkg), str(outdir), _ListLog(logs), out_type='zip')
    assert ok, '加密 OZIP 解密返回 False'
    outzips = list(outdir.glob('*.zip'))
    assert outzips, '未输出卡刷包'
    with zipfile.ZipFile(outzips[0]) as z:
        names = set(z.namelist())
        assert 'boot.img' in names and 'vbmeta.img' in names, f'条目缺失：{names}'
        assert z.read('boot.img') == b'\0' * 16, 'boot.img 解密结果不符'
        assert z.read('vbmeta.img')[:4] == b'AVB0', 'vbmeta.img 解密结果不符'
    assert not (outdir / od.TEMP_SUBDIR).exists(), '临时目录未清理'
    return f'{outzips[0].name} 重建成功，临时目录已清理'


def t_ozip_img():
    pkg = TMP / 'enc_img.ozip'
    _build_pk_ozip(pkg)
    outdir = TMP / 'out_img'
    logs = []
    ok = od.decrypt(str(pkg), str(outdir), _ListLog(logs), out_type='img')
    assert ok, 'img 模式解密返回 False'
    assert (outdir / 'vbmeta.img').exists(), '未展开 vbmeta.img'
    assert (outdir / 'boot.img').exists(), '未展开 boot.img'
    assert not (outdir / od.TEMP_SUBDIR).exists(), '临时目录未清理'
    return f'展开 {len(list(outdir.iterdir()))} 个条目，无残留临时目录'


class _ListLog:
    def __init__(self, sink):
        self.sink = sink

    def write(self, s):
        self.sink.append(s)

    def flush(self):
        pass


# ---------------- 6. 明文 OZIP ----------------
def t_ozip_plain():
    pkg = TMP / 'plain.ozip'
    with zipfile.ZipFile(pkg, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('boot.img', b'plain boot image')
        z.writestr('system.new.dat', b'\0' * 1024)
    outdir = TMP / 'out_plain'
    ok = od.decrypt(str(pkg), str(outdir), _ListLog([]), out_type='zip')
    assert ok, '明文 OZIP 处理返回 False'
    outs = list(outdir.glob('*.zip'))
    assert outs, '未输出卡刷包'
    assert outs[0].stat().st_size == pkg.stat().st_size, '明文包应原样复制'
    return '识别为明文，原样直出'


# ---------------- 6b. OFP（MTK）合成样本 ----------------
OFP_HEAD_PLAIN = b'0123456789abcdef'
OFP_REST_PLAIN = bytes(range(256)) * 16     # 4096 字节明文


def _nibswap(x):
    return ((x & 0xF) << 4) + ((x & 0xF0) >> 4)


def _ofp_shuffle_raw(data, key):
    """把明文编成「mtk_shuffle 逆运算」后的字节流（f(P) ^ k ^ S(k)，D 按 key 循环）。"""
    n = len(data)
    d = bytes(key[i % len(key)] ^ _nibswap(key[i % len(key)]) for i in range(n))
    f = od.mtk_shuffle(bytearray(key), len(key), bytearray(data), n)
    return bytes(a ^ b for a, b in zip(f, d))


def _build_ofp(path: Path):
    aeskey = bytes(od._OFP_KEYTABLES[8][0], 'utf-8')
    aesiv = bytes(od._OFP_KEYTABLES[8][1], 'utf-8')

    def cfp_encrypt(pt):
        enc = pyaes.Encrypter(pyaes.AESModeOfOperationCFB(aeskey, aesiv, segment_size=16))
        return enc.feed(pt) + enc.feed()

    data_off = 16
    enc_head = cfp_encrypt(OFP_HEAD_PLAIN)
    part_data = enc_head + OFP_REST_PLAIN

    hdr_plain = bytearray(0x6C)
    struct.pack_into("46s Q 4s 7s 5s H 32s H", hdr_plain, 0,
                     b'TESTPRJ', 0, b'\0' * 4, b'MT6750', b'EMMC', 1, b'ofp selftest', 0)
    hdr2_plain = bytearray(0x60)
    struct.pack_into("<32s Q Q Q 32s Q", hdr2_plain, 0,
                     b'boot', data_off, len(part_data), len(enc_head), b'boot.img', 0)

    buf = bytearray()
    buf += cfp_encrypt(b'MMM' + b'\0' * 13)   # OFP 魔数（加密）
    buf += part_data
    buf += _ofp_shuffle_raw(bytes(hdr2_plain), b'geyixue')
    buf += _ofp_shuffle_raw(bytes(hdr_plain), b'geyixue')
    path.write_bytes(bytes(buf))


def t_ofp():
    pkg = TMP / 'synthetic.ofp'
    _build_ofp(pkg)
    outdir = TMP / 'out_ofp'
    ok = od.decrypt(str(pkg), str(outdir), _ListLog([]), out_type='img')
    assert ok, 'OFP 解密返回 False'
    img = outdir / 'boot.img'
    assert img.exists(), '未导出 boot.img'
    expect = OFP_HEAD_PLAIN + OFP_REST_PLAIN
    assert img.read_bytes() == expect, '导出分区内容与预期不一致'
    return f'{len(expect)}B 分区导出并解密一致'


# ---------------- 6c. OPS（OnePlus）合成样本 ----------------
def _build_ops(path: Path):
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<OPPSettings><UFS_PROVISION>'
           '<File Path="test.bin" FileOffsetInSrc="0" SizeInByteInSrc="16"/>'
           '</UFS_PROVISION></OPPSettings>\n').encode('utf-8')
    xml_len = len(xml)
    pad = 0x200 - (xml_len % 0x200)
    region = xml + b'\0' * pad
    enc_xml = od._ops_key_custom(region, list(od._OPS_KEY), 0, encrypt=True,
                                 mbox=od._OPS_MBOX5)
    trailer = bytearray(0x200)
    trailer[0x18:0x1C] = xml_len.to_bytes(4, 'little')
    path.write_bytes(bytes(range(16)) + enc_xml + bytes(trailer))


def t_ops():
    pkg = TMP / 'synthetic.ops'
    _build_ops(pkg)
    outdir = TMP / 'out_ops'
    ok = od.decrypt(str(pkg), str(outdir), _ListLog([]), out_type='img')
    assert ok, 'OPS 解密返回 False'
    f = outdir / 'test.bin'
    assert f.exists(), '未导出 test.bin'
    assert f.read_bytes() == bytes(range(16)), '导出内容与预期不一致'
    return 'settings.xml 解密（MBox5）与分区导出一致'


# ---------------- 7. CLI ----------------
def t_cli():
    cli = ROOT / 'decrypt_cli.py'
    r = subprocess.run([sys.executable, str(cli), '--version'],
                       capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0 and r.stdout.strip() == '1.0.0.002', r.stdout
    ver = r.stdout.strip()

    r2 = subprocess.run([sys.executable, str(cli), 'decrypt', '--input',
                         str(TMP / 'no_such_file.ozip')],
                        capture_output=True, text=True, encoding='utf-8')
    assert r2.returncode == 1, f'缺文件应返回 1，实际 {r2.returncode}'

    pkg = TMP / 'cli_plain.ozip'
    with zipfile.ZipFile(pkg, 'w') as z:
        z.writestr('boot.img', b'plain')
    r3 = subprocess.run([sys.executable, str(cli), 'decrypt', '--input', str(pkg),
                         '--out-type', 'zip'],
                        capture_output=True, text=True, encoding='utf-8')
    assert r3.returncode == 0, f'CLI 解密返回 {r3.returncode}\n{r3.stdout[-500:]}'
    expect = TMP / 'cli_plain_decrypted'
    assert expect.is_dir() and any(expect.iterdir()), '默认输出目录未生成'
    assert not (ROOT / 'tmp').exists(), '启动目录残留 tmp/（临时目录应落在输出目录内）'
    return f'version={ver}，缺文件=1，正常解密=0'


# ---------------- 8. 更新模块 ----------------
def t_update():
    from app import updater
    assert updater.UPDATE_ENABLED is True, '更新总开关未启用'
    assert updater.is_configured('GitHub'), 'GitHub 更新源未配置'
    cfg = updater.UPDATE_SOURCES['GitHub']
    assert cfg['raw'].startswith('https://raw.githubusercontent.com/'), cfg['raw']
    assert '{tag}' in cfg['api'], cfg['api']
    assert cfg['contents_api'].startswith('https://api.github.com/'), cfg['contents_api']

    assert updater.is_configured('Gitee'), 'Gitee 更新源未配置'
    gitee = updater.UPDATE_SOURCES['Gitee']
    assert gitee['raw'].startswith('https://gitee.com/'), gitee['raw']
    assert 'gitee.com/api/v5/' in gitee['api'], gitee['api']
    assert '{tag}' in gitee['api'], gitee['api']
    return 'GitHub / Gitee 双更新源地址已配置'


# ---------------- 9. GUI ----------------
def t_gui():
    import tkinter as tk
    try:
        probe = tk.Tk()
        probe.destroy()
    except Exception as e:
        raise Skip(f'当前 Python 无可用 Tcl/Tk（{str(e).splitlines()[0]}）')
    from app import gui
    app = gui.App()
    app.withdraw()
    app.update_idletasks()
    assert app.title().startswith('OPPO'), app.title()
    assert app._icon_ready, '窗口图标未成功加载（app.ico / app.png）'
    assert len(app.repo_icons) == 2, f'仓库图标未全部加载：{len(app.repo_icons)}'
    assert app.update_source.get() == 'GitHub', '更新源默认值不是 GitHub'
    assert app.update_source_menu is not None, '更新源下拉框未创建'
    assert '刷机有风险' in app.risk_label.cget('text'), '风险提示未创建'
    app.destroy()
    return '控件构建、窗口图标、仓库图标、更新源切换与风险提示正常（窗口未显示）'


def t_gui_decrypt():
    """GUI 端到端：走 _start → 后台线程 → queue → _on_done 全链路。"""
    import time
    import tkinter as tk
    try:
        probe = tk.Tk()
        probe.destroy()
    except Exception as e:
        raise Skip(f'当前 Python 无可用 Tcl/Tk（{str(e).splitlines()[0]}）')
    from app import gui

    # 弹窗与资源管理器在自检里不应阻塞/弹窗
    gui.messagebox.showinfo = lambda *a, **k: None
    gui.messagebox.showwarning = lambda *a, **k: None
    gui.messagebox.showerror = lambda *a, **k: None
    gui.App._open_outdir = lambda self, outdir=None: None

    pkg = TMP / 'gui_plain.ozip'
    with zipfile.ZipFile(pkg, 'w') as z:
        z.writestr('boot.img', b'plain')
    outdir = TMP / 'out_gui'

    app = gui.App()
    app.withdraw()
    app.open_after_var.set(False)
    app.out_type_var.set('zip')          # 明文 OZIP + zip：应直接产出卡刷包
    app._set_fw(str(pkg))
    app.outdir_var.set(str(outdir))
    app._start()

    deadline = time.time() + 20
    while app._running and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    app.update()
    assert not app._running, 'GUI 解密超时未结束'
    assert list(outdir.glob('*.zip')), 'GUI 未产出卡刷包'
    status = app.status_var.get()
    app.destroy()
    return f'状态：{status}'


def main():
    print(f'自检临时目录：{TMP}\n')
    check('AES 后端一致性', t_aes)
    check('brotli 解压', t_brotli)
    check('sdat2img 转换', t_sdat2img)
    check('fsutil 只读删除', t_fsutil)
    check('单实例锁', t_singleton)
    check('固件格式识别', t_detect)
    check('加密 OZIP → 卡刷包', t_ozip_encrypted)
    check('加密 OZIP → 镜像展开', t_ozip_img)
    check('明文 OZIP 直出', t_ozip_plain)
    check('OFP → 分区导出', t_ofp)
    check('OPS → 分区导出', t_ops)
    check('CLI 契约', t_cli)
    check('GitHub / Gitee 更新源配置', t_update)
    if SKIP_GUI:
        for name in ('GUI 冒烟', 'GUI 端到端解密'):
            RESULTS.append((None, name, 'OPPO_SKIP_GUI=1'))
            print(f'[SKIP] {name} — OPPO_SKIP_GUI=1')
    else:
        check('GUI 冒烟', t_gui)
        check('GUI 端到端解密', t_gui_decrypt)

    failed = [r for r in RESULTS if r[0] is False]
    skipped = [r for r in RESULTS if r[0] is None]
    print(f'\n合计 {len(RESULTS)} 项：通过 {len(RESULTS) - len(failed) - len(skipped)}，'
          f'失败 {len(failed)}，跳过 {len(skipped)}')
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
