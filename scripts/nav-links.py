#!/usr/bin/env python3
"""nostalre-client's navigation links (lib/game/src/nav_link_tables.rs): every way from one map to another the
server has, for the navigation's routes (lib/game/src/navigation.rs). Warp portals; invisible NPCs walked onto that
warp (OnTouch, as portals); and NPCs whose script warps to a named map: talked to, as a ship's captain or the
Expedition Guide (npc/custom/mobs/fields/endgame.txt, whose maps are an array). An NPC sending to more than a few
maps is a service (a warper, a job changer's test) and left out, as are instances, the jail and links within a map.

Usage: scripts/nav-links.py [rathena dir] [output file]
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATHENA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "server")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "client/lib/game/src/nav_link_tables.rs")
# an NPC warping to more maps than this is a service, not a way
MOST_NPC_MAPS = 6
# teleport services, which ask for zeny, a membership or a level and lead anywhere: the Kafra network does that
SERVICE = re.compile(r"Kafra|Eden|Cool Event|Teleport|Spatial coordinate|Cash Sales|Winner Helper|Warper|Training Ground")
# no instances, guild castles, the jail, job and quest maps, battlegrounds, tutorial copies, arenas
NOT_A_WAY = re.compile(r"@|_cas\d|^sec_|^job|^que_|^bat_|^e_|pvp|arena|_q$|^1@|^2@")
# the sprites of NPCs walked onto (a portal's, the invisible ones)
WALKED_ON = {"45", "WARPNPC", "139", "HIDDEN_WARP_NPC", "111", "1_SHADOW_NPC", "844", "HIDDEN_NPC"}
HEADER = re.compile(r"^([a-z0-9_]+|-),(?:(\d+),(\d+),\d+)?\t?(script|duplicate\(([^)]*)\)|warp2?|shop|cashshop|trader|itemshop|pointshop|monster|boss_monster|mapflag)\t([^\t]*)\t?(.*)$")
NPC_HEAD = re.compile(r"^(?:(-)|([a-z0-9_]+),(\d+),(\d+),\d+)\t(script|duplicate\(([^)]*)\))\t([^\t]+)\t([^,{\t]+)")
WARP_LINE = re.compile(r"^([a-z0-9_]+),(\d+),(\d+),\d+\twarp2?\t[^\t]+\t\d+,\d+,([a-z0-9_]+),(\d+),(\d+)")
WARP_CMD = re.compile(r'\bwarp\s+"([a-z0-9_]+)"\s*,\s*(-?\d+)\s*,\s*(-?\d+)')
WARP_ARRAY = re.compile(r"\bwarp\s+\.(\w+\$)\[")


def main():
    os.environ["RATHENA_DIR"] = RATHENA
    spec = importlib.util.spec_from_file_location("waypoints", os.path.join(ROOT, "scripts/gen-waypoints.py"))
    waypoints = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(waypoints)
    cells = waypoints.map_cells(os.path.join(RATHENA, "db/map_cache.dat"))
    cells.update(waypoints.map_cells(os.path.join(RATHENA, "db/re/map_cache.dat")))
    seen = set()
    files = waypoints.loaded("npc/re/scripts_main.conf", seen)
    files += [f for f in waypoints.loaded("npc/scripts_custom.conf", seen) if f not in files]

    def a_way(src, dst):
        return src in cells and dst in cells and src != dst and not NOT_A_WAY.search(src) and not NOT_A_WAY.search(dst)

    links = set()
    # each NPC's (or template's) warps by its name, and where its copies stand
    warps_of, placed = {}, []
    for f in files:
        npc = None
        for line in open(os.path.join(RATHENA, f), errors="ignore"):
            m = WARP_LINE.match(line)
            if m:
                links.add((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4), int(m.group(5)), int(m.group(6)), ""))
                npc = None
                continue
            m = NPC_HEAD.match(line)
            if m:
                _, src, x, y, kind, template, name, sprite = m.groups()
                key = name.split("::")[-1]
                npc = None
                if kind == "script":
                    npc = warps_of.setdefault(key, {"warps": [], "arrays": {}, "touch": False})
                    if "::" in name:
                        warps_of[name.split("::")[0]] = npc
                    if src:
                        placed.append((src, int(x), int(y), name.split("::")[0], sprite.strip(), key))
                elif src:
                    placed.append((src, int(x), int(y), name, sprite.strip(), template))
                continue
            if npc is None:
                continue
            for d, dx, dy in WARP_CMD.findall(line):
                npc["warps"].append((d, int(dx), int(dy)))
            a = re.match(r"\s*setarray\s+\.(\w+\$)\s*(?:\[0\])?\s*,\s*(.*);", line)
            if a:
                npc["arrays"][a.group(1)] = re.findall(r'"([a-z0-9_]+)"', a.group(2))
            for name in WARP_ARRAY.findall(line):
                npc.setdefault("by_array", []).append(name)
            if re.match(r"^OnTouch_?:", line.strip()):
                npc["touch"] = True

    for src, x, y, name, sprite, key in placed:
        npc = warps_of.get(key)
        if not npc:
            continue
        dsts = [(d, dx, dy) for d, dx, dy in npc["warps"]]
        dsts += [(d, 0, 0) for a in npc.get("by_array", []) for d in npc["arrays"].get(a, [])]
        dsts = [w for w in dsts if a_way(src, w[0])]
        if not dsts or len({d for d, _, _ in dsts}) > MOST_NPC_MAPS or sprite == "-1" or SERVICE.search(name):
            continue
        walked = sprite in WALKED_ON and npc["touch"]
        shown = "" if walked else re.sub(r"#.*", "", name).strip() or "NPC"
        for d, dx, dy in dsts:
            links.add((src, x, y, d, max(dx, 0), max(dy, 0), shown))

    links = sorted(l for l in links if a_way(l[0], l[3]))
    lines = [
        "// Generated by scripts/nav-links.py from the server's warps and warping NPCs; do not edit.",
        "",
        "/// A way from one map to another: (map, x, y, to map, x, y, the NPC to talk to: \"\" for a portal walked onto).",
        "/// An arrival cell of 0, 0 is a random one. By map.",
        f"pub static LINKS: [(&str, u16, u16, &str, u16, u16, &str); {len(links)}] = [",
    ]
    for src, x, y, dst, dx, dy, npc in links:
        lines.append(f'    ("{src}", {x}, {y}, "{dst}", {dx}, {dy}, "{npc.replace(chr(92), "").replace(chr(34), "")}"),')
    lines += ["];", ""]
    open(OUT, "w").write("\n".join(lines))
    walks = sum(1 for l in links if not l[6])
    print(f"{walks} portals, {len(links) - walks} NPC ways -> {OUT}")


if __name__ == "__main__":
    main()
