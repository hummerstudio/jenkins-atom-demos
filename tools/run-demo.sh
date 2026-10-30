#!/usr/bin/env bash
# Run one demo stack the way the Jenkinsfile runs it — same atoms, same order, in a throwaway workspace.
#
#   ./tools/run-demo.sh java-maven
#   ./tools/run-demo.sh all
#
# The atoms are the built packages from the sibling repositories (dist/<atom>/<atom>.jar); this is the same contract the
# runner uses, so a step that cannot do its job fails here first.
set -uo pipefail

DEMOS="$(cd "$(dirname "$0")/.." && pwd)"
ATOMS="${ATOM_HOME:-$HOME/Codes}"
WORK="${DEMO_WORK:-$(mktemp -d)}"
export JAVA_HOME="${JAVA_HOME:-$HOME/tools/jdk-21.0.12.1+1/Contents/Home}"
JAVA="$JAVA_HOME/bin/java"

fail() { echo "  ✗ $*" >&2; exit 1; }
ok() { echo "  ✓ $*"; }

atom_jar() { # atom_jar <code>
  local jar="$ATOMS/jenkins-atom-$1/dist/$1/$1.jar"
  [ -f "$jar" ] || fail "atom package missing: $jar (build it: (cd $ATOMS/jenkins-atom-$1 && ./build.sh))"
  echo "$jar"
}

# run_atom <code> <workspace> <json inputs> [ENV=value ...]
run_atom() {
  local code="$1" dir="$2" inputs="$3"; shift 3
  local jar; jar="$(atom_jar "$code")"
  printf '%s' "$inputs" >"$dir/input.json"
  python3 - "$dir" "$@" <<'PY'
import json, os, sys
directory, extra = sys.argv[1], sys.argv[2:]
path = os.path.join(directory, "input.json")
given = json.load(open(path)) if os.path.getsize(path) else {}
data = {k: v for k, v in os.environ.items() if k.isupper()}
data.update(given)
for pair in extra:
    key, _, value = pair.partition("=")
    data[key] = value
data.setdefault("atom_workspace", directory)
json.dump(data, open(path, "w"))
PY
  ( cd "$dir" && env atom_data_dir="$dir" atom_data_input=input.json atom_data_output=output.json \
      atom_workspace="$dir" "$JAVA" -cp "$jar" com.jenkinschina.atom.sdk.AtomRunner ) >"$dir/atom-$code.log" 2>&1
  local status; status="$(python3 -c "import json,sys;print(json.load(open('$dir/output.json')).get('status',''))" 2>/dev/null)"
  if [ "$status" != "success" ]; then
    echo "  ✗ atom $code failed:" >&2
    tail -5 "$dir/atom-$code.log" >&2
    python3 -c "import json;d=json.load(open('$dir/output.json'));print('    message:', d.get('message'))" 2>/dev/null >&2
    exit 1
  fi
  ok "atom $code: $(python3 -c "
import json
d=json.load(open('$dir/output.json'))['data']
print(', '.join(f'{k}={v.get(\"value\")}' for k, v in list(d.items())[:4] if v.get('type')=='string'))")"
}

stack_java() {
  local dir="$WORK/java-maven"; mkdir -p "$dir"
  cp -R "$DEMOS/stacks/java-maven/." "$dir/"
  run_atom maven "$dir" '{"goals": "clean verify", "home": "'"$HOME"'/tools/apache-maven-3.9.16", "options": "-B -ntp"}'
  run_atom junit-report "$dir" '{"testResults": "**/surefire-reports/TEST-*.xml"}'
  run_atom artifact-size "$dir" '{"pattern": "**/target/*.jar", "maxMb": "50"}'
}

stack_node() {
  local dir="$WORK/node-tap"; mkdir -p "$dir"
  cp -R "$DEMOS/stacks/node-tap/." "$dir/"
  run_atom node "$dir" '{"command": "npm test"}'
  run_atom junit-report "$dir" '{"testResults": "reports/junit.xml"}'
  run_atom node "$dir" '{"command": "npm run build"}'
  run_atom zip-artifacts "$dir" '{"operation": "zip", "archive": "out/dist.zip", "includes": "dist/**"}'
}

stack_python() {
  local dir="$WORK/python-pytest"; mkdir -p "$dir"
  cp -R "$DEMOS/stacks/python-pytest/." "$dir/"
  run_atom python-env "$dir" '{"requirements": "requirements.txt"}'
  run_atom python-env "$dir" '{"command": "python -m pytest"}'
  run_atom junit-report "$dir" '{"testResults": "reports/junit.xml"}'
  run_atom files-tool "$dir" '{"operation": "find", "pattern": "src/**/*.py"}'
}

stack_cpp() {
  local dir="$WORK/cpp-cmake"; mkdir -p "$dir"
  cp -R "$DEMOS/stacks/cpp-cmake/." "$dir/"
  run_atom cmake-build "$dir" '{"buildType": "Debug", "runTests": "true", "testArgs": "--output-junit reports/ctest.xml"}'
  run_atom junit-report "$dir" '{"testResults": "build/reports/ctest.xml"}'
}

run_stack() { # run_stack <name>
  echo "== $1"
  case "$1" in
    java-maven) stack_java ;;
    node-tap) stack_node ;;
    python-pytest) stack_python ;;
    cpp-cmake) stack_cpp ;;
    *) fail "unknown stack $1" ;;
  esac
}

target="${1:-all}"
echo "workspace: $WORK"
if [ "$target" = "all" ]; then
  failed=0
  for stack in java-maven node-tap python-pytest cpp-cmake; do
    run_stack "$stack" || failed=1
  done
  [ "$failed" -eq 0 ] || { echo "some stacks failed" >&2; exit 1; }
  echo "all stacks passed"
else
  run_stack "$target"
fi
