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
# Fixture *content* lives here only as the generator's source: every Jenkinsfile carries the files it needs inline,
# so a pipeline read on its own is the whole story and nothing is copied around at build time.
FIXTURES = DEMOS / "tools" / "fixtures"
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

# Per-atom test inputs and setup. Everything here is data: the Jenkinsfile that uses it is committed next to it.
OVERRIDES: dict[str, dict] = {
    "build-time-blame": {"inputs": {
        "logFile": "build-time.log",
        "timestampFormat": "elapsedMillis",
        "steps": '[{"key": "compile", "label": "编译"}, {"key": "test", "label": "测试"},'
                 ' {"key": "package", "label": "打包"}]',
    }},
    "cucumber": {"inputs": {"pattern": "**/cucumber.json"}},
    "dependency-check": {"inputs": {"pattern": "**/dependency-check-report.xml"}},
    "file-ops": {"inputs": {"operation": "copy", "pattern": "dist/*.jar", "target": "out/copied"}},
    "gatling-report": {"inputs": {"pattern": "**/simulation.log"}},
    "git-checkout": {"inputs": {"url": "file:///Users/tangming/Codes/jenkins-atom-demos", "branch": "main"}},
    "git": {"prelude": [
        "git checkout -B main",
        'git init -q --bare "$WORKSPACE/../push-target.git"',
        'git remote set-url origin "$WORKSPACE/../push-target.git"',
        "git config user.email atom@example.com",
        "git config user.name atom",
    ]},
    "http-request": {"inputs": {"url": "http://127.0.0.1:8098/api/json", "expectStatus": "2xx"}},
    "git-push": {"prelude": [
        "git checkout -B main",
        'git init -q --bare "$WORKSPACE/../push-target.git"',
        'git remote set-url origin "$WORKSPACE/../push-target.git"',
        "git config user.email atom@example.com",
        "git config user.name atom",
    ]},
    "git-changelog": {"prelude": ["git checkout -B main"]},
    "html": {"inputs": {"path": "out/coverage"}},
    "log-parser": {"inputs": {"source": "clean.log", "rules": "{\"note\": \"WARN\"}"}},
    "robot": {"inputs": {"pattern": "**/output.xml"}},
    "script": {"inputs": {"interpreter": "sh", "script": "echo hello from the script atom"}},
    "sonargraph": {"inputs": {"reportPath": "target/sonargraph/sonargraph-report.xml"}},
    "text-file": {"inputs": {"option": "overwrite", "path": "notes.txt", "content": "hello"}},
    "text-finder": {"inputs": {"regexp": "NEVER_MATCHES_ANYWHERE", "useBuildLog": "false",
                               "fileSet": "build.log"}},
}

# Needs a service that is not on this machine at all: the failure is expected and is recorded, not fatal.
SERVICE |= {"deploy-war", "mail-ext", "python-build"}


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


# A few atoms read a project the fixture set has to provide first; the rest declare their file in task.json and are
# picked up by needs() below. Both lists stay explicit so a missing fixture is a review comment, not a mystery.
EXTRA_NEEDS: dict[str, list[str]] = {
    # build tools: the project file each one needs to have something to do
    "maven": ["pom.xml"],
    "maven-resolve": ["pom.xml"],
    "ant": ["build.xml"],
    "gradle": ["settings.gradle", "build.gradle"],
    "sbt": ["build.sbt", "project/build.properties"],
    "cmake-build": ["CMakeLists.txt", "hello.c"],
    "jmeter": ["results.jtl"],
    # report readers: the file each one parses
    "checkstyle": ["target/checkstyle-result.xml"],
    "coverage": ["coverage.xml", "lcov.info", "target/site/jacoco/jacoco.xml"],
    "violations": ["target/checkstyle-result.xml"],
    "warnings": ["build.log"],
    "html": ["out/coverage/index.html"],
    "cucumber": ["cucumber.json"],
    "testng": ["testng-results.xml"],
    "junit": ["target/surefire-reports/TEST-demo.SampleTest.xml"],
    "xunit": ["TestResults/demo.trx"],
    "tap": ["results/demo.tap"],
    "allure": ["allure-results/demo-result.json"],
    "dependency-check": ["dependency-check-report.xml"],
    "gatling-report": ["simulation.log"],
    "robot": ["output.xml"],
    "sonargraph": ["target/sonargraph/sonargraph-report.xml"],
    "selenium-html-report": ["target/index.html"],
    # everything else that reads a file
    "build-time-blame": ["build-time.log"],
    "log-parser": ["clean.log"],
    "text-finder": ["build.log"],
    "file-ops": ["dist/demo.jar"],
    "env-injector": [".env"],
    "json-tool": ["package.json"],
    "plot": ["data.csv"],
}


def needs(code: str, task: dict) -> list[str]:
    """The fixture files this atom reads, from the table above — the only place that says so."""
    return sorted(EXTRA_NEEDS.get(code, []))


def groovy_block(path: str, text: str) -> str:
    """One writeFile with the file's text inline, escaped so Groovy keeps it byte for byte."""
    body = text.replace("\\", "\\\\")
    if "'''" in body:
        body = body.replace('"""', '\\"\\"\\"')
        quote = '"""'
    else:
        quote = "'''"
    return f"        writeFile file: {groovy(path)}, text: {quote}{body}{quote}"


def groovy(value: object) -> str:
    text = (str(value).replace("\\", "\\\\").replace("'", "\\'")
            .replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t"))
    return "'" + text + "'"


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
    params.update(OVERRIDES.get(code, {}).get("inputs", {}))
    prelude = OVERRIDES.get(code, {}).get("prelude", [])
    # 1.latest, not 1.2.0: the demo should run the newest fix of the major the atom is on, so a republished atom is
    # picked up without editing 100 Jenkinsfiles. The resolver treats it exactly like 1.*.
    version = task.get("version") or ""
    major = version.split(".")[0] if version else ""
    pinned = f"{major}.latest" if major.isdigit() else version
    call = f"runAtom(atom: {groovy(code)}, version: {groovy(pinned)}"
    if params:
        call += ", inputs: [\n            " + ",\n            ".join(f"{k}: {groovy(v)}" for k, v in params.items()) + "\n          ]"
    if code in SERVICE:
        call += ",\n          continueOnError: true"
    call += ")"
    note = ("// 这个原子要外部服务/凭据：失败会被记录，流水线保持成功（continueOnError）。"
            if code in SERVICE else "// 原子失败即构建失败。")
    setup: list[str] = [groovy_block(name, (FIXTURES / name).read_text(encoding="utf-8"))
                        for name in needs(code, task)]
    setup += [f"        sh {groovy(line)}" for line in prelude]
    prepare = ""
    if setup:
        prepare = "    stage('准备') {\n      steps {\n" + "\n".join(setup) + "\n      }\n    }\n\n"
    return f"""// {code} @ {version} — 原子测试流水线；它需要的输入文件都写在这里
{note}
pipeline {{
  agent any
  options {{ timeout(time: 5, unit: 'MINUTES') }}

  stages {{
{prepare}    stage('{code}') {{
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
