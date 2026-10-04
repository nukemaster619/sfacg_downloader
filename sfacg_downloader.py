from api import SfacgClient
from auth import ensure_login
from catalog import get_novel_info, select_downloads
from config import tr
from exporter import build_epub_and_txt
from ui import choose_language, safe_print

def main() -> None:
    choose_language()
    client = SfacgClient()
    client.initialize_signature()
    ensure_login(client)
    novel_id = input(tr("input_novel_id")).strip()
    client.set_download_user_agent()
    catalog = get_novel_info(client, novel_id)
    if not catalog.volumes:
        safe_print(tr("catalog_empty"))
        raise SystemExit(1)
    safe_print(f"{tr('novel_title')}: {catalog.title}")
    safe_print(tr("choose_volume"))
    for volume in catalog.volumes:
        safe_print(f"{volume.index}: {volume.title}")
    selected_volumes = select_downloads(catalog)
    safe_print(f"{tr('plan_download')} {[selection.display() for selection in selected_volumes]}")
    txt_name, epub_name = build_epub_and_txt(client, catalog, selected_volumes)
    safe_print(f"{tr('saved')} {txt_name} / {epub_name}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        safe_print(f"{tr('fatal')} {exc}")
        raise
