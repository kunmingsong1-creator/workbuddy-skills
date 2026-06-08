---
name: KnowledgeGraph
description: >
  通用领域知识图库 Skill。将任意领域的专业文档（技术手册、规范文档、操作指南、 研究报告等
  PDF/Word/Excel/PPT）转化为结构化知识图谱，支持自定义实体类型、关系定义、 百科页面模板。底层使用 MarkItDown
  转换文档、Graphify 构建知识图谱、 Karpathy LLM Wiki 维护百科页面，顶层支持同步到乐享/IMA/WPS 等知识库平台。

  核心特性： - 领域无关：通过 domain_config.yaml 定义实体类型、关系和模板 -
  五层架构：L1(原始)→L2(Markdown)→L3(图谱)→L4(Wiki)→L5(平台) - 哈希锁定：SHA-256 保护原始文件，可从任意层重建
  - AI 实体抽取：基于领域配置的智能实体与关系抽取 - 多平台同步：支持乐享/IMA/WPS 知识库对接

  触发词：知识图库、KnowledgeGraph、知识图谱、文档解析、知识库搭建、 领域知识库、技术文档解析、专业文档入库、知识抽取。
---

# KnowledgeGraph — 通用领域知识图库

将任意领域的专业文档转化为结构化、可查询、可展示的知识图库。通过 `domain_config.yaml` 定义领域特定的实体类型、关系和页面模板，实现真正的领域无关知识管理。

---

## 五层架构

```
┌───────────────────────────────┐
│  L5  平台交互层               │  ← 乐享/IMA/WPS 知识库同步与查询
│      (sync-target/)           │
├───────────────────────────────┤
│  L4  Wiki 百科层              │  ← 结构化百科页面，交叉引用，矛盾标记
│      (wiki/*.md)              │
├───────────────────────────────┤
│  L3  知识图谱层               │  ← 实体 & 关系抽取，聚类，查询
│      (graphify-out/)          │
├───────────────────────────────┤
│  L2  统一文档层 (Markdown)     │  ← MarkItDown 转换产物
│      (converted/*.md)        │
├───────────────────────────────┤
│  L1  原始文档层 (只读)        │  ← 哈希锁定，绝不修改
│      (sources/)              │
└───────────────────────────────┘
```

### 分层原则

- **L1 只读**：原始文件存入 `sources/`，立即计算 SHA-256 写入 `sources/manifest.jsonl`。任何层不得修改原始文件。
- **L2 衍生**：由 `markitdown` 从 L1 自动生成，可随时从 L1 重新生成。
- **L3 抽取**：基于 `domain_config.yaml` 中定义的实体类型和关系，从 L2 抽取实体与关系构建图谱。
- **L4 编译**：Agent 基于 L2+L3 + 领域模板编写和交叉引用百科页面。
- **L5 展示**：从 L4 选取内容同步到乐享/IMA/WPS 等知识库平台，供用户交互查询。

---

## 目录结构

```
{project-name}-data/             ← 数据根目录（由 domain_config.yaml 的 data_root 指定）
├── sources/                     ← L1: 原始文档（只读）
│   ├── manifest.jsonl            ← 文件清单 & SHA-256 哈希
│   └── {category}/              ← 文档分类目录（由 config.yaml 的 categories 定义）
├── converted/                    ← L2: MarkItDown 转换后的 Markdown
│   └── {source-sha}/            ← 按源文件哈希分目录
├── graphify-out/                 ← L3: Graphify 知识图谱输出
│   ├── graph.json                ← 持久化可查询图谱
│   ├── graph.html                ← 交互式可视化
│   └── GRAPH_REPORT.md          ← 图谱审计报告
├── wiki/                         ← L4: Wiki 百科
│   ├── index.md                  ← 百科总索引
│   ├── log.md                    ← 操作日志
│   ├── entities/                 ← 实体页面（按 domain_config 定义的实体类型组织）
│   ├── concepts/                 ← 概念页面
│   └── mappings/                 ← 映射页面（术语对照、实体关系表等）
├── domain_config.yaml            ← 领域配置（实体类型、关系、模板路径、同步目标）
└── config.yaml                   ← 全局配置
```

---

## 领域配置：domain_config.yaml

这是本 Skill 与 KnowPilot 的核心区别。通过一个 YAML 文件定义整个领域的知识结构。

### 配置结构

```yaml
# domain_config.yaml — 领域配置
domain:
  name: "你的领域名称"
  description: "领域描述"
  version: "1.0.0"

# 实体类型定义 — 这是核心
entity_types:
  - name: equipment              # 实体类型名（英文，用于目录命名）
    display_name: "设备"          # 显示名（中文）
    plural_name: "设备列表"
    description: "领域中的设备、仪器、系统"
    id_pattern: "EQ-{name}"       # 实体 ID 生成模式（{name} 会被实体名替换）
    properties:                   # 实体属性定义
      - name: model               # 属性名
        display_name: "型号"
        type: string              # string | number | date | url | list
        required: true
      - name: manufacturer
        display_name: "制造商"
        type: string
      - name: specifications
        display_name: "规格参数"
        type: list
      - name: image_url
        display_name: "产品图片"
        type: url
    wiki_template: "assets/templates/equipment-template.md"  # 可选：自定义模板

  - name: concept
    display_name: "概念"
    plural_name: "概念列表"
    description: "领域中的专业术语和概念"
    id_pattern: "CON-{name}"
    properties:
      - name: definition
        display_name: "定义"
        type: string
        required: true
      - name: aliases
        display_name: "别名"
        type: list
      - name: related_concepts
        display_name: "相关概念"
        type: list

# 关系类型定义
relation_types:
  - name: applies_to             # 关系名
    display_name: "适用于"
    source: equipment             # 源实体类型
    target: equipment             # 目标实体类型
    description: "设备A适用于设备B的维护"
  - name: has_component
    display_name: "包含组件"
    source: equipment
    target: equipment
  - name: related_to
    display_name: "相关"
    source: concept
    target: concept

# 文档分类
categories:
  - name: technical
    display_name: "技术手册"
  - name: specifications
    display_name: "规格文档"
  - name: guides
    display_name: "操作指南"
  - name: research
    display_name: "研究报告"

# 映射页面定义
mappings:
  - name: glossary
    display_name: "术语对照表"
    description: "英中/别名术语对照"
    template: "assets/templates/glossary-template.md"
  - name: entity-index
    display_name: "实体索引"
    description: "所有实体的交叉索引表"

# 同步目标配置
sync:
  platform: "lexiang"           # lexiang | ima | wps | local
  config:
    space_id: ""                 # 乐享 space_id
    kb_name: ""                  # IMA 知识库名称
  sync_scope:
    - wiki                        # 同步百科页面
    - mappings                    # 同步映射表
    - sources                     # 同步原始文件（二进制上传）
```

### 示例配置

完整的示例配置见 `assets/examples/` 目录：
- `plm-domain-config.yaml` — PLM 制造业领域
- `generic-domain-config.yaml` — 通用模板（最简配置）

---

## 知识约束与出处规范

**核心原则 — 必须遵守，不可违反**

### 1. 知识来源限制

- **仅使用知识图库**：所有回答必须完全基于已摄入的 L1-L4 层数据
- **禁止杜撰**：不得编造、推测或生成知识图库中不存在的信息
- **禁止幻觉**：当知识库中没有相关信息时，必须明确告知用户

### 2. 出处标注规范

```markdown
## 回答内容

[实体/概念/关系信息]

**出处**：
- 源文件：[文件名](../../sources/{category}/文件名.pdf) — 页码/位置
- 知识图谱：graphify-out/graph.json — 实体 ID: {entity_id}
- 百科页面：[[wiki/entities/{type}/{entity-page}.md]]
```

### 3. 网络资源查询限制

- **默认禁止**：不得随意查询网络资源
- **例外**：仅当用户明确要求时才可查询，且须事先声明

### 4. 违规处理

如违反上述规则：
1. 立即停止当前回答
2. 声明"刚才的回答可能包含不准确信息"
3. 重新基于知识图库回答，或明确告知无法回答

---

## 核心工作流

### 1. init — 初始化

初始化领域知识图库的数据目录结构。

**触发**：用户说"初始化知识库"、"init"等。

**步骤**：

1. 读取 `domain_config.yaml` 获取领域定义
2. 创建数据根目录（默认 `{project-name}-data/`）
3. 按 `categories` 创建 `sources/` 子目录
4. 按 `entity_types` 创建 `wiki/entities/` 子目录
5. 按 `mappings` 创建 `wiki/mappings/` 子目录
6. 生成初始 `wiki/index.md` 和 `wiki/log.md`
7. 生成 `config.yaml` 全局配置
8. 生成 `sources/manifest.jsonl`（空文件）

**命令**：
```bash
python3 scripts/init.py \
  --config domain_config.yaml \
  --data-root ./{project-name}-data
```

### 2. ingest — 文档摄入

将文档导入系统，自动完成 L1→L2 转换。

**触发**：用户说"导入文档"、"添加文档"、"ingest"等。

**步骤**：

1. **接收源文件**：用户指定文件路径或 URL
2. **分类存放**：按文档类型存入 `sources/` 对应子目录
   - 如用户未指定分类，Agent 根据 `domain_config.yaml` 中的 `categories` 自动推断
3. **哈希锁定**：计算 SHA-256，追加到 `sources/manifest.jsonl`
4. **格式转换**：运行 MarkItDown 将文档转为 Markdown
   ```bash
   markitdown "<source-file>" -o "converted/<sha>/<filename>.md"
   ```
5. **图片提取**：MarkItDown 自动提取图片到 `converted/<sha>/<filename>_files/`
6. **日志记录**：在 `wiki/log.md` 记录摄入操作

**命令**：
```bash
python3 scripts/ingest.py \
  --source "/path/to/document.pdf" \
  --category technical \
  --data-root ./{project-name}-data
```

**MarkItDown 回退策略**：
- 优先使用 CLI：`markitdown --all-conversions --code-blocks --full-paths "{file}"`
- CLI 失败时回退 Python API：`markitdown.convert_file()`

### 3. extract-entities — 实体抽取

从 L2 的 Markdown 文件中抽取实体和关系，构建 L3 知识图谱。

**触发**：用户说"抽取实体"、"构建图谱"、"extract"等。通常在 ingest 后自动执行。

**步骤**：

1. **读取领域配置**：加载 `domain_config.yaml` 中的实体类型和关系定义
2. **生成抽取指令**：基于领域配置，为每个实体类型生成 AI 抽取 prompt
3. **AI 实体抽取**：对 `converted/` 目录下的每个 Markdown 文件：
   - 将文件内容分块（按标题或段落）
   - 对每个块，使用 AI 模型根据实体类型定义进行抽取
   - 输出 JSON 格式的实体列表和关系列表
4. **关系建立**：根据 `relation_types` 定义，建立实体间关系
5. **运行 Graphify**：可选，对抽取结果进行聚类和可视化
   ```bash
   graphify ./converted --output ./graphify-out
   ```
6. **生成报告**：输出 `GRAPH_REPORT.md`

**抽取输出格式**：
```json
{
  "entities": [
    {
      "id": "EQ-agilent-7890b",
      "type": "equipment",
      "name": "Agilent 7890B GC",
      "properties": {
        "model": "7890B",
        "manufacturer": "Agilent"
      },
      "source_file": "agilent-7890b-manual.pdf",
      "source_page": 5
    }
  ],
  "relations": [
    {
      "type": "has_component",
      "source": "EQ-agilent-7890b",
      "target": "EQ-fid-detector",
      "source_file": "agilent-7890b-manual.pdf"
    }
  ]
}
```

**命令**：
```bash
python3 scripts/extract-entities.py \
  --config domain_config.yaml \
  --input ./converted/ \
  --output ./graphify-out/entities.json \
  --data-root ./{project-name}-data
```

### 4. build-wiki — 编译百科页面

基于 L2+L3 的内容，编写和更新 L4 百科页面。

**触发**：用户说"编译百科"、"build wiki"、"生成百科"等。

**步骤**：

1. **读取图谱**：加载 `graphify-out/entities.json` 或 `graphify-out/graph.json`
2. **读取领域配置**：获取实体类型、属性、模板
3. **创建/更新实体页面**：
   - 使用领域模板（如自定义模板不存在，使用通用默认模板）
   - 填充实体属性和关系
   - 建立交叉引用（`[[wiki-link]]` 格式）
   - 标记矛盾信息
4. **更新索引**：刷新 `wiki/index.md`
5. **生成映射页面**：按 `mappings` 配置生成术语对照表、实体索引等
6. **日志记录**：更新 `wiki/log.md`

**命令**：
```bash
python3 scripts/build-wiki.py \
  --config domain_config.yaml \
  --graph ./graphify-out/entities.json \
  --output ./wiki/ \
  --data-root ./{project-name}-data
```

### 5. query — 知识查询

从知识图库中查询信息。**禁止杜撰，必须标注出处。**

**触发**：用户提出关于领域知识的任何问题。

**步骤**：

1. **检查知识库**：读取 `wiki/index.md` 和图谱数据
2. **判断是否可答**：
   - 有相关信息 → 标注出处后回答
   - 无相关信息 → 明确告知，建议导入或联网
3. **综合回答**：基于百科页面和图谱关系，标注完整出处
4. **记录查询**：追加到 `wiki/log.md`

### 6. sync — 同步到目标平台

将 L4 百科内容同步到目标知识库平台。

**触发**：用户说"同步到乐享"、"发布到知识库"、"sync"等。

**步骤**：

1. **读取同步配置**：从 `domain_config.yaml` 的 `sync` 段获取平台和配置
2. **选择同步内容**：按 `sync_scope` 选取要同步的内容
3. **执行同步**：
   - **乐享**：使用 `mcp__lexiang__*` 工具创建页面/上传文件
   - **IMA**：使用 `mcp__ima-mcp__*` 工具上传知识库/写笔记
   - **WPS**：使用 `mcp__kdocs__*` 工具创建文档
   - **本地**：仅复制文件到指定目录
4. **确认完成**：报告同步结果

**命令**：
```bash
python3 scripts/sync.py \
  --config domain_config.yaml \
  --scope wiki \
  --data-root ./{project-name}-data
```

### 7. lint — 健康检查

检查知识图库的完整性和一致性。

**触发**：用户说"健康检查"、"lint"、"检查知识库"等。

**检查项**：
- 哈希完整性：`manifest.jsonl` 中的哈希与实际文件匹配
- 转换覆盖率：`sources/` 中的文件是否都有对应的 `converted/` 文件
- 图谱完整性：实体是否有必要的属性、关系是否完整
- Wiki 完整性：所有实体是否有对应的百科页面
- 映射覆盖：`wiki/mappings/` 是否覆盖所有映射配置
- 矛盾检测：不同来源的信息冲突
- 孤立页面：未被引用的百科页面
- 缺失引用：被引用但未创建的页面

**命令**：
```bash
python3 scripts/lint.py \
  --config domain_config.yaml \
  --data-root ./{project-name}-data
```

**lint 报告格式**：
```markdown
# 知识图库健康检查报告

## 哈希完整性
- 总文件数：50
- 哈希匹配：50
- 哈希不匹配：0

## 转换覆盖率
- 已转换：48/50 (96%)
- 未转换：2
  - sources/technical/new-manual.pdf
  - sources/guides/quickstart.docx

## 图谱完整性
- 实体总数：320
- 实体类型分布：equipment(45), concept(120), procedure(155)
- 缺失必要属性的实体：3

## Wiki 完整性
- 百科页面总数：310/320 (96.9%)
- 缺失页面：10

## 映射覆盖
- 术语对照表：完整
- 实体索引：完整

## 矛盾检测
- 发现矛盾：0
```

---

## 操作决策表

| 用户意图 | 操作 | 工作流 | 关键输出 |
|----------|------|--------|----------|
| 初始化知识库 | init | 读配置→创建目录→生成初始文件 | 完整的目录结构 + 配置文件 |
| 导入/添加文档 | ingest | 接收→分类→哈希→MarkItDown | converted/<sha>/*.md |
| 抽取实体/构建图谱 | extract-entities | 读配置→AI抽取→关系建立→报告 | graphify-out/entities.json |
| 编译百科 | build-wiki | 读图谱→模板填充→交叉引用→索引 | wiki/entities/*/ |
| 查询知识 | query | 读索引→查图谱→标注出处 | 答案 + 出处 |
| 同步到平台 | sync | 读配置→选内容→执行同步→确认 | 平台知识库/笔记 |
| 健康检查 | lint | 哈希→转换→图谱→Wiki→映射→矛盾 | 健康检查报告 |
| 全流程（一键） | full-pipeline | init→ingest→extract→wiki→sync | 完整知识图库 |

---

## 前置依赖

### 工具链

| 工具 | 用途 | 安装 |
|------|------|------|
| **MarkItDown** | 文档转 Markdown | `pip install 'markitdown[all]'` |
| **Graphify** | 知识图谱构建（可选） | `pip install graphifyy && graphify install` |
| **PyYAML** | 配置文件解析 | `pip install pyyaml` |

### 平台凭证

同步到外部平台需要对应凭证：
- **乐享**：通过 WorkBuddy 乐享 connector 授权
- **IMA**：`IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY`
- **WPS**：通过 WorkBuddy WPS connector 授权

---

## 安全规则

1. **原始文件不可变**：`sources/` 目录下的文件只可追加，不可修改或删除
2. **哈希校验**：lint 时自动比对哈希，不一致则告警
3. **平台上传**：上传原始文件时保持原格式，不转码
4. **禁止杜撰**：不得编造知识图库中不存在的信息
5. **必须标注出处**：所有输出必须标注来源
6. **限制网络查询**：仅用户明确要求时可联网

---

## 常用命令速查

```bash
# 初始化
python3 scripts/init.py --config domain_config.yaml --data-root ./my-data

# 摄入文档
python3 scripts/ingest.py --source "/path/to/doc.pdf" --category technical --data-root ./my-data

# 实体抽取
python3 scripts/extract-entities.py --config domain_config.yaml --input ./converted/ --output ./graphify-out/entities.json

# 编译百科
python3 scripts/build-wiki.py --config domain_config.yaml --graph ./graphify-out/entities.json --output ./wiki/

# 同步
python3 scripts/sync.py --config domain_config.yaml --scope wiki --data-root ./my-data

# 健康检查
python3 scripts/lint.py --config domain_config.yaml --data-root ./my-data
```
