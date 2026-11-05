#!/usr/bin/env python3
"""Create and run the per-stack pipelines on this Jenkins, then write the results next to the script.

Runs on the Jenkins host on purpose: loopback HTTP does not have the flakiness the LAN does from the workstation.
"""

import html
import http.cookiejar
import json
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8098"
REPO = "https://github.com/hummerstudio/jenkins-atom-demos.git"
STACKS = ("java-maven", "cpp-cmake", "node-tap", "python-pytest")
VARIANTS = (("atoms", "Jenkinsfile"), ("mixed", "Jenkinsfile.mixed"))

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
crumb = json.load(opener.open(BASE + "/crumbIssuer/api/json", timeout=60))
XML = {crumb["crumbRequestField"]: crumb["crumb"], "Content-Type": "application/xml"}
POST = {crumb["crumbRequestField"]: crumb["crumb"]}


def config(path: str) -> str:
    return f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>{html.escape(path)}</description>
  <keepDependencies>false</keepDependencies>
  <properties/>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs><hudson.plugins.git.UserRemoteConfig><url>{REPO}</url></hudson.plugins.git.UserRemoteConfig></userRemoteConfigs>
      <branches><hudson.plugins.git.BranchSpec><name>*/main</name></hudson.plugins.git.BranchSpec></branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <extensions/>
    </scm>
    <scriptPath>{path}</scriptPath>
    <lightweight>true</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>
"""


def main() -> int:
    jobs: list[str] = []
    for stack in STACKS:
        for suffix, file_name in VARIANTS:
            job = f"demo-{stack}-{suffix}"
            try:
                try:
                    opener.open(urllib.request.Request(f"{BASE}/job/{job}/doDelete", data=b"", headers=XML), timeout=60)
                except Exception:
                    pass
                opener.open(urllib.request.Request(f"{BASE}/createItem?name={job}",
                                                   data=config(f"stacks/{stack}/{file_name}").encode(),
                                                   headers=XML), timeout=60)
                jobs.append(job)
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                print("create failed", job, exc, flush=True)
    print("jobs:", jobs, flush=True)

    for job in jobs:
        try:
            opener.open(urllib.request.Request(f"{BASE}/job/{job}/build?delay=0", data=b"", headers=POST), timeout=60)
        except Exception as exc:  # noqa: BLE001
            print("trigger failed", job, exc, flush=True)

    pending, done = set(jobs), {}
    deadline = time.time() + 45 * 60
    while pending and time.time() < deadline:
        time.sleep(8)
        for job in list(pending):
            try:
                data = json.load(opener.open(f"{BASE}/job/{job}/lastBuild/api/json?tree=number,result,building",
                                             timeout=60))
            except Exception:
                continue
            if data.get("building") or not data.get("number"):
                continue
            done[job] = {"job": job, "number": data["number"], "result": data.get("result")}
            pending.discard(job)
        print("remaining", len(pending), flush=True)

    with open("/tmp/stack-runs.json", "w", encoding="utf-8") as handle:
        json.dump(sorted(done.values(), key=lambda row: row["job"]), handle, ensure_ascii=False, indent=1)
    for job in sorted(done):
        print(done[job]["result"], f"{BASE}/job/{job}/{done[job]['number']}/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
