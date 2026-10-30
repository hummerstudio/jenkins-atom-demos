#!/usr/bin/env python3
"""Install the plugins a real Jenkins needs, resolving dependencies from update-center.json.

Jenkins' own update site is slow from here (~45 KB/s), while the TUNA mirror serves the same
hpi files at ~200 KB/s. So: resolve the closure locally, download each hpi from the mirror,
and drop them into $JENKINS_HOME/plugins — which is exactly what installing from the UI does.

    python3 install_plugins.py <jenkins-home> root1 root2 ...
"""
import json
import os
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UPDATE_CENTER = "/tmp/update-center.json"
MIRROR = "https://mirrors.tuna.tsinghua.edu.cn/jenkins/plugins/{name}/{version}/{name}.hpi"


def load_plugins():
    with open(UPDATE_CENTER, encoding="utf-8") as handle:
        text = handle.read()
    # the file starts with `updateCenter.post(` and ends with `);`
    if text.lstrip().startswith("updateCenter.post("):
        text = text.lstrip()[len("updateCenter.post("):]
        text = text.rstrip().rstrip(";").rstrip()
        if text.endswith(")"):
            text = text[:-1]
    return json.loads(text)["plugins"]


def closure(plugins, roots):
    seen = {}
    queue = list(roots)
    while queue:
        name = queue.pop()
        if name in seen or name not in plugins:
            continue
        entry = plugins[name]
        seen[name] = entry
        for dep in entry.get("dependencies", []):
            if dep.get("optional"):
                continue
            queue.append(dep["name"])
    return seen


def fetch(args):
    name, version, target_dir = args
    path = os.path.join(target_dir, name + ".jpi")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return name, "cached"
    url = MIRROR.format(name=name, version=version)
    try:
        with urllib.request.urlopen(url, timeout=90) as response, open(path, "wb") as handle:
            handle.write(response.read())
        return name, f"{os.path.getsize(path) // 1024}K"
    except Exception as error:  # a mirror miss should not stop the rest
        if os.path.exists(path):
            os.remove(path)
        return name, f"FAILED {error}"


def main():
    home = sys.argv[1]
    roots = sys.argv[2:]
    plugins = load_plugins()
    wanted = closure(plugins, roots)
    target = os.path.join(home, "plugins")
    os.makedirs(target, exist_ok=True)
    print(f"{len(wanted)} plugins to install into {target}")
    jobs = [(name, entry["version"], target) for name, entry in sorted(wanted.items())]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, status in pool.map(fetch, jobs):
            print(f"  {name:32s} {status}")
    failed = [name for name, entry in wanted.items()
              if not os.path.exists(os.path.join(target, name + ".jpi"))]
    if failed:
        print("missing:", ", ".join(sorted(failed)))
        sys.exit(1)


if __name__ == "__main__":
    main()
