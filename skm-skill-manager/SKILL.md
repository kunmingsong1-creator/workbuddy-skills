---
name: skm-技能管家
version: 2.1.0
description: Skill 全生命周期管理平台 —
  整合查看/统计、**技能说明**、质量审计/合规检查、触发词优化/趋势分析、深度卸载清理、GitHub/乐享双向同步、跨Skill自学习。触发词：管理skill、skill列表、查看skill、skill统计、我的skill、skill介绍、skill说明、skill质量、优化skill、同步skill、清理skill、卸载skill、打包skill。
author: agent_created
agent_created: true
tags:
  - skill-management
  - quality-audit
  - sync
  - optimizer
  - cleaner
  - utility
disable: false
---

# skm-skill-manager — Skill 全生命周期管理平台

> v2.0.0 | 整合 skill-trend-analyzer + skm-skill-sync，成为唯一的 Skill 管理入口

---

## 一、触发词路由表

本 Skill 是所有 Skill 管理类操作的统一入口。根据用户意图路由到对应能力模块：

### 模块 A：查看与统计（原 v1.0 功能）

| 触发词 | 能力 | 执行方式 |
|--------|------|---------|
| 管理skill、skill列表、查看skill、列出skill | 列出所有 Skill 摘要表格 | 扫描 `~/.workbuddy/skills/` → 解析 frontmatter |
| 我的skill、有哪些skill、show skills | 同上，含统计汇总 | 同上，追加分组统计 |
| skill统计、统计skill | 仅统计汇总（总数/自建/第三方） | 同上，仅输出统计 |
| 查看 <名称> skill详情 | 读取完整 SKILL.md 并展示 | `Read ~/.workbuddy/skills/<name>/SKILL.md` |
| 搜索skill <关键词>、找<关键词>skill | 按名称/描述/Tags 模糊匹配 | 遍历所有 SKILL.md frontmatter 进行匹配 |

### 模块 B：质量与安全审计（来自 skill-trend-analyzer）

| 触发词 | 能力 | 执行方式 |
|--------|------|---------|
| 检查质量、skill质量、质量审计、skill合规、合规检查 | 7大质量合规自检（标准/安全/性能/合规） | `python ~/.workbuddy/skills/skill-trend-analyzer/scripts/skill_quality_checker.py <path>` |
| 批量质量检查、检查所有skill质量 | 全量扫描所有 Skill 并生成评分排名 | `python --batch` |
| 安全审计、安全扫描、检查安全 | 安全风险扫描 P0/P1/P2 | `python --deps` |
| 质量报告、生成质量报告 | 生成详细 JSON/HTML 报告 | `python --report` |
| 自动修复 <名称>、修复skill问题 | 应用安全自动修复（frontmatter/manifest/safe_io） | `python --fix` |

### 模块 C：触发词优化与趋势分析（来自 skill-trend-analyzer）

| 触发词 | 能力 | 执行方式 |
|--------|------|---------|
| 优化skill <名称>、优化触发词、优化关键词 | 四源融合关键词优化建议 | `python ~/.workbuddy/skills/skill-trend-analyzer/scripts/skill_optimizer.py <path>` |
| 批量优化、优化所有skill | 全量优化分析 | `python --batch` |
| 趋势分析、市场趋势、skill趋势 | 市场关键词趋势分析 | `python ~/.workbuddy/skills/skill-trend-analyzer/scripts/trend_analyzer.py` |
| 扫描所有skill、深度扫描 | 本地全量扫描（8阶段） | `python ~/.workbuddy/skills/skill-trend-analyzer/scripts/local_skill_scanner.py` |
| 跨skill学习、skill自学习 | 跨Skill经验迁移+权重进化 | 自动触发（采纳/拒绝优化建议时） |

### 模块 D：同步与分发（来自 skm-skill-sync）

| 触发词 | 能力 | 执行方式 |
|--------|------|---------|
| 同步skill、push skills、更新skill库 | Skills → GitHub 推送 | `python ~/.workbuddy/skills/skm-skill-sync/scripts/github_sync.py push` |
| 拉取skill、pull skills、下载skill | 从 GitHub 拉取最新 | `python -- pull` |
| 双向同步、sync skills | 先 pull 后 push | `python -- sync` |
| 同步知识库、同步乐享、更新乐享 | 内容 → 乐享知识库 | 调用乐享 MCP 工具（详见第五章） |
| 同步到我的库、全部同步、sync all | Skills → GitHub + 内容 → 乐享 | 依次执行上述两步 |

### 模块 F：技能说明（v2.1.0 新增）

| 触发词 | 能力 | 执行方式 |
|--------|------|---------|
| skill介绍、功能介绍、有哪些skill、列出所有skill | 列出所有 Skill 的功能说明卡 | 扫描 `~/.workbuddy/skills/` → 逐 SKILL.md 提取 frontmatter + 触发词 + 核心能力说明 → 格式化输出 |
| 这是什么skill、<名称> 说明、说说 <名称> skill | 查看单个 Skill 的详细功能说明 | 精确名称匹配 → 展示对应卡片的完整版 |
| 搜索skill说明 <关键词> | 按关键词搜索 Skill 功能 | 遍历所有 SKILL.md 进行 full-text 匹配 |
| 所有skill说明、skill功能一览 | 生成全量 Skill 功能说明总览 | 同上，按分类分组输出 |

#### 功能说明卡的输出格式

```
┌─────────────────────────────────────────┐
│ 🏠 skm-skill-manager v2.0.0              │
│ Skill 全生命周期管理平台                   │
├─────────────────────────────────────────┤
│ 📋 用途：查看/统计/质量审计/同步/清理所有      │
│     Skill，统一的 Skill 管理入口             │
│ 🎯 触发词：管理skill、skill列表、查看skill、    │
│     skill统计、同步skill、优化skill等         │
│ 🏷️ 标签：skill-management, quality-audit   │
│ 🔌 依赖：skill-trend-analyzer/scripts/     │
│     skm-skill-sync/scripts/              │
│ 📂 位置：~/.workbuddy/skills/skm-        │
│     skill-manager/                       │
└─────────────────────────────────────────┘
```

#### 全量功能一览的分组规则

按标签自动分组，分组顺序：
1. 🏠 **自建核心**（`agent_created: true` + `skm-` 前缀）— 用户自建的关键工具
2. 📦 **用户 Skill** — 其他用户安装的 Skill
3. 🔌 **连接器 Skill** — 通过 MCP 连接器提供的 Skill

每组内按名称字母序排列。

#### 单 Skill 详细说明的扩展信息

当用户查看单个 Skill 的说明时，除了基础卡信息外，还包含：
- **使用场景**：从 description 提取的典型使用场景
- **使用方式**：如何触发/调用此 Skill
- **注意事项**：从 SKILL.md 中提取的 ⚠️ 警告或前提条件
- **关联 skill**：依赖或协同使用的其他 Skill

执行方式：
```bash
SKILL_DIR=~/.workbuddy/skills
# 列出所有 skill 功能说明
for dir in "$SKILL_DIR"/*/; do
  name=$(basename "$dir")
  [[ "$name" == _* ]] && continue
  [[ -f "$dir/SKILL.md" ]] || continue
  # 解析 frontmatter + 提取前 5 行说明内容
  header=$(head -30 "$dir/SKILL.md")
  echo "--- $name ---"
  echo "$header" | head -5
done
```

### 模块 E：清理与维护（来自 skill-trend-analyzer）

| 触发词 | 能力 | 执行方式 |
|--------|------|---------|
| 卸载skill <名称>、删除skill、深度卸载 | 7层安全检查 + 深度残余清理 | `python ~/.workbuddy/skills/skill-trend-analyzer/scripts/skill_cleaner.py <name>` |
| 预览卸载、卸载预览 | 仅预览不执行（--dry-run） | `python --dry-run` |
| 深度扫描清理 | 残余扫描 + 自动清理 | `python --deep-scan --clean` |
| 列出可卸载skill | 展示所有可卸载的 Skill | `python --list` |
| 打包skill <名称>、发布skill | 统一规范打包（SHA256校验+防篡改） | 参照 skill-trend-analyzer 打包流程 |
| 加密知识库、保护知识库 | AES-256-GCM 加密保护 | `python ~/.workbuddy/skills/skill-trend-analyzer/scripts/kb_protector.py` |

---

## 二、核心原则

1. **单入口原则**：所有 Skill 管理操作统一通过本 Skill 触发，不直接调用子 Skill
2. **脚本即能力**：Python 脚本路径指向 `skill-trend-analyzer/scripts/` 和 `skm-skill-sync/scripts/`，本 Skill 为编排层
3. **自建判定**：目录名以 `skm-` 开头且 SKILL.md 含 `agent_created: true` → 自建
4. **跳过特殊目录**：`_removed`、`_bm_*`、以 `_` 开头的隐藏目录、`.git` 等
5. **安全优先**：卸载/清理操作必须经过确认；卸载使用 trash 而非 rm

---

## 三、模块 A 详细执行流程

### A.1 扫描所有 Skill（核心方法）

```bash
# 收集所有有效 Skill 目录
SKILLS_DIR=~/.workbuddy/skills/
for dir in "$SKILLS_DIR"/*/; do
  name=$(basename "$dir")
  # 跳过特殊目录
  [[ "$name" == _* ]] && continue
  [[ "$name" == .* ]] && continue
  # 检查 SKILL.md 存在
  [[ -f "$dir/SKILL.md" ]] || continue
  # 解析 frontmatter
  ...
done
```

### A.2 解析 SKILL.md Frontmatter

从每个 SKILL.md 提取以下字段：
- `name`：Skill 名称
- `version`：版本号
- `description`：描述
- `author`：作者（`agent_created` 标记自建）
- `tags`：标签列表
- `agent_created`：是否自建

**判定规则**：`agent_created: true` 且目录名以 `skm-` 开头 → 🏠 自建

### A.3 输出格式

#### 列表视图

| # | 名称 | 版本 | 类型 | 描述 | Tags |
|---|------|------|------|------|------|
| 1 | skm-skill-manager | 2.0.0 | 🏠自建 | Skill全生命周期管理平台 | skill-management, utility |

#### 统计视图

```
总计: XX 个 Skill
  🏠 自建（skm-前缀 + agent_created）: XX 个
  📦 第三方/系统: XX 个
  🔌 连接器（connector）: XX 个
```

---

## 四、模块 B 详细执行流程

### B.1 质量合规自检（7大检查维度）

加载 `skill-trend-analyzer/scripts/skill_quality_checker.py`，检查以下维度：

| # | 维度 | 权重 | 说明 |
|---|------|------|------|
| 1 | 标准检查 | - | SKILL.md 存在性、scripts/ 目录结构 |
| 2 | 安全审计 | P0/P1/P2 | 硬编码密钥/eval/os.system/pickle/YAML注入等 |
| 3 | 性能评估 | - | 文件大小、脚本数量、函数复杂度 |
| 4 | 合规评分 | 0-100分 | ClawHub/SkillHub 发布就绪度 |
| 5 | 创建指南 | - | 缺失项 + 修复模板 |
| 6 | 依赖扫描 | P0/P1/P2 | Python import 安全检查 |
| 7 | 自动修复 | - | frontmatter/manifest/safe_io 自动生成 |

#### 单 Skill 检查

```bash
python ~/.workbuddy/skills/skill-trend-analyzer/scripts/skill_quality_checker.py \
  ~/.workbuddy/skills/<skill-name>
```

#### 批量检查

```bash
python ~/.workbuddy/skills/skill-trend-analyzer/scripts/skill_quality_checker.py --batch
```

**输出格式**：按合规评分降序排列的汇总表格

| Skill | 评分 | 等级 | P0 | P1 | 大小KB |
|-------|------|------|----|----|--------|
| skm-key-vault | 85% | B | 0 | 2 | 45 |

### B.2 安全审计规则

| 级别 | 检测项 | 正则模式 |
|------|--------|---------|
| P0 | 硬编码密码 | `password\s*=\s*['"][^'"]+['"]` |
| P0 | 硬编码API Key | `(api_key|apikey|secret_key)\s*=` |
| P0 | eval/exec | `\beval\s*\(` / `\bexec\s*\(` |
| P0 | Shell注入 | `subprocess.*shell\s*=\s*True` |
| P0 | SQL注入 | `execute\s*\([^)]*\+\s*['"]` |
| P1 | 硬编码IP/URL | IP地址、URL字面量 |
| P1 | os.system | `os\.system\s*\(` |
| P1 | pickle反序列化 | `pickle\.loads?\s*\(` |

---

## 五、模块 D 详细执行流程

### D.1 Skills → GitHub 同步

**目标仓库**：`https://github.com/kunmingsong1-creator/workbuddy-skills`

```bash
# 直接推送
python ~/.workbuddy/skills/skm-skill-sync/scripts/github_sync.py push

# 仅拉取
python ~/.workbuddy/skills/skm-skill-sync/scripts/github_sync.py pull

# 双向同步（先 pull 后 push）
python ~/.workbuddy/skills/skm-skill-sync/scripts/github_sync.py sync
```

**PAT 配置优先级**（高→低）：
1. 环境变量 `GITHUB_PAT`
2. 配置文件 `~/.workbuddy/skill-sync.conf`
3. Key Vault（`github-pat`，通过 `skm-key-vault` 查询）

**双向同步逻辑**：
- 比较本地 `skm-skill-sync/SKILL.md` 版本 vs GitHub 远程版本
- 本地落后 → 自动 pull
- 本地超前 → 自动 push
- 版本一致 → 跳过

### D.2 内容 → 乐享知识库同步

**目标知识库**：PLM 知识库（`space_id: 21522010bba540a7b6c1216912b727fc`）

执行步骤：
1. 检测乐享 MCP 可用性：`mcp__lexiang__space_describe_space`
2. 扫描本地目录变更
3. 对比乐享现有内容，按以下规则同步：

| 条件 | 操作 |
|------|------|
| 本地有、乐享无 | 创建新条目（`entry_import_content`） |
| 两边都有、内容相同 | 跳过 |
| 两边都有、内容不同 | 更新（清空块→写入新内容） |
| 乐享有、本地无 | **保留**（不删除） |

---

## 六、模块 E 详细执行流程

### E.1 深度卸载清理

执行 `skill-trend-analyzer/scripts/skill_cleaner.py`：

**7层安全检查**：
1. 目录存在性验证
2. 保护清单检查（`PROTECTED_SKILLS`）
3. 敏感 Skill 额外警告（`SENSITIVE_SKILLS`）
4. 二次确认提示
5. 使用 trash 命令（可恢复）
6. 残余扫描（automations/config/logs/memory/cache）
7. 自动清理残余（可选）

**保护清单**：`find-skills`、`skillhub-preference` 等系统关键 Skill 禁止卸载

**敏感清单**：`skill-trend-analyzer` 等卸载前需额外确认

### E.2 Token 消耗跟踪

自动记录每次质量检查/优化/同步操作的 token 消耗（通过 `exec_logger.py`）

---

## 七、技能依赖关系

```
skm-skill-manager (本 Skill — 编排层)
  ├── skill-trend-analyzer/scripts/ (质量检查/优化/清理/趋势)
  │   ├── skill_quality_checker.py
  │   ├── skill_optimizer.py
  │   ├── local_skill_scanner.py
  │   ├── skill_cleaner.py
  │   ├── trend_analyzer.py
  │   └── kb_protector.py
  ├── skm-skill-sync/scripts/ (GitHub 同步)
  │   └── github_sync.py
  └── 乐享 MCP (知识库同步)
      └── mcp__lexiang__*
```

---

## 八、快速参考卡片

```
┌─────────────────────────────────────────────────────────┐
│  skm-skill-manager v2.0.0 — 快速参考                      │
├─────────────────────────────────────────────────────────┤
│  查看        │ skill列表 / 我的skill / 统计skill          │
│  质量        │ 检查质量 <名> / 批量质量检查                 │
│  优化        │ 优化skill <名> / 趋势分析                   │
│  同步        │ 同步skill / 同步知识库 / 全部同步            │
│  清理        │ 卸载skill <名> / 深度卸载 / 打包发布          │
│  安全        │ 安全审计 <名> / 扫描所有skill               │
│  说明        │ skill介绍 / <名> 说明 / 搜索skill说明       │
├─────────────────────────────────────────────────────────┤
│  自建判定    │ skm-前缀 + agent_created: true = 🏠自建    │
│  安全机制    │ 卸载用trash / 关键操作需确认                  │
└─────────────────────────────────────────────────────────┘
```

---

*版本：v2.1.0 | 整合自 skm-skill-manager v1.0.0 + skill-trend-analyzer v2.4.0 + skm-skill-sync v1.0.0*
*合并日期：2026-06-06 | v2.1.0 新增模块 F（技能说明）*
