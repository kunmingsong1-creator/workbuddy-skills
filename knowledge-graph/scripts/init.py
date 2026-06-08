#!/usr/bin/env python3
"""
KnowledgeGraph — init.py
初始化领域知识图库的数据目录结构。

用法：
    python3 scripts/init.py --config domain_config.yaml --data-root ./my-data

读取 domain_config.yaml 中的实体类型、关系类型、分类和映射定义，
自动创建完整的数据目录结构、初始 Wiki 页面和全局配置。
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: 需要 PyYAML。请运行: pip install pyyaml")
    sys.exit(1)


def load_config(config_path: str) -> dict:
    """加载领域配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_directory_structure(data_root: Path, config: dict) -> list:
    """根据领域配置创建目录结构，返回创建的目录列表"""
    dirs_created = []

    # L1: sources 子目录
    categories = config.get("categories", [])
    for cat in categories:
        cat_dir = data_root / "sources" / cat["name"]
        cat_dir.mkdir(parents=True, exist_ok=True)
        dirs_created.append(str(cat_dir.relative_to(data_root)))

    # L2: converted 目录
    converted_dir = data_root / "converted"
    converted_dir.mkdir(parents=True, exist_ok=True)
    dirs_created.append("converted/")

    # L3: graphify-out 目录
    graph_dir = data_root / "graphify-out"
    graph_dir.mkdir(parents=True, exist_ok=True)
    dirs_created.append("graphify-out/")

    # L4: wiki 子目录
    wiki_dir = data_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    # 按 entity_types 创建实体目录
    entity_types = config.get("entity_types", [])
    for et in entity_types:
        entity_dir = wiki_dir / "entities" / et["name"]
        entity_dir.mkdir(parents=True, exist_ok=True)
        dirs_created.append(f"wiki/entities/{et['name']}/")

    # concepts 目录
    (wiki_dir / "concepts").mkdir(parents=True, exist_ok=True)
    dirs_created.append("wiki/concepts/")

    # mappings 目录
    mappings = config.get("mappings", [])
    if mappings:
        (wiki_dir / "mappings").mkdir(parents=True, exist_ok=True)
        dirs_created.append("wiki/mappings/")

    return dirs_created


def generate_index_md(data_root: Path, config: dict):
    """生成 Wiki 总索引页面"""
    domain = config.get("domain", {})
    entity_types = config.get("entity_types", [])
    mappings = config.get("mappings", [])

    lines = [
        f"# {domain.get('name', '知识图库')} — 百科索引",
        "",
        f"> {domain.get('description', '')}",
        "",
        f"> 最后更新：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "---",
        "",
        "## 实体目录",
        "",
    ]

    for et in entity_types:
        count = len(list((data_root / "wiki" / "entities" / et["name"]).glob("*.md")))
        lines.append(f"- [{et['display_name']}](entities/{et['name']}/) — {count} 条")

    lines.extend([
        "",
        "## 概念目录",
        "",
        "- [概念页面](concepts/)",
        "",
    ])

    if mappings:
        lines.extend(["## 映射页面", ""])
        for m in mappings:
            lines.append(f"- [{m['display_name']}](mappings/{m['name']}.md)")

    lines.extend(["", "---", "", "*由 KnowledgeGraph 自动生成*"])

    index_path = data_root / "wiki" / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")


def generate_log_md(data_root: Path):
    """生成操作日志文件"""
    lines = [
        "# 操作日志",
        "",
        f"> 知识库初始化于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "---",
        "",
    ]
    (data_root / "wiki" / "log.md").write_text("\n".join(lines), encoding="utf-8")


def generate_manifest(data_root: Path):
    """生成空的 manifest.jsonl"""
    manifest_path = data_root / "sources" / "manifest.jsonl"
    if not manifest_path.exists():
        manifest_path.write_text("", encoding="utf-8")


def generate_global_config(data_root: Path, config: dict, config_path: str):
    """生成全局配置文件 config.yaml"""
    domain = config.get("domain", {})
    sync_config = config.get("sync", {})

    global_config = {
        "data_root": str(data_root.resolve()),
        "domain_config": str(Path(config_path).resolve()),
        "domain_name": domain.get("name", ""),
        "glossary_file": "references/glossary.md",
        "graphify": {
            "output_dir": "graphify-out",
            "languages": ["python", "markdown"],
        },
        "sync": sync_config,
        "security": {
            "source_hash_algorithm": "sha256",
            "source_readonly": True,
            "max_file_size_mb": 200,
        },
    }

    config_yaml_path = data_root / "config.yaml"
    with open(config_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(global_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def main():
    parser = argparse.ArgumentParser(description="KnowledgeGraph — 初始化知识图库数据目录")
    parser.add_argument("--config", required=True, help="领域配置文件路径 (domain_config.yaml)")
    parser.add_argument("--data-root", required=True, help="数据根目录路径")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    data_root = Path(args.data_root).resolve()

    if not config_path.exists():
        print(f"ERROR: 配置文件不存在: {config_path}")
        sys.exit(1)

    config = load_config(str(config_path))
    domain = config.get("domain", {})
    domain_name = domain.get("name", "未知领域")

    print(f"KnowledgeGraph — 初始化知识图库")
    print(f"领域: {domain_name}")
    print(f"数据根目录: {data_root}")
    print("")

    # 1. 创建目录结构
    dirs = create_directory_structure(data_root, config)
    print(f"[OK] 目录结构已创建 ({len(dirs)} 个目录)")

    # 2. 生成初始文件
    generate_index_md(data_root, config)
    print("[OK] Wiki 索引已生成: wiki/index.md")

    generate_log_md(data_root)
    print("[OK] 操作日志已生成: wiki/log.md")

    generate_manifest(data_root)
    print("[OK] 文件清单已生成: sources/manifest.jsonl")

    generate_global_config(data_root, config, str(config_path))
    print("[OK] 全局配置已生成: config.yaml")

    # 3. 汇总
    entity_types = config.get("entity_types", [])
    categories = config.get("categories", [])
    print("")
    print("--- 初始化完成 ---")
    print(f"  领域: {domain_name}")
    print(f"  实体类型: {len(entity_types)} 种")
    print(f"  文档分类: {len(categories)} 个")
    print(f"  数据目录: {data_root}")
    print("")
    print("下一步: python3 scripts/ingest.py --source <文件> --category <分类> --data-root " + str(data_root))


if __name__ == "__main__":
    main()
