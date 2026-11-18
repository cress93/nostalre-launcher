# Debug and test commands

The commands nostalRE adds to rAthena, and the plain rAthena ones that help test its features. Type them in the
chat line: on a phone, **Menu → Chat** opens it.

GM commands need the account to be a GM: turn on **GM commands** in the app's settings (account group 99). It takes
effect from the next game. `@capture` works for every player.

## AI players (Population Engine shells)

| Command | What it does |
|---|---|
| `@populate <count> [map]` | Spawns `<count>` shells on your map (or `[map]`). They stand there, no autocombat |
| `@populate stop` | Stops the engine and removes every shell |
| `@populate status` | Whether the engine is running |
| `@populate stats` | Shells active, created and failed; chat lines, walk failures, memory |
| `@populate levels` | Every shell on your map: class, level, stats, gear and HP. Check map levels and class fitting with this |
| `@populate timing` | The wander and pathing profiler, and the perf sections (chat, spawn, …) |
| `@populate timingreset` | Clears the profiler |
| `@fakeplayers …` | Same as `@populate …` |
| `@reloadpopenginedb` | Reloads the shells' profiles and gear (`db/population_engine.yml` and the gear sets) without a restart |

The **Arena Manager** in Morroc (144, 101) starts 1v1, 3v3 or 5v5 fights against shells.

Shell behaviour comes from the app's settings (AI players on/off, Max AI players, AI players per map, AI player
respawn) and from `conf/battle/population_engine.conf`. Party companions: invite a shell into your party, or whisper
it "party" (that makes a party if you have none); whisper "leave" or "bye" to send it off.

## Capture balls and caught monsters

| Command | What it does |
|---|---|
| `@capture list` | Sends the slots to the client again (the Monsters screen does this itself) |
| `@capture call <1-3>` | Calls slot 1–3 out to fight, or back into its ball if it is out |
| `@capture release <1-3>` | Lets the monster in that slot go for good |

Useful with them:

| Command | |
|---|---|
| `@item 99901 10` | 10 Basic Capture Balls (99902 Great, 99903 Ultra, 99904 Master) |
| `@item 101129 5` | 5 Random Costume Boxes (the costume crate) |
| `@monster 31990` | A Capture Chest. A spawned one has 100 HP and drops nothing: only a chest the map rolls when you enter it drops balls |
| `@blvl <n>` | Raises your base level, to test catch-up EXP |

## Teleport network (Kafras and waystones)

| Command | What it does |
|---|---|
| `@waypoint list` | The destinations this character has found, and how many are left |
| `@waypoint all` | Finds every town and dungeon entrance |
| `@waypoint reset` | Back to a new character's: Prontera and the save town |

To try one waystone: `@warp prt_fild05 270 208` lands next to the Prontera Culvert's waystone. All the places, with the
waystones' cells, are in `server/npc/custom/waypoint_points.txt` (made by `scripts/gen-waypoints.py`).

## Quest board

| Command | What it does |
|---|---|
| `@board list` | Sends the board to the client again (the Board screen does this itself) |
| `@board take <1-4>` | Takes card 1–4, the fourth the instance (up to three active quests) |
| `@board reroll` | New cards (free once an hour; the cards also renew every 30 minutes) |
| `@board abort <1-3>` | Drops active quest 1–3 |
| `@boardreset` | GM: new cards, the reroll ready again, and the Board screen opens |

Every player can use `@board`; the Board screen sends it. The boards stand a few steps from each town's teleport
spot; the maps and the boards are in `server/npc/custom/questboard_maps.txt` (made by `scripts/gen-questboard.py`,
after `scripts/gen-waypoints.py`). The instances the fourth card picks from are in `server/npc/custom/questboard_instances.txt`
(`scripts/gen-questboard-instances.py`).

## Card Album

| Command | What it does |
|---|---|
| `@album` | Sends the album to the client again and lists the rewards earned in the chat |
| `@album sync` | Sends the album only (the Album screen does this itself) |
| `@item <card id>` | Any card of the album picked up goes in within 3 s (storage and the cart are swept every minute) |

The album is the account's: `#CA_<card id>` per card, the rewards in `#ALBUM_DISC`, `#ALBUM_OC`, `#ALBUM_WEIGHT`,
`#ALBUM_TRAVEL`, `#ALBUM_BOARD` and `#ALBUM_REFINE` (set again at every login). To empty it, clear those account
variables in the database (`acc_reg_num`). The cards, regions and rewards are in `server/npc/custom/cardalbum_table.txt`
(made by `scripts/gen-card-album.py`, after `scripts/nav-links.py` and `scripts/gen-waypoints.py`).

## Sieges, guild dungeons, the arena

| Command | What it does |
|---|---|
| `@agitstart` / `@agitend` | GM: starts or ends the classic castles' siege (`@agitstart2`/`@agitstart3` and `@agitend2`/`@agitend3` the SE and TE ones), as a Siege Herald does |
| `/guild <name>` | Founds a guild, typed in the chat with an Emperium in the bag (a Siege Herald sells one for 50,000z); `@guild <name>` does it for a GM without one |
| `@warp prt_gld 160 90` | The Valkyrie Realm: its Guild Dungeon Gate and Siege Herald (`pay_gld`, `alde_gld`, `gef_fild13`, `aru_gld`, `sch_gld`; TE heralds in `te_prt_gld`, `te_alde_gld`) |
| `@monster 1288` | An Emperium, to see a castle change hands without a siege's walk |

A **Siege Herald** (`server/npc/custom/siege.txt`) starts its edition's siege for an hour when a guild master asks; the
weekly schedules are not loaded. Each siege, raiders storm one of the declaring guild's castles of that edition: any
left when it ends, the castle is lost. A **Guild Dungeon Gate** (`server/npc/custom/guilddungeon.txt`) lets anyone of
level 70+ into a realm's guild dungeons for 10,000z, free for a guild holding one of its castles.

An **Arena Master** (`server/npc/custom/arenacircuit.txt`) beside each Maroll Battle Recruiter runs a match on
`pvp_y_1-2` against AI players of your level: 8 Bravery or Valor Badges, or 80 KVM Points, for a win, a third of it
otherwise. It needs AI players on in the app's settings.

## Cash Shop

The Cash Shop is the Kafra by Prontera's fountain (`@warp prontera 160 185`). `@zeny <amount>` pays for the costumes.

## Other rAthena commands worth knowing

`@warp <map> <x> <y>`, `@jumpto <name>`, `@go <town>`, `@item <id> [amount]`, `@monster <id> [amount]`,
`@killmonster`, `@blvl` / `@jlvl`, `@heal`, `@zeny`, `@speed <1-1000>`. `@commands` lists every command your group
may use.
