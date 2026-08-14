# PudimTranslate — chat translation for 0 A.D.

**Click a chat message to translate it. Click again to get the English back.** Works in a match, in
the multiplayer lobby and in the match setup screen.

Built for players whose English is shaky and who still want to play multiplayer, where everyone
talks in English.

> **No dependencies beyond 0 A.D. itself** — and none on PudimMod either. The two are independent;
> running both together causes no conflict, because PudimTranslate keeps its helpers in its own
> namespace (`pudimtr_*`).

---

## Installation

Put the `PudimTranslate` folder inside your 0 A.D. `mods` directory:

| System  | Path |
|---------|------|
| Windows | `Documents\My Games\0ad\mods\` |
| Linux   | `~/.local/share/0ad/mods/` |
| macOS   | `~/Library/Application Support/0ad/mods/` |

The folder must sit directly inside `mods/`, so that `mods/PudimTranslate/mod.json` exists.

Then open 0 A.D., go to **Settings → Mod Selection**, pick **PudimTranslate**, click **Enable**,
then **Save Configuration** and **Start Mods**.

## The companion program

Translation needs a small program running alongside the game, and there is no way around that: the
0 A.D. GUI script engine has **no HTTP at all** — no `fetch`, no XHR. The only networking exposed to
scripts is the XMPP lobby and mod.io, both in C++. So the mod writes the phrase to a file,
`tools/pudim_tradutor.py` translates it through Google Translate, and writes the answer back:

```
mod  --writes-->  saves/campaigns/pudim_tr_req.json  --reads-->  pudim_tradutor.py  --HTTP--> Google
mod  <---reads--  saves/campaigns/pudim_tr_res.json  <--writes-------'
```

Run `tools/PudimTradutor.bat` (needs Python) and leave the window open while you play. Without it
nothing breaks — the message just says the translator is off.

No API key and no sign-up: it calls the same free endpoint the translate.google.com page uses.
Translations are cached on disk, so a phrase already seen costs no network round trip.

**The target language follows the game.** Whatever locale 0 A.D. runs in is what you get back — play
in Spanish and the chat comes back in Spanish, with nothing to configure. The source language is
never declared: Google detects it on its own.

Set `pudimtranslate.auto` to `true` in the user config to translate every incoming message
automatically instead of clicking one by one.

## How it works, per screen

**In a match** no button had to be invented. The game's own `ChatOverlay` already treats each chat
line as a button — `gui/session/chat/ChatOverlay.js` sets `ghost = !chatMessage.callback` — and
sizes the line to the exact width of its text. So attaching a callback makes the message clickable
without covering the map or stealing clicks meant for units.

**In the lobby and the match setup screen** the chat is a `type="list"`, one item per message. There
is no per-line button there, but there is selection, so the gesture ends up the same: click the
message to translate it.

## Why `saves/campaigns/`

That folder is not a matter of taste. The GUI's `ReadJSONFile`/`WriteJSONFile` only accepts a closed
list of paths — `gui/`, `simulation/`, `maps/`, `campaigns/`, `saves/campaigns/`,
`config/matchsettings.json` and `config/matchsettings.mp.json`. Anything else answers *Restricted
access to …*. Of those, `saves/campaigns/` is the only writable user folder. It does not disturb
campaigns: the game only lists `*.0adcampaign` there, and these files are `.json`.

## Privacy

The chat messages you choose to translate are sent to Google Translate. Nothing else leaves your
machine, and nothing is sent until you click a message — unless you turn on `pudimtranslate.auto`,
in which case every incoming chat message is sent as it arrives.

## Language

The mod's own text (tooltips, notices) is Portuguese or English, following the game's language.

## License

PudimTranslate is released under the **GNU General Public License v3 or later** — see `LICENSE`.

All code is original — see `NOTICE`.
