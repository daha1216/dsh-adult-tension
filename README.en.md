<p align="center">
  <img src=".github/readme-lofi/hero.svg?v=212" width="100%" alt="Adult Tension. A pixel-art bedroom at dusk: someone sits on the edge of the bed playing a red electric guitar, a neon city outside the window, ADULT TENSION written on the glass. A pixel thought bubble by her head holds what she is thinking: one more song… he should be knocking by now. 18+, no holds barred, real adult interaction, rebuilt from scratch by Claude Opus 5.5. Three panels below: NPCs that feel alive, 211 deep worlds, a self-running state machine.">
</p>

<div align="center">

<a href="./README.md">中文</a> · <b>English</b>

### dsh-adult-tension<br>High-tension, long-horizon adult interactive fiction

<p>
<strong>18+ Uncensored Depth · Rebuilt from Scratch with Claude Opus 5.5</strong><br>
Native Agent Skill ｜ Two-faced, living NPCs<br>
15,000+ narrative building blocks ｜ Zero-drift SQLite state machine<br>
<sub>No compliant dolls here—only adults with leverage, secrets, and breaking points.</sub>
</p>

<br>

[211 Worlds](#worlds) · [Support & Sponsor](#support) · [Live Session](#proof) · [Quick Start](#start) · [Install](#install)

</div>

<br>

> **The worlds, the story and the commands are all in Chinese.** This page is a translation of the Chinese README; type the Chinese commands shown below to play.

<br>

<a id="worlds"></a>
<p align="center">
  <img src=".github/readme-lofi/world-library.svg?v=223" width="100%" alt="Built-in world library: standalone world frames across eras and over fifteen thousand story materials. The genres: seventeen videotapes face-out in two rows, one per genre (courts and wanderers, immortals and spirits, Japan and its shrines, late Qing and Republic, classical Europe, neighbours under one roof, trades and night shops, campus and study, gangs and old money, office and law, spies and the front, stage and screen, arena and wagers, extreme engineering, sci-fi and the end, cathedrals and demonkin, kingdoms and blades), each with its world count on top, a small night scene for the genre and the genre name below; all 211 worlds are open, and the whole tape wall is just below. A cassette rack below lists over fifteen thousand materials: 1090+ places, 1320+ NPCs, 1020+ player identities, 2050+ character pairings, 890+ tension engines, 1530+ daily activities, 1320+ pressure events, 3090+ opening hooks, 1650+ mid-story turns, 1750+ rules and customs.">
</p>

<br>

> **Every opening drops you into lived-in people and unspoken house rules from one coherent world—never random nouns stitched together.**

Every world is open. Pick one and play.  
Don't see what you want? Just say "custom world" (`自定义世界`), name the year and the place, and one is made for you on the spot.

<p align="center">
  <img src=".github/readme-lofi/worlds.svg?v=224" width="100%" alt="The tape wall: 211 videotapes lying flat on the walnut shelves of a late-night rental store, spines out with the world names, in seventeen genre columns on four shelves, each shelf with a brass plaque: East and old times (courts and wanderers, immortals and spirits, Japan and its shrines, late Qing and Republic), West and the decades (classical Europe, neighbours under one roof, trades and night shops, campus and study), the city's dark side (gangs and old money, office and law, spies and the front, stage and screen), fantasy and the edge (arena and wagers, extreme engineering, sci-fi and the end, cathedrals and demonkin, kingdoms and blades); each column labelled with its world count, eight staff picks pulled halfway out under a small gold light; all open, ready to start.">
</p>

<br>

<a id="support"></a>
### ☕ Support & Sponsor

If Adult Tension brought you excitement, inspiration, or a memorable run, consider buying the author a coffee. The author was recently laid off and income is currently unstable—every bit of support genuinely helps.

<p align="center">
  <img src="assets/alipay-qr.jpg" width="280" alt="Alipay Sponsor QR Code">
  <br>
  <sub>Scan with Alipay · Thank you for supporting open source creation</sub>
</p>

<br>

<a id="proof"></a>
<p align="center">
  <img src=".github/readme-lofi/section-proof.svg" width="100%" alt="A slice of play: a record of a real session">
</p>

**Harbor Night Shift · Pressure mode.** You're the night dispatcher. Last ship before the typhoon closes the port, and the bottom container in row three weighs in a full four tonnes over. The spreader locks on in fourteen minutes, and a fat red envelope from the shipping company is still pressed under your hand.

> 👤 **You:** `我去找能帮上忙的人，把情况跟对方说清楚` (I go find someone who can help and lay out the situation to them)
>
> You step back half a pace and turn your wrist to dodge the red envelope. It slides down the clipboard onto the edge of a steel container; the smile on shipping-company rep **Pan Baozhu**'s face falters, her hand slowly withdraws into her trench-coat pocket, and her eyes darken in the shadow of the mercury lamps.
>
> Far overhead, the claw of the gantry crane screeches metal on metal. Thirteen minutes left.
>
> 👤 **You:** `我想让对方答应替我分担一部分，看对方肯不肯` (I want them to agree to carry part of this for me, and see if they will)
>
> The gap between two rows of containers is black all the way down; humid sea wind pours in, howling like an exhaust fan. You pull loading crew chief **Liang Jiaxin** into the shadow of the steel wall and, voice low, get across that you want her to lend a hand.
>
> Liang Jiaxin wipes her maimed left hand on her canvas work pants, her eyes heavy as if soaked in seawater:
>
> *"Ah-Qing, when you first walked into dispatch, I was the one who taught you how to reconcile the ledger. You want me to help carry this—fine, let's be clear about it. In my name as crew chief I can call a spreader wire-rope inspection on the channel and force crane seven to stop; that buys you twenty minutes, tops. But the release slip is dispatch's call. Four tonnes over, I'm never putting my name on it, and if it blows up I won't take the fall for you. Two crane cycles is all you get from me."*
>
> <sub>[Time] Day 1, 23:36 ｜ [Place] Yard passage ｜ Turn: 5</sub>

> **Neither of them came around just because you asked: one, turned down, dropped the pleasantries; the other freed up twenty minutes but flatly refused to sign for you.**  
> **In the adult world there's no unconditional shelter; every concession has a clearly priced bottom line.**

<sub>From a real playtest record, host opencode, model gemini-3.8-flash; cuts are marked with "……". Translated from the Chinese. Full text: [`opencode-pt-harbor_night_shift-pressure-r3.json`](reports/playtests/opencode/opencode-pt-harbor_night_shift-pressure-r3.json) · All playtests and scores: [`reports/playtests/playtests.md`](reports/playtests/playtests.md)</sub>

<br>

<p align="center">
  <img src=".github/readme-lofi/section-why.svg" width="100%" alt="Why it won't fall apart: the model writes the story, the local engine keeps the facts">
</p>

| | What a typical AI does | Adult Tension |
|:---|:---|:---|
| **Character attitude** | Complies without limits, gives you anything you ask | Every NPC has goals and a bottom line; responses come in five grades: refuse, negotiate, limited help, surface compliance, sincere help |
| **Adult content** | Fades to black at the key moment, or skips straight to "afterwards" | **Uncensored depth, paced by you**: explicit erotica, leverage bargains, crisis surrender, toy control, and reluctant-on-the-lips tension go as far as you push—never a forced fade-out. Strictly 18+; player `pause` and hard limits are enforced by the local engine |
| **Long-run memory** | Forgets after a dozen turns; relationships and setting drift | Characters, relationships, time, and facts live in local SQLite; brief context ≤ 6 KB, full context ≤ 32 KB |
| **Passage of time** | When you leave, the world stands still | When you skip ahead, people offscreen make their own moves, promises come due, rumors spread |
| **Saving progress** | Close the window and it's all gone | Named saves, save as, import and export; retries never advance the story twice, automatic backup before upgrades |

Three more details: names fit the era and region, so nothing breaks immersion; no anachronistic words, nobody in the High Tang says "OK"; every NPC has a public face and a private one, and with "inner voice" on, you can see the line they didn't say out loud.

<br>

<a id="start"></a>
<p align="center">
  <img src=".github/readme-lofi/section-start.svg" width="100%" alt="How to start: no syntax to learn, just talk plainly">
</p>

**Start a game**

| You say | What happens |
|:---|:---|
| `开局` (start) | Fully random; first asks whether you want "daily" or "pressure" |
| `开局，港口夜班` (start, Harbor Night Shift) | Pick a world |
| `开局，不要职场` (start, no workplace) | Exclude a theme |
| `开局，我是三十岁的女摄影师` (start, I'm a 30-year-old female photographer) | Set up who you are |
| `自定义世界` (custom world) | Not sure yet? You get a list of ideas first |
| `自定义世界，民国的一座山城……` (custom world, a mountain town in the Republic era…) | The model writes a world on the spot |
| `开局 我的世界 名字` (start my world `<name>`) | Start a new game in a saved custom world |
| `重开 42 号` (restart number 42) | Same seed, replayed exactly |

**Move the story**

A new game gives you "the world", "the characters" and the opening scene, which stops on an action waiting for you to take over. Just write what you do or say:

```text
我走到她面前，把文件放在桌上：“我们单独谈谈。”
```

(I walk up to her and put the file on the desk: "Let's talk alone.")

**Adjust any time**

| You say | What happens |
|:---|:---|
| `继续` · `c` (continue) | Moves one scene forward; at least one thing in the scene changes |
| `快进到明天早上` (skip to tomorrow morning) | People offscreen make their moves; whatever was due has an outcome |
| `状态` (status) | Relationships, promises, rumors, what's coming due |
| `存档` · `qs` (save) | Saves to the current slot |
| `另存为 名字` · `读档 名字` (save as `<name>` · load `<name>`) | Branch into a new slot, or pick up from that moment |
| `存档列表` (save list) | All saves |
| `保存世界 名字` · `我的世界` (save world `<name>` · my worlds) | Save a custom world; list your saved worlds |
| `导出` · `导入` (export · import) | Export a save file, carry on from another computer |
| `刚才不算` (that didn't count) | Undo or rewrite the last turn |
| `内心可见 开` · `暂停` · `边界：不要 X` (inner voice on · pause · limit: no X) | See what goes unsaid; stop at once; draw a line the engine holds for you |

If another window changed the same save, you're asked whether to load the latest, save as, or cancel. Nothing is silently overwritten.

<br>

<a id="install"></a>
<p align="center">
  <img src=".github/readme-lofi/section-install.svg" width="100%" alt="Install: just hand it to the AI, native SKILL">
</p>

No `pip install`, no environment variables, no API key.

**Let the AI install it for you.** In your host, say:

```text
Install this skill for me: https://github.com/daha1216/dsh-adult-tension (the Skill is in the skill/adult-tension directory)
```

**Or install by hand**: put `skill/adult-tension/` into your host's Skill directory.

```bash
git clone --depth 1 https://github.com/daha1216/dsh-adult-tension.git
```

```bash
cp -r dsh-adult-tension/skill/adult-tension ~/.dsh/skills/
```

| Host | Skill directory |
|---|---|
| DeepSeek Harness (DSH) | `~/.dsh/skills/` · `.dsh/skills/` in a project |
| Claude Code | `~/.claude/skills/` · `.claude/skills/` in a project |
| Codex | `~/.agents/skills/` · `.agents/skills/` in a repo |
| OpenCode | `~/.config/opencode/skills/` · `.opencode/skills/` in a project |
| pi | `~/.pi/agent/skills/` · `~/.agents/skills/` |

Then open a new conversation and say: "Check whether Adult Tension works."

<details>
<summary><b>Where are saves kept, and do upgrades lose them?</b></summary>
<br>

Saves never live in the Skill directory; upgrading or uninstalling never touches them.

| System | Data directory |
|---|---|
| Windows | `%LOCALAPPDATA%\adult-tension` |
| macOS | `~/Library/Application Support/adult-tension` |
| Linux | `$XDG_DATA_HOME/adult-tension`, or `~/.local/share/adult-tension` when unset |

You can also set it with the `ADULT_TENSION_HOME` environment variable or the `--data-dir` option. Upgrading means replacing the Skill directory; if the database format changes, it is backed up automatically before migrating and restored if migration fails.

</details>

### Which model to play with

Writing quality varies with the model version, context length and platform settings; the deeper the conversation, the more character consistency and feel for language depend on the model itself. The timeline, relationships and saves are guarded by the local engine, so switching models loses nothing. The session above used gemini-3.8-flash.

### Scope & Boundaries

- **Adults only (18+).** All characters and events are fictional, and every character is explicitly an adult. You can trigger `pause` or set hard limits at any time—enforced deterministically by the engine, never left to the model's discretion.
- **Needs an Agent host that can run local commands**, such as the ones in the table above. How the host sends the conversation to a model is up to the host and the model service you choose; saves exist only on your own computer.
- **Writing quality depends on the model.** The engine keeps the facts from drifting; style and judgment are still the model's job.

<details>
<summary><b>Developers</b></summary>
<br>

```
skill/adult-tension/     The installable Skill: SKILL.md, references/, runtime/, compiled world packs
content-src/worlds/      World pack sources
tools/                   Compile, validate, preview openings, simulate, benchmark
tests/                   core · content · integration · e2e
reports/                 Playtest records, reviews, benchmarks and acceptance evidence
spec/                    Requirements spec
PROGRESS.md              Progress, actual numbers, open decisions
```

The runtime uses only the Python standard library; SQLite is the only state store, with a single write path. Every write carries a `request_id`, and writes inside a session also carry an `expected_revision`, so a retry never advances the story twice.

```bash
python -m unittest discover -s tests/core
```

```bash
python tools/validate_skill.py skill/adult-tension
```

Adding a world: following `spec/CONTENT_BIBLE.md`, draft it with `tools/new_world.py`, read each opening with `tools/preview_openings.py`, pass validation and the opening-diversity gate, then real playtests, and only then move it from `review` to `released`.

</details>

<br>

<p align="center">
  <img src=".github/readme-lofi/architecture.svg?v=223" width="100%" alt="Skill architecture: nothing to manage, just use it like any other skill. The player talks to the Agent host, which calls the local runtime with JSON as SKILL.md describes; the runtime has six layers (adapters/cli, application, content, projections, persistence, domain), saves go to SQLite in the user's data folder, and world sources are compiled by tools into read-only world packs.">
</p>

<br>

<div align="center">

<sub>Rebuilt from scratch by Claude Opus 5.5. Adults only; all characters and events are fictional.</sub>

</div>
