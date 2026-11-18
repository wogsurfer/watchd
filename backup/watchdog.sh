#!/bin/sh
# Watches Watchd and sends a push notification (to NTFY_URL, an ntfy.sh topic
# URL in .env) when something needs a look:
#
#   - the site stops answering (checked every CHECK_MINUTES; it alerts after
#     two failed checks in a row, and again when it's back)
#   - the nightly backup hasn't run for over 26 hours (once a day until it does)
#
# Runs in the "watchdog" service of docker-compose.watchd.yaml. It can't warn
# you if Docker itself or the PC is down: for that, point an outside uptime
# monitor at the site.
set -u

URL="${WATCH_URL:-http://app:7330/api/proxy/auth/has-users}"
CHECK_MINUTES="${CHECK_MINUTES:-5}"
LAST_BACKUP=/backups/last-backup.txt

notify() {
    [ -n "${NTFY_URL:-}" ] || { echo "watchdog: $1 (NTFY_URL not set, no notification)"; return 0; }
    curl -fsS -m 15 -H "Title: $1" -H "Priority: ${3:-high}" -H "Tags: ${4:-warning}" \
        -d "$2" "$NTFY_URL" >/dev/null 2>&1 || echo "watchdog: couldn't send notification"
    echo "watchdog: $1"
}

fails=0
down=0
backup_warned=""

# Give the app time to start after Docker does.
sleep 120
echo "watchdog: watching $URL every $CHECK_MINUTES minutes"
while true; do
    if curl -fsS -m 20 -o /dev/null "$URL"; then
        if [ "$down" = 1 ]; then
            notify "Watchd is back up" "The site is answering again." default white_check_mark
        fi
        fails=0; down=0
    else
        fails=$((fails + 1))
        if [ "$fails" -ge 2 ] && [ "$down" = 0 ]; then
            down=1
            notify "Watchd is down" "The site hasn't answered for $((fails * CHECK_MINUTES)) minutes. Try: docker logs scrob-app-1" urgent
        fi
    fi

    # The backup writes last-backup.txt each night; warn when it's gone stale.
    today=$(date +%Y-%m-%d)
    if [ -f "$LAST_BACKUP" ]; then
        age=$(( $(date +%s) - $(stat -c %Y "$LAST_BACKUP") ))
    else
        age=999999
    fi
    if [ "$age" -gt $((26 * 3600)) ] && [ "$backup_warned" != "$today" ]; then
        backup_warned=$today
        notify "Watchd backup missed" "The last successful backup was $(cat "$LAST_BACKUP" 2>/dev/null || echo never). See: docker logs scrob-backup-1" high floppy_disk
    fi

    sleep $((CHECK_MINUTES * 60))
done
