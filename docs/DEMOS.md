# demo 流水线：四条技术栈，跑在构建机上

目标不是写四个示例，而是**用真实项目把原子逼到出问题**：每条栈都是一个能真正编译、能真正跑测试的工程，跑的顺序与 Jenkinsfile 完全一致。
跑一次就知道缺什么，而不是等生产环境告诉缺什么。

执行环境：构建机 `ming@10.161.8.219`（arm64，办公网），本地 Mac 只编辑代码。

```bash
./tools/run-demo.sh java-maven     # 在构建机上跑一条栈
./tools/remote-demos.sh all        # 同步源码 → 构建原子 → 在构建机上跑全部
```

## 结果（2026-10-30，全部通过）

| 栈 | 工具链 | 原子序列 | 结果 |
|---|---|---|---|
| `java-maven` | JDK 21 + Maven 3.9.16 | `maven` → `junit-report` → `artifact-size` | 3 tests，jar 1.8 KiB |
| `node-tap` | Node v22.20.0 | `node`(npm test) → `junit-report` → `node`(build) → `zip-artifacts` | 3 tests，zip 243 B |
| `python-pytest` | Python 3.9 + pytest 8.4.2 | `python-env`(venv+deps) → `python-env`(pytest) → `junit-report` → `files-tool` | 3 tests，glob 命中 1 个文件 |
| `cpp-cmake` | CMake/CTest 4.4.4 + clang | `cmake-build`(configure+build+ctest) → `junit-report` | 1 test |

`all stacks passed`，共 13 个原子步骤。

## 构建机上装了什么

- **node v22.20.0** → `~/tools/node-v22`。官方包必须校验 sha256 再解压：链路上第一次只下到 11 MB，`tar` 报 `Damaged tar archive`，但目录结构已建了一半，看起来像"装好了"。用 `curl -C -` 续传到 49,838,299 字节、校验 `cc04a76a…f949` 才通过。
- **CMake/CTest 4.4.4** → `pip install --user cmake`（`~/Library/Python/3.9/bin`）。GitHub 的 `CMake.app` 包约 90 MB，在办公网下到 16 MB 就停滞；PyPI 的 wheel 几十秒装完，`ctest` 同目录。
- JDK 21 arm64、Maven 3.9.16 本来就在 `~/tools`。

## demo 抓出的五个真缺口

1. **`node` 吞掉命令失败**（1.1.0）
   `npm test` 因为报告目录不存在而崩溃，原子仍返回 `status=success` —— 一个坏掉的测试跑出了一个绿的构建。
   现在命令退出码决定步骤成败，`failOnCommandError=false` 可显式关闭，并导出 `exitCode`。

2. **`junit-report` 读不到 Node 的 JUnit**（1.2.0）
   Node 的 reporter 写的是 `<testsuites>` 直接套 `<testcase>`，中间没有 `<testsuite>`；原子按 suite 汇总，数出 0 个测试然后判"没问题"。
   现在 `testsuites` 为空时按扁平 `testcase` 统计，失败项照样进失败清单。

3. **`files-tool` 的 `**/` 不匹配零层目录**（1.1.0）
   `src/**/*.py` 找不到 `src/calc.py`。`PathMatcher` 把 `**/` 理解为"至少一层"，Ant 语义是"零或多层"。
   现在对每个 `**` 段生成折叠变体（`src/**/x.py` 也试 `src/x.py`）。
   顺带记一笔：**在 Java 块注释里写 `src/**/x` 会提前闭合注释**，编译报"非法字符 '\`'"。

4. **缺 `python-env` 原子**（新建，1.0.0）
   `python-build` 只会打 wheel，没有任何东西准备解释器。
   新原子：建 venext、按 `requirements.txt` 装依赖、在虚拟环境里跑一条命令，并把 `VIRTUAL_ENV` 和 `PATH` 作为同名出参交给后续步骤。

5. **`cmake-build` 不会跑测试**（1.2.0）
   加 `runTests` / `testArgs` / `failOnTestFailure`，并在这里连环踩了三个坑：
   - `--output-junit` 是**两个 token**（`--output-junit path`），不是 `--output-junit=path`；
   - 目标目录不存在时 ctest **静默不写文件**；
   - 相对路径是相对 **build 目录**（即 `--test-dir`），不是 workspace。
   原子现在按 ctest 的规则解析路径，并导出 `junitReport` 绝对路径；ctest 的 `100% tests passed, 0 tests failed out of 1` 也不能用"X tests passed"匹配（前面是百分号），改为从 `out of N` 取总数。

## 顺带修的基础设施

`tools/smoke-lib.sh` 原来从**目录名**推原子名，在 `git worktree` 里目录名是分支名（`cmake-tests`），jar 路径就成了 `dist/cmake-tests/cmake-tests.jar`，runner 类根本不在 classpath 上。
改为读 `task.json` 的 `atomCode`，31 个仓库已同步。

## 仍未做

- **在真 Jenkins 里跑**：以上经 `AtomRunner`（与 runner 同一个契约）验证，还没有走 JenkinsRule 或真实实例。
- **`**/` 折叠只修了 `files-tool`**：另有 18 个原子用 `PathMatcher`，同一个 bug 有 19 份拷贝。正解是把折叠提到 SDK 的 `Glob`，一次改完。
- 需要外网端点的步骤（`commit-status`、`notify-webhook`、`mail`、`s3-upload`）仍只有本地假服务器。
