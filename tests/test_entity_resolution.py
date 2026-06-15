import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.db import DB
from src.entity_resolution.people_matcher import find_or_create_person
from src.utils.text import normalize_name, normalize_title


def _db(tmp_path):
    return DB(str(tmp_path / "t.db"))


def test_normalize():
    assert normalize_name("Xipeng  Qiu!") == "xipeng qiu"
    assert normalize_title("LoRA: Low-Rank Adaptation") == "loralowrankadaptation"


def test_same_openalex_id_merges(tmp_path):
    db = _db(tmp_path)
    with db.session() as s:
        a = find_or_create_person(db, s, "Wei Zhang", openalex_author_id="A1", affiliation="THU")
        b = find_or_create_person(db, s, "Wei Zhang", openalex_author_id="A1", affiliation="THU")
        s.commit()
        assert a.id == b.id


def test_same_name_diff_affiliation_not_merge(tmp_path):
    db = _db(tmp_path)
    with db.session() as s:
        a = find_or_create_person(db, s, "Lei Zhang", affiliation="Peking University")
        b = find_or_create_person(db, s, "Lei Zhang", affiliation="Stanford University")
        s.commit()
        assert a.id != b.id


def test_diff_openalex_id_not_merge(tmp_path):
    db = _db(tmp_path)
    with db.session() as s:
        a = find_or_create_person(db, s, "Yang Liu", openalex_author_id="A1")
        b = find_or_create_person(db, s, "Yang Liu", openalex_author_id="A2")
        s.commit()
        assert a.id != b.id
