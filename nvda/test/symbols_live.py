"""Run actual NVDA symbol processing on a private, invisible Windows desktop.

Requires --runtime pointing to a portable NVDA executable and --addon pointing
to an extracted package. Never changes, stops or starts the installed NVDA.
Artifacts and a fresh test profile remain under --out for inspection.
"""
import argparse
import ctypes
from ctypes import wintypes as w
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
        ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
        ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD),
        ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD), ("dwFlags", w.DWORD),
        ("wShowWindow", w.WORD), ("cbReserved2", w.WORD), ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE),
                ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--addon", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("build/live-symbols"))
    p.add_argument("--secure", action="store_true")
    a = p.parse_args()
    runtime, addon = a.runtime.resolve(), a.addon.resolve()
    assert runtime.is_file() and (addon / "manifest.ini").is_file()
    a.out.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="symbols-", dir=a.out.resolve()))
    target = profile / "addons/openevv"
    shutil.copytree(addon, target)
    shutil.copyfile(Path(__file__).with_name("symbol_probe.py"), target / "globalPlugins/symbolProbe.py")
    (profile / "nvda.ini").write_text("""[general]
showWelcomeDialogAtStartup = False
saveConfigurationOnExit = False
askToExit = False
playStartAndExitSounds = False
[speech]
synth = openevv
symbolLevel = 0
    [[openevv]]
    volume = 0
    language = de_DE
    voice = 1
    samplerate = 11025
[update]
autoCheck = False
startupNotification = False
askedAllowUsageStats = True
allowUsageStats = False
[mouse]
enableMouseTracking = False
[braille]
display = noBraille
""", encoding="utf-8")
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.CreateDesktopW.argtypes = [w.LPCWSTR, w.LPCWSTR, ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.c_void_p]
    user.CreateDesktopW.restype = w.HANDLE
    user.CloseDesktop.argtypes = [w.HANDLE]
    kernel.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL,
        w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcessInfo)]
    kernel.CreateProcessW.restype = w.BOOL
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    name = "OpenEVVSymbols_%d" % time.time_ns()
    desktop = user.CreateDesktopW(name, None, None, 0, 0x1ff, None)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    pi, si = ProcessInfo(), StartupInfo()
    si.cb, si.lpDesktop, si.dwFlags, si.wShowWindow = ctypes.sizeof(si), "winsta0\\" + name, 1, 0
    args = [str(runtime), "--config-path=" + str(profile), "--log-file=" + str(profile / "nvda.log"),
            "--minimal", "--no-sr-flag"]
    if a.secure:
        args.append("--secure")
    try:
        if not kernel.CreateProcessW(str(runtime), ctypes.create_unicode_buffer(subprocess.list2cmdline(args)),
            None, None, False, 0x08000000, None, str(runtime.parent), ctypes.byref(si), ctypes.byref(pi)):
            raise ctypes.WinError(ctypes.get_last_error())
        print("Isolated profile:", profile, flush=True)
        deadline = time.monotonic() + 120
        while kernel.WaitForSingleObject(pi.hProcess, 100) != 0:
            if time.monotonic() > deadline:
                raise TimeoutError("Isolated NVDA symbol test did not finish")
        result = json.loads((profile / "symbol-results.json").read_text(encoding="utf-8"))
        assert not result["error"], result["error"]
        assert len(result["rows"]) >= 17
        print("PASS: real NVDA symbols, verbosity, character navigation, language switches and user override", flush=True)
    finally:
        if pi.hProcess:
            if kernel.WaitForSingleObject(pi.hProcess, 0) != 0:
                kernel.TerminateProcess(pi.hProcess, 1)  # Only the child created above.
                kernel.WaitForSingleObject(pi.hProcess, 5000)
            kernel.CloseHandle(pi.hThread)
            kernel.CloseHandle(pi.hProcess)
        user.CloseDesktop(desktop)


if __name__ == "__main__":
    main()
