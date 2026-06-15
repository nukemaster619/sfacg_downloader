import ctypes
import io
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

APP_NAME = "SFACG Downloader"

def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

APP_DIR = runtime_dir()
APP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = APP_DIR / "Downloads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR_PATH = APP_DIR / "cache"
CACHE_DIR_PATH.mkdir(parents=True, exist_ok=True)
COOKIE_FILE_PATH = APP_DIR / "cookie.txt"
APP_SETTINGS_FILE = APP_DIR / "ui_settings.json"
CREATED_FILE_PATHS = (OUTPUT_DIR, CACHE_DIR_PATH, COOKIE_FILE_PATH, APP_SETTINGS_FILE)

def load_ui_settings() -> Dict[str, object]:
    try:
        import json
        if APP_SETTINGS_FILE.exists():
            data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_ui_settings(data: Dict[str, object]) -> None:
    try:
        import json
        APP_SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

import config
config.COOKIE_FILE = COOKIE_FILE_PATH
config.CACHE_DIR = str(CACHE_DIR_PATH)

from config import DEFAULT_MAX_THREADS, set_language, tr
from models import ChapterContent, NovelCatalog, SelectedVolume
from api import SfacgClient
from exporter import (
    build_output_filename,
    chapter_to_xhtml,
    collect_unique_image_urls,
    download_images,
)
from ebooklib import epub

from PySide6.QtCore import QByteArray, QEasingCurve, QPoint, QPropertyAnimation, Qt, QThread, QTimer, Signal, QSize
from PySide6.QtGui import QAction, QCloseEvent, QColor, QCursor, QDesktopServices, QFont, QIcon, QPixmap, QPainter, QTextCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QTextBrowser,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMenu,
    QSlider,
)

try:
    import html
    import uuid
except Exception:
    html = None
    uuid = None

TEXT = {
    "zh": {
        "language_title": "选择语言",
        "language_sub": "选择界面语言。",
        "continue": "继续",
        "login_title": "登录账号",
        "login_sub": "登录后可访问 SF轻小说。保存的会话会在下次启动时自动使用。",
        "phone": "手机号",
        "password": "密码",
        "sign_in": "登录",
        "checking_session": "正在检查保存的会话...",
        "session_skipped": "未找到保存的会话，请登录。",
        "saved_session_ok": "已通过保存的会话登录。",
        "saved_session_bad": "保存的会话无效，请重新登录。",
        "login_failed": "登录失败。请检查手机号或密码。",
        "login_ok": "登录成功。",
        "novel_title": "小说查询",
        "novel_sub": "输入小说 ID，或粘贴包含 ID 的 SFACG 小说网址。",
        "novel_id": "小说 ID",
        "fetch": "获取",
        "fetching": "正在获取...",
        "select_download": "选择下载",
        "different_novel": "换一本",
        "not_found": "未找到小说或目录为空。请检查 ID。",
        "selection_title": "选择分卷与章节",
        "selection_sub": "勾选分卷会默认下载整卷。展开后可只选择部分章节。",
        "select_all": "全选",
        "deselect_all": "全不选",
        "back": "返回",
        "start_download": "开始下载",
        "no_selection": "请至少选择一个章节或一个分卷。",
        "selected_summary": "已选择 {volumes} 卷，{chapters} 章",
        "all_chapters": "全章",
        "download_title": "下载进度",
        "download_sub": "下载期间不能返回。取消会保留已缓存章节。",
        "cancel": "取消",
        "cancel_download": "取消下载",
        "cancel_confirm_title": "停止下载？",
        "cancel_confirm_text": "已缓存章节会保留。是否停止新的下载请求？",
        "stop": "停止",
        "continue_download": "继续",
        "complete_title": "下载完成",
        "complete_sub": "{title} · {volumes} 卷 · {chapters} 章 · {failed} 个失败占位符",
        "open_folder": "打开文件夹",
        "another": "下载另一本",
        "quit": "退出",
        "minimize": "最小化",
        "hide": "隐藏到托盘",
        "restore": "显示窗口",
        "fullscreen": "全屏",
        "exit_fullscreen": "退出全屏",
        "output_folder": "输出文件夹",
        "choose_folder": "选择",
        "threads": "线程",
        "threads_help": "线程决定同时下载多少章节。数值越高越快，但也更容易触发限流。",
        "uninstall": "卸载",
        "uninstall_title": "卸载 SFACG Downloader？",
        "uninstall_text": "这将移除程序可执行文件、卸载程序、保存的会话、缓存、设置，以及此程序目录里的默认 Downloads 文件夹。导出到其他文件夹的文件不会被删除。",
        "initializing": "正在初始化请求签名...",
        "downloading_volume": "正在下载 {title}",
        "volume_complete": "{title} 完成",
        "writing": "正在生成内置预览...",
        "viewer_title": "内容预览",
        "viewer_sub": "Rendered Preview",
        "preview_label": "预览",
        "preview_txt": "TXT",
        "preview_epub": "EPUB",
        "export_ok": "已导出 {count} 个文件。",
        "save_txt": "导出 TXT",
        "save_epub": "导出 EPUB",
        "save_both": "导出全部",
        "saved_file": "已导出：{path}",
        "save_failed": "导出失败：{error}",
        "fatal": "发生错误：{error}",
        "paid": "付费",
        "free": "已解锁",
        "chapters": "{count} 章",
        "author_unknown": "未知作者",
        "id_label": "ID: {id}",
        "done": "完成",
        "cached": "缓存",
        "locked": "付费章节，已插入占位符",
        "failed": "下载失败，已插入占位符",
    },
    "en": {
        "language_title": "Choose language",
        "language_sub": "Choose the interface language.",
        "continue": "Continue",
        "login_title": "Sign in",
        "login_sub": "Sign in to access SFACG. Saved sessions are reused on the next launch.",
        "phone": "Phone number",
        "password": "Password",
        "sign_in": "Sign in",
        "checking_session": "Checking saved session...",
        "session_skipped": "No saved session found. Sign in to continue.",
        "saved_session_ok": "Signed in with saved session.",
        "saved_session_bad": "Saved session is invalid. Sign in again.",
        "login_failed": "Login failed. Check your phone number or password.",
        "login_ok": "Signed in.",
        "novel_title": "Novel lookup",
        "novel_sub": "Enter a novel ID, or paste an SFACG novel URL containing the ID.",
        "novel_id": "Novel ID",
        "fetch": "Fetch",
        "fetching": "Fetching...",
        "select_download": "Select download",
        "different_novel": "Different novel",
        "not_found": "Novel not found or catalog is empty. Check the ID.",
        "selection_title": "Select volumes and chapters",
        "selection_sub": "Checking a volume downloads the whole volume by default. Expand it to pick chapters.",
        "select_all": "Select all",
        "deselect_all": "Deselect all",
        "back": "Back",
        "start_download": "Start download",
        "no_selection": "Select at least one chapter or volume.",
        "selected_summary": "Selected {volumes} volumes, {chapters} chapters",
        "all_chapters": "All chapters",
        "download_title": "Download progress",
        "download_sub": "You cannot go back during download. Cancel keeps cached chapters.",
        "cancel": "Cancel",
        "cancel_download": "Cancel download",
        "cancel_confirm_title": "Stop download?",
        "cancel_confirm_text": "Cached chapters will be kept. Stop new download requests?",
        "stop": "Stop",
        "continue_download": "Continue",
        "complete_title": "Download complete",
        "complete_sub": "{title} · {volumes} volumes · {chapters} chapters · {failed} failed placeholders",
        "open_folder": "Open folder",
        "another": "Download another novel",
        "quit": "Quit",
        "minimize": "Minimize",
        "hide": "Hide to tray",
        "restore": "Show window",
        "fullscreen": "Fullscreen",
        "exit_fullscreen": "Exit fullscreen",
        "output_folder": "Output folder",
        "choose_folder": "Choose",
        "threads": "Threads",
        "threads_help": "Threads control how many chapters download at the same time. Higher can be faster, but may trigger rate limits more easily.",
        "uninstall": "Uninstall",
        "uninstall_title": "Uninstall SFACG Downloader?",
        "uninstall_text": "This will remove the app executable, the uninstaller, saved session, cache, settings, and the default Downloads folder in this app directory. Files exported to another folder will not be deleted.",
        "initializing": "Preparing request signature...",
        "downloading_volume": "Downloading {title}",
        "volume_complete": "{title} complete",
        "writing": "Building in-app preview...",
        "viewer_title": "Content preview",
        "viewer_sub": "Rendered Preview",
        "preview_label": "Preview",
        "preview_txt": "TXT",
        "preview_epub": "EPUB",
        "export_ok": "Exported {count} file(s).",
        "save_txt": "Export TXT",
        "save_epub": "Export EPUB",
        "save_both": "Export both",
        "saved_file": "Exported: {path}",
        "save_failed": "Export failed: {error}",
        "fatal": "Error: {error}",
        "paid": "Paid",
        "free": "Unlocked",
        "chapters": "{count} chapters",
        "author_unknown": "Unknown author",
        "id_label": "ID: {id}",
        "done": "Done",
        "cached": "Cache",
        "locked": "Paid chapter, placeholder inserted",
        "failed": "Download failed, placeholder inserted",
        "settings": "Settings",
        "settings_title": "Settings",
        "settings_download": "Download",
        "settings_appearance": "Appearance",
        "viewer_font_size": "Viewer font size",
        "viewer_font_hint": "For the content preview reader",
        "output_hint": "Where exported files are saved",
        "threads_hint": "Simultaneous chapter downloads",
        "about": "About",
        "version_license": "Version · License",
        "close": "Close",
        "chapters_nav": "Contents",
        "contents_nav": "Contents",
        "export_txt": "Export TXT",
        "export_epub": "Export EPUB",
        "export_both_arrow": "Export both ↗",
        "preview_hint_txt": "Rendered Preview",
        "preview_hint_epub": "Rendered Preview",
    },
}

# English strings for redesign-only keys.
TEXT["zh"].update({
    "settings": "设置",
    "settings_title": "设置",
    "settings_download": "下载",
    "settings_appearance": "外观",
    "viewer_font_size": "阅读器字号",
    "viewer_font_hint": "用于内容预览阅读器",
    "output_hint": "导出文件保存位置",
    "threads_hint": "同时下载章节数",
    "about": "关于",
    "version_license": "版本 · 许可",
    "close": "关闭",
    "chapters_nav": "目录",
    "contents_nav": "目录",
    "export_txt": "导出 TXT",
    "export_epub": "导出 EPUB",
    "export_both_arrow": "导出全部 ↗",
    "preview_hint_txt": "Rendered Preview",
    "preview_hint_epub": "Rendered Preview",
})

LANG = "zh"

def ui_text(key: str, **kwargs: object) -> str:
    value = TEXT.get(LANG, TEXT["zh"]).get(key, key)
    return value.format(**kwargs)


def set_ui_language(language: str) -> None:
    global LANG
    LANG = "en" if language == "en" else "zh"
    set_language(LANG)


SVG_ICONS: Dict[str, str] = {
    "gear": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8.2a3.8 3.8 0 1 0 0 7.6 3.8 3.8 0 0 0 0-7.6Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 0 1-4 0v-.09a1.7 1.7 0 0 0-1.03-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 0 1 0-4h.09A1.7 1.7 0 0 0 4.65 8.9a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.88.34H9a1.7 1.7 0 0 0 1-1.56V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.88V9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 1 1 0 4h-.09A1.7 1.7 0 0 0 19.4 15Z"/></svg>""",
    "phone": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07A19.5 19.5 0 0 1 5.15 12.8 19.8 19.8 0 0 1 2.08 4.2 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.12.91.33 1.8.62 2.65a2 2 0 0 1-.45 2.11L8.1 9.6a16 16 0 0 0 6.3 6.3l1.12-1.12a2 2 0 0 1 2.11-.45c.85.29 1.74.5 2.65.62A2 2 0 0 1 22 16.92Z"/></svg>""",
    "lock": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v2"/></svg>""",
    "folder": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6.5A2.5 2.5 0 0 1 5.5 4H9l2 2.5h7.5A2.5 2.5 0 0 1 21 9v8.5A2.5 2.5 0 0 1 18.5 20h-13A2.5 2.5 0 0 1 3 17.5Z"/></svg>""",
    "bolt": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4 14h7l-1 8 10-13h-7Z"/></svg>""",
    "trash": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/></svg>""",
    "fullscreen": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H3v5"/><path d="M16 3h5v5"/><path d="M21 16v5h-5"/><path d="M8 21H3v-5"/></svg>""",
    "fullscreen_exit": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3v6H3"/><path d="M15 3v6h6"/><path d="M21 15h-6v6"/><path d="M3 15h6v6"/></svg>""",
    "minimize": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round"><path d="M6 18h12"/></svg>""",
    "close": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12"/><path d="M18 6 6 18"/></svg>""",
    "hide": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>""",
    "book": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/><path d="M8 6h8"/><path d="M8 10h6"/></svg>""",
    "info": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>""",
    "app": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect x="10" y="10" width="236" height="236" rx="42" fill="#1a1714" stroke="#3e3a36" stroke-width="6"/><circle cx="192" cy="62" r="28" fill="#d94f3d"/><text x="128" y="166" text-anchor="middle" font-family="Microsoft YaHei, SimSun, serif" font-size="112" font-weight="700" fill="#f0ebe2">册</text></svg>""",
}


def render_svg_pixmap(svg: str, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap


def svg_icon(name: str, color: str = "#a89f92", size: int = 22) -> QIcon:
    template = SVG_ICONS.get(name, SVG_ICONS["book"])
    return QIcon(render_svg_pixmap(template.format(color=color), size))


def svg_pixmap(name: str, color: str = "#a89f92", size: int = 22) -> QPixmap:
    return render_svg_pixmap(SVG_ICONS.get(name, SVG_ICONS["book"]).format(color=color), size)


def app_icon() -> QIcon:
    return QIcon(render_svg_pixmap(SVG_ICONS["app"], 256))

def open_path(path: Path) -> None:
    path = path.resolve()
    if sys.platform.startswith("win"):
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def strip_novel_id(raw: str) -> str:
    raw = raw.strip()
    match = re.search(r"/Novel/(\d+)", raw, re.IGNORECASE)
    if match:
        return match.group(1)
    digits = re.findall(r"\d+", raw)
    return digits[-1] if digits else raw


def clean_xml_text(value: str) -> str:
    return html.escape(value or "", quote=True) if html else (value or "")


def content_to_xhtml_body(title: str, content: str, image_registry: Dict[str, str]) -> str:
    parts = [f"<h1>{clean_xml_text(title)}</h1>"]
    img_pattern = re.compile(r"\[img=(https?://.*?)(?:\[/img\]|$)", re.IGNORECASE)
    for raw_line in content.splitlines():
        line = raw_line.strip("\ufeff")
        match = img_pattern.search(line)
        if match:
            url = match.group(1).strip()
            src = image_registry.get(url)
            if src:
                parts.append(f'<p><img src="{clean_xml_text(src)}" alt="image"/></p>')
            else:
                parts.append(f"<p>{clean_xml_text(line)}</p>")
        elif line:
            parts.append(f"<p>{clean_xml_text(line)}</p>")
        else:
            parts.append("<p></p>")
    return "".join(parts)


def xhtml_document(title: str, body: str) -> str:
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!DOCTYPE html>',
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh">',
        '<head>',
        f'<title>{clean_xml_text(title)}</title>',
        '<meta charset="utf-8"/>',
        '<style>body{font-family:serif;line-height:1.8;margin:5%;}img{max-width:100%;height:auto;}h1,h2{line-height:1.35;}</style>',
        '</head>',
        f'<body>{body}</body>',
        '</html>',
    ])


def normalize_preview_text(value: str) -> str:
    value = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    lines = [line.rstrip() for line in value.split("\n")]
    compact: List[str] = []
    blank_count = 0
    for line in lines:
        if line.strip():
            compact.append(line)
            blank_count = 0
        else:
            blank_count += 1
            if blank_count <= 1 and compact:
                compact.append("")
    return "\n".join(compact).strip() + ("\n" if compact else "")


def chapter_text_to_preview_html(content: str) -> str:
    blocks: List[str] = []
    img_pattern = re.compile(r"\[img=(https?://.*?)(?:\[/img\]|$)", re.IGNORECASE)
    for raw_line in normalize_preview_text(content).splitlines():
        line = raw_line.strip()
        if not line:
            blocks.append('<p class="spacer"></p>')
            continue
        match = img_pattern.search(line)
        if match:
            url = match.group(1).strip()
            blocks.append(f'<p class="image-note">[Image] {clean_xml_text(url)}</p>')
        else:
            blocks.append(f'<p>{clean_xml_text(line)}</p>')
    return "".join(blocks)


def build_epub_preview_html(catalog: NovelCatalog, volume_payloads: Sequence[Tuple[int, str, List[ChapterContent]]]) -> str:
    css = """
    body{background:#1a1714;color:#f0ebe2;font-family:'Microsoft YaHei','SimSun',serif;font-size:15px;line-height:1.85;margin:0;padding:18px;}
    h1{font-size:24px;line-height:1.35;margin:0 0 6px;color:#f0ebe2;}
    h2{font-size:19px;line-height:1.35;margin:30px 0 12px;color:#d94f3d;border-bottom:1px solid #3e3a36;padding-bottom:8px;}
    h3{font-size:17px;line-height:1.45;margin:24px 0 10px;color:#f0ebe2;}
    p{margin:0 0 10px;}
    .meta{font-family:'Cascadia Mono','Consolas',monospace;color:#c9a84c;font-size:12px;margin-bottom:22px;}
    .toc{background:#2c2825;border:1px solid #3e3a36;border-radius:10px;padding:12px 16px;margin:18px 0 24px;}
    .toc-title{font-family:'Segoe UI','Microsoft YaHei',sans-serif;color:#a89f92;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;}
    .toc div{color:#a89f92;font-size:13px;margin:3px 0;}
    .spacer{height:8px;margin:0;}
    .image-note{font-family:'Cascadia Mono','Consolas',monospace;color:#c9a84c;background:#2c2825;border:1px solid #3e3a36;border-radius:6px;padding:8px;}
    """
    parts: List[str] = ["<!DOCTYPE html><html><head><meta charset='utf-8'/>", f"<style>{css}</style>", "</head><body>"]
    parts.append(f"<h1>{clean_xml_text(catalog.title)}</h1>")
    meta = f"ID: {catalog.novel_id}"
    if catalog.author:
        meta += f" · {catalog.author}"
    parts.append(f"<div class='meta'>{clean_xml_text(meta)}</div>")
    parts.append("<div class='toc'><div class='toc-title'>Preview contents</div>")
    for volume_index, volume_title, chapter_results in volume_payloads:
        parts.append(f"<div>V{volume_index} · {clean_xml_text(volume_title)} · {len(chapter_results)} chapters</div>")
    parts.append("</div>")
    for volume_index, volume_title, chapter_results in volume_payloads:
        parts.append(f"<h2>V{volume_index} · {clean_xml_text(volume_title)}</h2>")
        for chapter in chapter_results:
            parts.append(f"<h3 id='chapter-{chapter.chapter_id}'>{clean_xml_text(chapter.title)}</h3>")
            parts.append(chapter_text_to_preview_html(chapter.content))
    parts.append("</body></html>")
    return "".join(parts)


def build_epub_bytes(catalog: NovelCatalog, volume_payloads: Sequence[Tuple[int, str, List[ChapterContent]]], image_cache: Dict[str, Tuple[str, str, bytes]], cover_bytes: Optional[bytes]) -> bytes:
    image_registry: Dict[str, str] = {}
    image_items: List[Tuple[str, str, bytes]] = []
    used_names: set[str] = set()
    for url, (filename, media_type, data) in image_cache.items():
        safe_name = sanitize_unique_epub_name(filename, used_names)
        path = f"images/{safe_name}"
        image_registry[url] = path
        image_items.append((path, media_type, data))
    chapters: List[Tuple[str, str, str]] = []
    nav_links: List[Tuple[str, str]] = []
    spine_ids: List[str] = ["nav"]
    manifest_items: List[str] = []
    for volume_index, volume_title, chapter_results in volume_payloads:
        volume_id = f"vol_{volume_index}"
        volume_file = f"{volume_id}.xhtml"
        chapters.append((volume_id, volume_file, xhtml_document(volume_title, f"<h1>{clean_xml_text(volume_title)}</h1>")))
        nav_links.append((volume_file, volume_title))
        spine_ids.append(volume_id)
        for chapter in chapter_results:
            chapter_id = f"chap_{chapter.chapter_id}"
            chapter_file = f"{chapter_id}.xhtml"
            body = content_to_xhtml_body(chapter.title, chapter.content, image_registry)
            chapters.append((chapter_id, chapter_file, xhtml_document(chapter.title, body)))
            nav_links.append((chapter_file, chapter.title))
            spine_ids.append(chapter_id)
    nav_items = "".join(f'<li><a href="{clean_xml_text(href)}">{clean_xml_text(title)}</a></li>' for href, title in nav_links)
    nav_doc = xhtml_document("Contents", f'<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{nav_items}</ol></nav>')
    ncx_points = []
    for idx, (href, title) in enumerate(nav_links, start=1):
        ncx_points.append(f'<navPoint id="navPoint-{idx}" playOrder="{idx}"><navLabel><text>{clean_xml_text(title)}</text></navLabel><content src="{clean_xml_text(href)}"/></navPoint>')
    ncx_doc = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">',
        f'<head><meta name="dtb:uid" content="{clean_xml_text(catalog.novel_id)}"/></head>',
        f'<docTitle><text>{clean_xml_text(catalog.title)}</text></docTitle>',
        f'<navMap>{"".join(ncx_points)}</navMap>',
        '</ncx>',
    ])
    manifest_items.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    manifest_items.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
    for item_id, item_file, _content in chapters:
        manifest_items.append(f'<item id="{item_id}" href="{item_file}" media-type="application/xhtml+xml"/>')
    if cover_bytes:
        manifest_items.append('<item id="cover-image" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>')
    for i, (path, media_type, _data) in enumerate(image_items, start=1):
        manifest_items.append(f'<item id="img_{i}" href="{clean_xml_text(path)}" media-type="{clean_xml_text(media_type)}"/>')
    spine_items = "".join(f'<itemref idref="{item_id}"/>' for item_id in spine_ids)
    opf = "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">',
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">',
        f'<dc:identifier id="bookid">{clean_xml_text(catalog.novel_id)}</dc:identifier>',
        f'<dc:title>{clean_xml_text(catalog.title)}</dc:title>',
        '<dc:language>zh</dc:language>',
        f'<dc:creator>{clean_xml_text(catalog.author or "")}</dc:creator>',
        '</metadata>',
        f'<manifest>{"".join(manifest_items)}</manifest>',
        f'<spine toc="ncx">{spine_items}</spine>',
        '</package>',
    ])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        zf.writestr(mimetype_info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/nav.xhtml", nav_doc)
        zf.writestr("OEBPS/toc.ncx", ncx_doc)
        for item_id, item_file, content in chapters:
            zf.writestr(f"OEBPS/{item_file}", content)
        if cover_bytes:
            zf.writestr("OEBPS/images/cover.jpg", cover_bytes)
        for path, _media_type, data in image_items:
            zf.writestr(f"OEBPS/{path}", data)
    return buffer.getvalue()


def epub_bytes_to_preview_text(epub_data: bytes) -> str:
    def strip_markup(value: str) -> str:
        value = re.sub(r"<\s*(h[1-6]|p|br|div|li|tr|section|article|nav)\b[^>]*>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"<\s*/\s*(h[1-6]|p|div|li|tr|section|article|nav)\s*>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", "", value)
        if html:
            value = html.unescape(value)
        lines = [line.strip() for line in value.splitlines()]
        compact: List[str] = []
        blank = False
        for line in lines:
            if line:
                compact.append(line)
                blank = False
            elif not blank and compact:
                compact.append("")
                blank = True
        return "\n".join(compact).strip()

    try:
        with zipfile.ZipFile(io.BytesIO(epub_data), "r") as zf:
            names = zf.namelist()
            content_names = [name for name in names if name.lower().endswith((".xhtml", ".html", ".htm"))]
            content_names = [name for name in content_names if not name.lower().endswith("nav.xhtml")]
            content_names.sort(key=lambda name: (0 if "/vol_" in name else 1, name))
            parts: List[str] = ["EPUB PREVIEW", "", "Files:"]
            for name in names:
                parts.append(f"- {name}")
            parts.extend(["", "Content:", ""])
            for name in content_names:
                raw = zf.read(name).decode("utf-8", errors="replace")
                text = strip_markup(raw)
                if text:
                    parts.extend([f"===== {name} =====", text, ""])
            return "\n".join(parts).strip()
    except Exception as exc:
        return f"EPUB preview unavailable: {exc}"


def sanitize_unique_epub_name(filename: str, used: set[str]) -> str:
    base = re.sub(r'[^A-Za-z0-9._-]', '_', filename or 'image.jpg').strip('._') or 'image.jpg'
    stem, dot, ext = base.partition('.')
    ext = f'.{ext}' if dot else '.jpg'
    candidate = f"{stem}{ext}"
    index = 2
    while candidate.lower() in used:
        candidate = f"{stem}_{index}{ext}"
        index += 1
    used.add(candidate.lower())
    return candidate


class FramelessWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._drag_pos: Optional[QPoint] = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(480, 640)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 56:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class Worker(QThread):
    log = Signal(str, str)
    error = Signal(str)
    finished_ok = Signal(object)


class StartupWorker(Worker):
    state = Signal(bool)

    def run(self) -> None:
        try:
            client = SfacgClient()
            cookie = COOKIE_FILE_PATH.read_text(encoding="utf-8").strip() if COOKIE_FILE_PATH.exists() else ""
            if not cookie:
                self.log.emit(ui_text("session_skipped"), "info")
                self.finished_ok.emit(client)
                self.state.emit(False)
                return
            self.log.emit(ui_text("checking_session"), "info")
            client.set_cookie_string(cookie)
            try:
                data = client.get_json(f"{config.API_BASE}/user?", retries=1, timeout=4)
                logged_in = data.get("status", {}).get("httpCode") == 200
            except Exception:
                logged_in = False
            if logged_in:
                self.log.emit(ui_text("saved_session_ok"), "ok")
                self.finished_ok.emit(client)
                self.state.emit(True)
                return
            self.log.emit(ui_text("saved_session_bad"), "warn")
            self.finished_ok.emit(client)
            self.state.emit(False)
        except Exception as exc:
            self.error.emit(ui_text("fatal", error=exc))


class LoginWorker(Worker):
    def __init__(self, client: SfacgClient, phone: str, password: str) -> None:
        super().__init__()
        self.client = client
        self.phone = phone
        self.password = password

    def run(self) -> None:
        try:
            self.log.emit(ui_text("sign_in"), "info")
            cookie = self.client.login(self.phone.replace(" ", ""), self.password)
            if cookie == "error":
                self.error.emit(ui_text("login_failed"))
                return
            self.client.set_cookie_string(cookie)
            if not self.client.check_login():
                self.client.set_cookie_string("")
                self.error.emit(ui_text("login_failed"))
                return
            COOKIE_FILE_PATH.write_text(cookie, encoding="utf-8")
            self.log.emit(ui_text("login_ok"), "ok")
            self.finished_ok.emit(self.client)
        except Exception as exc:
            self.error.emit(ui_text("fatal", error=exc))


class CatalogWorker(Worker):
    def __init__(self, client: SfacgClient, novel_id: str) -> None:
        super().__init__()
        self.client = client
        self.novel_id = novel_id

    def run(self) -> None:
        try:
            self.client.set_download_user_agent()
            catalog = self.client.fetch_catalog(self.novel_id)
            if not catalog.volumes:
                self.error.emit(ui_text("not_found"))
                return
            self.finished_ok.emit(catalog)
        except Exception as exc:
            self.error.emit(ui_text("fatal", error=exc))


@dataclass
class DownloadResult:
    txt_name: str
    txt_text: str
    epub_name: str
    epub_bytes: bytes
    epub_preview_html: str
    volume_payloads: List[Tuple[int, str, List[ChapterContent]]]
    failed: int
    chapters: int
    volumes: int


class DownloadWorker(Worker):
    progress = Signal(int, int, int)

    def __init__(self, client: SfacgClient, catalog: NovelCatalog, selections: Sequence[SelectedVolume], output_dir: Path, max_threads: int) -> None:
        super().__init__()
        self.client = client
        self.catalog = catalog
        self.selections = list(selections)
        self.output_dir = output_dir
        self.max_threads = max_threads
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def run(self) -> None:
        try:
            result = self._build()
            if not self.cancelled:
                self.finished_ok.emit(result)
        except Exception as exc:
            self.error.emit(ui_text("fatal", error=exc))

    def _download_batch(self, chapters_info: List[Dict], novel_id: str, volume_index: int) -> Tuple[Dict[int, Dict], List[int]]:
        cache = self.client._load_cache(novel_id)
        success_dict: Dict[int, Dict] = {}
        failed_ids: List[int] = []
        to_download: List[Dict] = []
        done = 0
        total = len(chapters_info)
        for chapter in chapters_info:
            if self.cancelled:
                break
            chap_id = int(chapter["id"])
            chapter_title = chapter.get("title") or str(chap_id)
            need_fire = int(chapter.get("need_fire") or 0)
            if need_fire > 0:
                success_dict[chap_id] = {"id": chap_id, "title": chapter_title, "content": tr("locked_placeholder"), "locked": True}
                done += 1
                self.log.emit(f"⚠ [{chapter_title}] {ui_text('locked')}", "warn")
                self.progress.emit(volume_index, done, total)
            elif chap_id in cache:
                title, content = cache[chap_id]
                success_dict[chap_id] = {"id": chap_id, "title": title, "content": content}
                done += 1
                self.log.emit(f"✓ [{title}] {ui_text('cached')}", "ok")
                self.progress.emit(volume_index, done, total)
            else:
                to_download.append(chapter)
        if self.cancelled:
            return success_dict, failed_ids
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, self.max_threads)) as executor:
            future_map = {executor.submit(self.client.download_chapter, int(chapter["id"])): chapter for chapter in to_download}
            for future in concurrent.futures.as_completed(future_map):
                chapter = future_map[future]
                chap_id = int(chapter["id"])
                chapter_title = chapter.get("title") or str(chap_id)
                if self.cancelled:
                    future.cancel()
                    continue
                try:
                    ok, title, content = future.result()
                except Exception as exc:
                    self.log.emit(f"✗ [{chapter_title}] {exc}", "err")
                    failed_ids.append(chap_id)
                    done += 1
                    self.progress.emit(volume_index, done, total)
                    continue
                if ok and title is not None and content is not None:
                    final_title = title or chapter_title
                    success_dict[chap_id] = {"id": chap_id, "title": final_title, "content": content}
                    cache[chap_id] = (final_title, content)
                    self.log.emit(f"✓ [{final_title}] {ui_text('done')}", "ok")
                else:
                    self.log.emit(f"✗ [{chapter_title}] {ui_text('failed')}", "err")
                    failed_ids.append(chap_id)
                done += 1
                self.progress.emit(volume_index, done, total)
        self.client._save_cache(novel_id, cache)
        return success_dict, failed_ids

    def _build(self) -> DownloadResult:
        import html as html_module
        self.log.emit(tr("book_building"), "info")
        txt_parts: List[str] = [self.catalog.title, "", ""]
        epub_volumes: List[Tuple[int, str, List[ChapterContent]]] = []
        epub_images: Dict[str, Tuple[str, str, bytes]] = {}
        cover_bytes: Optional[bytes] = None
        if self.catalog.cover_url:
            self.log.emit(tr("fetching_cover"), "info")
            try:
                cover_bytes = self.client.fetch_binary(self.catalog.cover_url, retries=3)
                self.log.emit(tr("cover_done"), "ok")
            except Exception:
                self.log.emit(tr("cover_fetch_failed"), "warn")
        selected_by_volume = {selection.index: selection for selection in self.selections}
        failed_total = 0
        chapter_total = 0
        for volume in self.catalog.volumes:
            if self.cancelled:
                raise RuntimeError("Cancelled")
            selection = selected_by_volume.get(volume.index)
            if selection is None:
                continue
            self.log.emit(ui_text("downloading_volume", title=volume.title), "info")
            txt_parts.extend([volume.title, "", ""])
            wanted = set(range(1, len(volume.chapters) + 1)) if selection.chapter_indices is None else set(selection.chapter_indices)
            chapters_info = [
                {"id": ref.chapter_id, "title": ref.title_hint, "need_fire": ref.need_fire}
                for idx, ref in enumerate(volume.chapters, start=1)
                if idx in wanted
            ]
            chapter_total += len(chapters_info)
            success_dict, failed_ids = self._download_batch(chapters_info, self.catalog.novel_id, volume.index)
            failed_total += len(failed_ids)
            chapter_results: List[ChapterContent] = []
            for chapter_info in chapters_info:
                chapter_id = int(chapter_info["id"])
                result = success_dict.get(chapter_id)
                if result is None:
                    title = chapter_info.get("title") or str(chapter_id)
                    content = tr("chapter_failed_placeholder").format(chapter_id=chapter_id)
                    chapter_results.append(ChapterContent(chapter_id=chapter_id, title=title, content=content))
                else:
                    chapter_results.append(ChapterContent(chapter_id=chapter_id, title=result.get("title") or chapter_info.get("title") or str(chapter_id), content=result.get("content") or ""))
            image_cache = download_images(self.client, collect_unique_image_urls(chapter_results))
            epub_images.update(image_cache)
            for chapter in chapter_results:
                txt_parts.extend([chapter.title, chapter.content, "", ""])
            epub_volumes.append((volume.index, volume.title, chapter_results))
            self.log.emit(ui_text("volume_complete", title=volume.title), "ok")
        selection_tag = "[" + ";".join(selection.filename_label() for selection in self.selections) + "]"
        epub_name = build_output_filename(self.catalog.title, selection_tag, ".epub")
        txt_name = build_output_filename(self.catalog.title, selection_tag, ".txt")
        txt_text = normalize_preview_text("\n".join(txt_parts))
        self.log.emit(ui_text("writing"), "info")
        epub_bytes = build_epub_bytes(self.catalog, epub_volumes, epub_images, cover_bytes)
        epub_preview_html = build_epub_preview_html(self.catalog, epub_volumes)
        return DownloadResult(txt_name, txt_text, epub_name, epub_bytes, epub_preview_html, epub_volumes, failed_total, chapter_total, len(self.selections))


class TitleBar(QWidget):
    def __init__(self, app: "MainWindow") -> None:
        super().__init__()
        self.app = app
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(8)
        icon = QLabel("册")
        icon.setObjectName("titleIcon")
        title = QLabel(APP_NAME)
        title.setObjectName("titleText")
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addStretch(1)
        self.settings_btn = QToolButton()
        self.settings_btn.setIcon(svg_icon("gear"))
        self.settings_btn.setToolTip(ui_text("settings"))
        self.settings_btn.clicked.connect(app.open_settings)
        self.fullscreen_btn = QToolButton()
        self.fullscreen_btn.setIcon(svg_icon("fullscreen"))
        self.fullscreen_btn.setToolTip(ui_text("fullscreen"))
        self.fullscreen_btn.clicked.connect(app.toggle_fullscreen)
        self.min_btn = QToolButton()
        self.min_btn.setIcon(svg_icon("minimize"))
        self.min_btn.clicked.connect(app.showMinimized)
        self.hide_btn = QToolButton()
        self.hide_btn.setIcon(svg_icon("hide"))
        self.hide_btn.clicked.connect(app.hide)
        self.close_btn = QToolButton()
        self.close_btn.setIcon(svg_icon("close"))
        self.close_btn.clicked.connect(app.quit_app)
        app.title_bar = self
        for button in (self.settings_btn, self.fullscreen_btn, self.min_btn, self.hide_btn, self.close_btn):
            button.setObjectName("windowButton")
            button.setFixedSize(28, 28)
            button.setIconSize(QSize(18, 18))
            layout.addWidget(button)


class MainWindow(FramelessWindow):
    def __init__(self) -> None:
        super().__init__()
        self.client: Optional[SfacgClient] = None
        self.catalog: Optional[NovelCatalog] = None
        self.ui_settings = load_ui_settings()
        self.output_dir = Path(str(self.ui_settings.get("output_dir") or OUTPUT_DIR))
        self.viewer_font_size = int(self.ui_settings.get("viewer_font_size") or 15)
        self.previous_page_index = 0
        self.volume_widgets: Dict[int, Dict[str, object]] = {}
        self.download_worker: Optional[DownloadWorker] = None
        self.current_result: Optional[DownloadResult] = None
        self.preview_mode = "txt"
        self.active_worker: Optional[QThread] = None
        self.force_quit = False
        self.fullscreen_active = False
        self.normal_geometry_before_fullscreen = None
        self.tray_actions: Dict[str, QAction] = {}
        self._build_ui()
        self._setup_tray()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self))
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.toast_label = QLabel(root)
        self.toast_label.setObjectName("toast")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.hide()
        self.setCentralWidget(root)
        self._apply_style()
        self._screen_language()
        self._screen_splash()
        self._screen_login()
        self._screen_lookup()
        self._screen_selection()
        self._screen_download()
        self._screen_complete()
        self._screen_settings()
        self._refresh_language_texts()
        self.stack.setCurrentIndex(0)

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray_menu = QMenu()
        self.tray_actions["restore"] = QAction(ui_text("restore"), self)
        self.tray_actions["restore"].triggered.connect(self.showNormal)
        self.tray_actions["uninstall"] = QAction(ui_text("uninstall"), self)
        self.tray_actions["uninstall"].triggered.connect(self._confirm_uninstall)
        self.tray_actions["quit"] = QAction(ui_text("quit"), self)
        self.tray_actions["quit"].triggered.connect(self.quit_app)
        self.tray_menu.addAction(self.tray_actions["restore"])
        self.tray_menu.addAction(self.tray_actions["uninstall"])
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.tray_actions["quit"])
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def _refresh_tray_texts(self) -> None:
        if not self.tray_actions:
            return
        self.tray_actions["restore"].setText(ui_text("restore"))
        self.tray_actions["uninstall"].setText(ui_text("uninstall"))
        self.tray_actions["quit"].setText(ui_text("quit"))


    def _show_toast(self, message: str, kind: str = "ok") -> None:
        if not message:
            return
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        width = min(max(self.toast_label.width() + 34, 260), max(260, self.width() - 80))
        self.toast_label.setFixedWidth(width)
        self.toast_label.setFixedHeight(42)
        self.toast_label.move((self.width() - width) // 2, self.height() - 72)
        self.toast_label.raise_()
        self.toast_label.show()
        QTimer.singleShot(2600, self.toast_label.hide)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast_label") and self.toast_label.isVisible():
            self.toast_label.move((self.width() - self.toast_label.width()) // 2, self.height() - 72)

    def _go(self, index: int) -> None:
        old = self.stack.currentIndex() if hasattr(self, "stack") else 0
        self.stack.setCurrentIndex(index)
        if self.isFullScreen():
            return
        target = QSize(720, 640) if index == 6 else QSize(480, 640)
        if index == 4:
            target = QSize(480, 680)
        elif index == 5:
            target = QSize(480, 560)
        if self.size() != target:
            animation = QPropertyAnimation(self, b"size", self)
            animation.setDuration(220 if index == 6 or old == 6 else 160)
            animation.setStartValue(self.size())
            animation.setEndValue(target)
            animation.setEasingCurve(QEasingCurve.Type.OutQuart)
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def open_settings(self) -> None:
        self.previous_page_index = self.stack.currentIndex()
        self._refresh_settings_values()
        self._go(7)

    def close_settings(self) -> None:
        self._go(self.previous_page_index if self.previous_page_index != 7 else 3)

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_active = False
            if hasattr(self, "title_bar"):
                self.title_bar.fullscreen_btn.setIcon(svg_icon("fullscreen"))
            return
        self.normal_geometry_before_fullscreen = self.geometry()
        self.showFullScreen()
        self.fullscreen_active = True
        if hasattr(self, "title_bar"):
            self.title_bar.fullscreen_btn.setIcon(svg_icon("fullscreen_exit"))

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def _persist_ui_settings(self) -> None:
        self.ui_settings["output_dir"] = str(self.output_dir)
        self.ui_settings["viewer_font_size"] = int(self.viewer_font_size)
        if hasattr(self, "threads_combo"):
            self.ui_settings["threads"] = self.threads_combo.currentText()
        save_ui_settings(self.ui_settings)

    def quit_app(self) -> None:
        self.force_quit = True
        app = QApplication.instance()
        if app:
            app.quit()

    def _confirm_uninstall(self) -> None:
        box = QMessageBox(self)
        box.setWindowIcon(self.windowIcon())
        box.setWindowTitle(ui_text("uninstall_title"))
        box.setText(ui_text("uninstall_text"))
        remove = box.addButton(ui_text("uninstall"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(ui_text("cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == remove:
            self._run_uninstaller()

    def _run_uninstaller(self) -> None:
        exe_path = Path(sys.executable).resolve()
        uninstaller = exe_path.with_name("Uninstall SFACG Downloader.exe")
        created_paths = [str(path.resolve()) for path in CREATED_FILE_PATHS]
        if sys.platform.startswith("win") and uninstaller.exists():
            subprocess.Popen([str(uninstaller), "--from-app", "--target", str(exe_path), "--pid", str(os.getpid())], close_fds=True)
        else:
            if sys.platform.startswith("win"):
                script = Path(os.environ.get("TEMP", str(Path.home()))) / "uninstall_sfacg_downloader.bat"
                script.write_text(
                    "@echo off\r\n"
                    "setlocal\r\n"
                    "set EXE=%~1\r\n"
                    "set CACHE=%~2\r\n"
                    "set DOWNLOADS=%~3\r\n"
                    "set COOKIE=%~4\r\n"
                    "set SETTINGS=%~5\r\n"
                    ":waitloop\r\n"
                    "ping 127.0.0.1 -n 2 >nul\r\n"
                    'del /f /q "%EXE%" >nul 2>nul\r\n'
                    'if exist "%EXE%" goto waitloop\r\n'
                    'rmdir /s /q "%CACHE%" >nul 2>nul\r\n'
                    'rmdir /s /q "%DOWNLOADS%" >nul 2>nul\r\n'
                    'del /f /q "%COOKIE%" >nul 2>nul\r\n'
                    'del /f /q "%SETTINGS%" >nul 2>nul\r\n'
                    'del /f /q "%~f0" >nul 2>nul\r\n',
                    encoding="utf-8",
                )
                subprocess.Popen(["cmd", "/c", "start", "", "/min", str(script), str(exe_path), str(CACHE_DIR_PATH), str(OUTPUT_DIR), str(COOKIE_FILE_PATH), str(APP_SETTINGS_FILE)], close_fds=True)
            else:
                script = Path("/tmp") / "uninstall_sfacg_downloader.sh"
                cleanup = "\n".join([f"rm -rf '{path}'" for path in created_paths])
                script.write_text(f"#!/bin/sh\nsleep 2\nrm -f '{exe_path}'\n{cleanup}\nrm -f '$0'\n", encoding="utf-8")
                script.chmod(0o700)
                subprocess.Popen([str(script)], close_fds=True)
        self.quit_app()

    def _page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(18)
        self.stack.addWidget(page)
        return page

    def _heading(self, parent_layout: QVBoxLayout, title: str, sub: str) -> None:
        label = QLabel(title)
        label.setObjectName("h1")
        sublabel = QLabel(sub)
        sublabel.setObjectName("sub")
        sublabel.setWordWrap(True)
        parent_layout.addWidget(label)
        parent_layout.addWidget(sublabel)

    def _card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 80))
        card.setGraphicsEffect(shadow)
        return card

    def _screen_language(self) -> None:
        page = self._page()
        layout = page.layout()
        self._heading(layout, "墨 · Mò", "SFACG Downloader")
        layout.addStretch(1)
        card = self._card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 30, 34, 30)
        title = QLabel("选择语言 / Choose language")
        title.setObjectName("h2")
        card_layout.addWidget(title)
        self.lang_group = QButtonGroup(self)
        zh = QPushButton("中文")
        en = QPushButton("English")
        zh.setCheckable(True)
        en.setCheckable(True)
        zh.setChecked(True)
        zh.setObjectName("pill")
        en.setObjectName("pill")
        self.lang_group.addButton(zh, 1)
        self.lang_group.addButton(en, 2)
        row = QHBoxLayout()
        row.addWidget(zh)
        row.addWidget(en)
        card_layout.addLayout(row)
        btn = QPushButton("继续 / Continue")
        btn.setObjectName("primary")
        btn.clicked.connect(self._language_continue)
        card_layout.addWidget(btn)
        layout.addWidget(card)
        layout.addStretch(2)

    def _language_continue(self) -> None:
        set_ui_language("en" if self.lang_group.checkedId() == 2 else "zh")
        self._refresh_language_texts()
        self._go(1)
        self._run_startup()

    def _screen_splash(self) -> None:
        page = self._page()
        layout = page.layout()
        layout.addStretch(1)
        glyph = QLabel("册")
        glyph.setObjectName("splashGlyph")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.splash_status = QLabel()
        self.splash_status.setObjectName("sub")
        self.splash_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dots = QHBoxLayout()
        dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.splash_dots: List[QLabel] = []
        for text in ("●", "●", "●"):
            dot = QLabel(text)
            dot.setObjectName("splashDot")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dots.addWidget(dot)
            self.splash_dots.append(dot)
        layout.addWidget(glyph)
        layout.addWidget(self.splash_status)
        layout.addLayout(dots)
        layout.addStretch(1)

    def _screen_login(self) -> None:
        page = self._page()
        layout = page.layout()
        self.login_title = QLabel()
        self.login_title.setObjectName("h1")
        self.login_sub = QLabel()
        self.login_sub.setObjectName("sub")
        self.login_sub.setWordWrap(True)
        layout.addWidget(self.login_title)
        layout.addWidget(self.login_sub)
        layout.addStretch(1)
        self.login_card = self._card()
        form = QVBoxLayout(self.login_card)
        form.setContentsMargins(28, 28, 28, 28)
        form.setSpacing(12)
        self.phone_label = QLabel()
        self.phone_label.setObjectName("label")
        self.phone_input = QLineEdit()
        self.phone_input.setObjectName("iconInput")
        self.phone_input.setPlaceholderText("+86 …")
        self.password_label = QLabel()
        self.password_label.setObjectName("label")
        self.password_input = QLineEdit()
        self.password_input.setObjectName("iconInput")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        phone_wrap = self._icon_input("phone", self.phone_input)
        pass_wrap = self._icon_input("lock", self.password_input)
        self.login_status = QLabel("")
        self.login_status.setObjectName("inlineError")
        self.login_status.hide()
        self.login_button = QPushButton()
        self.login_button.setObjectName("primary")
        self.login_button.clicked.connect(self._login)
        form.addWidget(self.phone_label)
        form.addWidget(phone_wrap)
        form.addWidget(self.login_status)
        form.addWidget(self.password_label)
        form.addWidget(pass_wrap)
        form.addWidget(self.login_button)
        layout.addWidget(self.login_card)
        layout.addStretch(2)

    def _icon_input(self, icon_name: str, field: QLineEdit) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("inputWrap")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        icon = QLabel()
        icon.setObjectName("inputIcon")
        icon.setPixmap(svg_pixmap(icon_name, "#5a5247", 18))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedWidth(34)
        row.addWidget(icon)
        row.addWidget(field, 1)
        return wrap

    def _screen_lookup(self) -> None:
        page = self._page()
        layout = page.layout()
        self.lookup_title = QLabel()
        self.lookup_title.setObjectName("h1")
        self.lookup_sub = QLabel()
        self.lookup_sub.setObjectName("sub")
        self.lookup_sub.setWordWrap(True)
        layout.addWidget(self.lookup_title)
        layout.addWidget(self.lookup_sub)
        card = self._card()
        body = QVBoxLayout(card)
        body.setContentsMargins(26, 26, 26, 26)
        self.novel_id_label = QLabel()
        self.novel_id_label.setObjectName("label")
        row = QHBoxLayout()
        self.novel_id_input = QLineEdit()
        self.novel_id_input.setObjectName("monoInput")
        self.fetch_button = QPushButton()
        self.fetch_button.setObjectName("primary")
        self.fetch_button.clicked.connect(self._fetch_catalog)
        row.addWidget(self.novel_id_input, 1)
        row.addWidget(self.fetch_button)
        self.lookup_status = QLabel("")
        self.lookup_status.setObjectName("status")
        body.addWidget(self.novel_id_label)
        body.addLayout(row)
        body.addWidget(self.lookup_status)
        self.novel_card = QFrame()
        self.novel_card.setObjectName("novelCard")
        novel_layout = QHBoxLayout(self.novel_card)
        novel_layout.setContentsMargins(18, 18, 18, 18)
        self.cover = QLabel("册")
        self.cover.setObjectName("cover")
        self.cover.setFixedSize(92, 126)
        info = QVBoxLayout()
        self.fetched_title = QLabel("")
        self.fetched_title.setObjectName("novelTitle")
        self.fetched_meta = QLabel("")
        self.fetched_meta.setObjectName("sub")
        self.fetched_id = QLabel("")
        self.fetched_id.setObjectName("mono")
        button_row = QHBoxLayout()
        self.select_button = QPushButton()
        self.select_button.setObjectName("primarySmall")
        self.select_button.clicked.connect(self._show_selection)
        self.different_button = QPushButton()
        self.different_button.setObjectName("ghostSmall")
        self.different_button.clicked.connect(lambda: self.novel_card.hide())
        button_row.addWidget(self.select_button)
        button_row.addWidget(self.different_button)
        button_row.addStretch(1)
        info.addWidget(self.fetched_title)
        info.addWidget(self.fetched_meta)
        info.addWidget(self.fetched_id)
        info.addLayout(button_row)
        novel_layout.addWidget(self.cover)
        novel_layout.addLayout(info, 1)
        body.addWidget(self.novel_card)
        self.novel_card.hide()
        layout.addWidget(card)
        layout.addStretch(1)

    def _screen_selection(self) -> None:
        page = self._page()
        layout = page.layout()
        self.selection_title = QLabel()
        self.selection_title.setObjectName("h1")
        self.selection_sub = QLabel()
        self.selection_sub.setObjectName("sub")
        self.selection_sub.setWordWrap(True)
        layout.addWidget(self.selection_title)
        layout.addWidget(self.selection_sub)
        toolbar = QHBoxLayout()
        self.select_all_btn = QPushButton()
        self.select_all_btn.setObjectName("ghostSmall")
        self.select_all_btn.clicked.connect(lambda: self._set_all(True))
        self.deselect_all_btn = QPushButton()
        self.deselect_all_btn.setObjectName("ghostSmall")
        self.deselect_all_btn.clicked.connect(lambda: self._set_all(False))
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.deselect_all_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.selection_scroll = QScrollArea()
        self.selection_scroll.setWidgetResizable(True)
        self.selection_scroll.setObjectName("scroll")
        self.selection_content = QWidget()
        self.selection_layout = QVBoxLayout(self.selection_content)
        self.selection_layout.setContentsMargins(0, 0, 0, 0)
        self.selection_layout.setSpacing(8)
        self.selection_scroll.setWidget(self.selection_content)
        layout.addWidget(self.selection_scroll, 1)
        bottom = QHBoxLayout()
        self.selection_back = QPushButton()
        self.selection_back.setObjectName("ghost")
        self.selection_back.clicked.connect(lambda: self._go(3))
        self.selection_summary = QLabel("")
        self.selection_summary.setObjectName("status")
        self.download_button = QPushButton()
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self._start_download)
        bottom.addWidget(self.selection_back)
        bottom.addWidget(self.selection_summary, 1)
        bottom.addWidget(self.download_button)
        layout.addLayout(bottom)

    def _screen_download(self) -> None:
        page = self._page()
        layout = page.layout()
        self.download_title = QLabel()
        self.download_title.setObjectName("h1")
        self.download_sub = QLabel()
        self.download_sub.setObjectName("sub")
        self.download_sub.setWordWrap(True)
        layout.addWidget(self.download_title)
        layout.addWidget(self.download_sub)
        self.progress_area = QScrollArea()
        self.progress_area.setWidgetResizable(True)
        self.progress_area.setObjectName("scroll")
        self.progress_content = QWidget()
        self.progress_layout = QVBoxLayout(self.progress_content)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(10)
        self.progress_area.setWidget(self.progress_content)
        layout.addWidget(self.progress_area, 1)
        self.log_panel = QTextEdit()
        self.log_panel.setObjectName("log")
        self.log_panel.setReadOnly(True)
        layout.addWidget(self.log_panel, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_button = QPushButton()
        self.cancel_button.setObjectName("dangerGhost")
        self.cancel_button.clicked.connect(self._cancel_download)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)

    def _screen_complete(self) -> None:
        page = self._page()
        layout = page.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.viewer_top = QFrame()
        self.viewer_top.setObjectName("viewerTop")
        top = QHBoxLayout(self.viewer_top)
        top.setContentsMargins(16, 8, 16, 8)
        top.setSpacing(8)
        self.complete_title = QLabel()
        self.complete_title.setObjectName("viewerTitle")
        self.complete_sub = QLabel()
        self.complete_sub.setObjectName("viewerHint")
        self.preview_toggle_group = QButtonGroup(self)
        self.preview_txt_btn = QPushButton()
        self.preview_txt_btn.setObjectName("viewerTab")
        self.preview_txt_btn.setCheckable(True)
        self.preview_txt_btn.setChecked(True)
        self.preview_epub_btn = QPushButton()
        self.preview_epub_btn.setObjectName("viewerTab")
        self.preview_epub_btn.setCheckable(True)
        self.preview_toggle_group.addButton(self.preview_txt_btn, 1)
        self.preview_toggle_group.addButton(self.preview_epub_btn, 2)
        self.preview_toggle_group.idClicked.connect(self._set_preview_mode)
        top.addWidget(self.preview_txt_btn)
        top.addWidget(self.preview_epub_btn)
        top.addStretch(1)
        top.addWidget(self.complete_sub)
        self.viewer_body = QFrame()
        self.viewer_body.setObjectName("viewerBody")
        body = QHBoxLayout(self.viewer_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.chapter_sidebar = QScrollArea()
        self.chapter_sidebar.setObjectName("chapterSidebar")
        self.chapter_sidebar.setWidgetResizable(True)
        self.chapter_sidebar.setFixedWidth(200)
        self.chapter_sidebar_content = QWidget()
        self.chapter_sidebar_layout = QVBoxLayout(self.chapter_sidebar_content)
        self.chapter_sidebar_layout.setContentsMargins(14, 14, 14, 14)
        self.chapter_sidebar_layout.setSpacing(3)
        self.chapter_sidebar.setWidget(self.chapter_sidebar_content)
        reader_wrap = QWidget()
        reader_layout = QVBoxLayout(reader_wrap)
        reader_layout.setContentsMargins(24, 24, 24, 18)
        reader_layout.setSpacing(12)
        self.viewer_label = QLabel()
        self.viewer_label.setObjectName("viewerChapterTitle")
        self.preview_txt_view = QPlainTextEdit()
        self.preview_txt_view.setObjectName("previewPlain")
        self.preview_txt_view.setReadOnly(True)
        self.preview_epub_view = QTextBrowser()
        self.preview_epub_view.setObjectName("previewHtml")
        self.preview_epub_view.setOpenExternalLinks(False)
        self.preview_epub_view.setOpenLinks(False)
        self.preview_epub_view.hide()
        reader_layout.addWidget(self.viewer_label)
        reader_layout.addWidget(self.preview_txt_view, 1)
        reader_layout.addWidget(self.preview_epub_view, 1)
        body.addWidget(self.chapter_sidebar)
        body.addWidget(reader_wrap, 1)
        self.viewer_toolbar = QFrame()
        self.viewer_toolbar.setObjectName("viewerToolbar")
        toolbar = QHBoxLayout(self.viewer_toolbar)
        toolbar.setContentsMargins(24, 10, 24, 10)
        toolbar.setSpacing(10)
        self.font_minus_btn = QPushButton("A−")
        self.font_minus_btn.setObjectName("fontBtn")
        self.font_minus_btn.clicked.connect(lambda: self._change_viewer_font(-1))
        self.font_value_label = QLabel()
        self.font_value_label.setObjectName("fontValue")
        self.font_plus_btn = QPushButton("A+")
        self.font_plus_btn.setObjectName("fontBtn")
        self.font_plus_btn.clicked.connect(lambda: self._change_viewer_font(1))
        self.save_txt_btn = QPushButton()
        self.save_txt_btn.setObjectName("toolbarBtn")
        self.save_txt_btn.clicked.connect(lambda: self._export_result("txt"))
        self.save_epub_btn = QPushButton()
        self.save_epub_btn.setObjectName("toolbarBtn")
        self.save_epub_btn.clicked.connect(lambda: self._export_result("epub"))
        self.save_both_btn = QPushButton()
        self.save_both_btn.setObjectName("toolbarPrimary")
        self.save_both_btn.clicked.connect(lambda: self._export_result("both"))
        self.open_folder_btn = QPushButton()
        self.open_folder_btn.setObjectName("toolbarBtn")
        self.open_folder_btn.clicked.connect(lambda: open_path(self.output_dir))
        self.another_btn = QPushButton()
        self.another_btn.setObjectName("toolbarBtn")
        self.another_btn.clicked.connect(self._reset_for_another)
        self.files_row = QHBoxLayout()
        toolbar.addWidget(self.font_minus_btn)
        toolbar.addWidget(self.font_value_label)
        toolbar.addWidget(self.font_plus_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.save_txt_btn)
        toolbar.addWidget(self.save_epub_btn)
        toolbar.addWidget(self.save_both_btn)
        toolbar.addWidget(self.open_folder_btn)
        toolbar.addWidget(self.another_btn)
        layout.addWidget(self.viewer_top)
        layout.addWidget(self.viewer_body, 1)
        layout.addWidget(self.viewer_toolbar)
        self._apply_viewer_font_size()

    def _screen_settings(self) -> None:
        page = self._page()
        layout = page.layout()
        row = QHBoxLayout()
        self.settings_title = QLabel()
        self.settings_title.setObjectName("h1")
        self.settings_close = QPushButton()
        self.settings_close.setObjectName("ghostSmall")
        self.settings_close.clicked.connect(self.close_settings)
        row.addWidget(self.settings_title)
        row.addStretch(1)
        row.addWidget(self.settings_close)
        layout.addLayout(row)
        self.settings_download_label = QLabel()
        self.settings_download_label.setObjectName("label")
        layout.addWidget(self.settings_download_label)
        card = QFrame()
        card.setObjectName("settingsCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.output_label = QLabel()
        self.output_label.setObjectName("settingsName")
        self.output_hint = QLabel()
        self.output_hint.setObjectName("settingsHint")
        self.output_path = QLineEdit(str(self.output_dir))
        self.output_path.setObjectName("monoInput")
        self.output_path.setReadOnly(True)
        self.output_choose = QPushButton()
        self.output_choose.setObjectName("ghostSmall")
        self.output_choose.clicked.connect(self._choose_output)
        self.threads_label = QLabel()
        self.threads_label.setObjectName("settingsName")
        self.threads_hint = QLabel()
        self.threads_hint.setObjectName("settingsHint")
        self.threads_combo = QComboBox()
        self.threads_combo.setObjectName("threadCombo")
        self.threads_combo.addItems(["2", "4", "8", "12", "16"])
        self.threads_combo.setCurrentText(str(self.ui_settings.get("threads") or "8"))
        self.threads_combo.currentTextChanged.connect(lambda _text: self._persist_ui_settings())
        grid.addWidget(self.output_label, 0, 0)
        grid.addWidget(self.output_hint, 1, 0)
        grid.addWidget(self.output_path, 0, 1, 2, 1)
        grid.addWidget(self.output_choose, 0, 2, 2, 1)
        grid.addWidget(self.threads_label, 2, 0)
        grid.addWidget(self.threads_hint, 3, 0)
        grid.addWidget(self.threads_combo, 2, 1, 2, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(card)
        self.settings_appearance_label = QLabel()
        self.settings_appearance_label.setObjectName("label")
        layout.addWidget(self.settings_appearance_label)
        appearance = QFrame()
        appearance.setObjectName("settingsCard")
        agrid = QGridLayout(appearance)
        agrid.setContentsMargins(16, 14, 16, 14)
        self.font_size_name = QLabel()
        self.font_size_name.setObjectName("settingsName")
        self.font_size_hint = QLabel()
        self.font_size_hint.setObjectName("settingsHint")
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(13, 22)
        self.font_slider.setValue(self.viewer_font_size)
        self.font_slider.valueChanged.connect(self._set_viewer_font_from_slider)
        self.settings_font_value = QLabel()
        self.settings_font_value.setObjectName("settingsVal")
        agrid.addWidget(self.font_size_name, 0, 0)
        agrid.addWidget(self.font_size_hint, 1, 0)
        agrid.addWidget(self.font_slider, 0, 1, 2, 1)
        agrid.addWidget(self.settings_font_value, 0, 2, 2, 1)
        agrid.setColumnStretch(1, 1)
        layout.addWidget(appearance)
        self.settings_about_label = QLabel()
        self.settings_about_label.setObjectName("label")
        layout.addWidget(self.settings_about_label)
        about = QFrame()
        about.setObjectName("settingsCard")
        abody = QVBoxLayout(about)
        self.about_name = QLabel("SFACG Downloader")
        self.about_name.setObjectName("settingsName")
        self.about_hint = QLabel()
        self.about_hint.setObjectName("settingsHint")
        uninstall = QPushButton()
        uninstall.setObjectName("dangerGhost")
        uninstall.clicked.connect(self._confirm_uninstall)
        self.settings_uninstall_btn = uninstall
        abody.addWidget(self.about_name)
        abody.addWidget(self.about_hint)
        abody.addWidget(uninstall)
        layout.addWidget(about)
        layout.addStretch(1)

    def _refresh_language_texts(self) -> None:
        self.login_title.setText(ui_text("login_title"))
        self.login_sub.setText(ui_text("login_sub"))
        self.phone_label.setText(ui_text("phone"))
        self.password_label.setText(ui_text("password"))
        self.login_button.setText(ui_text("sign_in"))
        self.lookup_title.setText(ui_text("novel_title"))
        self.lookup_sub.setText(ui_text("novel_sub"))
        self.novel_id_label.setText(ui_text("novel_id"))
        self.fetch_button.setText(ui_text("fetch"))
        self.select_button.setText(ui_text("select_download"))
        self.different_button.setText(ui_text("different_novel"))
        self.selection_title.setText(ui_text("selection_title"))
        self.selection_sub.setText(ui_text("selection_sub"))
        self.select_all_btn.setText(ui_text("select_all"))
        self.deselect_all_btn.setText(ui_text("deselect_all"))
        self.selection_back.setText(ui_text("back"))
        self.download_button.setText(ui_text("start_download"))
        self.download_title.setText(ui_text("download_title"))
        self.download_sub.setText(ui_text("download_sub"))
        self.cancel_button.setText(ui_text("cancel_download"))
        self.complete_title.setText(ui_text("viewer_title"))
        self.preview_txt_btn.setText(ui_text("preview_txt"))
        self.preview_epub_btn.setText(ui_text("preview_epub"))
        self.save_txt_btn.setText(ui_text("export_txt"))
        self.save_epub_btn.setText(ui_text("export_epub"))
        self.save_both_btn.setText(ui_text("export_both_arrow"))
        self.open_folder_btn.setText(ui_text("open_folder"))
        self.another_btn.setText(ui_text("another"))
        self.splash_status.setText(ui_text("checking_session"))
        self.settings_title.setText(ui_text("settings_title"))
        self.settings_close.setText(ui_text("close"))
        self.settings_download_label.setText(ui_text("settings_download"))
        self.settings_appearance_label.setText(ui_text("settings_appearance"))
        self.settings_about_label.setText(ui_text("about"))
        self.output_label.setText(ui_text("output_folder"))
        self.output_hint.setText(ui_text("output_hint"))
        self.output_choose.setText(ui_text("choose_folder"))
        self.threads_label.setText(ui_text("threads"))
        self.threads_hint.setText(ui_text("threads_hint"))
        self.font_size_name.setText(ui_text("viewer_font_size"))
        self.font_size_hint.setText(ui_text("viewer_font_hint"))
        self.about_hint.setText(ui_text("version_license"))
        self.settings_uninstall_btn.setText(ui_text("uninstall"))
        self._refresh_tray_texts()
        if hasattr(self, "title_bar"):
            self.title_bar.settings_btn.setToolTip(ui_text("settings"))
            self.title_bar.fullscreen_btn.setToolTip(ui_text("exit_fullscreen") if self.isFullScreen() else ui_text("fullscreen"))
            self.title_bar.min_btn.setToolTip(ui_text("minimize"))
            self.title_bar.hide_btn.setToolTip(ui_text("hide"))
            self.title_bar.close_btn.setToolTip(ui_text("quit"))
        if self.catalog:
            self._render_catalog_card()
            self._update_selection_summary()

    def _run_startup(self) -> None:
        worker = StartupWorker()
        self.active_worker = worker
        worker.log.connect(self._append_log)
        worker.error.connect(self._show_login_error)
        worker.finished_ok.connect(self._startup_done)
        worker.state.connect(lambda logged_in: self._go(3 if logged_in else 2))
        self.login_status.setText("")
        worker.start()

    def _startup_done(self, client: SfacgClient) -> None:
        self.client = client

    def _login(self) -> None:
        if not self.client:
            return
        self.login_button.setEnabled(False)
        self.login_card.setProperty("error", False)
        self.login_card.style().unpolish(self.login_card)
        self.login_card.style().polish(self.login_card)
        self.login_status.hide()
        self.login_button.setText(ui_text("sign_in"))
        worker = LoginWorker(self.client, self.phone_input.text(), self.password_input.text())
        self.active_worker = worker
        worker.log.connect(self._append_log)
        worker.error.connect(self._show_login_error)
        worker.finished_ok.connect(self._login_done)
        worker.start()

    def _login_done(self, client: SfacgClient) -> None:
        self.client = client
        self.login_button.setEnabled(True)
        self._go(3)

    def _show_login_error(self, message: str) -> None:
        self.login_button.setEnabled(True)
        self.login_button.setText(ui_text("sign_in") if not message else "Try again" if LANG == "en" else "重试")
        self.login_card.setProperty("error", True)
        self.login_card.style().unpolish(self.login_card)
        self.login_card.style().polish(self.login_card)
        self.login_status.setText(message)
        self.login_status.show()

    def _fetch_catalog(self) -> None:
        if not self.client:
            return
        novel_id = strip_novel_id(self.novel_id_input.text())
        if not novel_id.isdigit():
            self.lookup_status.setText(ui_text("not_found"))
            return
        self.novel_id_input.setText(novel_id)
        self.fetch_button.setEnabled(False)
        self.fetch_button.setText(ui_text("fetching"))
        worker = CatalogWorker(self.client, novel_id)
        self.active_worker = worker
        worker.error.connect(self._catalog_error)
        worker.finished_ok.connect(self._catalog_done)
        worker.start()

    def _catalog_error(self, message: str) -> None:
        self.fetch_button.setEnabled(True)
        self.fetch_button.setText(ui_text("fetch"))
        self.lookup_status.setText(message)

    def _catalog_done(self, catalog: NovelCatalog) -> None:
        self.catalog = catalog
        self.fetch_button.setEnabled(True)
        self.fetch_button.setText(ui_text("fetch"))
        self.lookup_status.setText("")
        self._render_catalog_card()
        self.novel_card.show()

    def _render_catalog_card(self) -> None:
        if not self.catalog:
            return
        total_chapters = sum(len(v.chapters) for v in self.catalog.volumes)
        self.fetched_title.setText(self.catalog.title)
        author = self.catalog.author or ui_text("author_unknown")
        self.fetched_meta.setText(f"{author} · {len(self.catalog.volumes)} · {ui_text('chapters', count=total_chapters)}")
        self.fetched_id.setText(ui_text("id_label", id=self.catalog.novel_id))

    def _show_selection(self) -> None:
        self._build_selection_list()
        self._go(4)

    def _clear_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_selection_list(self) -> None:
        self._clear_layout(self.selection_layout)
        self.volume_widgets.clear()
        if not self.catalog:
            return
        for volume in self.catalog.volumes:
            frame = QFrame()
            frame.setObjectName("volume")
            body = QVBoxLayout(frame)
            body.setContentsMargins(0, 0, 0, 0)
            body.setSpacing(0)
            header = QFrame()
            header.setObjectName("volumeHeader")
            row = QHBoxLayout(header)
            row.setContentsMargins(14, 10, 14, 10)
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            idx = QLabel(f"V{volume.index}")
            idx.setObjectName("volumeIndex")
            title = QLabel(volume.title)
            title.setObjectName("volumeTitle")
            count = QLabel(ui_text("chapters", count=len(volume.chapters)))
            count.setObjectName("sub")
            toggle = QToolButton()
            toggle.setText("▸")
            toggle.setObjectName("chevron")
            toggle.setCheckable(True)
            toggle.setFixedSize(28, 28)
            row.addWidget(checkbox)
            row.addWidget(idx)
            row.addWidget(title, 1)
            row.addWidget(count)
            row.addWidget(toggle)
            chapter_box = QFrame()
            chapter_box.setObjectName("chapterBox")
            chapter_layout = QVBoxLayout(chapter_box)
            chapter_layout.setContentsMargins(44, 8, 14, 10)
            chapter_layout.setSpacing(4)
            chapter_checks: List[QCheckBox] = []
            for chapter in volume.chapters:
                chapter_row = QHBoxLayout()
                chapter_check = QCheckBox(chapter.title_hint or str(chapter.chapter_id))
                chapter_check.setChecked(True)
                badge = QLabel(ui_text("paid") if chapter.need_fire else ui_text("free"))
                badge.setObjectName("badgePaid" if chapter.need_fire else "badgeFree")
                chapter_row.addWidget(chapter_check, 1)
                chapter_row.addWidget(badge)
                wrap = QWidget()
                wrap.setLayout(chapter_row)
                chapter_layout.addWidget(wrap)
                chapter_checks.append(chapter_check)
                chapter_check.stateChanged.connect(self._update_selection_summary)
            chapter_box.hide()
            toggle.toggled.connect(lambda checked, box=chapter_box, btn=toggle: (box.setVisible(checked), btn.setText("▾" if checked else "▸")))
            def toggle_header(event, header_widget=header, checkbox_widget=checkbox, btn=toggle):
                child = header_widget.childAt(event.position().toPoint())
                if child is checkbox_widget or (child is not None and checkbox_widget.isAncestorOf(child)):
                    event.ignore()
                    return
                btn.setChecked(not btn.isChecked())
                event.accept()
            header.mousePressEvent = toggle_header
            checkbox.stateChanged.connect(lambda state, checks=chapter_checks: [c.setChecked(state == Qt.CheckState.Checked.value) for c in checks])
            checkbox.stateChanged.connect(self._update_selection_summary)
            body.addWidget(header)
            body.addWidget(chapter_box)
            self.selection_layout.addWidget(frame)
            self.volume_widgets[volume.index] = {"volume": volume, "checkbox": checkbox, "chapter_checks": chapter_checks}
        self.selection_layout.addStretch(1)
        self._update_selection_summary()

    def _set_all(self, checked: bool) -> None:
        for info in self.volume_widgets.values():
            info["checkbox"].setChecked(checked)
            for chapter_check in info["chapter_checks"]:
                chapter_check.setChecked(checked)
        self._update_selection_summary()

    def _collect_selections(self) -> List[SelectedVolume]:
        selections: List[SelectedVolume] = []
        for index, info in self.volume_widgets.items():
            checks: List[QCheckBox] = info["chapter_checks"]
            selected = tuple(i for i, c in enumerate(checks, start=1) if c.isChecked())
            if not selected:
                continue
            if len(selected) == len(checks):
                selections.append(SelectedVolume(index=index, chapter_indices=None))
            else:
                selections.append(SelectedVolume(index=index, chapter_indices=selected))
        return selections

    def _update_selection_summary(self) -> None:
        selections = self._collect_selections() if self.volume_widgets else []
        chapters = 0
        if self.catalog:
            for selection in selections:
                volume = self.catalog.volumes[selection.index - 1]
                chapters += len(volume.chapters) if selection.chapter_indices is None else len(selection.chapter_indices)
        self.selection_summary.setText(ui_text("selected_summary", volumes=len(selections), chapters=chapters))

    def _choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, ui_text("output_folder"), str(self.output_dir))
        if folder:
            self.output_dir = Path(folder)
            self.output_path.setText(str(self.output_dir))
            self._persist_ui_settings()

    def _start_download(self) -> None:
        if not self.client or not self.catalog:
            return
        selections = self._collect_selections()
        if not selections:
            self.selection_summary.setText(ui_text("no_selection"))
            return
        self._build_progress_bars(selections)
        self.log_panel.clear()
        self._go(5)
        worker = DownloadWorker(self.client, self.catalog, selections, self.output_dir, int(self.threads_combo.currentText()))
        self.download_worker = worker
        worker.log.connect(self._append_log)
        worker.progress.connect(self._set_volume_progress)
        worker.error.connect(self._download_error)
        worker.finished_ok.connect(self._download_done)
        worker.start()

    def _build_progress_bars(self, selections: Sequence[SelectedVolume]) -> None:
        self._clear_layout(self.progress_layout)
        self.progress_widgets: Dict[int, QProgressBar] = {}
        if not self.catalog:
            return
        for selection in selections:
            volume = self.catalog.volumes[selection.index - 1]
            frame = QFrame()
            frame.setObjectName("progressCard")
            body = QVBoxLayout(frame)
            title = QLabel(f"V{volume.index} · {volume.title}")
            title.setObjectName("volumeTitle")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            detail = QLabel("0%")
            detail.setObjectName("mono")
            body.addWidget(title)
            body.addWidget(bar)
            body.addWidget(detail)
            self.progress_layout.addWidget(frame)
            self.progress_widgets[volume.index] = bar
            self.volume_widgets.setdefault(volume.index, {})["progress_detail"] = detail
        self.progress_layout.addStretch(1)

    def _set_volume_progress(self, volume_index: int, done: int, total: int) -> None:
        pct = int((done / max(1, total)) * 100)
        bar = self.progress_widgets.get(volume_index)
        if bar:
            bar.setValue(pct)
        detail = self.volume_widgets.get(volume_index, {}).get("progress_detail")
        if isinstance(detail, QLabel):
            detail.setText(f"{done} / {total} · {pct}%")

    def _append_log(self, message: str, kind: str = "info") -> None:
        colors = {"ok": "#4caf7d", "warn": "#c9a84c", "err": "#d94f3d", "info": "#a89f92"}
        safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log_panel.append(f'<span style="color:{colors.get(kind, colors["info"])}">{safe}</span>')
        self.log_panel.verticalScrollBar().setValue(self.log_panel.verticalScrollBar().maximum())

    def _cancel_download(self) -> None:
        if not self.download_worker:
            return
        box = QMessageBox(self)
        box.setWindowIcon(self.windowIcon())
        box.setWindowTitle(ui_text("cancel_confirm_title"))
        box.setText(ui_text("cancel_confirm_text"))
        stop = box.addButton(ui_text("stop"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(ui_text("continue_download"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == stop:
            self.download_worker.cancel()
            self._go(3)

    def _download_error(self, message: str) -> None:
        self._append_log(message, "err")

    def _download_done(self, result: DownloadResult) -> None:
        self.current_result = result
        self.complete_title.setText(ui_text("viewer_title"))
        self.complete_sub.setText(ui_text("complete_sub", title=self.catalog.title if self.catalog else "", volumes=result.volumes, chapters=result.chapters, failed=result.failed))
        self.preview_mode = "txt"
        self.preview_txt_btn.setChecked(True)
        self._build_chapter_sidebar()
        self._refresh_preview_text()
        self._show_toast(ui_text("done"), "ok")
        self._go(6)

    def _build_chapter_sidebar(self) -> None:
        self._clear_layout(self.chapter_sidebar_layout)
        if not self.current_result:
            return
        nav_title = QLabel(ui_text("contents_nav"))
        nav_title.setObjectName("sidebarTitle")
        self.chapter_sidebar_layout.addWidget(nav_title)
        first_button: Optional[QPushButton] = None
        for volume_index, volume_title, chapters in self.current_result.volume_payloads:
            heading = QLabel(f"V{volume_index} · {volume_title}")
            heading.setObjectName("volumeDivider")
            self.chapter_sidebar_layout.addWidget(heading)
            for chapter in chapters:
                btn = QPushButton(chapter.title)
                btn.setObjectName("chapterLink")
                btn.setCheckable(True)
                btn.clicked.connect(lambda _checked=False, cid=chapter.chapter_id: self._jump_to_chapter(cid))
                if first_button is None:
                    first_button = btn
                    btn.setChecked(True)
                self.chapter_sidebar_layout.addWidget(btn)
        self.chapter_sidebar_layout.addStretch(1)
        if first_button is not None:
            QTimer.singleShot(0, first_button.click)

    def _jump_to_chapter(self, chapter_id: int) -> None:
        for i in range(self.chapter_sidebar_layout.count()):
            widget = self.chapter_sidebar_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton) and widget.objectName() == "chapterLink":
                widget.setChecked(False)
        sender = self.sender()
        if isinstance(sender, QPushButton):
            sender.setChecked(True)
        title = ""
        for _volume_index, _volume_title, chapters in self.current_result.volume_payloads if self.current_result else []:
            for chapter in chapters:
                if chapter.chapter_id == chapter_id:
                    title = chapter.title
                    break
        if title:
            self.viewer_label.setText(title)
            needle = title
            if self.preview_mode == "txt":
                doc = self.preview_txt_view.document()
                cursor = doc.find(needle)
                if not cursor.isNull():
                    self.preview_txt_view.setTextCursor(cursor)
                    self.preview_txt_view.centerCursor()
            else:
                self.preview_epub_view.scrollToAnchor(f"chapter-{chapter_id}")

    def _apply_viewer_font_size(self) -> None:
        self.font_value_label.setText(f"{self.viewer_font_size}px") if hasattr(self, "font_value_label") else None
        if hasattr(self, "settings_font_value"):
            self.settings_font_value.setText(f"{self.viewer_font_size} px")
        if hasattr(self, "font_slider") and self.font_slider.value() != self.viewer_font_size:
            self.font_slider.blockSignals(True)
            self.font_slider.setValue(self.viewer_font_size)
            self.font_slider.blockSignals(False)
        for widget in (getattr(self, "preview_txt_view", None), getattr(self, "preview_epub_view", None)):
            if widget:
                font = widget.font()
                font.setPointSize(self.viewer_font_size)
                widget.setFont(font)

    def _change_viewer_font(self, delta: int) -> None:
        self.viewer_font_size = max(13, min(22, self.viewer_font_size + delta))
        self._apply_viewer_font_size()
        self._persist_ui_settings()

    def _set_viewer_font_from_slider(self, value: int) -> None:
        self.viewer_font_size = int(value)
        self._apply_viewer_font_size()
        self._persist_ui_settings()

    def _refresh_settings_values(self) -> None:
        if hasattr(self, "output_path"):
            self.output_path.setText(str(self.output_dir))
        self._apply_viewer_font_size()

    def _set_preview_mode(self, button_id: int) -> None:
        self.preview_mode = "epub" if button_id == 2 else "txt"
        self._build_chapter_sidebar()
        self._refresh_preview_text()

    def _refresh_preview_text(self) -> None:
        if not self.current_result:
            self.preview_txt_view.clear()
            self.preview_epub_view.clear()
            return
        self.preview_txt_view.setPlainText(self.current_result.txt_text)
        self.preview_epub_view.setHtml(self.current_result.epub_preview_html)
        show_epub = self.preview_mode == "epub"
        self.preview_txt_view.setVisible(not show_epub)
        self.preview_epub_view.setVisible(show_epub)
        self.complete_sub.setText(ui_text("preview_hint_epub" if show_epub else "preview_hint_txt"))
        self._apply_viewer_font_size()

    def _export_result(self, mode: str) -> None:
        if not self.current_result:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            exported: List[Path] = []
            if mode in ("txt", "both"):
                txt_path = self.output_dir / self.current_result.txt_name
                txt_path.write_text(self.current_result.txt_text, encoding="utf-8")
                exported.append(txt_path)
            if mode in ("epub", "both"):
                epub_path = self.output_dir / self.current_result.epub_name
                epub_path.write_bytes(self.current_result.epub_bytes)
                exported.append(epub_path)
            self._clear_layout(self.files_row)
            for path in exported:
                btn = QPushButton(path.name)
                btn.setObjectName("fileButton")
                btn.clicked.connect(lambda _=False, p=path: open_path(p))
                self.files_row.addWidget(btn)
            if exported:
                self.complete_sub.setText(ui_text("saved_file", path=str(exported[-1].parent)))
                self._show_toast(ui_text("export_ok", count=len(exported)), "ok")
        except Exception as exc:
            message = ui_text("save_failed", error=exc)
            self.complete_sub.setText(message)
            self._show_toast(message, "err")

    def _reset_for_another(self) -> None:
        self.current_result = None
        self.catalog = None
        self.novel_card.hide()
        self.novel_id_input.clear()
        self.lookup_status.clear()
        self._go(3)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.download_worker and self.download_worker.isRunning():
            self._cancel_download()
            event.ignore()
            return
        self.force_quit = True
        app = QApplication.instance()
        if app:
            QTimer.singleShot(0, app.quit)
        event.accept()

    def _apply_style(self) -> None:
        self.setStyleSheet("""
        QWidget#root{background:#1a1714;color:#f0ebe2;font-family:'Segoe UI','Microsoft YaHei','Noto Sans CJK SC',sans-serif;font-size:14px}
        QWidget#page{background:#1a1714;color:#f0ebe2}
        QLabel#titleIcon{font-family:'Microsoft YaHei';font-size:16px;font-weight:700;color:#d94f3d}
        QLabel#titleText{font-size:11px;font-weight:700;letter-spacing:1px;color:#5a5247;text-transform:uppercase}
        QToolButton#windowButton,QToolButton#chevron{background:transparent;border:0;border-radius:6px;color:#5a5247;font-size:15px;min-width:28px;max-width:28px;min-height:28px;max-height:28px}
        QToolButton#windowButton:hover,QToolButton#chevron:hover{background:#2c2825;color:#f0ebe2}
        QLabel#h1{font-family:'Georgia','SimSun',serif;font-size:30px;font-weight:700;color:#f0ebe2;line-height:1.15}
        QLabel#h2{font-family:'Georgia','SimSun',serif;font-size:22px;font-weight:700;color:#f0ebe2}
        QLabel#sub,QLabel#viewerHint{color:#a89f92;font-size:13px;line-height:1.55}
        QLabel#label,QLabel#sidebarTitle{color:#a89f92;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px}
        QLabel#status{color:#c9a84c;font-size:12px}
        QLabel#inlineError{color:#d94f3d;font-size:12px}
        QLabel#mono,QLabel#fontValue,QLabel#settingsVal{font-family:'Cascadia Mono','Consolas',monospace;color:#a89f92;font-size:12px}
        QLabel#splashGlyph{font-family:'Georgia','SimSun',serif;font-size:54px;color:#d94f3d}
        QLabel#splashDot{color:#d94f3d;font-size:10px;padding:3px}
        QFrame#card,QFrame#novelCard,QFrame#volume,QFrame#progressCard,QFrame#settingsCard{background:#2c2825;border:1px solid #3e3a36;border-radius:14px}
        QFrame#card[error="true"]{border:1px solid rgba(217,79,61,.55)}
        QFrame#novelCard{background:#1a1714;border-radius:10px}
        QFrame#volume{background:#1a1714;border-radius:8px}
        QFrame#volumeHeader{background:#1a1714;border-radius:8px}
        QFrame#volumeHeader:hover{background:#231f1c}
        QFrame#chapterBox{background:#2c2825;border-top:1px solid #3e3a36}
        QWidget#inputWrap{background:#111009;border:1px solid #3e3a36;border-radius:8px}
        QWidget#inputWrap:focus-within{border:1px solid #d94f3d}
        QLabel#inputIcon{color:#5a5247;font-size:14px;padding-left:10px}
        QLineEdit{background:#111009;border:1px solid #3e3a36;border-radius:8px;color:#f0ebe2;padding:11px 14px;selection-background-color:#d94f3d}
        QLineEdit:focus{border:1px solid #d94f3d}
        QLineEdit#iconInput{border:0;border-radius:8px;padding-left:2px}
        QLineEdit#monoInput{font-family:'Cascadia Mono','Consolas',monospace}
        QPushButton{border-radius:8px;padding:10px 18px;font-weight:700}
        QPushButton#primary,QPushButton#primarySmall{background:#d94f3d;color:white;border:0}
        QPushButton#primary:hover,QPushButton#primarySmall:hover,QPushButton#toolbarPrimary:hover{background:#b8382a}
        QPushButton#primarySmall,QPushButton#ghostSmall{padding:7px 14px;font-size:13px}
        QPushButton#ghost,QPushButton#ghostSmall,QPushButton#toolbarBtn{background:transparent;border:1px solid #3e3a36;color:#a89f92}
        QPushButton#ghost:hover,QPushButton#ghostSmall:hover,QPushButton#toolbarBtn:hover{border-color:#a89f92;color:#f0ebe2}
        QPushButton#dangerGhost{background:transparent;border:1px solid rgba(217,79,61,.35);color:#d94f3d}
        QPushButton#dangerGhost:hover{border-color:#d94f3d}
        QPushButton#pill{background:#1a1714;border:1px solid #3e3a36;color:#a89f92;border-radius:20px}
        QPushButton#pill:checked{background:#d94f3d;color:white;border-color:#d94f3d}
        QLabel#cover{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3e3028,stop:1 #2a201a);border:1px solid #3e3a36;border-radius:6px;color:#d94f3d;font-family:'Microsoft YaHei';font-size:38px;qproperty-alignment:AlignCenter}
        QLabel#novelTitle{font-family:'Georgia','SimSun',serif;font-size:22px;font-weight:700;color:#f0ebe2}
        QLabel#volumeIndex{font-family:'Cascadia Mono','Consolas',monospace;color:#d94f3d;font-size:12px;font-weight:700}
        QLabel#volumeTitle{color:#f0ebe2;font-size:14px;font-weight:600}
        QLabel#badgePaid{background:rgba(201,168,76,.15);color:#c9a84c;border-radius:10px;padding:2px 8px;font-size:10px;font-weight:700}
        QLabel#badgeFree{background:rgba(76,175,125,.12);color:#4caf7d;border-radius:10px;padding:2px 8px;font-size:10px;font-weight:700}
        QCheckBox{color:#a89f92;spacing:8px}
        QCheckBox::indicator{width:15px;height:15px;border:1px solid #3e3a36;border-radius:3px;background:#1a1714}
        QCheckBox::indicator:checked{background:#d94f3d;border-color:#d94f3d}
        QScrollArea#scroll,QScrollArea#chapterSidebar{background:transparent;border:0}
        QScrollArea QWidget{background:transparent}
        QTextEdit#log{background:#111009;border:1px solid #3e3a36;border-radius:8px;color:#a89f92;font-family:'Cascadia Mono','Consolas',monospace;font-size:11px;padding:10px}
        QFrame#viewerTop,QFrame#viewerToolbar{background:#111009;border-top:0;border-bottom:1px solid #2c2825}
        QFrame#viewerToolbar{border-top:1px solid #2c2825;border-bottom:0}
        QFrame#viewerBody{background:#1a1714}
        QPushButton#viewerTab{background:#111009;border:0;border-radius:6px;color:#5a5247;font-size:12px;text-transform:uppercase;padding:8px 18px}
        QPushButton#viewerTab:checked{background:#2c2825;color:#f0ebe2}
        QScrollArea#chapterSidebar{background:#111009;border-right:1px solid #2c2825}
        QLabel#volumeDivider{color:#3e3a36;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:10px 8px 4px}
        QPushButton#chapterLink{background:transparent;border:0;border-radius:6px;color:#5a5247;text-align:left;padding:8px 10px;font-size:12px;font-weight:500}
        QPushButton#chapterLink:checked{background:#2c2825;color:#f0ebe2}
        QLabel#viewerChapterTitle{color:#5a5247;font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;border-bottom:1px solid #2c2825;padding-bottom:10px}
        QPlainTextEdit#previewPlain,QTextBrowser#previewHtml{background:#111009;border:1px solid #2c2825;border-radius:8px;color:#e4ddd3;font-family:'Georgia','SimSun',serif;padding:20px;line-height:1.85}
        QPushButton#fontBtn{background:#1a1714;border:1px solid #3e3a36;color:#a89f92;border-radius:6px;min-width:34px;padding:6px}
        QPushButton#toolbarBtn,QPushButton#toolbarPrimary{border-radius:6px;padding:8px 12px;font-size:11px;text-transform:uppercase;letter-spacing:1px}
        QPushButton#toolbarPrimary{background:#d94f3d;border:1px solid #d94f3d;color:white}
        QProgressBar{height:8px;border:0;border-radius:4px;background:#3e3a36;text-align:center;color:transparent}
        QProgressBar::chunk{background:#d94f3d;border-radius:4px}
        QComboBox{background:#111009;border:1px solid #3e3a36;border-radius:18px;color:#f0ebe2;padding:8px 18px;min-width:72px}
        QComboBox::drop-down{border:0;width:20px}
        QComboBox::down-arrow{image:none;border:0}
        QLabel#toast{background:#2c2825;border:1px solid #3e3a36;border-radius:21px;color:#f0ebe2;font-weight:600;padding:8px 16px}
        QPushButton#fileButton{background:#2c2825;border:1px solid #3e3a36;color:#f0ebe2;font-family:'Cascadia Mono','Consolas',monospace;font-size:12px}
        QLabel#settingsName{font-size:13px;font-weight:700;color:#f0ebe2}
        QLabel#settingsHint{font-size:11px;color:#5a5247}
        QSlider::groove:horizontal{height:3px;background:#3e3a36;border-radius:2px}
        QSlider::handle:horizontal{background:#d94f3d;width:14px;height:14px;margin:-6px 0;border-radius:7px}
        """)


def install_windows_app_id() -> None:
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("sfacg.downloader.gui")
        except Exception:
            pass


def main() -> None:
    install_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
