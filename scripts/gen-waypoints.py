#!/usr/bin/env python3
"""Writes server/npc/custom/waypoint_points.txt: the places the Kafra teleport network (npc/custom/waypoints.txt)
can take a character once found there: every town (arriving where its Kafra saves, or by its teleport service, or
in the middle), found by talking to its Kafra, Zonda or Cool Event Corp. staff or, where it has none, by walking
in; and a waystone at the first entrance to every dungeon, standing a few cells off the portal on a walkable cell.

All of it comes from the server's own data: the Kafras' savepoints, the warp portals into the maps that have
dungeon monster spawns (npc/re/mobs/dungeons), the walkable cells (db/map_cache.dat, db/re/map_cache.dat). The names come from the
game's map name table (data/mapnametable.txt, English with the English text installed: the app keeps a copy in its
files folder), which is not in this repository, so it is given on the command line.

Usage: scripts/gen-waypoints.py <mapnametable.txt>   (RATHENA_DIR=<checkout> for another server than server/)
"""
import os
import re
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATHENA = os.environ.get("RATHENA_DIR", os.path.join(ROOT, "server"))
OUT = os.path.join(RATHENA, "npc/custom/waypoint_points.txt")
TOWN_FEE, DUNGEON_FEE = 800, 1200
WAYSTONE_SPRITE = "4_ENERGY_BLUE"
# no instances, guild castles, job and quest maps, battlegrounds, tutorial copies (guild dungeons are places: their
# gates, npc/custom/guilddungeon.txt, let anyone in)
NOT_A_PLACE = re.compile(r"@|_cas|^job|^que_|_que\d|^tur_|^bat_|^e_|pvp|arena|_q$|\d[a-z]$")
# a guild dungeon's deeper floors and its Abyss share its 1F's gate, and its waystone
SAME_GATE = re.compile(r"^gld_dun0\d_2$|^gld2_")


def loaded(conf, seen):
    """The npc files the server loads from `conf`, following its import: lines"""
    files = []
    for line in open(os.path.join(RATHENA, conf), errors="ignore"):
        line = line.split("//")[0].strip()
        m = re.match(r"(npc|import):\s*(\S+)", line)
        if not m or m.group(2) in seen:
            continue
        seen.add(m.group(2))
        files += loaded(m.group(2), seen) if m.group(1) == "import" else [m.group(2)]
    return [f for f in files if os.path.isfile(os.path.join(RATHENA, f))]


def map_cells(path):
    """map name -> (width, height, cell types) from rAthena's map cache"""
    data = open(path, "rb").read()
    _, count = struct.unpack_from("<IH", data, 0)
    pos, maps = 8, {}
    for _ in range(count):
        name = data[pos:pos + 12].split(b"\0")[0].decode()
        xs, ys, length = struct.unpack_from("<hhi", data, pos + 12)
        cells = zlib.decompress(data[pos + 20:pos + 20 + length])
        maps[name] = (xs, ys, cells)
        pos += 20 + length
    return maps


def walkable(maps, name, x, y):
    xs, ys, cells = maps[name]
    return 0 <= x < xs and 0 <= y < ys and cells[x + y * xs] in (0, 3)


def spot_near(maps, name, x, y, keep_off):
    """A walkable cell 3 to 6 cells from (x, y) with a walkable neighbour (where a teleport lands), out of the
    portal's reach (`keep_off` cells around it); nearest first"""
    for r in range(3, 7):
        ring = [(x + dx, y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if max(abs(dx), abs(dy)) == r]
        for cx, cy in sorted(ring, key=lambda c: abs(c[0] - x) + abs(c[1] - y)):
            if max(abs(cx - x), abs(cy - y)) <= keep_off or not walkable(maps, name, cx, cy):
                continue
            for ax, ay in ((cx, cy - 1), (cx, cy + 1), (cx - 1, cy), (cx + 1, cy)):
                if walkable(maps, name, ax, ay) and max(abs(ax - x), abs(ay - y)) > keep_off:
                    return (cx, cy), (ax, ay)
    return None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    names = {}
    for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
        parts = line.strip().split("#")
        if len(parts) >= 2 and parts[0].endswith(".rsw"):
            names[parts[0][:-4].lower()] = parts[1]
    # the shared cache, with what Renewal changed over it
    maps = map_cells(os.path.join(RATHENA, "db/map_cache.dat"))
    maps.update(map_cells(os.path.join(RATHENA, "db/re/map_cache.dat")))
    files = loaded("npc/re/scripts_main.conf", set())

    dungeons, fields = set(), set()
    for f in files:
        if "/mobs/fields/" in f:
            for line in open(os.path.join(RATHENA, f), errors="ignore"):
                m = re.match(r"([a-z0-9_]+)(?:,\d+,\d+(?:,\d+,\d+)?)?\t(?:boss_)?monster\t", line)
                if m:
                    fields.add(m.group(1))
        if "/mobs/dungeons/" in f:
            for line in open(os.path.join(RATHENA, f), errors="ignore"):
                m = re.match(r"([a-z0-9_]+)(?:,\d+,\d+(?:,\d+,\d+)?)?\t(?:boss_)?monster\t", line)
                if m:
                    dungeons.add(m.group(1))

    # a Kafra on Byalan Island or by the Orc Dungeon is no town: only maps flagged as towns are
    town_maps = set()
    for f in files:
        for line in open(os.path.join(RATHENA, f), errors="ignore"):
            m = re.match(r"([a-z0-9_]+)\tmapflag\ttown\b", line)
            if m:
                town_maps.add(m.group(1))

    # where each town's Kafra saves, and where any of its teleport services stands
    saves, services = {}, {}
    for f in files:
        if "/kafras/" not in f:
            continue
        text = open(os.path.join(RATHENA, f), errors="ignore").read()
        for m in re.finditer(r'savepoint\s+"([a-z0-9_]+)",\s*(\d+),\s*(\d+)', text):
            saves.setdefault(m.group(1), (int(m.group(2)), int(m.group(3))))
        for m in re.finditer(r"^([a-z0-9_]+),(\d+),(\d+),\d+\t(?:script|duplicate\([^)]*\))\t", text, re.M):
            services.setdefault(m.group(1), (int(m.group(2)), int(m.group(3))))

    # every town (Renewal's Morroc is not flagged as one, its Kafras still save there): the Izlude channels (izlude_a
    # to _d) are Izlude, and the script takes them as it
    towns = {}
    for town in sorted(town_maps | {"morocc"}):
        if NOT_A_PLACE.search(town) or town not in maps or town not in names or re.search(r"_in\d*$|^in_|_in_", town):
            continue
        if re.fullmatch(r"izlude_[a-d]", town):
            continue
        name = names[town].split(",")[0].strip()
        if town in saves and walkable(maps, town, *saves[town]):
            at = saves[town]
        else:
            x, y = services.get(town, (maps[town][0] // 2, maps[town][1] // 2))
            spot = spot_near(maps, town, x, y, 0)
            if spot is None:
                print(f"no walkable spot in {town}", file=sys.stderr)
                continue
            at = spot[0]
        # no Kafra, Zonda or Cool Event Corp. there: walking in finds it
        auto = int(town not in services)
        towns[town] = (name, at[0], at[1], auto)

    # the ways into each dungeon: warp portals, and NPCs whose script warps there (a guard, as into the Prontera
    # Culvert); from a field or town first, then from any other map that is no dungeon, job or quest map
    ways = []
    for f in sorted(files):
        npc = None
        for line in open(os.path.join(RATHENA, f), errors="ignore"):
            m = re.match(r"([a-z0-9_]+),(\d+),(\d+),\d+\twarp2?\t[^\t]+\t(\d+),(\d+),([a-z0-9_]+),\d+,\d+", line)
            if m:
                src, dst = m.group(1), m.group(6)
                span = max(int(m.group(4)), int(m.group(5))) + 1
                ways.append((src, int(m.group(2)), int(m.group(3)), span, dst, False))
                continue
            m = re.match(r"([a-z0-9_]+),(\d+),(\d+),\d+\t(?:script|duplicate\([^)]*\))\t", line)
            if m:
                npc = (m.group(1), int(m.group(2)), int(m.group(3)))
                continue
            m = re.search(r'\bwarp\s+"([a-z0-9_]+)"', line)
            if m and npc:
                ways.append((npc[0], npc[1], npc[2], 1, m.group(1), True))

    def rank(way):
        src, _, _, _, _, by_npc = way
        return (by_npc, src not in fields and src not in town_maps)

    entrances, taken = {}, set()
    for src, x, y, span, dst, _ in sorted(ways, key=rank):
        if dst not in dungeons or dst in entrances or NOT_A_PLACE.search(dst) or dst not in names:
            continue
        if src in dungeons or src not in maps or NOT_A_PLACE.search(src) or re.search(r"_dun\d|dun\d+$", src):
            continue
        # one waystone a dungeon, at its first entrance: its floors and other doors share its name
        name = names[dst].split(" - ")[0].split(" (")[0]
        name = re.sub(r"\s+(?:[FB]\d+|\d+F)$", "", name).strip()
        if SAME_GATE.match(dst) or name in taken:
            continue
        spot = spot_near(maps, src, x, y, span)
        if spot is None:
            print(f"no spot by the way into {dst} on {src},{x},{y}", file=sys.stderr)
            continue
        taken.add(name)
        entrances[dst] = (name, src, spot)

    out = [
        "//===== rAthena Script =======================================",
        "//= Kafra teleport network: the places",
        "//===== Description: =========================================",
        "//= Generated by scripts/gen-waypoints.py from the Kafras'",
        "//= savepoints, the warps into dungeons and the map cache: do",
        "//= not edit. npc/custom/waypoints.txt is what uses them.",
        "//============================================================",
        "",
        "// $@way_key$ is what a character has found (WP_<key>), the rest where and how much: towns, then dungeons;",
        "// $@way_auto: a town with no Kafra to find it at, found on walking in",
        "-\tscript\tWaypointTable\t-1,{",
        "OnInit:",
    ]
    rows = [(k, n, k, x, y, 0, TOWN_FEE, auto) for k, (n, x, y, auto) in sorted(towns.items(), key=lambda t: t[1][0])]
    rows += [(d, n, src, a[0], a[1], 1, DUNGEON_FEE, 0) for d, (n, src, (s, a)) in sorted(entrances.items(), key=lambda t: t[1][0])]
    for i in range(0, len(rows), 20):
        chunk = rows[i:i + 20]
        out.append(f'\tsetarray $@way_key$[{i}], ' + ", ".join(f'"{r[0]}"' for r in chunk) + ";")
        out.append(f'\tsetarray $@way_name$[{i}], ' + ", ".join(f'"{r[1]}"' for r in chunk) + ";")
        out.append(f'\tsetarray $@way_map$[{i}], ' + ", ".join(f'"{r[2]}"' for r in chunk) + ";")
        out.append(f'\tsetarray $@way_x[{i}], ' + ", ".join(str(r[3]) for r in chunk) + ";")
        out.append(f'\tsetarray $@way_y[{i}], ' + ", ".join(str(r[4]) for r in chunk) + ";")
        out.append(f'\tsetarray $@way_dungeon[{i}], ' + ", ".join(str(r[5]) for r in chunk) + ";")
        out.append(f'\tsetarray $@way_fee[{i}], ' + ", ".join(str(r[6]) for r in chunk) + ";")
        out.append(f'\tsetarray $@way_auto[{i}], ' + ", ".join(str(r[7]) for r in chunk) + ";")
    out += [
        "\t// a town with no Kafra is found on walking in (Waypoints::OnPCLoadMapEvent)",
        "\tfor (.@i = 0; .@i < getarraysize($@way_key$); .@i++)",
        "\t\tif ($@way_auto[.@i])",
        "\t\t\tsetmapflag $@way_key$[.@i], MF_LOADEVENT;",
        "\tend;",
        "}",
        "",
        "// the waystones, one by the first entrance to each dungeon (touch or talk: found)",
    ]
    for d, (n, src, (s, a)) in sorted(entrances.items()):
        out.append(f"{src},{s[0]},{s[1]},4\tduplicate(Waystone)\tWaystone#{d}\t{WAYSTONE_SPRITE},3,3")
    open(OUT, "w").write("\n".join(out) + "\n")
    print(f"{len(towns)} towns, {len(entrances)} dungeon entrances -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
