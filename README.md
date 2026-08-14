# PudimTranslate — chat translation for 0 A.D.

**Click a chat message to translate it. Click again to get the English back.** Works in a match, in
the multiplayer lobby and in the match setup screen.

Built for players whose English is shaky and who still want to play multiplayer, where everyone
talks in English.

> **No dependencies beyond 0 A.D. itself** — and none on PudimMod either. The two are independent;
> running both together causes no conflict, because PudimTranslate keeps its helpers in its own
> namespace (`pudimtr_*`).

---

## ⚠️ Read this first: the translator must be running *before* the game

Translation needs a small companion program. **Start it before you open 0 A.D., every time.**

That is not a style preference — it is how the game works. 0 A.D. indexes its data folders once, at
startup, and never notices files that appear afterwards. If the translator is not already running
when the game starts, the game cannot see the bridge at all and nothing will translate for that
whole session. Closing and reopening 0 A.D. fixes it.

So the routine is:

1. Open the translator. Leave its window open.
2. Open 0 A.D.
3. Play. Click any chat message to translate it.

**The first time you run the translator it creates a `0 A.D. Translator` shortcut on your desktop**,
with the 0 A.D. icon and the correct path for your machine, so you do not have to go hunting for the
folder again. Put it next to your 0 A.D. shortcut and always click it first.

If you would rather not think about the order at all, use **`tools/Jogar0AD.bat`** instead: it starts
the translator, waits for it to be ready, opens 0 A.D., and shuts the translator down when you quit.
One click, right order, nothing to remember.

---

## Installation

Download the repository (**Code → Download ZIP**, or `git clone`) and put the `PudimTranslate`
folder inside your 0 A.D. `mods` directory:

| System  | Path |
|---------|------|
| Windows | `%APPDATA%\0ad\mods\` — or `Documents\My Games\0ad\mods\` |
| Linux   | `~/.local/share/0ad/mods/` |
| macOS   | `~/Library/Application Support/0ad/mods/` |

If you are unsure, the game's own reference is at
<https://trac.wildfiregames.com/wiki/GameDataPaths>.

The folder must sit directly inside `mods/`, so that `mods/PudimTranslate/mod.json` exists — a
common mistake is ending up with `mods/PudimTranslate/PudimTranslate/`.

Then open 0 A.D., go to **Settings → Mod Selection**, pick **PudimTranslate**, click **Enable**,
then **Save Configuration** and **Start Mods**.

**Python is required** for the translator — the mod itself needs nothing extra. If you do not have
it, get it at <https://python.org/downloads> and tick *Add Python to PATH* during setup.

To update, replace the folder with the newer version and restart the game.

---

## Using it

Click a chat message. It turns into your language; click again and the English comes back. The
original is always in the tooltip, so nothing is lost.

While a phrase is being translated the line shows *translating…*. If it says the translator is off,
you opened the game without starting the translator first — close 0 A.D., start the translator, open
the game again.

System notices (*"== Someone joined."*) are never sent anywhere: 0 A.D. already shows those in your
own language.

Set `pudimtranslate.auto` to `true` in the user config to translate every incoming message
automatically instead of clicking one by one.

**The target language follows the game.** Whatever locale 0 A.D. runs in is what you get back — play
in Spanish and the chat comes back in Spanish, with nothing to configure. The source language is
never declared: Google detects it on its own.

---

## Why a companion program at all

There is no way around it: the 0 A.D. GUI script engine has **no HTTP** — no `fetch`, no XHR. The
only networking exposed to scripts is the XMPP lobby and mod.io, both in C++. A mod simply cannot
call a translation service.

What a mod *can* do is read and write files. So the mod writes the phrase to a file, the companion
program translates it, and writes the answer back:

```
mod  --writes-->  saves/campaigns/pudim_tr_req.json  --reads-->  pudim_tradutor.py  --HTTP--> Google
mod  <---reads--  saves/campaigns/pudim_tr_res.json  <--writes-------'
```

No API key and no sign-up: it calls the same free endpoint the translate.google.com page uses.
Translations are cached on disk, so a phrase already seen costs no network round trip.

That folder is not a matter of taste. The GUI's `ReadJSONFile`/`WriteJSONFile` only accepts a closed
list of paths — `gui/`, `simulation/`, `maps/`, `campaigns/`, `saves/campaigns/`,
`config/matchsettings.json` and `config/matchsettings.mp.json`. Anything else answers *Restricted
access to …*. Of those, `saves/campaigns/` is the only writable user folder. It does not disturb
campaigns: the game only lists `*.0adcampaign` there, and these files are `.json`.

The response file is always exactly 64 KB, padded with spaces. The game's VFS remembers a file's
size from when it indexed the folder, so a file that grows gets read truncated — a JSON cut in half.
A fixed size keeps that remembered value correct forever.

## How it works, per screen

**In a match** no button had to be invented. The game's own `ChatOverlay` already treats each chat
line as a button — `gui/session/chat/ChatOverlay.js` sets `ghost = !chatMessage.callback` — and
sizes the line to the exact width of its text. So attaching a callback makes the message clickable
without covering the map or stealing clicks meant for units.

**In the lobby and the match setup screen** the chat is a `type="list"`, one item per message. There
is no per-line button there, but there is selection, so the gesture ends up the same: click the
message to translate it.

## Privacy

The chat messages you choose to translate are sent to Google Translate. Nothing else leaves your
machine, and nothing is sent until you click a message — unless you turn on `pudimtranslate.auto`,
in which case every incoming chat message is sent as it arrives.

## Language

The mod's own text (tooltips, notices) is Portuguese or English, following the game's language.

## License

PudimTranslate is released under the **GNU General Public License v3 or later** — see `LICENSE`.

All code is original — see `NOTICE`.
