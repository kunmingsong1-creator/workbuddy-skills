#!/usr/bin/env python3
"""
KnowledgeGraph — build-wiki.py
基于图谱数据编译 Wiki 百科页面。

用法：
    python3 scripts/build-wiki.py \
        --config domain_config.yaml \
        --graph ./graphify-out/entities.json \
        --output ./wiki/ \
        --data-root ./my-data

流程：
    1. 读取 entities.json 图谱数据
    2. 读取 domain_config.yaml 获取实体类型和模板定义
    3. 为每个实体生成百科页面（使用领域模板或默认模板）
    4. 建立交叉引用
    5. 生成映射页面
    6. 更新索引和日志
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: 需要 PyYAML。请运行: pip install pyyaml")
    sys.exit(1)


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_entities(graph_path: str) -> dict:
    with open(graph_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_template(template_path: str) -> str | None:
    """加载自定义模板"""
    if template_path and Path(template_path).exists():
        return Path(template_path).read_text(encoding="utf-8")
    return None


def render_default_entity_page(entity: dict, entity_type_def: dict, config: dict) -> str:
    """使用默认模板渲染实体页面"""
    name = entity.get("name", "未知实体")
    et_name = entity.get("type", "unknown")
    entity_id = entity.get("id", "")
    display_name = entity_type_def.get("display_name", et_name)
    properties = entity.get("properties", {})
    sources = entity.get("sources", [])

    lines = [
        f"# {display_name}: {name}",
        "",
    ]

    # 描述
    if properties.get("description"):
        lines.append(f"> {properties['description']}")
        lines.append("")

    # 属性
    prop_defs = entity_type_def.get("properties", [])
    lines.append("## 基本信息")
    lines.append("")

    prop_display = {p["name"]: p["display_name"] for p in prop_defs}
    for p_name, p_display in prop_display.items():
        value = properties.get(p_name)
        if value is not None:
            if isinstance(value, list):
                lines.append(f"- **{p_display}**: {', '.join(str(v) for v in value)}")
            else:
                lines.append(f"- **{p_display}**: {value}")

    lines.append("")

    # ID
    if entity_id:
        lines.append(f"- **实体 ID**: `{entity_id}`")
        lines.append("")

    # 关系（由 Agent 在实际执行时补充交叉引用）
    lines.append("## 相关实体")
    lines.append("")
    lines.append("> *此部分由 Agent 在 build-wiki 工作流中根据关系数据自动填充。*")
    lines.append("")

    # 出处
    if sources:
        lines.append("## Sources")
        lines.append("")
        for src in sources:
            if isinstance(src, dict):
                file_name = src.get("file", src.get("source_file", "未知"))
                page = src.get("page", "")
                lines.append(f"- [{file_name}](../../sources/{file_name})" +
                             (f" — 第 {page} 页" if page else ""))
            else:
                lines.append(f"- {src}")
        lines.append("")

    lines.append("---")
    lines.append(f"*由 KnowledgeGraph 自动生成 | 实体 ID: `{entity_id}`*")

    return "\n".join(lines)


def render_entity_page(entity: dict, config: dict) -> str:
    """渲染单个实体页面（优先使用自定义模板）"""
    et_name = entity.get("type", "")
    entity_types = config.get("entity_types", [])

    et_def = None
    for et in entity_types:
        if et["name"] == et_name:
            et_def = et
            break

    if et_def is None:
        et_def = {"name": et_name, "display_name": et_name, "properties": []}

    # 尝试加载自定义模板
    template_path = et_def.get("wiki_template")
    if template_path:
        template = load_template(template_path)
        if template:
            # 简单模板替换
            result = template
            for k, v in entity.get("properties", {}).items():
                result = result.replace(f"{{{k}}}", str(v))
            result = result.replace("{name}", entity.get("name", ""))
            result = result.replace("{id}", entity.get("id", ""))
            result = result.replace("{type}", et_def.get("display_name", et_name))
            return result

    # 使用默认模板
    return render_default_entity_page(entity, et_def, config)


def build_entity_pages(entities: list, config: dict, wiki_dir: Path) -> int:
    """为所有实体生成 Wiki 页面，返回生成数量"""
    count = 0
    for entity in entities:
        et_name = entity.get("type", "uncategorized")
        name = entity.get("name", "unknown")
        entity_id = entity.get("id", name)

        # 清理文件名
        safe_name = entity_id.replace("/", "-").replace("\\", "-").replace(" ", "-").strip("-")
        page_path = wiki_dir / "entities" / et_name / f"{safe_name}.md"

        content = render_entity_page(entity, config)
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(content, encoding="utf-8")
        count += 1

    return count


def build_index(wiki_dir: Path, config: dict, entities: list):
    """更新 Wiki 总索引"""
    domain = config.get("domain", {})
    entity_types = config.get("entity_types", [])
    mappings = config.get("mappings", [])

    # 按类型统计
    type_counts = defaultdict(int)
    for e in entities:
        type_counts[e.get("type", "unknown")] += 1

    lines = [
        f"# {domain.get('name', '知识图库')} — 百科索引",
        "",
        f"> {domain.get('description', '')}",
        "",
        f"> 最后更新: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"> 实体总数: {len(entities)}",
        "",
        "---",
        "",
        "## 实体目录",
        "",
    ]

    type_map = {et["name"]: et for et in entity_types}
    for et in entity_types:
        count = type_counts.get(et["name"], 0)
        lines.append(f"- [{et['display_name']}](entities/{et['name']}/) — {count} 条")

    lines.extend(["", "## 概念目录", "", "- [概念页面](concepts/)", ""])

    if mappings:
        lines.extend(["## 映射页面", ""])
        for m in mappings:
            lines.append(f"- [{m['display_name']}](mappings/{m['name']}.md)")

    lines.extend(["", "---", "", "*由 KnowledgeGraph 自动生成*"])

    (wiki_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def build_glossary(entities: list, config: dict, wiki_dir: Path):
    """生成术语对照映射页面"""
    entity_types = config.get("entity_types", [])

    # 查找有别名属性的实体
    glossary_entries = []
    for e in entities:
        props = e.get("properties", {})
        aliases = props.get("aliases", [])
        english_name = props.get("english_name", "")
        name = e.get("name", "")

        if aliases or english_name:
            entry = {"name": name, "type": e.get("type", "")}
            if english_name:
                entry["english"] = english_name
            if aliases:
                entry["aliases"] = aliases if isinstance(aliases, list) else [aliases]
            glossary_entries.append(entry)

    if not glossary_entries:
        return

    lines = [
        "# 术语对照表",
        "",
        f"> 自动生成，共 {len(glossary_entries)} 条术语",
        "",
        "| 术语名称 | 英文/别名 | 类型 |",
        "|----------|-----------|------|",
    ]

    type_map = {et["name"]: et["display_name"] for et in entity_types}
    for entry in sorted(glossary_entries, key=lambda x: x["name"]):
        english = entry.get("english", "")
        aliases = entry.get("aliases", [])
        alias_str = ", ".join(aliases) if aliases else ""
        combined = ", ".join(filter(None, [english, alias_str]))
        type_display = type_map.get(entry["type"], entry["type"])
        lines.append(f"| {entry['name']} | {combined} | {type_display} |")

    lines.extend(["", "---", "", "*由 KnowledgeGraph 自动生成*"])

    mappings_dir = wiki_dir / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)
    (mappings_dir / "glossary.md").write_text("\n".join(lines), encoding="utf-8")


def build_entity_index(entities: list, config: dict, wiki_dir: Path):
    """生成实体索引映射页面"""
    entity_types = config.get("entity_types", [])

    lines = [
        "# 实体索引",
        "",
        f"> 所有实体的交叉索引，共 {len(entities)} 条",
        "",
    ]

    type_map = {et["name"]: et["display_name"] for et in entity_types}
    type_entities = defaultdict(list)
    for e in entities:
        type_entities[e.get("type", "unknown")].append(e)

    for et in entity_types:
        et_name = et["name"]
        if et_name not in type_entities:
            continue
        lines.extend(["", f"## {et['display_name']}", ""])
        lines.append("| 名称 | 实体 ID | 百科页面 |")
        lines.append("|------|---------|----------|")
        for e in sorted(type_entities[et_name], key=lambda x: x.get("name", "")):
            safe_name = e.get("id", e.get("name", "")).replace("/", "-").replace(" ", "-")
            lines.append(
                f"| {e.get('name', '')} | `{e.get('id', '')}` | "
                f"[[entities/{et_name}/{safe_name}.md]] |"
            )

    lines.extend(["", "---", "", "*由 KnowledgeGraph 自动生成*"])

    mappings_dir = wiki_dir / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)
    (mappings_dir / "entity-index.md").write_text("\n".join(lines), encoding="utf-8")


def append_to_log(wiki_dir: Path, action: str, details: dict):
    """追加到操作日志"""
    log_path = wiki_dir / "log.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = ["", f"## [{timestamp}] {action}", ""]
    for k, v in details.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="KnowledgeGraph — 编译 Wiki 百科")
    parser.add_argument("--config", required=True, help="领域配置文件路径")
    parser.add_argument("--graph", required=True, help="实体数据文件路径 (entities.json)")
    parser.add_argument("--output", required=True, help="Wiki 输出目录")
    parser.add_argument("--data-root", required=True, help="数据根目录")
    args = parser.parse_args()

    config = load_config(args.config)
    data = load_entities(args.graph)
    wiki_dir = Path(args.output).resolve()

    entities = data.get("entities", [])
    relations = data.get("relations", [])

    print(f"KnowledgeGraph — 编译 Wiki 百科")
    print(f"  实体数: {len(entities)}")
    print(f"  关系数: {len(relations)}")
    print(f"  输出目录: {wiki_dir}")
    print("")

    # 1. 生成实体页面
    page_count = build_entity_pages(entities, config, wiki_dir)
    print(f"[OK] 生成 {page_count} 个实体页面")

    # 2. 更新索引
    build_index(wiki_dir, config, entities)
    print("[OK] 索引已更新: wiki/index.md")

    # 3. 生成映射页面
    build_glossary(entities, config, wiki_dir)
    print("[OK] 术语对照表已生成: wiki/mappings/glossary.md")

    build_entity_index(entities, config, wiki_dir)
    print("[OK] 实体索引已生成: wiki/mappings/entity-index.md")

    # 4. 记录日志
    append_to_log(wiki_dir, "Wiki 编译", {
        "实体页面数": page_count,
        "关系数": len(relations),
    })

    print("")
    print("--- Wiki 编译完成 ---")
    print(f"  总页面: {page_count} + 索引 + 映射")
    print(f"  输出目录: {wiki_dir}")
    print("")
    print("下一步: python3 scripts/sync.py --config domain_config.yaml --scope wiki")


if __name__ == "__main__":
    main()
