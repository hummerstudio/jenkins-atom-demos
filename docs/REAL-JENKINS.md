# 真 Jenkins：四条栈，先混合、再全原子

构建机 `10.161.8.219` 上跑着一台真实例：`http://localhost:8088`，Jenkins 2.580.1 + 57 个插件 + `jenkins-atom-runner`，
无鉴权（一次性验证机），`autoInstall=true`。

## 结果

| 流水线 | 形态 | 步骤 | 结果 |
|---|---|---|---|
| `demo-java-maven` | 混合 | `checkout scm` → `sh mvn` → runAtom `junit-report` → runAtom `artifact-size` | **#8 SUCCESS** |
| `demo-node-tap` | 混合 | `checkout scm` → `sh npm test` → runAtom `junit-report` → `sh npm run build` → runAtom `zip-artifacts` | **#1 SUCCESS** |
| `demo-python-pytest` | 混合 | `checkout scm` → `sh venv+pytest` → runAtom `junit-report` → runAtom `files-tool` | **#1 SUCCESS** |
| `demo-cpp-cmake` | 混合 | `checkout scm` → `sh cmake/ctest` → runAtom `junit-report` | **#2 SUCCESS** |
| `demo-java-maven-atoms` | 全原子 | runAtom `ws-cleanup` → `git-checkout` → `maven` → `junit-report` → `artifact-size` | **#5 SUCCESS**（3 tests） |
| `demo-node-tap-atoms` | 全原子 | `ws-cleanup` → `git-checkout` → `node`(npm test) → `junit-report` → `node`(build) → `zip-artifacts` | **#4 SUCCESS**（3 tests） |
| `demo-python-pytest-atoms` | 全原子 | `ws-cleanup` → `git-checkout` → `python-env`×2 → `junit-report` → `files-tool` | **#4 SUCCESS**（3 tests） |
| `demo-cpp-cmake-atoms` | 全原子 | `ws-cleanup` → `git-checkout` → `cmake-build`(含 ctest) → `junit-report` | **#4 SUCCESS**（1 test） |

原子全部由 `autoInstall` 从中心自动装上的，控制台能看到：

```
[Atom Runner] auto-install junit-report (it was not installed; the center offers 1.0.0, 1.0.1, 1.1.0, 1.2.0, auto install is on)
[Atom Runner] install junit-report:1.2.0
[Atom Runner] agent cache miss hummerstudio/junit-report:1.2.0 (not on this agent yet); unpacking
[Atom Runner] run $atom_java_path -cp junit-report.jar com.jenkinschina.atom.sdk.AtomRunner
```

## 装一台能用的 Jenkins（网络受限时）

官方 update center 在这里只有 ~45 KB/s，而各镜像站都**不再提供 `update-center.json`**（tuna/aliyun/ustc/huawei 全部 404）。
做法是：用官方 `update-center.json` 本地解析依赖闭包，把每个 hpi 的下载地址换成 TUNA 镜像（~200 KB/s）直接落
`$JENKINS_HOME/plugins/*.jpi` —— 等价于在 UI 里装。

- war：`https://mirrors.tuna.tsinghua.edu.cn/jenkins/war-stable/2.580.1/jenkins.war`（54 MB，校验 sha256）
- 插件：`tools/install_plugins.py`（依赖闭包 + 并发下载 + 缓存）
- 需要 `pipeline-model-definition`，否则 declarative 的 `pipeline` 步骤不存在

启动：

```bash
JENKINS_HOME=~/jenkins-real \
  java -Djenkins.install.runSetupWizard=false \
       -Dhudson.plugins.git.GitSCM.ALLOW_LOCAL_CHECKOUT=true \
       -jar /tmp/jenkins.war --httpPort=8088
```

`-D` 必须写在 `-jar` **前面**，写在后面会被当成程序参数忽略（我第一次踩了这个，结果跑了初始化向导）。

## 这台机器的三个网络限制，以及怎么绕

1. **github.com 完全不通**（curl 8 秒超时），而且 git 里有一条把 github 改写到 `gh-proxy.com` 的配置，checkout 卡 225 秒才失败。
   → 用**本地裸仓库** `file:///Users/ming/repos/jenkins-atom-demos.git`，本地 `git push` 过去。需要 `ALLOW_LOCAL_CHECKOUT=true`。
2. **raw.githubusercontent.com 不通**，官方中心拉不下来。
   → 中心镜像到 `~/atom-center`，用 `python3 -m http.server 8099` 在 loopback 上服务，`centerUrl=http://127.0.0.1:8099`。
3. **中心客户端会在 URL 后面拼 `centerRef`**（默认 `main`），所以静态目录必须是 `~/atom-center-http/main -> ~/atom-center`，
   否则它请求 `/main/index.json` 得到 404，缓存目录空着，报 `channel 'stable' requested but no index.json`。

## 真环境才暴露的四个 bug（都已修）

1. `runAtom` 的 `version` 是**必填**（构造参数，刻意如此）：它决定这一跑的是哪个版本，省略就等于"跑 stable 此刻指向的东西"，
   构建不可复现。declarative 会在编译期报 `Missing required parameter: "version"`；运行时拿到空的也直接 AbortException，
   提示写 `version: '1.2.0'` 或显式 `version: 'stable'`。demo 的八条流水线因此都钉了具体版本。
2. `AtomCenter.findVersion` 对 null version 调 `version.equals(...)` → NPE。
3. `resolve(null)` 一路落到目录查找，最后炸在 `FilePath.child(null)`：`Cannot invoke "String.startsWith(String)" because "rel" is null`。
   → null/blank 归一成 `stable`，`atomDirectory` 改成明确的 `IllegalStateException`。
4. ctest 的 `--output-junit reports/ctest.xml` 落在 **build 目录**里，混合流水线读 `reports/ctest.xml` 读不到。

## 全原子阶段新写的原子

`jenkins-atom-git-checkout`（1.0.0）：不依赖任务里配置 SCM，自己接受 url/branch/commit。

两个实现要点来自真环境：
- **不能用 `git clone`**：Jenkins 的 workspace 永远不空（`input.json`、日志），clone 直接拒绝非空目录。
  改成 `git init` + `remote add/set-url` + `fetch` + `checkout -f`。
- **本地分支不跟踪任何东西**，第二次构建 `git checkout -f main` 不会移动 HEAD。改成 `checkout -f -B <branch> origin/<branch>`。

## 两个"看起来是原子 bug、其实是流水线 bug"

- **6 个测试而不是 3 个**：全原子流水线一开始把 `git-checkout` 放在 `dir('stacks/node-tap')` 里，等于把仓库克隆进它自己的一份拷贝，
  `node --test` 自动发现扫到两份测试。→ checkout 放在 workspace 根，构建步骤再 `dir()`。
- **workspace 在两次构建之间不会自己变干净**，上一轮的嵌套拷贝留在那里，第二次构建照样报 6 个测试。
  → 流水线第一步用 `ws-cleanup` 原子（`patterns: '**'`，它拒绝空 pattern 列表）。

## 复现这套环境

```bash
tools/install_plugins.py ~/jenkins-real pipeline-model-definition workflow-* git credentials
# 中心镜像 + 静态服务
rsync -a --delete /path/to/jenkins-atom-center/ ming@10.161.8.219:atom-center/
ln -sfn ~/atom-center ~/atom-center-http/main && (cd ~/atom-center-http && python3 -m http.server 8099 --bind 127.0.0.1 &)
# 仓库镜像
git init --bare ~/repos/jenkins-atom-demos.git && git push ssh://ming@10.161.8.219/Users/ming/repos/jenkins-atom-demos.git main
```

`~/jenkins-real/init.groovy.d/` 里四个脚本：开 autoInstall 并指向 loopback 中心、2 个 executor、关鉴权、给内置节点补 PATH（maven/node/pip/cmake）。

## 一键启停（`tools/jenkins-rehearsal/`）

```bash
tools/jenkins-rehearsal/start.sh            # (重)启动：先把中心镜像挂到 :8099，再拉起 Jenkins
tools/jenkins-rehearsal/start.sh status     # 在跑吗、八个 job 最后一次结果
tools/jenkins-rehearsal/start.sh restart
tools/jenkins-rehearsal/start.sh stop
```

`init.groovy.d/` 四个脚本随仓库走（autoInstall + loopback 中心、2 executor、关鉴权、给内置节点补 PATH），
配置随实例走，重启不掉。

一个不起眼但会浪费半天的点：**`nohup … &` 不足以脱离 ssh**。子进程仍留在 ssh 会话里，sshd 会一直等着它，
`ssh host ./start.sh restart` 看起来像卡死（其实服务早起来了）。`start.sh` 通过 `detach.py` 用
`start_new_session=True` 起新会话，重启从「卡 7 分钟」变成 8 秒返回。
