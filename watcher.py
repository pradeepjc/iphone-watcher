#!/usr/bin/env python3
"""iPhone Duo 256GB Night Sky (MK1F4LL/A) availability watcher.

Checks Apple's public availability data every 45-75s for:
  - In-store pickup at the 4 MSP Apple Stores
  - Delivery to 55340 arriving within 7 days
Alerts via ntfy (phone) + macOS notification/sound + opens Apple bag.
Read-only: never logs in, never adds to bag, never buys.

Usage:
  python3 watcher.py           run for 72 hours
  python3 watcher.py --test    send a test alert and exit
  python3 watcher.py --once    do one check, print result, exit
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys
import time

PART = "MK1F4LL/A"
ZIP = "55340"
STORES = {
    "R022": "Rosedale (Roseville)",
    "R007": "Mall of America (Bloomington)",
    "R054": "Southdale (Edina)",
    "R183": "Ridgedale (Minnetonka)",
}
MAX_DELIVERY_DAYS = 7
RUN_HOURS = 72
INTERVAL = (45, 75)           # seconds between checks (randomized)
HERE = os.path.dirname(os.path.abspath(__file__))
# ntfy topic is a secret (anyone who knows it can read/send alerts).
# Set NTFY_TOPIC env var, or put the topic in .ntfy_topic (git-ignored).
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
if not NTFY_TOPIC and os.path.exists(os.path.join(HERE, ".ntfy_topic")):
    with open(os.path.join(HERE, ".ntfy_topic")) as _f:
        NTFY_TOPIC = _f.read().strip()
NTFY_URL = "https://ntfy.sh/" + NTFY_TOPIC
BAG_URL = "https://www.apple.com/shop/bag"
HEARTBEAT_HOUR = 8            # daily "still watching" at 8 AM
REPEAT_ALERTS = 3             # alerts per availability episode
REPEAT_GAP = 120              # seconds between repeat alerts
FAIL_ALERT_AFTER = 10         # consecutive failures before problem alert

URL = ("https://www.apple.com/shop/fulfillment-messages?fae=true&pl=true"
       "&mts.0=regular&mts.1=compact&parts.0=MK1F4LL%2FA"
       "&searchNearby=true&location=" + ZIP)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/18.0 Safari/605.1.15")

LOG = os.path.join(HERE, "checks.log")


def now():
    return dt.datetime.now()


def log(line):
    stamp = now().strftime("%Y-%m-%d %H:%M:%S")
    msg = "%s  %s" % (stamp, line)
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def ntfy(title, message, priority="default", tags="", click=None):
    cmd = ["curl", "-s", "-m", "15", "-o", "/dev/null", "-w", "%{http_code}",
           "-H", "Title: " + title, "-H", "Priority: " + priority]
    if tags:
        cmd += ["-H", "Tags: " + tags]
    if click:
        cmd += ["-H", "Click: " + click]
    cmd += ["-d", message, NTFY_URL]
    try:
        code = subprocess.run(cmd, capture_output=True, text=True).stdout
        if code != "200":
            log("ntfy send failed (HTTP %s)" % code)
    except Exception as e:
        log("ntfy send error: %s" % e)


def mac_alert(title, message, open_bag=False):
    if sys.platform != "darwin":
        return
    t = title.replace('"', "'")
    m = message.replace('"', "'")
    subprocess.run(["osascript", "-e",
                    'display notification "%s" with title "%s" sound name "Glass"' % (m, t)],
                   capture_output=True)
    for _ in range(3):
        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], capture_output=True)
    if open_bag:
        subprocess.run(["open", BAG_URL], capture_output=True)


def fetch():
    """Returns (http_code, parsed_json_or_None)."""
    cmd = ["curl", "-s", "-m", "20", "--compressed",
           "-H", "User-Agent: " + UA,
           "-H", "Accept: application/json, text/plain, */*",
           "-H", "Referer: https://www.apple.com/shop/buy-iphone/iphone-duo",
           "-w", "\n%{http_code}", URL]
    r = subprocess.run(cmd, capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    code = code.strip() or "000"
    if code != "200":
        return code, None
    try:
        return code, json.loads(body)
    except ValueError:
        return "BADJSON", None


def parse(data):
    """Returns dict: stores{num:(display,quote)}, delivery_date, delivery_zip, buyable.
    Raises KeyError/TypeError if the format changed."""
    content = data["body"]["content"]
    stores = {}
    for s in content["pickupMessage"]["stores"]:
        num = s.get("storeNumber")
        if num in STORES:
            p = s["partsAvailability"][PART]
            stores[num] = (p.get("pickupDisplay", "?"), p.get("pickupSearchQuote", ""))
    dmsg = content.get("deliveryMessage", {}).get(PART, {})
    reg = dmsg.get("regular", {})
    ddate = None
    for opt in reg.get("deliveryOptionMessages", []):
        s = opt.get("encodedUpperDateString")
        if s:
            d = dt.datetime.strptime(s, "%Y%m%d").date()
            ddate = d if ddate is None or d < ddate else ddate
    dzip = reg.get("address", {}).get("postalCode")
    buyable = reg.get("buyability", {}).get("isBuyable")
    if not stores:
        raise KeyError("none of the MSP stores in response")
    return {"stores": stores, "delivery_date": ddate,
            "delivery_zip": dzip, "buyable": buyable}


def check_once(verbose=True):
    code, data = fetch()
    if data is None:
        return code, None
    try:
        return code, parse(data)
    except (KeyError, TypeError, ValueError) as e:
        return "FORMAT:%s" % e, None


def main():
    args = sys.argv[1:]
    if not NTFY_TOPIC:
        sys.exit("No ntfy topic set. Put it in .ntfy_topic or export NTFY_TOPIC=...")
    if "--test" in args:
        ntfy("iPhone watcher TEST", "Test alert from your Mac. If you see this, alerts work. Tap to open Apple bag.",
             priority="urgent", tags="white_check_mark", click=BAG_URL)
        mac_alert("iPhone watcher TEST", "Test alert - Mac notifications work.")
        print("Test alert sent to ntfy topic:", NTFY_TOPIC[:6] + "...")
        return
    if "--once" in args:
        code, r = check_once()
        print("HTTP/status:", code)
        print(json.dumps(r, indent=2, default=str))
        return

    end = now() + dt.timedelta(hours=RUN_HOURS)
    log("Watcher started. Runs until %s. Part %s, ZIP %s." % (end.strftime("%a %b %d %I:%M %p"), PART, ZIP))
    ntfy("iPhone watcher started",
         "Watching 4 MSP stores + delivery to %s every ~1 min until %s." % (ZIP, end.strftime("%a %b %d %I:%M %p")),
         tags="eyes")

    episode = {}          # key -> {"count": n, "last": ts} while available
    fails = 0
    problem_alerted_at = None
    backoff = 0
    last_heartbeat_day = None
    zip_warned = False
    checks = 0

    while now() < end:
        code, r = check_once()
        checks += 1
        if r is None:
            fails += 1
            if code in ("403", "429", "503"):
                backoff = min(600, (backoff or 60) * 2)
            log("CHECK FAILED (%s) consecutive=%d backoff=%ds" % (code, fails, backoff))
            if fails >= FAIL_ALERT_AFTER and (problem_alerted_at is None or
                                              time.time() - problem_alerted_at > 7200):
                ntfy("iPhone watcher PROBLEM",
                     "%d checks in a row failed (last: %s). Apple may be blocking or changed format. Check the Mac."
                     % (fails, code), priority="high", tags="warning")
                problem_alerted_at = time.time()
        else:
            if problem_alerted_at is not None:
                ntfy("iPhone watcher recovered", "Checks are working again.", tags="white_check_mark")
            fails, backoff, problem_alerted_at = 0, 0, None

            hits = []
            for num, (disp, quote) in r["stores"].items():
                if disp == "available":
                    hits.append((num, "%s pickup: %s" % (STORES[num], quote)))
            d = r["delivery_date"]
            if d and (d - now().date()).days <= MAX_DELIVERY_DAYS and r["buyable"] is not False:
                hits.append(("delivery", "Delivery to %s by %s" % (r["delivery_zip"] or ZIP, d.strftime("%a %b %d"))))
            if r["delivery_zip"] and r["delivery_zip"] != ZIP and not zip_warned:
                log("NOTE: Apple quoted delivery for ZIP %s, not %s" % (r["delivery_zip"], ZIP))
                zip_warned = True

            summary = " | ".join("%s=%s" % (n, r["stores"][n][0]) for n in sorted(r["stores"]))
            log("ok  %s | delivery=%s" % (summary, d))

            hit_keys = set(k for k, _ in hits)
            for k in list(episode):
                if k not in hit_keys:
                    log("Stock gone: %s" % k)
                    del episode[k]
            for k, text in hits:
                ep = episode.setdefault(k, {"count": 0, "last": 0})
                if ep["count"] < REPEAT_ALERTS and time.time() - ep["last"] >= REPEAT_GAP:
                    ep["count"] += 1
                    ep["last"] = time.time()
                    log("ALERT %d/%d: %s" % (ep["count"], REPEAT_ALERTS, text))
                    ntfy("iPhone Duo AVAILABLE", text + ". Tap to open bag and buy now.",
                         priority="urgent", tags="rotating_light", click=BAG_URL)
                    mac_alert("iPhone Duo AVAILABLE", text, open_bag=(ep["count"] == 1))

        t = now()
        if t.hour == HEARTBEAT_HOUR and last_heartbeat_day != t.date():
            last_heartbeat_day = t.date()
            ntfy("iPhone watcher: still watching",
                 "%d checks so far. No action needed. Ends %s." % (checks, end.strftime("%a %b %d %I:%M %p")),
                 priority="low", tags="eyes")

        time.sleep(random.uniform(*INTERVAL) + backoff)

    log("Watcher finished after %d hours (%d checks)." % (RUN_HOURS, checks))
    ntfy("iPhone watcher stopped", "72-hour run finished after %d checks." % checks, tags="stop_sign")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user.")
