#!/usr/bin/env python3
"""
Tablet Spoof Patcher (GUI)
.apkm 해제 -> LSPatch + TabletSpoof 패치 -> (선택) USB로 adb 자동 설치

필요한 도구(Java 21, LSPatch, TabletSpoof, adb)는 최초 실행 시 공식 배포처에서
자동으로 내려받아 tools 폴더에 저장합니다. 프로그램 안에는 포함하지 않습니다.
"""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:
    HAS_DND = False

BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
TOOLS = BASE / "tools"
TMP = BASE / "_work"
OUT = BASE / "output"

JRE_URL = "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jre/hotspot/normal/eclipse"
ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
DEPS = {
    "lspatch": ("JingMatrix/LSPatch", r"\.jar$", "lspatch.jar"),
    "spoof": ("miner7222/TabletSpoof", r"\.apk$", "TabletSpoof.apk"),
}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PatchError(Exception):
    pass


# ---------------------------------------------------------------- 다운로드/도구
def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tablet-spoof-patcher"})
    return urllib.request.urlopen(req, timeout=120)


def download(url, dest, log, label):
    log(f"{label} 다운로드 중...")
    part = dest.with_name(dest.name + ".part")
    with http_get(url) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    part.replace(dest)


def unzip_top_folder(zip_path, target):
    """zip 안의 최상위 폴더 하나를 target 으로 옮긴다."""
    tmp = TOOLS / "_unzip_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    top = next(p for p in tmp.iterdir() if p.is_dir())
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(top), str(target))
    shutil.rmtree(tmp, ignore_errors=True)


def ensure_jre(log):
    java = TOOLS / "jre" / "bin" / "java.exe"
    if java.exists():
        return str(java)
    TOOLS.mkdir(exist_ok=True)
    z = TOOLS / "jre.zip"
    try:
        download(JRE_URL, z, log, "Java 21 (약 50MB)")
        unzip_top_folder(z, TOOLS / "jre")
    except Exception as e:
        raise PatchError(f"Java 다운로드 실패: {e}")
    finally:
        z.unlink(missing_ok=True)
    if not java.exists():
        raise PatchError("Java 설치에 실패했습니다.")
    return str(java)


def ensure_adb(log):
    sysadb = shutil.which("adb")
    if sysadb:
        return sysadb
    adb = TOOLS / "platform-tools" / "adb.exe"
    if adb.exists():
        return str(adb)
    TOOLS.mkdir(exist_ok=True)
    z = TOOLS / "platform-tools.zip"
    try:
        download(ADB_URL, z, log, "adb (platform-tools)")
        unzip_top_folder(z, TOOLS / "platform-tools")
    except Exception as e:
        raise PatchError(f"adb 다운로드 실패: {e}")
    finally:
        z.unlink(missing_ok=True)
    if not adb.exists():
        raise PatchError("adb 설치에 실패했습니다.")
    return str(adb)


def ensure_tool(key, log):
    repo, pattern, filename = DEPS[key]
    dest = TOOLS / filename
    if dest.exists():
        return dest
    TOOLS.mkdir(exist_ok=True)
    log(f"{filename} 다운로드 중...")
    try:
        with http_get(f"https://api.github.com/repos/{repo}/releases?per_page=10") as r:
            releases = json.load(r)
        assets = []
        for rel in releases:
            assets = [a for a in rel.get("assets", []) if re.search(pattern, a["name"], re.I)]
            if assets:
                break
        if not assets:
            raise RuntimeError("일치하는 릴리스 파일 없음")
        with http_get(assets[0]["browser_download_url"]) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise PatchError(
            f"{filename} 자동 다운로드 실패: {e}\n"
            f"https://github.com/{repo}/releases 에서 받아\n{dest} 로 저장하세요."
        )
    return dest


# ---------------------------------------------------------------- 실행 도우미
def run(cmd, log, check=True):
    log("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    if p.returncode != 0 and check:
        log(p.stdout.strip())
        log(p.stderr.strip())
        tail = [l for l in (p.stderr + "\n" + p.stdout).splitlines() if l.strip()]
        raise PatchError(f"명령 실패 (code {p.returncode})\n" + (tail[-1] if tail else ""))
    return p


def pick_device(adb, log):
    try:
        subprocess.run([adb, "start-server"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=NO_WINDOW, timeout=30)
    except Exception:
        pass
    p = run([adb, "devices"], log)
    devs = []
    for line in p.stdout.splitlines():
        if "\t" in line and not line.startswith("*"):
            serial, state = line.split("\t", 1)
            devs.append((serial.strip(), state.strip()))
    ready = [s for s, st in devs if st == "device"]
    if ready:
        log(f"기기 연결됨: {ready[0]}" + (f" (외 {len(ready) - 1}대)" if len(ready) > 1 else ""))
        return ready[0]
    if any(st == "unauthorized" for _, st in devs):
        raise PatchError("기기 화면에 뜬 'USB 디버깅 허용'을 누른 뒤 다시 시도하세요.")
    raise PatchError("연결된 기기가 없습니다.\nUSB 케이블 연결과 '개발자 옵션 > USB 디버깅'을 확인하세요.")


# ---------------------------------------------------------------- 메인 작업
def read_pkg(src: Path):
    """APKMirror 번들(.apkm)의 info.json 에서 패키지명을 읽는다."""
    try:
        with zipfile.ZipFile(src) as z:
            return json.loads(z.read("info.json").decode("utf-8")).get("pname")
    except Exception:
        return None


def patch(src: Path, log, step, do_install, do_uninstall):
    if not src.exists():
        raise PatchError(f"파일 없음: {src}")

    step(0.03, "도구 준비 중")
    java = ensure_jre(log)
    step(0.10, "도구 준비 중")
    lspatch = ensure_tool("lspatch", log)
    step(0.15, "도구 준비 중")
    spoof = ensure_tool("spoof", log)

    adb = serial = None
    if do_install:
        step(0.18, "기기 확인 중")
        adb = ensure_adb(log)
        serial = pick_device(adb, log)

    if TMP.exists():
        shutil.rmtree(TMP)
    srcdir = TMP / "src"
    srcdir.mkdir(parents=True)
    OUT.mkdir(exist_ok=True)

    pkg = read_pkg(src)
    if pkg:
        log(f"패키지: {pkg}")
    step(0.25, "apkm 압축 해제 중")
    if src.suffix.lower() == ".apk":
        apks = [src]
    else:
        apks = []
        try:
            with zipfile.ZipFile(src) as z:
                for n in z.namelist():
                    if n.lower().endswith(".apk") and "/" not in n:
                        z.extract(n, srcdir)
                        apks.append(srcdir / n)
        except zipfile.BadZipFile:
            raise PatchError("올바른 apkm 파일이 아닙니다.")
    if not apks:
        raise PatchError("apkm 안에 APK가 없습니다.")
    apks.sort(key=lambda p: (p.name != "base.apk", p.name))
    log(f"APK {len(apks)}개 발견")

    step(0.35, "LSPatch 패치 중 (수 분 걸릴 수 있음)")
    pdir = TMP / "patched"
    pdir.mkdir()
    run([java, "-jar", lspatch, *apks, "-m", spoof, "-l", "2", "-f", "-o", pdir], log)
    results = sorted(pdir.glob("*.apk"))
    if not results:
        raise PatchError("패치된 APK가 생성되지 않았습니다.")

    step(0.75, "결과 정리 중")
    outdir = OUT / f"{src.stem}-spoofed"
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir()
    for r in results:
        shutil.copy2(r, outdir / r.name)
    bundle = OUT / f"{src.stem}-spoofed.apks"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        for r in results:
            z.write(r, r.name)
    shutil.rmtree(TMP, ignore_errors=True)

    installed = False
    if do_install:
        files = sorted(outdir.glob("*.apk"))
        if do_uninstall:
            if pkg:
                step(0.85, "기존 앱 삭제 중")
                run([adb, "-s", serial, "uninstall", pkg], log, check=False)
            else:
                log("패키지명을 알 수 없어 기존 앱 삭제는 건너뜁니다. 직접 삭제해 주세요.")
        step(0.9, "기기에 설치 중 (1~2분)")
        p = run([adb, "-s", serial, "install-multiple", *files], log)
        if "Success" not in p.stdout:
            log(p.stdout.strip())
            raise PatchError("설치에 실패했습니다. 로그를 확인하세요.\n(기존 앱이 남아 있으면 서명 충돌이 납니다.)")
        installed = True

    step(1.0, "완료")
    return bundle, installed


# ---------------------------------------------------------------- GUI
class App:
    def __init__(self, root):
        self.root = root
        root.title("Tablet Spoof Patcher")
        root.geometry("520x440")
        root.minsize(420, 340)

        self.path = tk.StringVar()
        self.status = tk.StringVar(value="대기 중")
        self.auto_install = tk.BooleanVar(value=True)
        self.uninstall_first = tk.BooleanVar(value=True)
        self.q = queue.Queue()

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)

        row = ttk.Frame(frm)
        row.pack(fill="x")
        self.entry = ttk.Entry(row, textvariable=self.path)
        self.entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾기", command=self.browse).pack(side="left", padx=(6, 0))

        hint = "apkm 파일을 여기에 드롭하거나 [찾기]" if HAS_DND else "[찾기]로 apkm 파일 선택"
        ttk.Label(frm, text=hint, foreground="#888").pack(anchor="w", pady=(4, 6))

        ttk.Checkbutton(frm, text="패치 후 USB로 기기에 자동 설치",
                        variable=self.auto_install, command=self.sync_opts).pack(anchor="w")
        self.un_cb = ttk.Checkbutton(frm, text="기존 앱 먼저 삭제 (앱 데이터 삭제됨)",
                                     variable=self.uninstall_first)
        self.un_cb.pack(anchor="w", padx=(20, 0), pady=(0, 8))

        self.btn = ttk.Button(frm, text="패치 시작", command=self.start)
        self.btn.pack(fill="x")

        self.bar = ttk.Progressbar(frm, maximum=1.0)
        self.bar.pack(fill="x", pady=(10, 2))
        ttk.Label(frm, textvariable=self.status).pack(anchor="w")

        self.logbox = tk.Text(frm, height=10, state="disabled", wrap="word", font=("Consolas", 9))
        self.logbox.pack(fill="both", expand=True, pady=(8, 0))

        self.open_btn = ttk.Button(frm, text="출력 폴더 열기", command=self.open_out)

        if HAS_DND:
            for w in (root, self.entry, self.logbox):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop)

        self.root.after(100, self.poll)

    def sync_opts(self):
        self.un_cb.config(state="normal" if self.auto_install.get() else "disabled")

    def browse(self):
        p = filedialog.askopenfilename(
            title="apkm 파일 선택",
            filetypes=[("APKM / APK 번들", "*.apkm *.xapk *.apks"), ("모든 파일", "*.*")])
        if p:
            self.path.set(p)

    def on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.path.set(files[0])

    def log(self, msg):
        self.q.put(("log", msg))

    def step(self, frac, text):
        self.q.put(("step", (frac, text)))

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.logbox.config(state="normal")
                    self.logbox.insert("end", val + "\n")
                    self.logbox.see("end")
                    self.logbox.config(state="disabled")
                elif kind == "step":
                    self.bar["value"] = val[0]
                    self.status.set(val[1])
                elif kind == "done":
                    bundle, installed = val
                    self.btn.config(state="normal")
                    self.open_btn.pack(fill="x", pady=(8, 0))
                    if installed:
                        messagebox.showinfo("완료", "패치 및 기기 설치가 완료되었습니다.")
                    else:
                        messagebox.showinfo(
                            "완료",
                            f"{bundle}\n\nSAI로 위 .apks 파일을 설치하세요.\n"
                            "설치 전 기존 앱을 삭제해야 합니다(서명 변경).")
                elif kind == "error":
                    self.btn.config(state="normal")
                    self.status.set("실패")
                    messagebox.showerror("오류", val)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def start(self):
        p = self.path.get().strip().strip('"')
        if not p:
            messagebox.showwarning("알림", "apkm 파일을 선택하세요.")
            return
        do_install = self.auto_install.get()
        do_un = do_install and self.uninstall_first.get()
        if do_un and not messagebox.askyesno(
                "확인", "기기에 설치된 기존 앱을 삭제합니다.\n앱 데이터(로컬 대화 등)가 지워지니 백업했는지 확인하세요.\n\n계속할까요?"):
            return
        self.btn.config(state="disabled")
        self.open_btn.pack_forget()
        self.bar["value"] = 0
        self.logbox.config(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.config(state="disabled")
        threading.Thread(target=self.worker, args=(Path(p), do_install, do_un), daemon=True).start()

    def worker(self, src, do_install, do_un):
        try:
            self.q.put(("done", patch(src, self.log, self.step, do_install, do_un)))
        except PatchError as e:
            self.q.put(("error", str(e)))
        except Exception as e:
            self.q.put(("error", f"예기치 않은 오류: {e}"))

    def open_out(self):
        OUT.mkdir(exist_ok=True)
        os.startfile(OUT)


def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
