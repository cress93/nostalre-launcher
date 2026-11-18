#!/usr/bin/env python3
"""Writes server/npc/custom/questboard_maps.txt: the maps the quest board (npc/custom/questboard.txt) sends a
character to, from the server's own data. For every field and dungeon with ordinary monsters (npc/re/mobs): its
level (the count-weighted mean of its monsters, as src/map/population_engine.cpp's map levels), its monsters with
their spawn counts, levels and EXP, the common drops a Gather quest can ask for (Etc items dropped at 5% or more),
and a rare drop for a Hard quest (a drop of 0.01% to 3%, no card, gear first). And a board in every town of the
Kafra network (npc/custom/waypoint_points.txt, scripts/gen-waypoints.py: run that first), a few steps from where its
teleport lands, on a walkable cell. The names come from the game's map
name table (data/mapnametable.txt; the app keeps a copy in its files folder), which is not in this repository.

Usage: scripts/gen-questboard.py <mapnametable.txt>   (RATHENA_DIR=<checkout> for another server than server/)
"""
import glob
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATHENA = os.environ.get("RATHENA_DIR", os.path.join(ROOT, "server"))
OUT = os.path.join(RATHENA, "npc/custom/questboard_maps.txt")
# no instances, guild castles, job and quest maps, battlegrounds, tutorial copies (guild dungeons are places: their
# gates, npc/custom/guilddungeon.txt, let anyone in)
NOT_A_PLACE = re.compile(r"@|_cas|^job|^que_|^tur_|^bat_|^e_|pvp|arena|_q$|\d[a-z]$")
BOARD_SPRITE = "4_BULLETIN_BOARD2"
# a board somewhere else than by the teleport spot: Prontera's by the fountain, beside the Cash Shop
BOARD_AT = {"prontera": (151, 185)}
# a spawn line, with or without its area ("lasa_dun01\tmonster\t...")
SPAWN = re.compile(r"([a-z0-9_]+)(?:,\d+,\d+(?:,\d+,\d+)?)?\t(?:boss_)?monster\t[^\t]+\t(\d+),(\d+)")


def loaded(conf, seen):
    """The npc files the server loads from `conf`, following its import: lines"""
    files = []
    if not os.path.isfile(os.path.join(RATHENA, conf)):
        return files
    for line in open(os.path.join(RATHENA, conf), errors="ignore"):
        line = line.split("//")[0].strip()
        m = re.match(r"(npc|import):\s*(\S+)", line)
        if not m or m.group(2) in seen:
            continue
        seen.add(m.group(2))
        files += loaded(m.group(2), seen) if m.group(1) == "import" else [m.group(2)]
    return [f for f in files if os.path.isfile(os.path.join(RATHENA, f))]


def items():
    """AegisName -> (id, type)"""
    out = {}
    for f in glob.glob(os.path.join(RATHENA, "db/re/item_db_*.yml")):
        for blk in open(f, errors="ignore").read().split("\n  - Id: ")[1:]:
            a = re.search(r"\n    AegisName: (\S+)", blk)
            t = re.search(r"\n    Type: (\w+)", blk)
            if a:
                out[a.group(1)] = (int(blk.split("\n")[0].split()[0]), t.group(1) if t else "Etc")
    return out


def monsters(item_ids):
    """id -> level, base exp, whether it is an ordinary fighting monster, drops [(item id, type, rate)]"""
    out = {}
    text = open(os.path.join(RATHENA, "db/re/mob_db.yml"), errors="ignore").read()
    for blk in text.split("\n  - Id: ")[1:]:
        mob_id = int(blk.split("\n")[0].split()[0])
        get = lambda k: (lambda m: int(m.group(1)) if m else 0)(re.search(r"\n    " + k + r": (\d+)", blk))
        cls = re.search(r"\n    Class: (\w+)", blk)
        ai = re.search(r"\n    Ai: (\d+)", blk)
        ordinary = not (cls and cls.group(1) != "Normal") and "\n    Mvp" not in blk and not (ai and ai.group(1) == "06")
        drops = []
        dm = re.search(r"\n    Drops:\n((?:      .*\n)+)", blk + "\n")
        if dm:
            for item, rate in re.findall(r"- Item: (\S+)\n\s+Rate: (\d+)", dm.group(1)):
                if item in item_ids:
                    drops.append((item_ids[item][0], item_ids[item][1], int(rate)))
        out[mob_id] = (get("Level"), get("BaseExp"), ordinary, drops)
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    names = {}
    for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
        parts = line.strip().split("#")
        if len(parts) >= 2 and parts[0].endswith(".rsw"):
            names[parts[0][:-4].lower()] = parts[1]
    # the endgame fields' names, which the table lacks: their guide's (npc/custom/mobs/fields/endgame.txt)
    endgame = open(os.path.join(RATHENA, "npc/custom/mobs/fields/endgame.txt"), errors="ignore").read()
    arrays = [re.findall(r'"([^"]*)"', m) for m in re.findall(r"setarray \.(?:map|name)\$, (.*);", endgame)]
    if len(arrays) == 2:
        for map_name, name in zip(*arrays):
            names.setdefault(map_name, name)
    item_ids = items()
    mobs = monsters(item_ids)

    spawns = {}
    # with our own (npc/custom/mobs: the endgame fields rAthena has no monsters on)
    seen = set()
    for f in loaded("npc/re/scripts_main.conf", seen) + loaded("npc/scripts_custom.conf", seen):
        if "/mobs/fields/" not in f and "/mobs/dungeons/" not in f and "/custom/lasagna/" not in f:
            continue
        for line in open(os.path.join(RATHENA, f), errors="ignore"):
            m = SPAWN.match(line)
            if m:
                spawns.setdefault(m.group(1), {})
                mob_id, count = int(m.group(2)), int(m.group(3))
                spawns[m.group(1)][mob_id] = spawns[m.group(1)].get(mob_id, 0) + count

    rows = []
    for map_name in sorted(spawns):
        if NOT_A_PLACE.search(map_name) or map_name not in names:
            continue
        fighting = {i: c for i, c in spawns[map_name].items() if i in mobs and mobs[i][2] and mobs[i][0] > 0}
        if not fighting:
            continue
        total = sum(fighting.values())
        level = round(sum(mobs[i][0] * c for i, c in fighting.items()) / total)
        # the ones common enough to hunt: 5 or more on the map
        hunt = sorted(((i, c) for i, c in fighting.items() if c >= 5), key=lambda ic: mobs[ic[0]][0])
        if not hunt:
            continue
        # gather: Etc drops of 5% or more, by how many a kill brings on average across the map
        gather = {}
        for i, c in fighting.items():
            for item, kind, rate in mobs[i][3]:
                if kind == "Etc" and rate >= 500:
                    gather[item] = gather.get(item, 0) + rate * c / total
        gather = sorted(gather.items(), key=lambda g: -g[1])[:3]
        # rare: 0.01% to 3%, no card; gear first, then the rarest
        rare = [(item, kind, rate) for i in fighting for item, kind, rate in mobs[i][3] if 1 <= rate <= 300 and kind != "Card"]
        rare.sort(key=lambda r: (r[1] not in ("Weapon", "Armor"), r[2]))
        name = names[map_name].split(" - ")[0].strip()
        rows.append((
            map_name, name, level,
            ",".join(f"{i}:{c}:{mobs[i][0]}:{mobs[i][1]}" for i, c in hunt),
            ",".join(f"{item}:{round(rate)}" for item, rate in gather),
            rare[0][0] if rare else 0,
        ))

    out = [
        "//===== rAthena Script =======================================",
        "//= Quest board: the maps",
        "//===== Description: =========================================",
        "//= Generated by scripts/gen-questboard.py from the monster",
        "//= spawns, mob_db and item_db: do not edit.",
        "//= npc/custom/questboard.txt is what uses them.",
        "//============================================================",
        "",
        "// $@qb_mobs$: id:count:level:base exp of each monster 5 or more of spawn; $@qb_gather$: item:rate (per 10000",
        "// kills, across the map) of the common Etc drops; $@qb_rare: one rare drop (0 for none)",
        "-\tscript\tQuestBoardMaps\t-1,{",
        "OnInit:",
    ]
    for i in range(0, len(rows), 20):
        chunk = rows[i:i + 20]
        out.append(f"\tsetarray $@qb_map$[{i}], " + ", ".join(f'"{r[0]}"' for r in chunk) + ";")
        out.append(f"\tsetarray $@qb_name$[{i}], " + ", ".join('"' + r[1].replace('"', "'") + '"' for r in chunk) + ";")
        out.append(f"\tsetarray $@qb_lv[{i}], " + ", ".join(str(r[2]) for r in chunk) + ";")
        out.append(f"\tsetarray $@qb_mobs$[{i}], " + ", ".join(f'"{r[3]}"' for r in chunk) + ";")
        out.append(f"\tsetarray $@qb_gather$[{i}], " + ", ".join(f'"{r[4]}"' for r in chunk) + ";")
        out.append(f"\tsetarray $@qb_rare[{i}], " + ", ".join(str(r[5]) for r in chunk) + ";")
    out += ["\tend;", "}", "", "// a board in every town of the Kafra network, a few steps from where its teleport lands"]
    # the map cache and the cell search of scripts/gen-waypoints.py
    spec = importlib.util.spec_from_file_location("waypoints", os.path.join(ROOT, "scripts/gen-waypoints.py"))
    waypoints = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(waypoints)
    cells = waypoints.map_cells(os.path.join(RATHENA, "db/map_cache.dat"))
    cells.update(waypoints.map_cells(os.path.join(RATHENA, "db/re/map_cache.dat")))
    table = open(os.path.join(RATHENA, "npc/custom/waypoint_points.txt")).read()
    def arr(name):
        values = []
        for chunk in re.findall(r"\$@" + re.escape(name) + r"\[\d+\], (.*);", table):
            values += re.findall(r'"([^"]*)"|(-?\d+)', chunk)
        return [a or b for a, b in values]
    boards = 0
    for key, town, x, y, dungeon in zip(arr("way_key$"), arr("way_map$"), arr("way_x"), arr("way_y"), arr("way_dungeon")):
        if dungeon != "0":
            continue
        if town in BOARD_AT:
            at = BOARD_AT[town]
        else:
            spot = waypoints.spot_near(cells, town, int(x), int(y), 1)
            if spot is None:
                print(f"no spot for a board in {town}", file=sys.stderr)
                continue
            at = spot[0]
        out.append(f"{town},{at[0]},{at[1]},4\tduplicate(QuestBoard)\tQuest Board#{key}\t{BOARD_SPRITE}")
        boards += 1
    open(OUT, "w").write("\n".join(out) + "\n")
    print(f"{len(rows)} maps, {boards} boards -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
