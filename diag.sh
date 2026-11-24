#!/bin/bash
# Tries several request variants against Apple and prints the HTTP status of each.
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
B="https://www.apple.com/shop/fulfillment-messages"
try() {
  label="$1"; shift
  out=$(curl -s -m 20 --compressed "$@" -w "\n%{http_code}")
  code=$(echo "$out" | tail -n1)
  head=$(echo "$out" | sed '$d' | head -c 120 | tr '\n' ' ')
  printf "%-28s %s  %s\n" "$label" "$code" "$head"
}
H=(-H "User-Agent: $UA" -H "Accept: application/json, text/plain, */*" -H "Referer: https://www.apple.com/shop/buy-iphone/iphone-duo")
try "1 current"          "${H[@]}" "$B?fae=true&pl=true&mts.0=regular&mts.1=compact&parts.0=MK1F4LL%2FA&searchNearby=true&location=55340"
try "2 raw slash"        "${H[@]}" "$B?fae=true&pl=true&mts.0=regular&mts.1=compact&parts.0=MK1F4LL/A&searchNearby=true&location=55340"
try "3 with store"       "${H[@]}" "$B?fae=true&pl=true&mts.0=regular&mts.1=compact&parts.0=MK1F4LL/A&searchNearby=true&store=R022"
try "4 minimal"          "${H[@]}" "$B?pl=true&mts.0=regular&parts.0=MK1F4LL/A&location=55340"
try "5 store+location"   "${H[@]}" "$B?pl=true&mts.0=regular&mts.1=compact&parts.0=MK1F4LL/A&searchNearby=true&store=R022&location=55340"
try "6 plain curl"       "$B?pl=true&mts.0=regular&parts.0=MK1F4LL/A&location=55340"
try "7 apple.com home"   "${H[@]}" "https://www.apple.com/shop/buy-iphone/iphone-duo" -o /dev/null
