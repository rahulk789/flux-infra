#!/usr/bin/env bash
# Sends one request per second to the load balancer and prints results.
# Green = success, Red = failure. Keep this running during the migration.

LB_URL="${1:-http://localhost:8080/inference}"
INTERVAL="${2:-1}"

echo "Sending traffic to $LB_URL every ${INTERVAL}s"
echo "Press Ctrl+C to stop"
echo ""

seq_num=0
pass=0
fail=0

while true; do
    seq_num=$((seq_num + 1))
    timestamp=$(date +%H:%M:%S)

    response=$(curl -s -o /tmp/traffic-response.json -w "%{http_code}" "$LB_URL" 2>/dev/null)

    if [ "$response" = "200" ]; then
        pass=$((pass + 1))
        instance=$(cat /tmp/traffic-response.json | grep -o '"instance_id":"[^"]*"' | head -1 | cut -d'"' -f4)
        host=$(cat /tmp/traffic-response.json | grep -o '"operator_host":"[^"]*"' | head -1 | cut -d'"' -f4)
        cluster=$(cat /tmp/traffic-response.json | grep -o '"cluster": *"[^"]*"' | head -1 | cut -d'"' -f4)
        printf "\033[32m[%s] #%04d ✓ [%s] %s → %s\033[0m\n" "$timestamp" "$seq_num" "${cluster:-unknown}" "${host:-ok}" "${instance:-ok}"
    else
        fail=$((fail + 1))
        error=$(cat /tmp/traffic-response.json 2>/dev/null | head -c 120)
        printf "\033[31m[%s] #%04d ✗ HTTP %s — %s\033[0m\n" "$timestamp" "$seq_num" "$response" "$error"
    fi

    if [ $((seq_num % 10)) -eq 0 ]; then
        total=$((pass + fail))
        pct=$((pass * 100 / total))
        printf "\033[36m         — %d/%d passed (%d%%)\033[0m\n" "$pass" "$total" "$pct"
    fi

    sleep "$INTERVAL"
done
