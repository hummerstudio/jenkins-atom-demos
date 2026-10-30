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

```bash
./tools/run-demo.sh java-maven      # one stack, in a throwaway workspace
./tools/e2e.sh                      # all of them
```

Each `Jenkinsfile` is the pipeline the same steps run in, for a real Jenkins.
