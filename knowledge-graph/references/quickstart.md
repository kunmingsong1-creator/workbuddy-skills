# 快速开始

## 前置依赖

```bash
pip install 'markitdown[all]'   # 文档转 Markdown
pip install pyyaml                 # YAML 配置解析
# Graphify 可选：pip install graphifyy && graphify install
```

## 第一步：编写领域配置

复制 `assets/examples/generic-domain-config.yaml` 到你的工作目录，然后根据你的领域修改：

```bash
cp assets/examples/generic-domain-config.yaml ./my-domain-config.yaml
# 编辑 my-domain-config.yaml
```

最少需要定义：
1. `domain.name` — 领域名称
2. `entity_types` — 至少 1 个实体类型
3. `relation_types` — 至少 1 个关系类型
4. `categories` — 至少 1 个文档分类

## 第二步：初始化知识库

```bash
python3 scripts/init.py \
  --config ./my-domain-config.yaml \
  --data-root ./my-knowledge-base
```

这会创建：
```
my-knowledge-base/
├── sources/          ← L1: 原始文档
├── converted/        ← L2: Markdown 转换产物
├── graphify-out/     ← L3: 知识图谱
├── wiki/             ← L4: Wiki 百科
│   ├── index.md
│   └── log.md
├── config.yaml       ← 全局配置
└── domain_config.yaml ← 你的领域配置（已复制）
```

## 第三步：摄入文档

```bash
python3 scripts/ingest.py \
  --source "/path/to/your-document.pdf" \
  --category documents \
  --data-root ./my-knowledge-base
```

可以批量摄入多个文档：
```bash
for f in /path/to/docs/*.pdf; do
  python3 scripts/ingest.py --source "$f" --category documents --data-root ./my-knowledge-base
done
```

## 第四步：构建知识图谱

```bash
python3 scripts/extract-entities.py \
  --config ./my-domain-config.yaml \
  --input ./my-knowledge-base/converted/ \
  --output ./my-knowledge-base/graphify-out/entities.json \
  --data-root ./my-knowledge-base
```

**注意**：此脚本生成抽取 prompt 框架。实际的 AI 抽取由 Agent 根据 `domain_config.yaml` 执行。

如果使用 Graphify：
```bash
graphify ./my-knowledge-base/converted --output ./my-knowledge-base/graphify-out
```

## 第五步：编译 Wiki 百科

```bash
python3 scripts/build-wiki.py \
  --config ./my-domain-config.yaml \
  --graph ./my-knowledge-base/graphify-out/entities.json \
  --output ./my-knowledge-base/wiki/ \
  --data-root ./my-knowledge-base
```

这会生成：
- `wiki/entities/<type>/*.md` — 每个实体的百科页面
- `wiki/index.md` — 总索引
- `wiki/mappings/glossary.md` — 术语对照表
- `wiki/mappings/entity-index.md` — 实体索引

## 第六步：健康检查

```bash
python3 scripts/lint.py \
  --config ./my-domain-config.yaml \
  --data-root ./my-knowledge-base
```

## 第七步：同步到平台（可选）

先配置 `domain_config.yaml` 中的 `sync` 段：

```yaml
sync:
  platform: "lexiang"               # lexiang | ima | wps | local
  config:
    space_id: "你的乐享 space_id"
  sync_scope:
    - wiki
    - mappings
```

然后在 WorkBuddy 中执行同步（通过对应 MCP 工具）：
```bash
python3 scripts/sync.py \
  --config ./my-domain-config.yaml \
  --data-root ./my-knowledge-base \
  --scope wiki mappings
```

---

## 完整流程（一键）

Agent 可以执行以下完整流程：

1. 检查 `domain_config.yaml` 是否存在
2. 初始化数据目录
3. 摄入所有文档
4. 抽取实体和关系
5. 编译 Wiki 百科
6. 健康检查
7. 同步到平台

---

## 常见问题

**Q: 如何添加新的实体类型？**
A: 编辑 `domain_config.yaml`，在 `entity_types` 中新增一项，然后重新运行 `build-wiki`。

**Q: 如何更新已有实体？**
A: 重新摄入文档（会通过 SHA-256 去重），然后重新运行 `extract-entities` 和 `build-wiki`。

**Q: 如何支持中文内容？**
A: 所有脚本均使用 `encoding="utf-8"`，天然支持中文。

**Q: 如何自定义百科页面模板？**
A: 在 `entity_types` 的某项中设置 `wiki_template` 字段，指向模板文件路径。

**Q: 如何接入其他同步平台？**
A: 修改 `sync.platform` 为 `wps` 或 `ima`，并在 `sync.config` 中填写对应凭证。
