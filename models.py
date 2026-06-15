from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass(frozen=True)
class ChapterRef:
    chapter_id: int
    title_hint: str = ""
    need_fire: int = 0

@dataclass
class ChapterContent:
    chapter_id: int
    title: str
    content: str

@dataclass
class Volume:
    index: int
    title: str
    chapters: List[ChapterRef]

@dataclass(frozen=True)
class SelectedVolume:
    index: int
    chapter_indices: Optional[Tuple[int, ...]] = None

    def display(self) -> str:
        if self.chapter_indices is None:
            return f"{self.index}:*"
        return f"{self.index}:" + ",".join(str(index) for index in self.chapter_indices)

    def filename_label(self) -> str:
        if self.chapter_indices is None:
            return f"v{self.index}-all"
        chapter_label = "-".join(str(index) for index in self.chapter_indices)
        return f"v{self.index}-c{chapter_label}"

@dataclass
class NovelCatalog:
    novel_id: str
    title: str
    author: str
    cover_url: str
    volumes: List[Volume]
