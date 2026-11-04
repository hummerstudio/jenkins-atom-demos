# jenkins-atom-demos

Four real projects, one per tech stack, each driven by atom steps. The point is not the demo code — it is that
`tools/run-demo.sh <stack>` runs the **same sequence as the Jenkinsfile** through the atoms themselves, so a gap shows up
as a failed step rather than as a surprise in production.

| stack | toolchain | atoms used |
|---|---|---|
| `java-maven` | JDK 21 + Maven | `maven`, `junit-report`, `artifact-size` |
| `node-tap` | Node 20+ (`node --test`) | `node`, `junit-report`, `zip-artifacts` |
| `python-pytest` | Python 3 + pytest | `python-env`, `junit-report`, `files-tool` |
| `cpp-cmake` | CMake + CTest | `cmake-build`, `junit-report` |


## 每个原子的测试流水线（`atoms/`）

`atoms/<atomCode>/Jenkinsfile` 是**入库**的流水线，一原子一条，Jenkins 作业直接指向它
（`file://…/jenkins-atom-demos` + scriptPath），不在作业里拼脚本：

```
atoms/
  _shared/fixtures/     所有原子共用的最小 fixture（测试报告、构建文件、样本日志…）
  <atomCode>/Jenkinsfile 该原子的测试流水线（fixtures → runAtom）
  <atomCode>/fixtures/   该原子额外需要的文件（可选）
  _negative/           失败场景本身也是测试：fail / continue / unstable 三条
```

`tools/scaffold-atoms.py` 只在 task.json 变化时重写这些文件（`--check` 用于 CI 判断是否过期）。
流水线里的 fixture 是**仓库里的文件**，不是运行时生成的脚本。

需要外部服务/凭据的原子（AWS、Jira、Slack…）用 `continueOnError: true`：失败被记录、流水线保持成功——
这份名单写死在 `tools/scaffold-atoms.py` 的 `SERVICE` 里，必须是显式决定，不能靠吞掉失败来变绿。

```bash
./tools/run-demo.sh java-maven      # one stack, in a throwaway workspace
./tools/e2e.sh                      # all of them
```

Each `Jenkinsfile` is the pipeline the same steps run in, for a real Jenkins.
