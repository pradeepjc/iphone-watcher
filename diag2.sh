#!/bin/bash
# Visit the store page first (to get session cookies), then request availability with them.
cd "$(dirname "$0")"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
J=cookies.txt; : > "$J"
H=(-H "User-Agent: $UA" -H "Accept-Language: en-US,en;q=0.9")
curl -s -m 20 --compressed "${H[@]}" -c "$J" -b "$J" -o /dev/null -w "page: %{http_code}\n" "https://www.apple.com/shop/buy-iphone/iphone-duo"
echo "cookies set: $(grep -vc '^#' "$J")"
try() {
  label="$1"; url="$2"
  out=$(curl -s -m 20 --compressed "${H[@]}" -c "$J" -b "$J" \
    -H "Accept: */*" -H "Referer: https://www.apple.com/shop/buy-iphone/iphone-duo" \
    -H "x-requested-with: XMLHttpRequest" -H "Sec-Fetch-Mode: cors" -H "Sec-Fetch-Site: same-origin" \
    "$url" -w "\n%{http_code}")
  code=$(echo "$out" | tail -n1)
  head=$(echo "$out" | sed '$d' | head -c 120 | tr '\n' ' ')
  printf "%-22s %s  %s\n" "$label" "$code" "$head"
}
B="https://www.apple.com/shop/fulfillment-messages"
try "A with cookies" "$B?fae=true&pl=true&mts.0=regular&mts.1=compact&parts.0=MK1F4LL/A&searchNearby=true&location=55340"
sleep 3
try "B cookies+store" "$B?fae=true&pl=true&mts.0=regular&mts.1=compact&parts.0=MK1F4LL/A&searchNearby=true&store=R022"
