#!/usr/bin/env python3
"""Tarot Birth Card and Year Card calculator.

Usage:
  birth_card.py 1995-08-17
  birth_card.py 17/08/2538            # Thai Buddhist year (> 2400) is converted automatically
  birth_card.py 1995-08-17 --year 2026
"""

import argparse
import json
import re
import sys
from datetime import date

from tarot_data import MAJOR


def parse_date(text):
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text.strip())
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", text.strip())
        if not m:
            raise ValueError("รูปแบบวันที่ต้องเป็น YYYY-MM-DD หรือ DD/MM/YYYY")
        d, mo, y = map(int, m.groups())
    if y > 2400:  # พ.ศ.
        y -= 543
    return date(y, mo, d)


def digit_sum(n):
    return sum(int(c) for c in str(n))


def card_chain(total):
    """Reduce to <= 22, then follow the digit-sum chain to a single digit."""
    n = total
    while n > 22:
        n = digit_sum(n)
    chain = [n]
    while chain[-1] >= 10:
        nxt = digit_sum(chain[-1])
        chain.append(nxt)
    return chain


def to_cards(chain):
    cards = []
    for n in chain:
        idx = 0 if n == 22 else n
        en, th = MAJOR[idx]
        cards.append({"number": n, "card": en, "card_th": th})
    return cards


def main():
    p = argparse.ArgumentParser()
    p.add_argument("birthdate")
    p.add_argument("--year", type=int, help="ปีที่ต้องการดู Year Card (ค.ศ. หรือ พ.ศ.)")
    args = p.parse_args()
    try:
        b = parse_date(args.birthdate)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    total = b.day + b.month + b.year
    chain = card_chain(digit_sum(total) if total > 22 else total)
    birth = to_cards(chain)
    res = {
        "ok": True,
        "birthdate": b.isoformat(),
        "sum": total,
        "birth_cards": birth,
        "personality_card": birth[0],
        "soul_card": birth[-1],
        "note": "ใบแรก = ไพ่บุคลิก, ใบสุดท้าย = ไพ่แก่นวิญญาณ (ถ้ามีใบเดียว ทั้งสองคือใบเดียวกัน)",
    }
    year = args.year if args.year else date.today().year
    if year > 2400:
        year -= 543
    ytotal = b.day + b.month + year
    ychain = card_chain(digit_sum(ytotal) if ytotal > 22 else ytotal)
    res["year"] = year
    res["year_card"] = to_cards(ychain)[0]
    res["year_note"] = f"ธีมตั้งแต่วันเกิดปี {year} ถึงวันเกิดปี {year + 1}"
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
