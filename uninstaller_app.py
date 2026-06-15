import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP_NAME = "SFACG Downloader"
MAIN_EXE = "SFACG Downloader.exe"
UNINSTALLER_EXE = "Uninstall SFACG Downloader.exe"
CREATED_NAMES = ("cache", "Downloads", "cookie.txt", "ui_settings.json")


def is_windows() -> bool:
    return sys.platform.startswith("win")


def message_box(text: str, title: str = APP_NAME, flags: int = 0x40) -> int:
    if is_windows():
        return ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    print(f"{title}: {text}")
    return 1


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except PermissionError:
            pass


def remove_created_files(exe_dir: Path) -> None:
    for name in CREATED_NAMES:
        remove_path(exe_dir / name)


def create_self_delete_script(main_exe: Path, uninstaller_exe: Path, exe_dir: Path) -> Path:
    script = Path(tempfile.gettempdir()) / f"sfacg_uninstall_{os.getpid()}.bat"
    script.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"MAIN=%~1\"\r\n"
        "set \"UNINSTALLER=%~2\"\r\n"
        "set \"EXE_DIR=%~3\"\r\n"
        "for /l %%i in (1,1,80) do (\r\n"
        "  del /f /q \"%MAIN%\" >nul 2>nul\r\n"
        "  del /f /q \"%UNINSTALLER%\" >nul 2>nul\r\n"
        "  if not exist \"%MAIN%\" if not exist \"%UNINSTALLER%\" goto cleanup\r\n"
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        ")\r\n"
        ":cleanup\r\n"
        "rmdir /s /q \"%EXE_DIR%\\cache\" >nul 2>nul\r\n"
        "rmdir /s /q \"%EXE_DIR%\\Downloads\" >nul 2>nul\r\n"
        "del /f /q \"%EXE_DIR%\\cookie.txt\" >nul 2>nul\r\n"
        "del /f /q \"%EXE_DIR%\\ui_settings.json\" >nul 2>nul\r\n"
        "del /f /q \"%~f0\" >nul 2>nul\r\n",
        encoding="ascii",
    )
    return script


def main() -> None:
    exe_dir = Path(sys.executable).resolve().parent
    if not is_windows():
        remove_created_files(exe_dir)
        return
    if "--from-app" not in sys.argv:
        answer = message_box(
            "Remove SFACG Downloader, saved session, cache, and default Downloads folder next to the executable?\n\nFiles exported to custom folders are not removed.",
            "Uninstall SFACG Downloader",
            0x21 | 0x30,
        )
        if answer != 1:
            return
    main_exe = exe_dir / MAIN_EXE
    uninstaller_exe = Path(sys.executable).resolve()
    remove_created_files(exe_dir)
    script = create_self_delete_script(main_exe, uninstaller_exe, exe_dir)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    subprocess.Popen(
        ["cmd.exe", "/d", "/q", "/c", str(script), str(main_exe), str(uninstaller_exe), str(exe_dir)],
        close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        startupinfo=startupinfo,
    )


if __name__ == "__main__":
    main()
