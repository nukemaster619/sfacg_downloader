import os
import sys
from typing import List, Optional, Tuple

from config import set_language, tr
from models import NovelCatalog, SelectedVolume, Volume

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    ctypes.windll.kernel32.SetConsoleCP(65001)
except Exception:
    pass
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def safe_print(*args, **kwargs) -> None:
    text = " ".join(str(arg) for arg in args)
    print(text.encode("utf-8", errors="replace").decode("utf-8"), **kwargs)

def format_tr(key: str, **kwargs) -> str:
    return tr(key).format(**kwargs)

def log_tr(key: str, **kwargs) -> None:
    safe_print(format_tr(key, **kwargs))

def choose_language() -> None:
    safe_print(tr("select_lang"))
    safe_print(tr("lang_menu"))
    choice = input(tr("lang_prompt")).strip()
    if choice == "2":
        set_language("en")
    elif choice in ("", "1"):
        set_language("zh")
    else:
        safe_print(tr("invalid_lang"))
        set_language("zh")

def parse_number_selection(raw: str, total_items: int, *, blank_means_all: bool = True) -> List[int]:
    if not raw.strip():
        if blank_means_all:
            return list(range(1, total_items + 1))
        raise ValueError(tr("empty_selection"))
    selected: set[int] = set()
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start_str, end_str = item.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            if start > end:
                start, end = end, start
            selected.update(value for value in range(start, end + 1) if 1 <= value <= total_items)
            continue
        value = int(item)
        if 1 <= value <= total_items:
            selected.add(value)
    result = sorted(selected)
    if not result:
        raise ValueError(tr("empty_selection"))
    return result

def parse_volume_selection(raw: str, total_volumes: int) -> List[int]:
    return parse_number_selection(raw, total_volumes)

def ask_volume_selection(total_volumes: int) -> List[int]:
    while True:
        raw = input(tr("volume_prompt")).strip()
        try:
            return parse_volume_selection(raw, total_volumes)
        except Exception:
            safe_print(tr("volume_error"))

def ask_chapter_selection(volume: Volume) -> Optional[Tuple[int, ...]]:
    safe_print(f"{tr('choose_chapter')} {volume.title}")
    for index, chapter in enumerate(volume.chapters, start=1):
        safe_print(f"  {index}: {chapter.title_hint or chapter.chapter_id}")
    while True:
        raw = input(tr("chapter_prompt")).strip()
        if not raw:
            return None
        try:
            return tuple(parse_number_selection(raw, len(volume.chapters), blank_means_all=False))
        except Exception:
            safe_print(tr("chapter_error"))

def ask_download_selection(catalog: NovelCatalog) -> List[SelectedVolume]:
    selected_volume_indices = ask_volume_selection(len(catalog.volumes))
    selected_volumes: List[SelectedVolume] = []
    for volume_index in selected_volume_indices:
        volume = catalog.volumes[volume_index - 1]
        chapter_indices = ask_chapter_selection(volume)
        selected_volumes.append(SelectedVolume(index=volume.index, chapter_indices=chapter_indices))
    return selected_volumes
