#!/usr/bin/env bash
# Run the demo stacks on the build machine — the local Mac only edits code.
#
#   ./tools/remote-demos.sh              # all stacks
#   ./tools/remote-demos.sh node-tap     # one stack
#
# It syncs the atom repositories and the demo tree, builds the atoms that changed, then runs tools/run-demo.sh there.
set -uo pipefail
HOST="${BUILD_HOST:-10.161.8.219}"
KEY="${BUILD_KEY:-$HOME/.ssh/id_buildmac}"
DEMOS="$(cd "$(dirname "$0")/.." && pwd)"
ATOMS="${ATOM_HOME:-$HOME/Codes}"
stack="${1:-all}"

ssh_run() { ssh -i "$KEY" -o BatchMode=yes "ming@$HOST" "$@"; }

echo "[sync] atom sources -> ~/build/atoms-src"
ssh_run "mkdir -p ~/build/atoms-src ~/build/demos" >/dev/null
for repo in "$ATOMS"/jenkins-atom-*; do
  [ -d "$repo" ] || continue
  name="$(basename "$repo")"
  rsync -a --delete --exclude '.git/' --exclude 'dist/' --exclude 'target/' -e "ssh -i $KEY" \
        "$repo/" "ming@$HOST:build/atoms-src/$name/" || echo "  ! $name"
done
echo "[sync] demo tree -> ~/build/demos"
rsync -a --delete --exclude '.git/' -e "ssh -i $KEY" "$DEMOS/" "ming@$HOST:build/demos/"

echo "[build] the atoms the demos need"
ssh_run 'set -e
export JAVA_HOME=$HOME/tools/jdk-21-arm64/Contents/Home
export PATH="$JAVA_HOME/bin:$HOME/tools/apache-maven-3.9.16/bin:$PATH"
cd ~/build/atoms-src
for atom in junit-report node python-env cmake-build maven artifact-size zip-artifacts files-tool; do
  ( cd jenkins-atom-$atom && ./build.sh >/dev/null 2>&1 && echo "  built $atom" ) || echo "  FAILED $atom"
done'

echo "[run] $stack"
ssh_run "export JAVA_HOME=\$HOME/tools/jdk-21-arm64/Contents/Home
export PATH=\"\$HOME/tools/node-v22/bin:\$HOME/Library/Python/3.9/bin:\$JAVA_HOME/bin:\$PATH\"
export ATOM_HOME=\$HOME/build/atoms-src
cd ~/build/demos && ./tools/run-demo.sh $stack"
