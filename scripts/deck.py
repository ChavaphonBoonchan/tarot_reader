#!/usr/bin/env python3
"""Virtual tarot deck that the *user* shuffles, cuts and draws.

The deck order lives in a state file. Every command changes the real deck order,
so the result depends on the user's choices (method, times, cut points, picked positions).
Shuffle/cut/fan never reveal card faces; only draw/bottom do.

Usage examples:
  deck.py new [--fresh] [--no-reversals]
  deck.py shuffle --method riffle|overhand|wash|pile [--times N] [--piles K] [--order 2,1,3]
  deck.py cut [--at N|top|upper|middle|lower|bottom] [--piles K] [--points 20,50] [--order 3,1,2] [--turn 2]
  deck.py fan
  deck.py draw (--pick 5,23,61 | --top N | --bottom N) [--spread celtic-cross]
  deck.py bottom
  deck.py status
  deck.py return-jumpers
  deck.py quick (--spread ID | --count N) [--no-reversals]
  deck.py list-spreads
"""

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

from tarot_data import DECK, load_spreads

RNG = random.SystemRandom()
DEFAULT_STATE = Path(tempfile.gettempdir()) / "tarot-deck-state.json"
CUT_WORDS = {"top": 0.15, "upper": 0.3, "middle": 0.5, "lower": 0.7, "bottom": 0.85}
JUMPER_CHANCE = {"riffle": 0.02, "overhand": 0.015, "wash": 0.0, "pile": 0.0}


# ---------- helpers ----------

def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fail(msg):
    out({"ok": False, "error": msg})
    sys.exit(1)


def load_state(path):
    if not path.exists():
        fail("ยังไม่มีสำรับ — เรียก `deck.py new` ก่อน")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path, state):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def card_view(entry, reversals):
    cid, rev = entry
    c = DECK[cid]
    rev = bool(rev) and reversals
    return {
        "card": c["name"],
        "card_th": c["name_th"],
        "arcana": c["arcana"],
        "suit": c["suit"],
        "element": c["element"],
        "orientation": "reversed" if rev else "upright",
        "orientation_th": "กลับหัว" if rev else "หัวตั้ง",
    }


def parse_int_list(text, name):
    try:
        return [int(x) for x in text.split(",") if x.strip()]
    except ValueError:
        fail(f"{name} ต้องเป็นตัวเลขคั่นด้วยจุลภาค เช่น 2,1,3")


def flip(entry):
    return [entry[0], not entry[1]]


# ---------- shuffle methods (deck[0] is the top card) ----------

def riffle(deck):
    n = len(deck)
    k = sum(RNG.random() < 0.5 for _ in range(n))  # binomial cut, like a human split
    left, right = deck[:k], deck[k:]
    result = []
    while left or right:  # Gilbert–Shannon–Reeds interleave
        if RNG.random() < len(left) / (len(left) + len(right)):
            result.append(left.pop(0))
        else:
            result.append(right.pop(0))
    return result


def overhand(deck):
    remaining = list(deck)
    result = []
    while remaining:
        size = RNG.randint(1, min(10, len(remaining)))
        packet, remaining = remaining[:size], remaining[size:]
        result = packet + result
    return result


def wash(deck, reversals):
    result = list(deck)
    RNG.shuffle(result)
    if reversals:
        result = [flip(e) if RNG.random() < 0.5 else e for e in result]
    return result


def pile_shuffle(deck, piles, order):
    stacks = [[] for _ in range(piles)]
    for i, e in enumerate(deck):
        stacks[i % piles].insert(0, e)  # dealing face-down reverses each pile
    if order is None:
        order = list(range(1, piles + 1))
        RNG.shuffle(order)
    return [e for idx in order for e in stacks[idx - 1]], order


def maybe_jumper(state, method):
    if state["deck"] and RNG.random() < JUMPER_CHANCE[method]:
        idx = RNG.randrange(len(state["deck"]))
        entry = state["deck"].pop(idx)
        state["jumpers"].append(entry)
        return card_view(entry, state["reversals"])
    return None


# ---------- commands ----------

def cmd_new(args):
    entries = [[c["id"], False] for c in DECK]
    if not args.fresh:
        RNG.shuffle(entries)
        if not args.no_reversals:
            entries = [flip(e) if RNG.random() < 0.5 else e for e in entries]
    state = {"deck": entries, "reversals": not args.no_reversals, "drawn": [],
             "jumpers": [], "spread": None, "history": []}
    state["history"].append("new (fresh, เรียงลำดับ)" if args.fresh else "new (สำรับที่เคยใช้)")
    save_state(args.state, state)
    out({"ok": True, "message": "เปิดสำรับใหม่แล้ว", "cards_in_deck": len(entries),
         "fresh": args.fresh, "reversals": state["reversals"]})


def cmd_shuffle(args):
    state = load_state(args.state)
    if state["drawn"]:
        fail("จั่วไพ่ไปแล้ว ห้ามสับใหม่สำหรับคำถามเดิม — เริ่มคำถามใหม่ด้วย `deck.py new`")
    times = max(1, args.times)
    jumpers = []
    order_used = None
    order = parse_int_list(args.order, "--order") if args.order else None
    if args.method == "pile":
        if order and sorted(order) != list(range(1, args.piles + 1)):
            fail(f"--order ต้องเป็นเลข 1..{args.piles} ครบทุกกองไม่ซ้ำ")
    for _ in range(times):
        if args.method == "riffle":
            state["deck"] = riffle(state["deck"])
        elif args.method == "overhand":
            state["deck"] = overhand(state["deck"])
        elif args.method == "wash":
            state["deck"] = wash(state["deck"], state["reversals"])
        elif args.method == "pile":
            state["deck"], order_used = pile_shuffle(state["deck"], args.piles, order)
        j = maybe_jumper(state, args.method)
        if j:
            jumpers.append(j)
    desc = f"shuffle {args.method} x{times}"
    if args.method == "pile":
        desc += f" ({args.piles} กอง, รวมลำดับ {order_used})"
    state["history"].append(desc)
    save_state(args.state, state)
    res = {"ok": True, "message": f"สับแบบ {args.method} {times} รอบแล้ว",
           "cards_in_deck": len(state["deck"]), "jumpers": jumpers}
    if jumpers:
        res["note"] = "มีไพ่กระเด็นออกมา — ถามผู้ใช้ว่าจะอ่านเป็นข้อความเสริม หรือใส่คืนด้วย return-jumpers"
    out(res)


def cmd_cut(args):
    state = load_state(args.state)
    if state["drawn"]:
        fail("จั่วไพ่ไปแล้ว ห้ามตัดใหม่สำหรับคำถามเดิม — เริ่มคำถามใหม่ด้วย `deck.py new`")
    deck = state["deck"]
    n = len(deck)
    if n < 2:
        fail("ไพ่เหลือน้อยเกินกว่าจะตัด")

    def to_point(value):
        if isinstance(value, str) and value in CUT_WORDS:
            base = CUT_WORDS[value] * n
            return max(1, min(n - 1, round(base + RNG.uniform(-3, 3))))  # human hands are imprecise
        try:
            p = int(value)
        except (TypeError, ValueError):
            fail(f"จุดตัด '{value}' ไม่ถูกต้อง ใช้ตัวเลข 1..{n - 1} หรือ {', '.join(CUT_WORDS)}")
        if not 1 <= p <= n - 1:
            fail(f"จุดตัดต้องอยู่ระหว่าง 1..{n - 1}")
        return p

    if args.points:
        points = sorted({to_point(x.strip()) for x in args.points.split(",")})
    elif args.at:
        points = [to_point(args.at)]
    else:
        piles = max(2, args.piles)
        if piles > min(5, n):
            fail("ตัดได้ 2–5 กอง")
        points = sorted(RNG.sample(range(1, n), piles - 1))
    bounds = [0] + points + [n]
    stacks = [deck[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]
    k = len(stacks)

    order = parse_int_list(args.order, "--order") if args.order else list(range(k, 0, -1))
    if sorted(order) != list(range(1, k + 1)):
        fail(f"--order ต้องเป็นเลข 1..{k} ครบทุกกองไม่ซ้ำ (กอง 1 = กองบนสุดเดิม)")
    turns = parse_int_list(args.turn, "--turn") if args.turn else []
    for t in turns:
        if not 1 <= t <= k:
            fail(f"--turn ต้องเป็นเลขกอง 1..{k}")
        stacks[t - 1] = [flip(e) for e in reversed(stacks[t - 1])]

    state["deck"] = [e for idx in order for e in stacks[idx - 1]]
    sizes = [len(s) for s in stacks]
    desc = f"cut {k} กอง ขนาด {sizes} รวมลำดับ {order}" + (f" หมุนกอง {turns}" if turns else "")
    state["history"].append(desc)
    save_state(args.state, state)
    out({"ok": True, "message": desc, "piles": k, "pile_sizes": sizes, "order": order,
         "turned": turns, "cards_in_deck": n})


def cmd_fan(args):
    state = load_state(args.state)
    n = len(state["deck"])
    out({"ok": True, "message": f"แผ่ไพ่คว่ำหน้า {n} ใบ ตำแหน่ง 1 (ซ้ายสุด/บนสุด) ถึง {n} (ขวาสุด/ล่างสุด)",
         "cards_in_deck": n, "positions": f"1-{n}",
         "visual": " ".join("🂠" for _ in range(min(n, 26))) + (" ..." if n > 26 else "")})


def cmd_draw(args):
    state = load_state(args.state)
    deck = state["deck"]
    n = len(deck)
    spreads = load_spreads()
    if args.spread:
        if args.spread not in spreads:
            fail(f"ไม่รู้จักสเปรด '{args.spread}' — ดู list-spreads")
        state["spread"] = args.spread

    if args.pick:
        picks = parse_int_list(args.pick, "--pick")
        if len(set(picks)) != len(picks):
            fail("เลือกตำแหน่งซ้ำ — ขอให้ผู้ใช้เลือกใหม่ไม่ให้ซ้ำ")
        bad = [p for p in picks if not 1 <= p <= n]
        if bad:
            fail(f"ตำแหน่ง {bad} อยู่นอกช่วง 1..{n}")
        idxs = [p - 1 for p in picks]
        how = f"pick {picks}"
    else:
        count = args.top or args.bottom
        if not count and args.spread:
            count = len(spreads[args.spread]["positions"])
        if not count:
            fail("ระบุ --pick, --top N, หรือ --bottom N")
        if count > n:
            fail(f"ไพ่เหลือ {n} ใบ ไม่พอจั่ว {count} ใบ")
        idxs = list(range(count)) if not args.bottom else list(range(n - 1, n - 1 - count, -1))
        how = f"{'top' if not args.bottom else 'bottom'} {count}"

    chosen = [deck[i] for i in idxs]
    for i in sorted(idxs, reverse=True):
        deck.pop(i)

    positions = spreads[state["spread"]]["positions"] if state["spread"] else None
    results = []
    for entry in chosen:
        pos_no = len(state["drawn"]) + 1
        view = card_view(entry, state["reversals"])
        view["position_no"] = pos_no
        if positions:
            view["position"] = positions[pos_no - 1] if pos_no <= len(positions) else "ไพ่ขยายความ (Clarifier)"
        state["drawn"].append(entry)
        results.append(view)

    state["history"].append(f"draw {how}")
    save_state(args.state, state)
    res = {"ok": True, "spread": state["spread"], "drawn": results,
           "total_drawn": len(state["drawn"]), "cards_left": len(deck)}
    if positions:
        res["spread_name"] = spreads[state["spread"]]["name"]
        res["spread_positions_total"] = len(positions)
        if len(state["drawn"]) < len(positions):
            res["note"] = f"ยังต้องจั่วอีก {len(positions) - len(state['drawn'])} ใบให้ครบสเปรด"
    out(res)


def cmd_bottom(args):
    state = load_state(args.state)
    if not state["deck"]:
        fail("ไม่มีไพ่เหลือในสำรับ")
    state["history"].append("reveal bottom card")
    save_state(args.state, state)
    out({"ok": True, "bottom_card": card_view(state["deck"][-1], state["reversals"]),
         "note": "ไพ่ก้นสำรับ = รากลึกของเรื่อง อ่านเป็นข้อมูลเสริม"})


def cmd_status(args):
    state = load_state(args.state)
    out({"ok": True, "cards_in_deck": len(state["deck"]), "drawn": len(state["drawn"]),
         "jumpers_set_aside": [card_view(e, state["reversals"]) for e in state["jumpers"]],
         "reversals": state["reversals"], "spread": state["spread"], "history": state["history"]})


def cmd_return_jumpers(args):
    state = load_state(args.state)
    count = len(state["jumpers"])
    for e in state["jumpers"]:
        state["deck"].insert(RNG.randint(0, len(state["deck"])), e)
    state["jumpers"] = []
    state["history"].append(f"return {count} jumper(s)")
    save_state(args.state, state)
    out({"ok": True, "returned": count, "cards_in_deck": len(state["deck"])})


def cmd_quick(args):
    spreads = load_spreads()
    if args.spread:
        if args.spread not in spreads:
            fail(f"ไม่รู้จักสเปรด '{args.spread}' — ดู list-spreads")
        positions = spreads[args.spread]["positions"]
        count = len(positions)
    elif args.count:
        positions, count = None, args.count
    else:
        fail("ระบุ --spread หรือ --count")
    if not 1 <= count <= 78:
        fail("จำนวนไพ่ต้องอยู่ระหว่าง 1–78")
    reversals = not args.no_reversals
    ids = [c["id"] for c in DECK if c["name"] not in set(args.exclude or [])]
    RNG.shuffle(ids)
    results = []
    for i, cid in enumerate(ids[:count]):
        view = card_view([cid, RNG.random() < 0.5], reversals)
        view["position_no"] = i + 1
        if positions:
            view["position"] = positions[i]
        results.append(view)
    res = {"ok": True, "mode": "quick", "spread": args.spread, "drawn": results}
    if args.spread:
        res["spread_name"] = spreads[args.spread]["name"]
    out(res)


def cmd_list_spreads(args):
    spreads = load_spreads()
    out({k: {"name": v["name"], "cards": len(v["positions"]), "positions": v["positions"]}
         for k, v in spreads.items()})


def main():
    p = argparse.ArgumentParser(description="Virtual tarot deck the user shuffles, cuts and draws.")
    p.add_argument("--state", type=Path, default=DEFAULT_STATE, help="path ของไฟล์สถานะสำรับ")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="เปิดสำรับใหม่")
    s.add_argument("--fresh", action="store_true", help="สำรับใหม่แกะกล่อง เรียงลำดับ หัวตั้งทั้งหมด")
    s.add_argument("--no-reversals", action="store_true", help="ไม่ใช้ไพ่กลับหัว")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("shuffle", help="สับไพ่")
    s.add_argument("--method", choices=["riffle", "overhand", "wash", "pile"], default="riffle")
    s.add_argument("--times", type=int, default=1)
    s.add_argument("--piles", type=int, default=3, help="จำนวนกองสำหรับ pile shuffle")
    s.add_argument("--order", help="ลำดับรวมกองสำหรับ pile shuffle เช่น 2,3,1")
    s.set_defaults(func=cmd_shuffle)

    s = sub.add_parser("cut", help="ตัดไพ่")
    s.add_argument("--at", help="จุดตัดครั้งเดียว: ตัวเลข หรือ top/upper/middle/lower/bottom")
    s.add_argument("--points", help="จุดตัดหลายจุด เช่น 20,55")
    s.add_argument("--piles", type=int, default=2, help="จำนวนกอง (จุดตัดสุ่ม) ถ้าไม่ระบุ --at/--points")
    s.add_argument("--order", help="ลำดับรวมกอง (กอง 1 = กองบนเดิม) เช่น 3,1,2 ค่าเริ่มต้นกลับลำดับ")
    s.add_argument("--turn", help="หมุนกองกลับหัว เช่น 2 หรือ 1,3")
    s.set_defaults(func=cmd_cut)

    s = sub.add_parser("fan", help="แผ่ไพ่คว่ำหน้าให้ผู้ใช้เลือกตำแหน่ง")
    s.set_defaults(func=cmd_fan)

    s = sub.add_parser("draw", help="จั่วไพ่")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--pick", help="ตำแหน่งที่ผู้ใช้เลือกจากการแผ่ไพ่ เช่น 5,23,61")
    g.add_argument("--top", type=int, help="จั่วจากบนสุด N ใบ")
    g.add_argument("--bottom", type=int, help="จั่วจากล่างสุด N ใบ")
    s.add_argument("--spread", help="id สเปรด (ดู list-spreads)")
    s.set_defaults(func=cmd_draw)

    s = sub.add_parser("bottom", help="เปิดดูไพ่ก้นสำรับ")
    s.set_defaults(func=cmd_bottom)

    s = sub.add_parser("status", help="ดูสถานะ/ประวัติ (ไม่เปิดหน้าไพ่ในสำรับ)")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("return-jumpers", help="ใส่ไพ่ที่กระเด็นกลับเข้าสำรับ")
    s.set_defaults(func=cmd_return_jumpers)

    s = sub.add_parser("quick", help="สุ่มให้ทันทีโดยไม่ทำพิธี")
    s.add_argument("--spread")
    s.add_argument("--count", type=int)
    s.add_argument("--no-reversals", action="store_true")
    s.add_argument("--exclude", action="append", help="ชื่อไพ่ที่ไม่เอา (ใช้ซ้ำได้)")
    s.set_defaults(func=cmd_quick)

    s = sub.add_parser("list-spreads", help="รายชื่อสเปรดทั้งหมด")
    s.set_defaults(func=cmd_list_spreads)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
