#!/usr/bin/env python3
"""
KnowledgeGraph — extract-entities.py
基于领域配置的 AI 实体抽取。

用法：
    python3 scripts/extract-entities.py \
        --config domain_config.yaml \
        --input ./converted/ \
        --output ./graphify-out/entities.json \
        --data-root ./my-data

流程：
    1. 读取 domain_config.yaml 获取实体类型和关系定义
    2. 扫描 converted/ 目录下的 Markdown 文件
    3. 将文件分块，对每块执行 AI 实体抽取
    4. 合并去重，建立关系
    5. 输出结构化的 entities.json

注意：此脚本生成抽取指令和结构化框架。
实际的 AI 抽取由 Agent 执行（需要 LLM 能力），脚本负责数据管理和结果验证。
"""

import argparse
import hashlib
import json
import os
import re
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
    """加载领域配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_extraction_prompt(entity_types: list, relation_types: list, text_chunk: str) -> str:
    """
    基于 domain_config 构建实体抽取 prompt。
    返回可供 LLM 使用的一段指令文本。
    """
    type_descriptions = []
    for et in entity_types:
        props = ", ".join(p["name"] + ("*" if p.get("required") else "") for p in et.get("properties", []))
        type_descriptions.append(
            f'- **{et["display_name"]}** (type: "{et["name"]}")\n'
            f'  描述: {et["description"]}\n'
            f'  属性: {props}'
        )

    relation_descriptions = []
    for rt in relation_types:
        relation_descriptions.append(
            f'- **{rt["display_name"]}** (type: "{rt["name"]}", {rt["source"]} → {rt["target"]})'
        )

    prompt = f"""## 实体抽取指令

请从以下文本中抽取实体和关系。

### 实体类型
{chr(10).join(type_descriptions)}

### 关系类型
{chr(10).join(relation_descriptions)}

### 输出格式（严格 JSON）
```json
{{
  "entities": [
    {{
      "name": "实体名称",
      "type": "实体类型名",
      "properties": {{
        "属性名": "属性值"
      }}
    }}
  ],
  "relations": [
    {{
      "type": "关系类型名",
      "source_name": "源实体名称",
      "target_name": "目标实体名称"
    }}
  ]
}}
```

### 待抽取文本
{text_chunk}
"""
    return prompt


def generate_entity_id(entity: dict, entity_types: list) -> str:
    """根据实体类型定义的 id_pattern 生成实体 ID"""
    name = entity.get("name", "unknown")
    et_name = entity.get("type", "")

    # 查找匹配的实体类型定义
    id_pattern = "ENTITY-{name}"
    for et in entity_types:
        if et["name"] == et_name:
            id_pattern = et.get("id_pattern", f"{et_name.upper()}-{{name}}")
            break

    # 清理名称用于 ID
    clean_name = re.sub(r'[^\w\u4e00-\u9fff-]', '-', name).strip("-")
    return id_pattern.replace("{name}", clean_name)


def scan_markdown_files(input_dir: Path) -> list:
    """扫描目录下的 Markdown 文件"""
    files = []
    for md_file in sorted(input_dir.rglob("*.md")):
        files.append(md_file)
    return files


def load_existing_entities(output_path: Path) -> dict:
    """加载已有的实体数据"""
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entities": [], "relations": []}


def merge_entities(new_entities: list, existing: dict, entity_types: list) -> dict:
    """
    合并新抽取的实体到已有数据中。
    基于 (name, type) 去重。
    """
    existing_map = {}
    for e in existing["entities"]:
        key = (e.get("name", ""), e.get("type", ""))
        existing_map[key] = e

    for e in new_entities:
        key = (e.get("name", ""), e.get("type", ""))
        if key in existing_map:
            # 合并属性（新属性覆盖旧属性）
            for k, v in e.get("properties", {}).items():
                existing_map[key].setdefault("properties", {})[k] = v
            # 合并来源
            if "sources" not in existing_map[key]:
                existing_map[key]["sources"] = []
            existing_map[key]["sources"].extend(e.get("sources", []))
        else:
            # 生成 ID
            e["id"] = generate_entity_id(e, entity_types)
            existing_map[key] = e

    existing["entities"] = list(existing_map.values())
    return existing


def merge_relations(new_relations: list, existing: dict) -> dict:
    """合并关系数据，基于 (type, source, target) 去重"""
    existing_set = set()
    for r in existing.get("relations", []):
        key = (r.get("type", ""), r.get("source", ""), r.get("target", ""))
        existing_set.add(key)

    for r in new_relations:
        key = (r.get("type", ""), r.get("source", ""), r.get("target", ""))
        if key not in existing_set:
            existing.setdefault("relations", []).append(r)
            existing_set.add(key)

    return existing


def generate_report(data: dict, entity_types: list, output_dir: Path):
    """生成图谱审计报告"""
    entities = data.get("entities", [])
    relations = data.get("relations", [])

    type_counts = defaultdict(int)
    for e in entities:
        type_counts[e.get("type", "unknown")] += 1

    relation_counts = defaultdict(int)
    for r in relations:
        relation_counts[r.get("type", "unknown")] += 1

    lines = [
        "# 知识图谱审计报告",
        "",
        f"> 生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "---",
        "",
        "## 概览",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 实体总数 | {len(entities)} |",
        f"| 关系总数 | {len(relations)} |",
        "",
        "## 实体类型分布",
        "",
        "| 类型 | 数量 |",
        "|------|------|",
    ]

    type_map = {et["name"]: et["display_name"] for et in entity_types}
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        display = type_map.get(t, t)
        lines.append(f"| {display} ({t}) | {c} |")

    lines.extend([
        "",
        "## 关系类型分布",
        "",
        "| 关系类型 | 数量 |",
        "|----------|------|",
    ])

    for rt, c in sorted(relation_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {rt} | {c} |")

    # 缺失属性检查
    required_missing = []
    for et in entity_types:
        required_props = [p["name"] for p in et.get("properties", []) if p.get("required")]
        type_entities = [e for e in entities if e.get("type") == et["name"]]
        for e in type_entities:
            props = e.get("properties", {})
            for rp in required_props:
                if not props.get(rp):
                    required_missing.append(f"  - {et['display_name']}「{e.get('name', '?')}」缺少「{rp}」")

    if required_missing:
        lines.extend(["", "## 缺失必要属性", ""])
        lines.extend(required_missing)

    lines.extend(["", "---", "", "*由 KnowledgeGraph 自动生成*"])

    report_path = output_dir / "GRAPH_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="KnowledgeGraph — AI 实体抽取（框架）")
    parser.add_argument("--config", required=True, help="领域配置文件路径")
    parser.add_argument("--input", required=True, help="Markdown 文件目录 (converted/)")
    parser.add_argument("--output", required=True, help="输出文件路径 (entities.json)")
    parser.add_argument("--data-root", required=True, help="数据根目录")
    parser.add_argument("--generate-prompts-only", action="store_true",
                        help="仅生成抽取 prompt 文件（不执行抽取）")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    input_dir = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    data_root = Path(args.data_root).resolve()

    config = load_config(str(config_path))
    entity_types = config.get("entity_types", [])
    relation_types = config.get("relation_types", [])

    print(f"KnowledgeGraph — 实体抽取")
    print(f"  实体类型: {len(entity_types)} 种")
    print(f"  关系类型: {len(relation_types)} 种")
    print(f"  输入目录: {input_dir}")
    print(f"  输出文件: {output_path}")
    print("")

    # 扫描 Markdown 文件
    md_files = scan_markdown_files(input_dir)
    print(f"[OK] 找到 {len(md_files)} 个 Markdown 文件")

    if not md_files:
        print("[WARN] 未找到 Markdown 文件。请先运行 ingest。")
        sys.exit(0)

    # 加载已有实体
    existing_data = load_existing_entities(output_path)
    if existing_data.get("entities"):
        print(f"[OK] 已有 {len(existing_data['entities'])} 个实体，将合并")

    if args.generate_prompts_only:
        # 仅生成 prompt 文件
        prompts_dir = data_root / "graphify-out" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        prompt_count = 0
        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            # 按标题分块
            chunks = re.split(r'\n(?=#{1,3}\s)', content)
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 50:
                    continue
                prompt = build_extraction_prompt(entity_types, relation_types, chunk)
                chunk_hash = hashlib.md5(chunk.encode()).hexdigest()[:8]
                prompt_file = prompts_dir / f"{md_file.stem}_{i}_{chunk_hash}.txt"
                prompt_file.write_text(prompt, encoding="utf-8")
                prompt_count += 1

        print(f"[OK] 生成 {prompt_count} 个抽取 prompt 到 {prompts_dir}")
        print("")
        print("注意：prompt 文件已生成。请使用 LLM 对每个 prompt 文件执行抽取，")
        print("然后将结果 JSON 保存到 graphify-out/extractions/ 目录。")
        print("之后可运行: python3 scripts/merge-extractions.py --extractions graphify-out/extractions/ --output graphify-out/entities.json")
        return

    # 完整流程说明
    print("")
    print("=== AI 实体抽取流程 ===")
    print("")
    print("此脚本提供了实体抽取的框架和工具函数。")
    print("由于需要 LLM 能力执行实际抽取，建议由 Agent 直接调用以下函数：")
    print("")
    print("  1. scan_markdown_files(input_dir) — 获取 Markdown 文件列表")
    print("  2. build_extraction_prompt(entity_types, relation_types, chunk) — 构建抽取 prompt")
    print("  3. merge_entities(results, existing_data, entity_types) — 合并去重")
    print("  4. merge_relations(relations, data) — 合并关系")
    print("  5. generate_report(data, entity_types, output_dir) — 生成报告")
    print("")
    print("或者使用 --generate-prompts-only 生成 prompt 文件后手动处理。")
    print("")
    print(f"已加载的实体类型定义已准备好，可直接用于抽取。")

    # 生成报告（即使没有新数据）
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 实体数据已保存到: {output_path}")

    generate_report(existing_data, entity_types, output_path.parent)
    print(f"[OK] 审计报告已生成: {output_path.parent}/GRAPH_REPORT.md")


if __name__ == "__main__":
    main()
