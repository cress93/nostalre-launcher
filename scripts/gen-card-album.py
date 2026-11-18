#!/usr/bin/env python3
"""The Card Album's tables, for the server (npc/custom/cardalbum_table.txt, read by npc/custom/cardalbum.txt) and the
client (lib/game/src/card_album_tables.rs, its Album screen): every card a monster on the server's permanent spawns
drops, in the region of the town nearest the maps it spawns on, and the rewards: one at each count of cards, and
one for each region whose cards (bosses' aside) are all in.

A region is a town of the Kafra network (npc/custom/waypoint_points.txt, scripts/gen-waypoints.py) and the maps
fewest map changes from it (the navigation's links, lib/game/src/nav_link_tables.rs, scripts/nav-links.py: run both
first); Isgard and Muspelheim make one of their own. A card's monster is the one dropping it most spawned, its map
where it spawns most. Cards of monsters only in castles or quest maps are no part of it (guild dungeons are in, their gates being
npc/custom/guilddungeon.txt).

The rewards are no stats: shop discount and overcharge, max weight, Kafra teleports' fee off, the quest board's
waits shorter, refine chance. The counts' are set here; the two biggest regions' refine chance, each other region's
the next kind round, by size, the kind's share of what regions give split between its regions by their cards.

Usage: scripts/gen-card-album.py [rathena dir] [client output] [server output]
"""
import collections
import glob
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATHENA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "server")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "client/lib/game/src/card_album_tables.rs")
SERVER_OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(RATHENA, "npc/custom/cardalbum_table.txt")
LINKS = os.path.join(ROOT, "client/lib/game/src/nav_link_tables.rs")

# the rewards' kinds, as the server's #ALBUM_ variables and the client's PerkKind number them
DISCOUNT, OVERCHARGE, WEIGHT, TRAVEL, BOARD, REFINE = 1, 2, 3, 4, 5, 6
# at each count of cards: (count, kind, amount): % off buying, % more selling, max weight, % off Kafra teleports,
# % off the quest board's waits, refine chance in % points
MILESTONES = [
    (5, TRAVEL, 10), (10, DISCOUNT, 2), (20, WEIGHT, 200), (30, OVERCHARGE, 2), (45, BOARD, 5), (60, REFINE, 1),
    (80, TRAVEL, 10), (100, DISCOUNT, 3), (125, WEIGHT, 300), (150, OVERCHARGE, 3), (175, BOARD, 10),
    (200, TRAVEL, 15), (250, REFINE, 1), (300, DISCOUNT, 3), (350, WEIGHT, 500), (400, OVERCHARGE, 3),
    (450, TRAVEL, 15), (500, BOARD, 10), (550, REFINE, 1), (600, DISCOUNT, 4), (650, OVERCHARGE, 4),
]
# what all the regions give, each kind: with the counts', the most there is (20%, 20%, +2000, free, half, +5%)
REGION_BUDGET = {DISCOUNT: 8, OVERCHARGE: 8, WEIGHT: 1000, TRAVEL: 50, BOARD: 25, REFINE: 2}
# refine chance for the biggest regions only, it is the one that counts most; the other kinds round the rest,
# biggest first
REFINE_REGIONS = 2
REGION_ORDER = [WEIGHT, DISCOUNT, TRAVEL, OVERCHARGE, BOARD]
# a town and the one beside it that is its own part (Morroc's ruins, Payon's archers)
MERGE = {"moc_ruins": "morocc", "pay_arche": "payon"}
REGION_NAME = {"morocc": "Morroc", "payon": "Payon"}
BEYOND = re.compile(r"^(jor_|mu_|hem_)")
BEYOND_NAME = "Beyond Midgard"
NOT_A_PLACE = re.compile(r"@|_cas|^gl_cas|^job|^que_|^tur_d04|^bat_|^e_|pvp|arena|_q$|\d[a-z]$|^prt_q$|^slabw|^jupe_core")
SPAWN = re.compile(r"([a-z0-9_]+)(?:,\d+,\d+(?:,\d+,\d+)?)?\t(?:boss_)?monster\t[^\t]+\t(\d+),(\d+)")


def main():
    spec = importlib.util.spec_from_file_location("waypoints", os.path.join(ROOT, "scripts/gen-waypoints.py"))
    waypoints = importlib.util.module_from_spec(spec)
    os.environ["RATHENA_DIR"] = RATHENA
    spec.loader.exec_module(waypoints)
    seen = set()
    files = waypoints.loaded("npc/re/scripts_main.conf", seen) + waypoints.loaded("npc/scripts_custom.conf", seen)

    spawns = collections.defaultdict(collections.Counter)
    for f in files:
        if "/mobs/" not in f and "/custom/lasagna/" not in f:
            continue
        for line in open(os.path.join(RATHENA, f), errors="ignore"):
            m = SPAWN.match(line)
            if m and not NOT_A_PLACE.search(m.group(1)):
                spawns[int(m.group(2))][m.group(1)] += int(m.group(3))

    cards = {}
    for f in sorted(glob.glob(os.path.join(RATHENA, "db/re/item_db_*.yml"))):
        for blk in open(f, errors="ignore").read().split("\n  - Id: ")[1:]:
            if re.search(r"\n    Type: Card\b", blk):
                cards[re.search(r"\n    AegisName: (\S+)", blk).group(1)] = int(blk.split("\n")[0].split()[0])
    droppers = collections.defaultdict(list)
    boss = {}
    for blk in open(os.path.join(RATHENA, "db/re/mob_db.yml"), errors="ignore").read().split("\n  - Id: ")[1:]:
        mob = int(blk.split("\n")[0].split()[0])
        boss[mob] = "\n    Mvp" in blk or re.search(r"\n    Class: Boss\b", blk) is not None
        for item in re.findall(r"- Item: (\S+)", blk):
            if item in cards and mob in spawns:
                droppers[cards[item]].append(mob)

    # each map's nearest town, by map changes along the navigation's links
    graph = collections.defaultdict(set)
    for a, b in re.findall(r'\("([a-z0-9_]+)", \d+, \d+, "([a-z0-9_]+)"', open(LINKS).read()):
        graph[a].add(b)
        graph[b].add(a)
    table = open(os.path.join(RATHENA, "npc/custom/waypoint_points.txt")).read()

    def arr(name):
        values = []
        for chunk in re.findall(r"\$@" + re.escape(name) + r"\[\d+\], (.*);", table):
            values += re.findall(r'"([^"]*)"|(-?\d+)', chunk)
        return [a or b for a, b in values]

    town_name = {}
    for town, name, dungeon in zip(arr("way_map$"), arr("way_name$"), arr("way_dungeon")):
        if dungeon == "0":
            key = MERGE.get(town, town)
            town_name[key] = REGION_NAME.get(key, name)
    nearest = {}
    for town in town_name:
        queue, found = collections.deque([(town, 0)]), {town}
        for start in [t for t, k in MERGE.items() if k == town]:
            queue.append((start, 0))
            found.add(start)
        while queue:
            m, d = queue.popleft()
            if m not in nearest or nearest[m][0] > d:
                nearest[m] = (d, town_name[town])
            for n in sorted(graph[m]):
                if n not in found:
                    found.add(n)
                    queue.append((n, d + 1))

    def region_of(m):
        return BEYOND_NAME if BEYOND.match(m) else nearest.get(m, (0, None))[1]

    album = []
    for card, mobs in sorted(droppers.items()):
        # the dropper most spawned (an ordinary one before a boss), on its map with the most
        mob = max(mobs, key=lambda i: (not boss[i], sum(spawns[i].values()), -i))
        on = [(c, m) for m, c in spawns[mob].items() if region_of(m)]
        if not on:
            continue
        _, map_name = max(on)
        album.append((card, region_of(map_name), mob, all(boss[i] for i in mobs), map_name))

    need = collections.Counter(r for _, r, _, b, _ in album if not b)
    regions = sorted(need, key=lambda r: (-need[r], r))
    kinds = {r: REFINE if i < REFINE_REGIONS else REGION_ORDER[(i - REFINE_REGIONS) % len(REGION_ORDER)]
             for i, r in enumerate(regions)}
    rewards = {}
    for kind, budget in REGION_BUDGET.items():
        mine = [r for r in regions if kinds[r] == kind]
        total = sum(need[r] for r in mine)
        step = 50 if kind == WEIGHT else 1
        for r in mine:
            rewards[r] = max(step, round(budget * need[r] / total / step) * step)
    index = {r: i for i, r in enumerate(regions)}
    album = [a for a in album if a[1] in index]
    album.sort(key=lambda a: (index[a[1]], a[3], a[0]))

    rust = [
        "// Generated by scripts/gen-card-album.py from rAthena's spawns, mob_db, item_db and the navigation's links;",
        "// do not edit.",
        "",
        "/// The regions: name, cards to complete it (bosses' aside), its reward's kind and amount (`crate::card_album::Perk`)",
        f"pub static REGIONS: [(&str, u16, u8, u16); {len(regions)}] = [",
    ]
    for r in regions:
        rust.append(f'    ("{r}", {need[r]}, {kinds[r]}, {rewards[r]}),')
    rust += [
        "];",
        "",
        "/// The cards: card id, region, the monster dropping it, whether only bosses do, the map it spawns most on",
        f"pub static CARDS: [(u32, u8, u16, bool, &str); {len(album)}] = [",
    ]
    for card, region, mob, is_boss, map_name in album:
        rust.append(f'    ({card}, {index[region]}, {mob}, {str(is_boss).lower()}, "{map_name}"),')
    rust += [
        "];",
        "",
        "/// The rewards at each count of cards: count, kind, amount",
        f"pub static MILESTONES: [(u16, u8, u16); {len(MILESTONES)}] = [",
    ]
    rust += [f"    ({c}, {k}, {v})," for c, k, v in MILESTONES]
    rust += ["];", ""]
    open(OUT, "w").write("\n".join(rust))

    server = [
        "//===== rAthena Script =======================================",
        "//= Card Album: the cards and rewards",
        "//===== Description: =========================================",
        "//= Generated by scripts/gen-card-album.py: do not edit.",
        "//= npc/custom/cardalbum.txt is what uses them.",
        "//============================================================",
        "",
        "// $@ca_card: the cards, by region; $@ca_region, $@ca_boss each one's region and whether only bosses drop it;",
        "// $@ca_at[card id]: its place + 1. $@ca_rname$, $@ca_rneed, $@ca_rkind, $@ca_rval: the regions, cards to",
        "// complete one, its reward. $@ca_mcount, $@ca_mkind, $@ca_mval: the rewards at each count",
        "-\tscript\tCardAlbumTable\t-1,{",
        "OnInit:",
        "\tfreeloop(1);",
    ]

    def setarray(name, values, quote=False):
        for i in range(0, len(values), 40):
            chunk = values[i:i + 40]
            text = ", ".join(f'"{v}"' if quote else str(v) for v in chunk)
            server.append(f"\tsetarray {name}[{i}], {text};")

    setarray("$@ca_rname$", regions, True)
    setarray("$@ca_rneed", [need[r] for r in regions])
    setarray("$@ca_rkind", [kinds[r] for r in regions])
    setarray("$@ca_rval", [rewards[r] for r in regions])
    setarray("$@ca_card", [a[0] for a in album])
    setarray("$@ca_region", [index[a[1]] for a in album])
    setarray("$@ca_boss", [int(a[3]) for a in album])
    setarray("$@ca_mcount", [m[0] for m in MILESTONES])
    setarray("$@ca_mkind", [m[1] for m in MILESTONES])
    setarray("$@ca_mval", [m[2] for m in MILESTONES])
    server += [
        "\tfor (.@i = 0; .@i < getarraysize($@ca_card); .@i++)",
        "\t\t$@ca_at[$@ca_card[.@i]] = .@i + 1;",
        "\tend;",
        "}",
        "",
    ]
    open(SERVER_OUT, "w").write("\n".join(server))
    print(f"{len(album)} cards ({sum(1 for a in album if a[3])} bosses'), {len(regions)} regions -> "
          f"{OUT}, {SERVER_OUT}")
    for r in regions:
        print(f"  {r}: {need[r]} cards, kind {kinds[r]} +{rewards[r]}")


if __name__ == "__main__":
    main()
