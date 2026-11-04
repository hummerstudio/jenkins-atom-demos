#!/usr/bin/env python3
"""Write one Jenkinsfile per ported atom under atoms/<code>/, plus the negative-test pipelines.

The Jenkinsfiles and the fixtures they use are **committed** — this script only writes them once (and again when an
atom's task.json changes). Nothing is generated at build time: a pipeline you cannot read in the repository is a
pipeline you cannot review.

    python3 tools/scaffold-atoms.py            # writes atoms/*/Jenkinsfile
    python3 tools/scaffold-atoms.py --check    # fails if the tree is out of date
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

DEMOS = Path(__file__).resolve().parent.parent
SOURCES = Path(os.environ.get("ATOM_SOURCES", Path.home() / "Codes"))
SKIP = {"jenkins-atom-demo", "jenkins-atom-demos", "jenkins-atom-center", "jenkins-atom-site",
        "jenkins-atom-plugin", "jenkins-atom-sdk"}

# Atoms whose work needs a service or a credential this machine does not have. Their failure is recorded and the
# pipeline stays green — that is exactly what continueOnError is for. Keep this list explicit: a green pipeline must
# mean "we decided this failure is acceptable", never "the failure was swallowed".
SERVICE = {
    "aws-cloudformation", "aws-codedeploy", "aws-codepipeline", "aws-lambda-invoke", "azure-blob",
    "azure-keyvault", "jira", "jira-build-info", "jira-issue", "github", "github-checks", "gitlab", "gitea",
    "gitee", "bitbucket-status", "bitbucket-cloud-status", "slack-upload", "telegram-notify", "chat-notify",
    "notify-webhook", "rocketchat", "datadog-metrics", "influxdb", "splunk-hec", "splunk-devops", "sonar",
    "sonar-gate", "qtest", "xray-import", "browserstack", "newrelic-deployment", "vault-read", "s3-upload",
    "gcs", "gcs-upload", "sbom-gate", "artifact-publish", "artifact-promote", "artifact-copy",
    "artifact-deployer", "ftp-publish", "ssh-publish", "ssh-exec", "mail", "mail-ext", "ecr-push",
    "k8s-deploy", "docker-build", "build-token-trigger", "bind-credentials", "pyenv", "ansible-run",
    "maven-resolve",
}

NOT_INFORMATIVE = {"timeoutSeconds", "label", "outputDir", "failOnError", "dryRun", "verbose"}


def atoms() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for repo in sorted(glob.glob(str(SOURCES / "jenkins-atom-*"))):
        task_file = Path(repo) / "task.json"
        if Path(repo).name in SKIP or not task_file.is_file():
            continue
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        code = task.get("atomCode")
        if code:
            found[code] = task
    return found


def groovy(value: object) -> str:
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def inputs_of(task: dict) -> dict[str, str]:
    """Required inputs, then the first few defaults that say what the atom is for."""
    params: dict[str, str] = {}
    for name, spec in (task.get("input") or {}).items():
        if isinstance(spec, dict) and spec.get("required"):
            default = spec.get("default")
            params[name] = default if default not in (None, "") else f"<填:{spec.get('label') or name}>"
    added = 0
    for name, spec in (task.get("input") or {}).items():
        if not isinstance(spec, dict) or spec.get("required") or added >= 3:
            continue
        default = spec.get("default")
        if default in (None, "") or str(default) in ("true", "false"):
            continue
        if str(default).replace(".", "", 1).isdigit() or name in NOT_INFORMATIVE:
            continue
        params.setdefault(name, str(default))
        added += 1
    return params


def jenkinsfile(code: str, task: dict) -> str:
    params = inputs_of(task)
    call = f"runAtom(atom: {groovy(code)}, version: {groovy(task.get('version') or '')}"
    if params:
        call += ", inputs: [\n            " + ",\n            ".join(f"{k}: {groovy(v)}" for k, v in params.items()) + "\n          ]"
    if code in SERVICE:
        call += ",\n          continueOnError: true"
    call += ")"
    note = ("// 这个原子要外部服务/凭据：失败会被记录，流水线保持成功（continueOnError）。"
            if code in SERVICE else "// 原子失败即构建失败。")
    return f"""// {code} @ {task.get('version')} — 生成的测试流水线，fixtures 在 atoms/_shared/fixtures
{note}
pipeline {{
  agent any
  options {{ timeout(time: 5, unit: 'MINUTES') }}

  stages {{
    stage('fixtures') {{
      steps {{
        sh 'cp -R atoms/_shared/fixtures/. .'
        sh 'if [ -d atoms/{code}/fixtures ]; then cp -R atoms/{code}/fixtures/. .; fi'
      }}
    }}

    stage('{code}') {{
      steps {{
        {call}
      }}
    }}
  }}
}}
"""


NEGATIVE = {
    "fail": ("""// 失败必须让构建失败：没有 continueOnError 时，原子失败 = 流水线失败。
pipeline {
  agent any
  stages {
    stage('a failing atom') {
      steps {
        runAtom(atom: 'script', version: '1.1.1', inputs: [interpreter: 'sh', script: 'exit 3'])
      }
    }
  }
}
""", "expect: FAILURE"),
    "continue": ("""// continueOnError：同一个失败，流水线保持成功，失败仍然被记录。
pipeline {
  agent any
  stages {
    stage('a failing atom, continued') {
      steps {
        runAtom(atom: 'script', version: '1.1.1', inputs: [interpreter: 'sh', script: 'exit 3'],
                continueOnError: true)
      }
    }
    stage('after') {
      steps { echo 'the pipeline kept going' }
    }
  }
}
""", "expect: SUCCESS"),
    "unstable": ("""// markUnstable：失败继续，但构建标黄。
pipeline {
  agent any
  stages {
    stage('a failing atom, marked') {
      steps {
        runAtom(atom: 'script', version: '1.1.1', inputs: [interpreter: 'sh', script: 'exit 3'],
                continueOnError: true, markUnstable: true)
      }
    }
  }
}
""", "expect: UNSTABLE"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    written, stale = [], []
    for code, task in sorted(atoms().items()):
        path = DEMOS / "atoms" / code / "Jenkinsfile"
        content = jenkinsfile(code, task)
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        if args.check:
            stale.append(str(path.relative_to(DEMOS)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(path.relative_to(DEMOS)))

    for name, (content, _expect) in NEGATIVE.items():
        path = DEMOS / "atoms" / "_negative" / name / "Jenkinsfile"
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        if args.check:
            stale.append(str(path.relative_to(DEMOS)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(path.relative_to(DEMOS)))

    if args.check:
        if stale:
            print("out of date:\n  " + "\n  ".join(stale), file=sys.stderr)
            return 1
        print("atoms/*/Jenkinsfile are up to date")
        return 0

    print(f"wrote {len(written)} files")
    for one in written:
        print("  " + one)
    return 0


if __name__ == "__main__":
    sys.exit(main())
