import sys
import tempfile
import types
from pathlib import Path

sys.modules.setdefault("ebooklib", types.SimpleNamespace(epub=types.SimpleNamespace(EpubHtml=object)))

from exporter import find_existing_export, merge_selections, parse_selection_tag
from models import SelectedVolume


def test_parse_selection_tag():
    assert parse_selection_tag("Book[v1-all;v2-c1-3-7].epub") == [
        SelectedVolume(1, None),
        SelectedVolume(2, (1, 3, 7)),
    ]
    assert parse_selection_tag("Book.epub") == []


def test_merge_selections():
    assert merge_selections(
        [SelectedVolume(2, (1, 2)), SelectedVolume(1, (4,))],
        [SelectedVolume(2, (2, 3)), SelectedVolume(3, None)],
    ) == [
        SelectedVolume(1, (4,)),
        SelectedVolume(2, (1, 2, 3)),
        SelectedVolume(3, None),
    ]
    assert merge_selections([SelectedVolume(2, None)], [SelectedVolume(2, (5,))]) == [SelectedVolume(2, None)]


def test_find_existing_export_prefers_newest_stem():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        old = root / "Book[v1-c1-2].txt"
        new_txt = root / "Book[v1-c1-2-3].txt"
        new_epub = root / "Book[v1-c1-2-3].epub"
        old.write_text("old", encoding="utf-8")
        new_txt.write_text("new", encoding="utf-8")
        new_epub.write_bytes(b"epub")
        old.touch()
        new_txt.touch()
        new_epub.touch()
        stem, selections = find_existing_export(root, "Book")
        assert stem == "Book[v1-c1-2-3]"
        assert selections == [SelectedVolume(1, (1, 2, 3))]


if __name__ == "__main__":
    test_parse_selection_tag()
    test_merge_selections()
    test_find_existing_export_prefers_newest_stem()
    print("All export merge tests passed.")
