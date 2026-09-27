#!/bin/bash
set -u
LOG=/tmp/xenc_install.log
rm -f "$LOG"
/usr/bin/systemd-run --scope --quiet --unit=xenc-install \
  /root/.venv-rag/bin/pip install --no-cache-dir sentence-transformers \
  > "$LOG" 2>&1 || {
  echo "systemd-run failed, trying setsid"
  setsid /root/.venv-rag/bin/pip install --no-cache-dir sentence-transformers \
    > "$LOG" 2>&1 < /dev/null &
}
echo LAUNCHED
sleep 20
tail -c 400 "$LOG"
