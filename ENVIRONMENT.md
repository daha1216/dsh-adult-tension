# 本机环境与操作约束

这是用户为这台机器写的说明，不是产品规范。它和 `spec/` 一样必须遵守；两者冲突时先问用户。不要删改本文件，环境变了由用户更新。

## Git

- 本仓库 `D:\projects\adult-tension-v2` 是独立的 Git 仓库，主分支是 `main`。
- 用户主目录 `C:\Users\daha` 本身也是一个 Git 仓库，与本项目无关。
  - 执行任何 git 命令前，先确认 `git rev-parse --show-toplevel` 输出的是本仓库。
  - 不在主目录那个仓库上做任何操作，也不读它的历史。
- 直接在本仓库目录里工作，不用 Claude app 为会话创建的 worktree。
  - 这些 worktree 建在 `.claude/worktrees/` 下，每个会话的提交落在各自的分支上，进度会断开。
  - 发现自己在 worktree 里时，停下来告诉用户。
- `.claude/` 是宿主的本地目录，加进 `.gitignore`，不提交。
- 只在本地提交：不 push、不添加远程、不创建 GitHub 仓库。
  - 本机的 `gh` 已经登录用户的 GitHub 账号，一次推送就可能把成人内容公开到用户名下。
  - 需要跑 CI 时先问用户。

## 读写范围

- 只在本仓库内读写。本仓库以外只有三处可以用：
  - 系统临时目录；
  - 运行时自己的数据目录（`spec/SKILL_PACKAGING.md` §6）；
  - 下面“真实宿主测试”里说的测试目录。
- 自动测试一律用临时数据目录。
- 不删除、不修改本仓库以外的文件，不改任何宿主的用户级配置或 Skill 目录。确实需要时先问用户。
- 全文搜索只在本仓库内做。

## 旧项目

这台机器上散落着旧项目的副本、压缩包、已安装的旧版 Skill 和旧会话记录，例如：

- 桌面上的 `adult-tension` 目录和压缩包；
- `D:\dsh work`；
- `C:\Users\daha\ZCodeProject` 和 `C:\Users\daha\dsh-splits`；
- 各宿主目录里的会话记录。

规则：

- 一律不打开、不搜索、不引用（见 `spec/AGENTS.md` 的来源边界）。
- 上一个审查会话导出的会话记录里有大量旧代码摘录，同样不读。
- dsh、WorkBuddy、Gemini、ZCode 四个宿主里装着旧版 Skill，名字是 `adult-tension` 或 `dsh-adult-tension`。不要打开，也不要自己删除或覆盖；要在这些宿主上测试时先问用户。
- Claude Code 的用户级 Skill 目录里没有旧版。

## 运行环境

- 系统是 Windows 11，Shell 是 Git Bash。
- Python：`python` 是 3.12.10，`py` 默认是 3.14。本机没有 3.10、3.9、3.8。
  - 最低支持版本是 3.10（`spec/DESIGN_DECISIONS.md` D2）。在装上 3.10 真实跑测试之前，先用静态检查兜底，并记为遗留。安装 3.10 前先问用户。
  - 版本过低的演练按 `spec/DELIVERY_PLAN.md` 阶段 0 的说法，用测试模拟，并在 `PROGRESS.md` 注明。
- 本机没有 WSL，也没有 Docker。
  - 规范要求的 Linux 测试、Linux CI 和 Linux 真实演练怎么做，由用户决定：推到私有仓库跑 CI，或者安装 WSL。
  - 先把 CI 配置写好，记为待决事项，其他工作继续。
- 开发工具需要第三方依赖时，装进本仓库的虚拟环境（`.venv`，不提交），不装到全局 Python。

## 真实宿主测试

- 本机 PATH 上有 `claude`（Claude Code CLI）和 `opencode`。
- 测试项目放在本仓库之外、`D:\projects\` 下的独立目录，例如 `D:\projects\at-host-test\`。
  1. 把 Skill 装进测试项目的项目级 Skill 目录（Claude Code 是 `.claude/skills/adult-tension/`）。
  2. 在测试项目里用无头命令（例如 `claude -p`）开新会话。
- 测试项目不能放在这两个地方：
  - 本仓库里：宿主会读到本仓库的 `CLAUDE.md`，把开发指示混进被测会话；
  - `C:\Users\daha` 下：那里是一个无关的 Git 仓库。
- 也不要把 Skill 装进任何宿主的用户级 Skill 目录。
- 每个阶段少量的冒烟运行可以直接做。端到端评测这类成批运行会消耗较多模型额度，先问用户。
- 无头命令跑不通时，把手动操作步骤写给用户。
