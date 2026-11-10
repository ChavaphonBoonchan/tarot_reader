"""Shared tarot deck data: 78 cards in standard order (Major 0-21, then Wands, Cups, Swords, Pentacles)."""

import json
from pathlib import Path

MAJOR = [
    ("The Fool", "คนโง่/ผู้เริ่มต้น"),
    ("The Magician", "นักมายากล"),
    ("The High Priestess", "นักบวชหญิง"),
    ("The Empress", "จักรพรรดินี"),
    ("The Emperor", "จักรพรรดิ"),
    ("The Hierophant", "พระสังฆราช"),
    ("The Lovers", "คู่รัก"),
    ("The Chariot", "รถศึก"),
    ("Strength", "พละกำลัง"),
    ("The Hermit", "ฤาษี"),
    ("Wheel of Fortune", "กงล้อแห่งโชคชะตา"),
    ("Justice", "ความยุติธรรม"),
    ("The Hanged Man", "คนแขวน"),
    ("Death", "ความตาย/การเปลี่ยนแปลง"),
    ("Temperance", "ความพอดี"),
    ("The Devil", "ปีศาจ"),
    ("The Tower", "หอคอย"),
    ("The Star", "ดวงดาว"),
    ("The Moon", "ดวงจันทร์"),
    ("The Sun", "ดวงอาทิตย์"),
    ("Judgement", "การพิพากษา"),
    ("The World", "โลก"),
]

SUITS = [
    ("Wands", "ไม้เท้า", "ไฟ"),
    ("Cups", "ถ้วย", "น้ำ"),
    ("Swords", "ดาบ", "ลม"),
    ("Pentacles", "เหรียญ", "ดิน"),
]

RANKS = [
    ("Ace", "เอซ"), ("Two", "2"), ("Three", "3"), ("Four", "4"), ("Five", "5"),
    ("Six", "6"), ("Seven", "7"), ("Eight", "8"), ("Nine", "9"), ("Ten", "10"),
    ("Page", "เพจ"), ("Knight", "อัศวิน"), ("Queen", "ราชินี"), ("King", "ราชา"),
]


def build_deck():
    """Return the 78 cards in standard order. Index 0..77 == number 1..78 in techniques.md."""
    cards = []
    for i, (en, th) in enumerate(MAJOR):
        cards.append({"id": len(cards), "name": en, "name_th": th, "arcana": "major",
                      "number": i, "suit": None, "element": None})
    for suit_en, suit_th, element in SUITS:
        for rank_en, rank_th in RANKS:
            cards.append({"id": len(cards), "name": f"{rank_en} of {suit_en}",
                          "name_th": f"{rank_th} {suit_th}", "arcana": "minor",
                          "rank": rank_en, "suit": suit_en, "element": element})
    return cards


DECK = build_deck()
assert len(DECK) == 78

SPREADS_PATH = Path(__file__).resolve().parent.parent / "assets" / "spreads.json"


def load_spreads():
    with open(SPREADS_PATH, encoding="utf-8") as f:
        return json.load(f)
