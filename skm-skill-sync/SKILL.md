---
name: skm-技能同步
version: 2.0.0
description: |
  多平台 Skill 和知识库同步工具（底层执行引擎）。
  ⚠️ 对外触发词已委托至 skm-skill-manager（D.同步模块），本 Skill 作为底层脚本库不直接接受用户指令。
  当用户说"同步skill"、"同步知识库"、"同步到我的库"等意图时，应加载 skm-skill-manager。
  支持两类同步：
  (1) Skills 同步 → GitHub 仓库 kunmingsong1-creator/workbuddy-skills
  (2) 知识库内容同步 → 乐享知识库「PLM 知识库」
author: 恬恬
agent_created: true
tags:
  - sync
  - github
  - skills
  - 知识库
  - 乐享
  - 多平台
  - 底层引擎
  - 委托至skm-skill-manager
disable: false
---

# skill-sync — 多平台内容同步工具

## 触发词识别

当用户说以下任意关键词时，加载本 Skill 并执行对应同步操作：

| 触发词 | 同步操作 |
|--------|---------|
| 同步skill / sync skills / 更新skill库 / push skills | → 同步 Skills 到 GitHub |
| 同步知识库 / sync knowledge / 更新乐享 / 同步乐享 | → 同步内容到乐享知识库 |
| 同步到我的库 / sync to my repo / 全部同步 / sync all | → 两者都同步 |

---

## 一、Skills 同步到 GitHub

**目标仓库**：`https://github.com/kunmingsong1-creator/workbuddy-skills`  
**本地路径**：`~/.workbuddy/skills/`  
**认证方式**：PAT（已内置在脚本中）

### 执行步骤

**Step 1**：检测本地 `~/.workbuddy/skills/.git` 是否存在
- 存在 → Step 2 尝试直接 `git push`
- 不存在 → Step 3 使用 API 推送

**Step 2**：直接 git push（快速路径）

```bash
cd ~/.workbuddy/skills
git add .
git commit -m "sync: $(date '+%Y-%m-%d %H:%M') 自动同步"
git push origin master:main
```

- 推送成功 → 完成，打印结果
- 推送失败（网络超时等）→ Step 3

**Step 3**：GitHub API 推送（支持双向同步）**NEW in v2.0**

执行以下命令（Python 脚本，支持 push / pull / sync 三种模式）：

```bash
# 自动判断（本地落后则 pull，否则 push）
python ~/.workbuddy/skills/skill-sync/scripts/github_sync.py

# 仅推送本地到 GitHub
python ~/.workbuddy/skills/skill-sync/scripts/github_sync.py push

# 仅从 GitHub 拉取最新
python ~/.workbuddy/skills/skill-sync/scripts/github_sync.py pull

# 先 pull 再 push（推荐）
python ~/.workbuddy/skills/skill-sync/scripts/github_sync.py sync
```

**PAT 配置升级（v2.0）**：
1. 新提供了 PAT 时，自动写入 `~/.workbuddy/skill-sync.conf`
2. 同时存入 Key Vault（`github-pat`，分类 `api-key`）
3. 脚本按优先级读取：环境变量 → 配置文件 → Key Vault

**双向同步逻辑（v2.0 新增）**：
- 检查本地 `skill-sync/SKILL.md` 的 `version` 字段
- 本地版本 < GitHub 版本 → 自动 `pull` 拉取最新
- 本地版本 > GitHub 版本 → 自动 `push` 推送
- 版本一致 → 跳过

脚本说明：见 `scripts/github_sync.py`，v2.0 新增版本检测 + 双向拉取。

**输出结果**：
```
✅ Skills 同步完成
仓库：https://github.com/kunmingsong1-creator/workbuddy-skills
文件数：XXX
最新提交：XXXXXXXX
```

---

## 二、知识库内容同步到乐享

**目标知识库**：PLM 知识库（乐享）  
**space_id**：`21522010bba540a7b6c1216912b727fc`  
**本地路径**：`D:\PLM_知识库\`（如存在）

### 前置检查

```
优先级：
1. 乐享 MCP 可用 → 使用 MCP 工具同步
2. 乐享 MCP 不可用 → 提示用户检查乐享连接器
```

检测 MCP 可用性：调用 `mcp__lexiang__space_describe_space(space_id="21522010bba540a7b6c1216912b727fc")`
- 成功 → 继续执行同步
- 失败 → 提示：「乐享 MCP 当前不可用，请在连接器管理页面确认乐享已连接」

### 同步规则

同步时遵循以下优先级规则，**不破坏乐享现有内容**：

| 条件 | 操作 |
|------|------|
| 本地文件在乐享不存在 | 创建新条目（upload） |
| 本地文件在乐享已存在且内容相同 | 跳过 |
| 本地文件在乐享已存在但内容不同 | 更新（先清空块，再写入） |
| 乐享有但本地没有 | **保留**（不删除） |

### 执行步骤

**Step 1**：确认同步目录

询问用户或自动检测：
- 用户指定路径 → 使用指定路径
- 未指定 → 探测 `D:\PLM_知识库\` 是否存在
- 都没有 → 提示「请指定要同步的本地目录」

**Step 2**：扫描本地目录变更

扫描本地目录下所有 `.md` 文件，与乐享目录结构对比，列出：
- 新增文件（N 个）
- 需更新文件（N 个）
- 已最新文件（N 个）

**Step 3**：确认后执行同步

向用户展示摘要，确认后按以下方式同步每个文件：

```
新建文件：
  mcp__lexiang__entry_import_content(
    space_id="21522010bba540a7b6c1216912b727fc",
    parent_entry_id={对应目录的乐享entry_id},
    title={文件名（去掉.md后缀）},
    content={文件内容}
  )

更新文件：
  1. mcp__lexiang__block_list_block_children(entry_id={现有entry_id})
  2. mcp__lexiang__block_delete_block_children(entry_id, block_ids=[全部])
  3. mcp__lexiang__block_convert_content_to_blocks(content={新内容}, content_format="markdown")
  4. mcp__lexiang__block_create_block_descendant(entry_id, descendants={新块})
```

**Step 4**：同步结果报告

```
✅ 知识库同步完成
知识库：PLM 知识库（乐享）
新建：X 个
更新：Y 个
跳过：Z 个
```

---

## 三、全部同步（sync all）

当触发词为「同步到我的库」「全部同步」「sync all」时，依次执行：
1. 先执行 Section 一（Skills → GitHub）
2. 再执行 Section 二（内容 → 乐享）
3. 输出合并报告

---

## 四、配置信息（内置，无需用户配置）

```yaml
github:
  owner: kunmingsong1-creator
  repo: workbuddy-skills
  branch: main
  local_path: ~/.workbuddy/skills/
  # PAT 存储在脚本中，不在此暴露

lexiang:
  space_id: 21522010bba540a7b6c1216912b727fc
  root_entry_id: 61f3059395014a2a8163ba7fb24f05f5
  local_path: D:\PLM_知识库\  # Windows 主机默认路径
```

---

## 五、常见问题排查

| 问题 | 原因 | 解决 |
|------|------|------|
| git push 超时 | GitHub 直连被封 | 自动降级为 API 推送 |
| MCP 连接失败 | 乐享连接器未连 | 在 WorkBuddy 连接器管理页重新授权 |
| 本地路径找不到 | 路径不存在 | 手动指定路径 |
| API 推送 401 | PAT 过期或无效 | 更新 `~/.workbuddy/skill-sync.conf` 中的 `GITHUB_PAT`，或重新运行 `python ~/.workbuddy/skills/skill-sync/scripts/github_sync.py push` 重新配置 |

---

*版本：v1.0.0 | 作者：恬恬 | 创建：2026-05-24*
