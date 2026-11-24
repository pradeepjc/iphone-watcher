#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
B="https://www.apple.com/shop/fulfillment-messages?fae=true&pl=true&mts.0=regular&mts.1=compact&cppart=UNLOCKED/US&parts.0=MK1F4LL/A&searchNearby=true"
try() {
  out=$(curl -s -m 20 --compressed -H "User-Agent: $UA" -H "Accept: */*" -H "Referer: https://www.apple.com/shop/buy-iphone/iphone-duo" "$2" -w "\n%{http_code}")
  code=$(echo "$out" | tail -n1); body=$(echo "$out" | sed '$d')
  printf "%-16s %s  " "$1" "$code"
  echo "$body" | python3 -c '
import sys,json
try:
    c=json.load(sys.stdin)["body"]["content"]
    st=c["pickupMessage"]["stores"]
    print("stores:", ", ".join("%s=%s"%(s["storeNumber"],s["partsAvailability"]["MK1F4LL/A"]["pickupDisplay"]) for s in st))
    d=c.get("deliveryMessage",{}).get("MK1F4LL/A",{}).get("regular",{})
    print("                    delivery zip:", d.get("address",{}).get("postalCode"), "date:", [o.get("displayName") for o in d.get("deliveryOptionMessages",[])])
except Exception as e:
    print("not JSON / unexpected:", str(e)[:80])'
  sleep 3
}
try "with ZIP 55340" "$B&location=55340"
try "with store R022" "$B&store=R022"
