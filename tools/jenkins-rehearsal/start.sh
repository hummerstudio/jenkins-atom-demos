#!/usr/bin/env bash
# Start (or restart) the rehearsal Jenkins on the build machine.
#
# The instance is disposable: no login, no agents, atoms auto-installed from a loopback mirror of the center.
# Everything it needs lives under $JENKINS_HOME, so restarting is safe and reuses the plugins already installed.
#
#   ./start.sh              # (re)start
#   ./start.sh status       # is it up, and what do the demo jobs say
#   ./start.sh stop
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
JENKINS_HOME="${JENKINS_HOME:-$HOME/jenkins-real}"
WAR="${WAR:-/tmp/jenkins.war}"
PORT="${PORT:-8088}"
CENTER_DIR="${CENTER_DIR:-$HOME/atom-center-http}"
CENTER_PORT="${CENTER_PORT:-8099}"
JDK="${JDK:-$HOME/tools/jdk-21-arm64/Contents/Home}"

log() { printf '[jenkins] %s\n' "$*"; }

jenkins_pid() { pgrep -f "java .*${WAR}" | head -1; }

start_center() {
  if curl -fsS -o /dev/null "http://127.0.0.1:${CENTER_PORT}/main/index.json" 2>/dev/null; then
    log "center mirror is already served on ${CENTER_PORT}"
    return
  fi
  # the client appends centerRef (default "main") to the base URL, so the files must sit one level down
  mkdir -p "$CENTER_DIR"
  [ -e "$CENTER_DIR/main" ] || ln -sfn "$HOME/atom-center" "$CENTER_DIR/main"
  ( cd "$CENTER_DIR" && python3 "$HERE/detach.py" "$HOME/atom-center-server.log" \
      python3 -m http.server "$CENTER_PORT" --bind 127.0.0.1 >/dev/null )
  sleep 2
  curl -fsS -o /dev/null "http://127.0.0.1:${CENTER_PORT}/main/index.json" \
    && log "center mirror on ${CENTER_PORT}" || log "WARN: center mirror did not answer"
}

start_jenkins() {
  if [ -n "$(jenkins_pid)" ]; then
    log "already running (pid $(jenkins_pid))"
    return
  fi
  [ -f "$WAR" ] || { log "no war at $WAR"; exit 1; }
  # -D before -jar: after -jar it is a program argument and the setup wizard runs
  # a new session, not just nohup: otherwise sshd waits for the JVM and the call looks hung
  JENKINS_HOME="$JENKINS_HOME" python3 "$HERE/detach.py" "$JENKINS_HOME/jenkins.log" "$JDK/bin/java" \
      -Djenkins.install.runSetupWizard=false \
      -Dhudson.plugins.git.GitSCM.ALLOW_LOCAL_CHECKOUT=true \
      -jar "$WAR" --httpPort="$PORT" >/dev/null
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "http://localhost:${PORT}/api/json" 2>/dev/null; then
      log "up on http://localhost:${PORT} (pid $(jenkins_pid))"
      return
    fi
    sleep 2
  done
  log "did not come up in 120s; see $JENKINS_HOME/jenkins.log"
  exit 1
}

stop() {
  local pid; pid="$(jenkins_pid)"
  if [ -z "$pid" ]; then log "not running"; return; fi
  kill "$pid" && log "stopped $pid"
  for _ in $(seq 1 30); do [ -z "$(jenkins_pid)" ] && return; sleep 1; done
  log "WARN: still alive after 30s"
}

status() {
  if [ -z "$(jenkins_pid)" ]; then log "down"; return; fi
  log "pid $(jenkins_pid) on :${PORT}"
  python3 - "$PORT" <<'PY'
import json, sys, urllib.request
port = sys.argv[1]
with urllib.request.urlopen("http://localhost:%s/api/json?tree=jobs[name,lastBuild[number,result]]" % port) as response:
    data = json.load(response)
for job in data["jobs"]:
    build = job.get("lastBuild") or {}
    print("  %-30s #%-3s %s" % (job["name"], build.get("number"), build.get("result")))
PY
}

case "${1:-start}" in
  start)  start_center; start_jenkins ;;
  stop)   stop ;;
  status) status ;;
  restart) stop; sleep 5; start_center; start_jenkins ;;
  *) echo "usage: $0 [start|stop|restart|status]" >&2; exit 2 ;;
esac
