# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, etc.) working in this folder. Read `README.md` for the user-facing documentation.

## Project summary

A small, single-purpose tool that watches Apple's undocumented stock endpoint (`/shop/fulfillment-messages`) for one product, **part `MK1F4LL/A`** (iPhone Duo 256GB Night Sky, unlocked). It covers pickup at 4 Minneapolis-area stores and delivery to ZIP `55340`, and sends alerts through ntfy.sh and macOS notifications.

Two implementations of the same logic:
- `watcher.py`: Python 3, standard library only. Makes requests by running `curl` through `subprocess`. Entry point: `start.sh`.
- `browser-watcher.js`: a self-contained function you paste into the DevTools console of an apple.com tab. Uses `fetch` with the browser's cookies.

`diag*.sh` are throwaway scripts for investigating why requests get blocked. `checks.log`, `cookies.txt` and `.ntfy_topic` are local-only files that git ignores.

The project has no build step, dependencies or test suite.

## Hard rules

1. **Stay read-only.** Never add code that logs in, adds to the bag, starts checkout, fills in forms or buys anything. Opening `https://www.apple.com/shop/bag` for the user to act on is the only allowed interaction.
2. **Don't hammer Apple.** Keep the randomized interval at about 45 s or more. Don't add parallel or burst requests or multiple copies. Keep backoff on errors.
3. **Don't try to defeat bot protection.** Using the user's real browser session (`browser-watcher.js`) is the approved approach. Don't add CAPTCHA solving, fingerprint spoofing, proxy rotation or similar.
4. **Keep the two implementations in sync.** Any change to targets, thresholds, alert wording, request URL or parsing must be made in both `watcher.py` and `browser-watcher.js`, unless the user asks otherwise.
5. **Standard library only** for `watcher.py`. No `pip install`. Keep shelling out to `curl` as it does now, unless the user asks to change that.
6. **The ntfy topic is a secret.** Never hardcode it or commit it. `watcher.py` reads it from the `NTFY_TOPIC` env var or the git-ignored `.ntfy_topic` file. `browser-watcher.js` reads it from `localStorage.duoNtfyTopic`. Don't print the full topic in logs or output.
7. **Privacy:** don't post the ntfy topic, the user's ZIP or `checks.log` contents to any outside service other than ntfy itself. Never commit or upload `cookies.txt`.

## Code map

### `watcher.py`

| Lines (approx.) | Item | Notes |
|---|---|---|
| 23–47 | Config constants | `PART`, `ZIP`, `STORES`, `MAX_DELIVERY_DAYS`, `RUN_HOURS`, `INTERVAL`, `NTFY_TOPIC` (loaded from env/`.ntfy_topic`), `HEARTBEAT_HOUR`, `REPEAT_ALERTS`, `REPEAT_GAP`, `FAIL_ALERT_AFTER` |
| 42–46 | `URL`, `UA` | Request URL and Safari User-Agent. Note that `URL` has no `cppart=UNLOCKED/US`, unlike the JS version. |
| 56 | `log()` | Writes timestamped lines to stdout and appends them to `checks.log` |
| 64 | `ntfy()` | POSTs to ntfy.sh with `curl`. Only logs failures and never raises. |
| 80 | `mac_alert()` | `osascript` notification, then `afplay` 3 times, then optionally `open` the bag. Does nothing on systems other than macOS. |
| 94 | `fetch()` | Returns `(http_code_str, json_or_None)`. `"BADJSON"` when the body isn't JSON. |
| 112 | `parse()` | Returns `{stores: {num: (display, quote)}, delivery_date, delivery_zip, buyable}`. Raises `KeyError`/`TypeError` when the format changes. |
| 138 | `check_once()` | Wraps `fetch` and `parse`. A format error comes back as code `"FORMAT:<msg>"`. |
| 148 | `main()` | Handles the `--test` and `--once` flags, then runs the main loop: failure count, backoff, hit detection, alert repeats per episode, daily heartbeat. |

### `browser-watcher.js`

The whole script is one function that runs immediately. It guards against running twice with `window.__duoWatcher`.
- Config constants are near the top and match the Python ones. The topic comes from `localStorage.duoNtfyTopic`; the script exits early with instructions if it is missing.
- `refreshSession()` opens a pop-up window named `duoRefresh` for 12 s to renew Apple's bot-protection cookies. It runs every 20 min and on HTTP `541`.
- `check()` and `parse()` mirror the Python logic.
- `loop()` calls itself again with `setTimeout`, every 45–75 s.
- To stop it: `window.__duoWatcher.stop()`.

## Response shape relied on

```
body.content.pickupMessage.stores[] {
  storeNumber: "R022",
  partsAvailability: { "MK1F4LL/A": { pickupDisplay: "available"|"unavailable"|"ineligible", pickupSearchQuote: "..." } }
}
body.content.deliveryMessage["MK1F4LL/A"].regular {
  deliveryOptionMessages[]: { encodedUpperDateString: "YYYYMMDD", displayName: "..." },
  address: { postalCode },
  buyability: { isBuyable }
}
```

If you change `parse()`, keep it failing loudly (raise or throw) when the format is unexpected, so the failure counter and PROBLEM alert still fire. Don't quietly treat missing data as "unavailable".

## Alert behaviour that must be preserved

- Hits are keyed by store number, or `"delivery"`.
- Each episode sends at most `REPEAT_ALERTS` (3) alerts, at least `REPEAT_GAP` (120 s) apart. The bag opens only on the first alert.
- The episode is deleted when the hit disappears, so stock that comes back alerts again.
- A PROBLEM alert goes out after `FAIL_ALERT_AFTER` failures in a row, throttled to once every 2 hours, followed by a "recovered" message.
- A "still watching" heartbeat goes out once a day at `HEARTBEAT_HOUR`.

## How to verify changes

There are no automated tests. Use these checks:

```bash
python3 -m py_compile watcher.py       # syntax check
python3 watcher.py --once              # one real request; prints status + parsed result
python3 watcher.py --test              # sends a real push and Mac notification (ask the user first)
./diag3.sh                             # raw store list, to compare against parse() output
node --check browser-watcher.js        # JS syntax check (if node is installed)
```

- `--test` sends a real notification to the user's phone. Ask before running it.
- Don't start the full 72-hour run (`start.sh` or `watcher.py` with no flags) unless the user asks. It is long-running and sends a "started" push.
- To test alert logic without network access, feed a sample JSON into `parse()` in a scratch script, rather than changing `fetch()`.

## Known issues / likely follow-ups

1. `watcher.py` `URL` is missing `&cppart=UNLOCKED/US`, so it may report on a carrier model rather than the unlocked one. The JS version and `diag3.sh` include it.
2. `watcher.py` only adds backoff for `403`/`429`/`503`, not for `541` (Apple's bot-protection response).
3. `watcher.py` usually gets blocked by Apple when using plain curl, so the browser version is the one that works.
4. The topic is configured separately for each version (file/env for Python, localStorage for JS), because the JS version must stay paste-and-run.

## Style

- Python: keep the existing style, which uses `%` formatting and is compatible with older Python 3, has no type hints, and uses simple functions.
- JS: keep it as one self-contained function with no imports or build step, so it can be pasted directly into the console.
- Keep log lines short and easy to scan with grep (`ok`, `CHECK FAILED`, `ALERT n/3`, `Stock gone`).
