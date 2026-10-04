from typing import List

from api import SfacgClient
from models import NovelCatalog, SelectedVolume
from ui import ask_download_selection

def get_novel_info(client: SfacgClient, novel_id: str) -> NovelCatalog:
    return client.fetch_catalog(novel_id)

def select_downloads(catalog: NovelCatalog) -> List[SelectedVolume]:
    return ask_download_selection(catalog)
