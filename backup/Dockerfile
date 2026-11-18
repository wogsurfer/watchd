# The nightly backup: Postgres's own tools, plus rsync for the files,
# openssl to encrypt what holds secrets and curl for push notifications.
# The same image runs the watchdog (watchdog.sh).
FROM postgres:16-alpine
RUN apk add --no-cache rsync openssl curl
COPY backup.sh /usr/local/bin/backup.sh
COPY watchdog.sh /usr/local/bin/watchdog.sh
ENTRYPOINT ["/bin/sh", "/usr/local/bin/backup.sh"]
