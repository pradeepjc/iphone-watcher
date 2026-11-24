# iPhone Duo Availability Watcher

Watches Apple's public stock data for the **iPhone Duo 256GB Night Sky, unlocked (part `MK1F4LL/A`)** and alerts you the moment it can be picked up nearby or delivered soon.

**It only checks stock.** It never logs in, never adds anything to your bag and never buys anything. When stock shows up, you finish the purchase yourself.

---

## What it watches

| Target | Condition that triggers an alert |
|---|---|
| Apple Rosedale (Roseville), store `R022` | In-store pickup shows `available` |
| Apple Mall of America (Bloomington), store `R007` | In-store pickup shows `available` |
| Apple Southdale (Edina), store `R054` | In-store pickup shows `available` |
| Apple Ridgedale (Minnetonka), store `R183` | In-store pickup shows `available` |
| Delivery to ZIP `55340` | Earliest delivery date is within 7 days and the item can be bought |

## How you get alerted

| Channel | `watcher.py` (Mac) | `browser-watcher.js` (Chrome) |
|---|---|---|
| Phone push through [ntfy.sh](https://ntfy.sh), tapping it opens your Apple bag | ✅ | ✅ |
| macOS notification and the "Glass" sound played 3 times | ✅ | — |
| Opens the Apple bag page in your browser (first alert only) | ✅ | — |
| Beeps in the tab and changes the tab title to `IN STOCK - …` | — | ✅ |

To get phone alerts, install the **ntfy** app (iOS or Android) and subscribe to your topic (see [Setting your ntfy topic](#setting-your-ntfy-topic)).

### Setting your ntfy topic

The topic name works like a password: anyone who knows it can read your alerts or send you fake ones. So it is **not stored in the repo**. Pick a long random name, for example `iphone-duo-$(openssl rand -hex 6)`, then:

- **`watcher.py`:** put it in a file called `.ntfy_topic` in this folder (git ignores this file), or `export NTFY_TOPIC=...`. The environment variable takes priority.
  ```bash
  echo "iphone-duo-$(openssl rand -hex 6)" > .ntfy_topic
  ```
- **`browser-watcher.js`:** in the DevTools console on apple.com, run this once (it is remembered for that browser):
  ```js
  localStorage.duoNtfyTopic = "your-topic-name"
  ```

Subscribe to the same name in the ntfy app.

---

## Files

| File | Purpose |
|---|---|
| `watcher.py` | The main watcher. A Python script that checks stock with `curl`. |
| `start.sh` | Runs `watcher.py` under `caffeinate` so the Mac stays awake. |
| `browser-watcher.js` | The same watcher, run inside a Chrome tab on apple.com. Use this one when Apple blocks the Python version. |
| `diag.sh` | Diagnostic: tries several request variants and prints the HTTP status of each. |
| `diag2.sh` | Diagnostic: visits the store page first to get cookies, then requests stock with those cookies. Writes `cookies.txt`. |
| `diag3.sh` | Diagnostic: requests the unlocked model (`cppart=UNLOCKED/US`) and prints a readable stock summary. |
| `checks.log` | Created by `watcher.py`. One line per check, alert and error. Git ignores it. |
| `cookies.txt` | Created by `diag2.sh`. Temporary cookies; safe to delete. Git ignores it. |
| `.ntfy_topic` | Your private ntfy topic name. Git ignores it. |

---

## Requirements

- macOS. Linux also works for `watcher.py`, but without the desktop notification, sound or auto-opening the bag.
- `python3` (standard library only, nothing to install)
- `curl`
- Google Chrome, for `browser-watcher.js`
- The ntfy app on your phone, for push alerts

---

## Usage

### Option A: Python watcher (`watcher.py`)

```bash
cd ~/iphone-watcher

# 0. One-time: set your private ntfy topic (see above)
echo "iphone-duo-$(openssl rand -hex 6)" > .ntfy_topic

# 1. Check that alerts reach your phone and Mac
python3 watcher.py --test

# 2. Do a single check and print what Apple returned
python3 watcher.py --once

# 3. Run for 72 hours, keeping the Mac awake
./start.sh
```

Stop it any time with **Ctrl+C**. Leave the Mac plugged in with the lid open: `caffeinate -is` stops idle and system sleep, but closing the lid on battery still puts the Mac to sleep.

If `--once` prints an HTTP status other than `200`, such as `403` or `541`, Apple's bot protection is blocking plain `curl` requests. Use Option B.

### Option B: Chrome watcher (`browser-watcher.js`)

This runs inside a real browser tab, so it uses your normal apple.com cookies and gets past the bot protection.

1. In Chrome, open `https://www.apple.com/shop/buy-iphone/iphone-duo`.
2. Allow pop-ups for apple.com: click the address-bar icon, or go to Settings → Privacy → Site settings → Pop-ups. The watcher briefly opens a small window to renew the session.
3. Open DevTools (**⌥⌘J**). The first time only, run `localStorage.duoNtfyTopic = "your-topic-name"`.
4. Paste the whole contents of `browser-watcher.js` into the Console and press Enter.
5. Leave the tab open. Background tabs work, but keep the Mac awake, for example by running `caffeinate -is` in a terminal.

To stop it, run this in the same Console:

```js
__duoWatcher.stop()
```

Pasting the script a second time does nothing while it is already running.

---

## How it works

### 1. Stock check

Both versions call Apple's stock endpoint, the same one the Apple Store website uses:

```
https://www.apple.com/shop/fulfillment-messages
  ?fae=true&pl=true
  &mts.0=regular&mts.1=compact
  &cppart=UNLOCKED/US          ← browser version only
  &parts.0=MK1F4LL/A
  &searchNearby=true
  &location=55340
```

The JSON response holds:
- `body.content.pickupMessage.stores[]`: one entry per nearby store, each with `partsAvailability["MK1F4LL/A"].pickupDisplay` (`available` / `unavailable` / `ineligible`) and `pickupSearchQuote` (for example "Available Today").
- `body.content.deliveryMessage["MK1F4LL/A"].regular`: delivery options. `encodedUpperDateString` (`YYYYMMDD`) is the latest arrival date, `address.postalCode` is the ZIP Apple quoted for, and `buyability.isBuyable` says whether it can be ordered.

### 2. Deciding whether to alert

- A store counts as a hit when its `pickupDisplay == "available"`.
- Delivery counts as a hit when the earliest date is **7 days or fewer** from today and `isBuyable` is not `false`.
- If Apple quotes delivery for a different ZIP than `55340`, `watcher.py` logs a one-time note.

### 3. Avoiding repeat alerts

Each hit (each store, plus delivery) is tracked as an **episode**:
- It sends up to **3 alerts**, at least **2 minutes apart**.
- When the hit disappears, the episode resets and `Stock gone: …` is logged. If stock comes back later, you get alerted again.

### 4. Timing

- A check every **45–75 seconds**, randomized so the requests look less robotic.
- `watcher.py`: after an HTTP `403`, `429` or `503`, it adds extra wait time that doubles each time (60 s → 120 s → … up to 10 min). The extra wait resets after a successful check.
- `browser-watcher.js`: it renews the session every 20 minutes. On HTTP `541` (Apple's bot-protection block) it renews immediately and retries once.

### 5. Health messages

| Message | When |
|---|---|
| `iPhone watcher started` | At launch |
| `iPhone watcher: still watching` | Daily at 8 AM, with the number of checks so far |
| `iPhone watcher PROBLEM` | After 10 failed checks in a row (at most once every 2 hours) |
| `iPhone watcher recovered` | First successful check after a PROBLEM alert |
| `iPhone watcher stopped` | After 72 hours, or when stopped manually (browser version) |

---

## Configuration

Edit the constants at the top of `watcher.py`:

| Constant | Default | Meaning |
|---|---|---|
| `PART` | `MK1F4LL/A` | Apple part number to watch |
| `ZIP` | `55340` | ZIP code for the nearby-store search and delivery quote |
| `STORES` | 4 Minneapolis-area stores | Store numbers to watch, and their display names |
| `MAX_DELIVERY_DAYS` | `7` | Delivery alert threshold in days |
| `RUN_HOURS` | `72` | How long to run before stopping |
| `INTERVAL` | `(45, 75)` | Random range of seconds between checks |
| `NTFY_TOPIC` | from env var or `.ntfy_topic` | ntfy topic for phone alerts (never hardcode it) |
| `HEARTBEAT_HOUR` | `8` | Hour (24-hour clock) for the daily "still watching" message |
| `REPEAT_ALERTS` | `3` | Alerts per availability episode |
| `REPEAT_GAP` | `120` | Seconds between repeat alerts |
| `FAIL_ALERT_AFTER` | `10` | Consecutive failures before a PROBLEM alert |

`browser-watcher.js` has the same settings in short form near its top: `PART`, `ZIP`, `STORES`, `RUN_MS`, `MAX_DAYS`, `REPEAT`, `REPEAT_GAP`, `FAIL_ALERT`. **If you change a setting, change it in both files.**

### Finding other part numbers or store numbers

- **Part number:** on apple.com, choose the model, colour and storage, then look in DevTools → Network for a `fulfillment-messages` request. The `parts.0=` value is the part number.
- **Store numbers:** run `./diag3.sh`. It lists every nearby store number with its status.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `--once` shows `403` or `541` | Apple is blocking curl. Use `browser-watcher.js`. |
| `CHECK FAILED (FORMAT:…)` in the log | Apple changed the JSON format, or none of the 4 stores were in the response. Run `diag3.sh` to look at the raw data. |
| `CHECK FAILED (BADJSON)` | Apple returned a page that isn't JSON, usually a block or error page. |
| Browser console: `POPUP BLOCKED` | Allow pop-ups for apple.com in Chrome. |
| Browser console: `ntfy FAILED (blocked?)` | An ad blocker or privacy extension is blocking `ntfy.sh`. Allow it for apple.com. |
| `No ntfy topic set` / `No ntfy topic` | Set the topic. See [Setting your ntfy topic](#setting-your-ntfy-topic). |
| No phone pushes | Check you subscribed to the exact topic name in the ntfy app, then run `python3 watcher.py --test`. |
| Watcher stops overnight | The Mac went to sleep. Use `start.sh` or `caffeinate`, stay on power and keep the lid open. |
| Python and browser versions disagree | `watcher.py` leaves out `cppart=UNLOCKED/US`, so it may be checking a carrier model rather than the unlocked one. Add `&cppart=UNLOCKED/US` to `URL` in `watcher.py`. |

---

## Known limitations

- **Python version and Apple's block:** `watcher.py` doesn't treat Apple's bot-protection status `541` as a reason to wait longer, and it has no way to renew its session. The browser version handles both.
- **Unlocked vs carrier model:** see the last troubleshooting row above.
- **The topic name is the only protection on your alerts:** anyone who knows it can read or send messages on it. Keep it out of the repo and don't put anything sensitive in alerts. If it ever leaks, pick a new name and re-subscribe.
- **Undocumented endpoint:** Apple doesn't document the stock endpoint, so it can change or disappear without notice.
- **Run time is fixed:** both versions stop after 72 hours. Restart them to keep watching.

## Responsible use

The watcher checks about once a minute from a single machine, roughly what a person refreshing the page would do. Don't shorten the interval much or run many copies, and keep it read-only. Buy the phone yourself.
