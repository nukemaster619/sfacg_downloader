import csv
import json
import os
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests

from config import API_BASE, BASE_HEADERS, CACHE_DIR, DEFAULT_MAX_THREADS, DEFAULT_RETRIES, DEVICE_TOKEN, REQUEST_TIMEOUT, SIGNATURE_BOOTSTRAP_CHAPTER, replace_chars, tr
from models import ChapterContent, ChapterRef, NovelCatalog, Volume
from sign import get_sign
from ui import log_tr, safe_print

class SfacgClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=0)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(BASE_HEADERS.copy())
        self._retry_log_lock = threading.Lock()
        self._last_417_log_time = 0.0

    def set_cookie_string(self, cookie_string: str) -> None:
        if cookie_string:
            self.session.headers["cookie"] = cookie_string
        else:
            self.session.headers.pop("cookie", None)

    def set_download_user_agent(self) -> None:
        self.session.headers["user-agent"] = f"boluobao/5.2.16(android;35)/OPPO/{DEVICE_TOKEN.lower()}/OPPO"

    def apply_sfsecurity(self) -> str:
        nonce = str(uuid.uuid4()).upper()
        timestamp = int(time.time() * 1000)
        sign = get_sign(nonce, timestamp, DEVICE_TOKEN)
        sfsecurity = f"nonce={nonce}&timestamp={timestamp}&devicetoken={DEVICE_TOKEN}&sign={sign}"
        self.session.headers["sfsecurity"] = sfsecurity
        return sfsecurity

    def _log_417_retry(self, attempt: int, retries: int) -> None:
        now = time.monotonic()
        with self._retry_log_lock:
            if now - self._last_417_log_time >= 2.0:
                self._last_417_log_time = now
                log_tr("retrying_417", attempt=attempt, retries=retries)
            elif attempt == 1:
                log_tr("retrying_417_suppressed")

    def request_json(self, method: str, url: str, *, payload: Optional[dict] = None, retries: int = DEFAULT_RETRIES, allow_417_retry: bool = True, timeout: int = REQUEST_TIMEOUT) -> Tuple[requests.Response, dict]:
        last_error: Optional[Exception] = None
        method_upper = method.upper()
        for attempt in range(1, retries + 1):
            try:
                self.apply_sfsecurity()
                if method_upper == "GET":
                    response = self.session.get(url, timeout=timeout)
                elif method_upper == "POST":
                    response = self.session.post(url, data=json.dumps(payload or {}), timeout=timeout)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                try:
                    data = response.json()
                except ValueError as exc:
                    raise RuntimeError(f"{tr('request_json_invalid')}: HTTP {response.status_code}") from exc
                http_code = data.get("status", {}).get("httpCode", response.status_code)
                if http_code == 417 and allow_417_retry:
                    if attempt < retries:
                        self._log_417_retry(attempt, retries)
                        self.session.headers.pop("sfsecurity", None)
                        time.sleep(min(0.35 * attempt, 2.0) + random.uniform(0.05, 0.25))
                        continue
                    log_tr("retrying_417_exhausted", retries=retries)
                return response, data
            except requests.RequestException as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(0.35 * attempt, 2.0) + random.uniform(0.05, 0.25))
                    continue
                raise
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(0.35 * attempt, 2.0) + random.uniform(0.05, 0.25))
                    continue
        if last_error is not None:
            raise last_error
        raise RuntimeError("Request failed without an explicit error")

    def get_json(self, url: str, *, retries: int = DEFAULT_RETRIES, timeout: int = REQUEST_TIMEOUT) -> dict:
        return self.request_json("GET", url, retries=retries, timeout=timeout)[1]

    def post_json(self, url: str, payload: dict, *, retries: int = DEFAULT_RETRIES, timeout: int = REQUEST_TIMEOUT) -> Tuple[requests.Response, dict]:
        return self.request_json("POST", url, payload=payload, retries=retries, timeout=timeout)

    def initialize_signature(self) -> None:
        safe_print(tr("bootstrapping"))
        self.get_json(f"{API_BASE}/Chaps/{SIGNATURE_BOOTSTRAP_CHAPTER}?expand=content%2Cexpand.content", retries=8)
        safe_print(tr("bootstrapped"))

    def check_login(self) -> bool:
        try:
            data = self.get_json(f"{API_BASE}/user?", retries=2)
            return data.get("status", {}).get("httpCode") == 200
        except Exception:
            return False

    def login(self, username: str, password: str) -> str:
        payload = {"password": password, "shuMeiId": "", "username": username}
        response, data = self.post_json(f"{API_BASE}/sessions", payload, retries=5)
        if data.get("status", {}).get("httpCode") != 200:
            return "error"
        cookie_map = requests.utils.dict_from_cookiejar(response.cookies)
        community = cookie_map.get(".SFCommunity")
        session_app = cookie_map.get("session_APP")
        if not community or not session_app:
            return "error"
        return f".SFCommunity={community}; session_APP={session_app}"

    def fetch_catalog(self, novel_id: str) -> NovelCatalog:
        safe_print(tr("fetching_catalog"))
        try:
            novel_data = self.get_json(f"{API_BASE}/novels/{novel_id}?expand=bigNovelCover")
            title = novel_data["data"]["novelName"]
            author = novel_data["data"].get("authorName", "")
            cover_url = novel_data["data"].get("expand", {}).get("bigNovelCover", "")
        except Exception as exc:
            raise RuntimeError(f"{tr('title_fetch_failed')}: {exc}") from exc
        try:
            catalog_data = self.get_json(f"{API_BASE}/novels/{novel_id}/dirs?expand=originNeedFireMoney")
            volume_list = catalog_data["data"]["volumeList"]
        except Exception as exc:
            raise RuntimeError(f"{tr('catalog_fetch_failed')}: {exc}") from exc
        volumes: List[Volume] = []
        for index, volume_data in enumerate(volume_list, start=1):
            chapter_refs = [
                ChapterRef(
                    chapter_id=int(chapter["chapId"]),
                    title_hint=chapter.get("title", ""),
                    need_fire=int(chapter.get("needFireMoney") or chapter.get("originNeedFireMoney") or 0),
                )
                for chapter in volume_data.get("chapterList", [])
            ]
            volumes.append(Volume(index=index, title=volume_data.get("title", f"Volume {index}"), chapters=chapter_refs))
        return NovelCatalog(novel_id=novel_id, title=title, author=author, cover_url=cover_url, volumes=volumes)

    def fetch_chapter(self, chapter_ref: ChapterRef) -> Optional[ChapterContent]:
        chapter_id = chapter_ref.chapter_id
        url = f"{API_BASE}/Chaps/{chapter_id}?expand=content%2Cexpand.content"
        try:
            data = self.get_json(url, retries=5)
        except Exception as exc:
            safe_print(f"{chapter_id} {tr('chapter_network_fail')}: {exc}")
            return None
        http_code = data.get("status", {}).get("httpCode")
        if http_code == 403:
            safe_print(f"{chapter_id} {tr('chapter_locked')}")
            return None
        if http_code != 200:
            safe_print(f"{chapter_id} {tr('chapter_network_fail')} (httpCode={http_code})")
            return None
        body = data.get("data", {})
        title = body.get("title") or chapter_ref.title_hint or str(chapter_id)
        combined = f"{body.get('content', '')}{body.get('expand', {}).get('content', '')}"
        if not combined:
            safe_print(f"{title}: {tr('missing_content')}")
        text = replace_chars(combined)
        safe_print(f"{title} {tr('downloaded')}")
        return ChapterContent(chapter_id=chapter_id, title=title, content=text)

    def download_chapter(self, chap_id: int) -> Tuple[bool, Optional[str], Optional[str]]:
        chapter = self.fetch_chapter(ChapterRef(chapter_id=int(chap_id)))
        if chapter is None:
            return False, None, None
        return True, chapter.title, chapter.content

    def fetch_binary(self, url: str, *, retries: int = 3, timeout: int = REQUEST_TIMEOUT) -> bytes:
        last_error: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response.content
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(0.2 * attempt, 1.0))
        if last_error is not None:
            raise last_error
        raise RuntimeError(tr("binary_failed"))

    def _get_cache_path(self, novel_id: str) -> str:
        os.makedirs(CACHE_DIR, exist_ok=True)
        return os.path.join(CACHE_DIR, f"{novel_id}.csv")

    def _load_cache(self, novel_id: str) -> Dict[int, Tuple[str, str]]:
        cache_path = self._get_cache_path(novel_id)
        cache: Dict[int, Tuple[str, str]] = {}
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8", newline="") as file:
                    reader = csv.reader(file)
                    next(reader, None)
                    for row in reader:
                        if len(row) >= 3:
                            cache[int(row[0])] = (row[1], row[2])
                log_tr("cache_loaded", path=cache_path, count=len(cache))
            except Exception as exc:
                log_tr("cache_load_failed", error=exc)
        return cache

    def _save_cache(self, novel_id: str, cache: Dict[int, Tuple[str, str]]) -> None:
        cache_path = self._get_cache_path(novel_id)
        try:
            with open(cache_path, "w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["chap_id", "title", "content"])
                for chap_id, (title, content) in cache.items():
                    writer.writerow([chap_id, title, content])
            log_tr("cache_saved", path=cache_path, count=len(cache))
        except Exception as exc:
            log_tr("cache_save_failed", error=exc)

    def download_chapters_concurrent(self, chapters_info: List[Dict], novel_id: str, max_workers: int = DEFAULT_MAX_THREADS) -> Tuple[Dict[int, Dict], List[int]]:
        cache = self._load_cache(novel_id)
        success_dict: Dict[int, Dict] = {}
        failed_ids: List[int] = []
        to_download: List[Dict] = []
        for chapter in chapters_info:
            chap_id = int(chapter["id"])
            chapter_title = chapter.get("title") or str(chap_id)
            need_fire = int(chapter.get("need_fire") or 0)
            if need_fire > 0:
                success_dict[chap_id] = {"id": chap_id, "title": chapter_title, "content": tr("locked_placeholder"), "locked": True}
                safe_print(f"【{chapter_title}】 {tr('chapter_locked')}")
            elif chap_id in cache:
                title, content = cache[chap_id]
                success_dict[chap_id] = {"id": chap_id, "title": title, "content": content}
                log_tr("cache_hit", title=title)
            else:
                to_download.append(chapter)
        if to_download:
            with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
                future_map = {executor.submit(self.download_chapter, int(chapter["id"])): chapter for chapter in to_download}
                for future in as_completed(future_map):
                    chapter = future_map[future]
                    chap_id = int(chapter["id"])
                    chapter_title = chapter.get("title") or str(chap_id)
                    try:
                        ok, title, content = future.result()
                    except Exception as exc:
                        safe_print(f"[{chapter_title}] {tr('chapter_network_fail')}: {exc}")
                        failed_ids.append(chap_id)
                        continue
                    if ok and title is not None and content is not None:
                        final_title = title or chapter_title
                        success_dict[chap_id] = {"id": chap_id, "title": final_title, "content": content}
                        cache[chap_id] = (final_title, content)
                        log_tr("downloaded_cached", title=final_title)
                    else:
                        log_tr("download_failed_uncached", title=chapter_title)
                        failed_ids.append(chap_id)
        self._save_cache(novel_id, cache)
        return success_dict, failed_ids

