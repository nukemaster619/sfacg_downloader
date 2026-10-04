import concurrent.futures
import html
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ebooklib import epub

from api import SfacgClient
from config import DEFAULT_MAX_THREADS, IMAGE_WORKERS, tr
from models import ChapterContent, NovelCatalog, SelectedVolume
from ui import log_tr, safe_print

IMG_PATTERN = re.compile(r"\[img=(https?://.*?)(?:\[/img\]|$)", re.IGNORECASE)

def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', " ", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(" .")
    return cleaned or "output"

def build_output_filename(title: str, selection_tag: str, extension: str) -> str:
    safe_stem = sanitize_filename(f"{title}{selection_tag}")
    safe_extension = extension if extension.startswith(".") else f".{extension}"
    return f"{safe_stem}{safe_extension}"


SELECTION_TAG_PATTERN = re.compile(r"\[(?P<tag>v\d+(?:-(?:all|c\d+(?:-\d+)*))?(?:;v\d+(?:-(?:all|c\d+(?:-\d+)*))?)*)\]$")

def parse_selection_tag(filename: str) -> List[SelectedVolume]:
    stem = Path(filename).stem
    match = SELECTION_TAG_PATTERN.search(stem)
    if not match:
        return []
    selections: List[SelectedVolume] = []
    for part in match.group("tag").split(";"):
        volume_text, mode = part.split("-", 1)
        volume_index = int(volume_text[1:])
        if mode == "all":
            selections.append(SelectedVolume(volume_index, None))
        elif mode.startswith("c"):
            chapters = tuple(sorted({int(value) for value in mode[1:].split("-") if value}))
            selections.append(SelectedVolume(volume_index, chapters))
    return selections

def merge_selections(*groups: Sequence[SelectedVolume]) -> List[SelectedVolume]:
    merged: Dict[int, Optional[set[int]]] = {}
    for group in groups:
        for selection in group:
            if selection.index in merged and merged[selection.index] is None:
                continue
            if selection.chapter_indices is None:
                merged[selection.index] = None
                continue
            bucket = merged.setdefault(selection.index, set())
            if bucket is not None:
                bucket.update(selection.chapter_indices)
    result: List[SelectedVolume] = []
    for index in sorted(merged):
        chapters = merged[index]
        result.append(SelectedVolume(index, None if chapters is None else tuple(sorted(chapters))))
    return result

def find_existing_export(output_dir: Path, title: str) -> Tuple[Optional[str], List[SelectedVolume]]:
    if not output_dir.exists():
        return None, []
    prefix = sanitize_filename(title) + "["
    candidates = [
        path for path in output_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".txt", ".epub"} and path.name.startswith(prefix) and parse_selection_tag(path.name)
    ]
    if not candidates:
        return None, []
    newest = max(candidates, key=lambda path: path.stat().st_mtime)
    stem = newest.stem
    matching = [path for path in candidates if path.stem == stem]
    newest = max(matching, key=lambda path: path.stat().st_mtime)
    return newest.stem, parse_selection_tag(newest.name)

def detect_media_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    return "image/jpeg"

def extract_image_urls(text: str) -> List[str]:
    return [match.group(1).strip() for match in IMG_PATTERN.finditer(text)]

def collect_unique_image_urls(chapters: Sequence[ChapterContent]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for chapter in chapters:
        for url in extract_image_urls(chapter.content):
            if url not in seen:
                seen.add(url)
                ordered.append(url)
    return ordered

def filename_from_url(url: str) -> str:
    name = url.split("/")[-1].split("?")[0].strip()
    if not name:
        name = f"img_{uuid.uuid4().hex}.jpg"
    if "." not in name:
        name += ".jpg"
    return sanitize_filename(name)

def download_images(client: SfacgClient, image_urls: Sequence[str]) -> Dict[str, Tuple[str, str, bytes]]:
    if not image_urls:
        return {}
    results: Dict[str, Tuple[str, str, bytes]] = {}

    def worker(url: str) -> Optional[Tuple[str, Tuple[str, str, bytes]]]:
        try:
            data = client.fetch_binary(url, retries=3)
            filename = filename_from_url(url)
            media_type = detect_media_type(filename)
            safe_print(f"{filename} {tr('image_downloaded')}")
            return url, (filename, media_type, data)
        except Exception as exc:
            safe_print(f"{tr('image_embed_failed')}: {url} -> {exc}")
            return None

    max_workers = max(1, min(IMAGE_WORKERS, len(image_urls)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for future in concurrent.futures.as_completed(executor.submit(worker, url) for url in image_urls):
            item = future.result()
            if item is not None:
                url, payload = item
                results[url] = payload
    return results

def chapter_to_xhtml(chapter: ChapterContent, image_cache: Dict[str, Tuple[str, str, bytes]], image_registry: Dict[str, str]) -> epub.EpubHtml:
    item = epub.EpubHtml(title=chapter.title, file_name=f"chap_{chapter.chapter_id}.xhtml", lang="zh")
    parts: List[str] = [f"<h2>{html.escape(chapter.title)}</h2>"]
    for raw_line in chapter.content.splitlines():
        line = raw_line.strip("\ufeff")
        match = IMG_PATTERN.search(line)
        if match:
            url = match.group(1).strip()
            cached = image_cache.get(url)
            if cached:
                filename, _media_type, _bytes_data = cached
                src = image_registry.get(url, f"img/{filename}")
                parts.append(f'<p><img src="{html.escape(src)}" alt="{html.escape(filename)}"/></p>')
            else:
                parts.append(f"<p>{html.escape(line)}</p>")
        elif line:
            parts.append(f"<p>{html.escape(line)}</p>")
        else:
            parts.append("<p></p>")
    item.content = "".join(parts)
    return item

def build_epub_and_txt(client: SfacgClient, catalog: NovelCatalog, selected_volumes: Sequence[SelectedVolume]) -> Tuple[str, str]:
    safe_print(tr("book_building"))
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(catalog.title)
    book.set_language("zh")
    if catalog.author:
        book.add_author(catalog.author)
    if catalog.cover_url:
        safe_print(tr("fetching_cover"))
        try:
            cover_bytes = client.fetch_binary(catalog.cover_url, retries=3)
            book.set_cover("cover.jpg", cover_bytes)
            safe_print(tr("cover_done"))
        except Exception:
            safe_print(tr("cover_fetch_failed"))
    txt_parts: List[str] = [catalog.title, "", ""]
    toc_entries: List[Tuple[epub.EpubHtml, Tuple[epub.EpubHtml, ...]]] = []
    spine: List[object] = ["nav"]
    selected_by_volume = {selection.index: selection for selection in selected_volumes}
    for volume in catalog.volumes:
        selection = selected_by_volume.get(volume.index)
        if selection is None:
            safe_print(f"{tr('skipping_volume')} {volume.title}")
            continue
        safe_print(f"{tr('downloading_volume')} {volume.title}")
        txt_parts.extend([volume.title, "", ""])
        wanted_chapter_indices = set(range(1, len(volume.chapters) + 1)) if selection.chapter_indices is None else set(selection.chapter_indices)
        chapters_info = [
            {"id": chapter_ref.chapter_id, "title": chapter_ref.title_hint, "need_fire": chapter_ref.need_fire}
            for chapter_index, chapter_ref in enumerate(volume.chapters, start=1)
            if chapter_index in wanted_chapter_indices
        ]
        success_dict, failed_ids = client.download_chapters_concurrent(chapters_info, catalog.novel_id, max_workers=DEFAULT_MAX_THREADS)
        chapter_results: List[ChapterContent] = []
        for chapter_info in chapters_info:
            chapter_id = int(chapter_info["id"])
            result = success_dict.get(chapter_id)
            if result is None:
                title = chapter_info.get("title") or str(chapter_id)
                content = tr("chapter_failed_placeholder").format(chapter_id=chapter_id)
                chapter_results.append(ChapterContent(chapter_id=chapter_id, title=title, content=content))
                log_tr("chapter_placeholder_added", title=title)
            else:
                chapter_results.append(ChapterContent(chapter_id=chapter_id, title=result.get("title") or chapter_info.get("title") or str(chapter_id), content=result.get("content") or ""))
        if failed_ids:
            safe_print(f"{tr('chapters_done')} {len(chapter_results)} ({tr('failed_placeholders').format(count=len(failed_ids))})")
        else:
            safe_print(f"{tr('chapters_done')} {len(chapter_results)}")
        image_cache = download_images(client, collect_unique_image_urls(chapter_results))
        image_registry: Dict[str, str] = {}
        for url, (filename, media_type, data) in image_cache.items():
            src_path = f"img/{filename}"
            image_registry[url] = src_path
            book.add_item(epub.EpubImage(uid=str(uuid.uuid4()), file_name=src_path, media_type=media_type, content=data))
        volume_page = epub.EpubHtml(title=volume.title, file_name=f"vol_{volume.index}.xhtml", lang="zh")
        volume_page.content = f"<h2>{html.escape(volume.title)}</h2>"
        book.add_item(volume_page)
        spine.append(volume_page)
        volume_chapter_pages: List[epub.EpubHtml] = []
        for chapter in chapter_results:
            txt_parts.extend([chapter.title, chapter.content, "", ""])
            chapter_page = chapter_to_xhtml(chapter, image_cache, image_registry)
            book.add_item(chapter_page)
            volume_chapter_pages.append(chapter_page)
            spine.append(chapter_page)
        toc_entries.append((volume_page, tuple(volume_chapter_pages)))
        safe_print(f"{tr('volume_done')} {volume.title}")
    book.toc = tuple(toc_entries)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    selection_tag = "[" + ";".join(selection.filename_label() for selection in selected_volumes) + "]"
    epub_name = build_output_filename(catalog.title, selection_tag, ".epub")
    txt_name = build_output_filename(catalog.title, selection_tag, ".txt")
    safe_print(tr("book_writing"))
    epub.write_epub(epub_name, book, {})
    Path(txt_name).write_text("\n".join(txt_parts), encoding="utf-8")
    return txt_name, epub_name
