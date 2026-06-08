#!/usr/bin/env python3
"""
KnowledgeGraph — sync.py
多平台同步：将 Wiki 内容同步到乐享/IMA/WPS 等知识库平台。

用法：
    python3 scripts/sync.py --config domain_config.yaml --scope wiki --data-root ./my-data

注意：
    此脚本提供同步框架和配置解析。
    实际同步操作通过对应平台的 MCP 工具执行（需在 WorkBuddy 中调用）。
"""

import argparse
import json
import sys
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


def collect_sync_items(data_root: Path, scope: list, config: dict) -> list:
    """
    收集需要同步的文件和内容。
    返回待同步项列表。
    """
    items = []
    wiki_dir = data_root / "wiki"

    if "wiki" in scope:
        # 收集所有百科页面
        for md_file in sorted(wiki_dir.rglob("*.md")):
            if md_file.name in ("index.md", "log.md"):
                continue
            relative = md_file.relative_to(data_root)
            items.append({
                "type": "wiki_page",
                "path": str(relative),
                "absolute_path": str(md_file),
                "content": md_file.read_text(encoding="utf-8"),
            })

    if "mappings" in scope:
        # 收集映射页面
        mappings_dir = wiki_dir / "mappings"
        if mappings_dir.exists():
            for md_file in sorted(mappings_dir.glob("*.md")):
                relative = md_file.relative_to(data_root)
                items.append({
                    "type": "mapping",
                    "path": str(relative),
                    "absolute_path": str(md_file),
                    "content": md_file.read_text(encoding="utf-8"),
                })

    if "sources" in scope:
        # 收集原始文件（二进制，不读取内容）
        manifest_path = data_root / "sources" / "manifest.jsonl"
        if manifest_path.exists():
            for line in open(manifest_path, "r", encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("sha256") and record.get("target_path"):
                    file_path = data_root / record["target_path"]
                    if file_path.exists():
                        items.append({
                            "type": "source_file",
                            "path": record["target_path"],
                            "absolute_path": str(file_path),
                            "original_name": record.get("original_name", ""),
                            "category": record.get("category", ""),
                            "size_bytes": file_path.stat().st_size,
                        })

    return items


def generate_sync_plan(items: list, config: dict) -> dict:
    """
    生成同步计划。
    返回按平台组织的同步指令。
    """
    sync_config = config.get("sync", {})
    platform = sync_config.get("platform", "local")
    platform_config = sync_config.get("config", {})

    # 按类型分组
    wiki_pages = [i for i in items if i["type"] in ("wiki_page", "mapping")]
    source_files = [i for i in items if i["type"] == "source_file"]

    plan = {
        "platform": platform,
        "config": platform_config,
        "wiki_pages": len(wiki_pages),
        "source_files": len(source_files),
        "total_items": len(items),
        "instructions": [],
    }

    if platform == "lexiang":
        plan["instructions"].extend([
            "### 乐享知识库同步",
            "",
            f"使用 MCP 工具 `mcp__lexiang__entry_import_content` 导入百科页面。",
            f"使用 MCP 工具 `mcp__lexiang__file_apply_upload` 上传原始文件。",
            f"space_id: {platform_config.get('space_id', '未配置')}",
            "",
            "**Wiki 页面导入步骤**:",
            "1. 对每个百科页面，调用 `mcp__lexiang__entry_import_content`",
            "2. content_type: 'markdown'",
            "3. parent_entry_id: 需要在乐享中先创建对应的文件夹结构",
            "",
            "**原始文件上传步骤**:",
            "1. 对每个原始文件，先调用 `mcp__lexiang__file_apply_upload` 获取上传凭证",
            "2. 使用 curl PUT 上传文件到返回的 upload_url",
            "3. 调用 `mcp__lexiang__file_commit_upload` 确认上传",
        ])

    elif platform == "ima":
        plan["instructions"].extend([
            "### IMA 知识库同步",
            "",
            "使用 MCP 工具 `mcp__ima-mcp__*` 系列工具。",
            f"知识库名称: {platform_config.get('kb_name', '未配置')}",
            "",
            "**同步步骤**:",
            "1. 原始文件 → `mcp__ima-mcp__search_knowledge` + 知识库上传",
            "2. 百科页面 → `mcp__ima-mcp__search_knowledge` + 笔记写入",
        ])

    elif platform == "wps":
        plan["instructions"].extend([
            "### WPS 云文档同步",
            "",
            "使用 MCP 工具 `mcp__kdocs__*` 系列工具。",
            "",
            "**同步步骤**:",
            "1. Wiki 页面 → `mcp__kdocs__create_file_with_content` 创建文档",
            "2. 原始文件 → `mcp__kdocs__upload_file` 上传文件",
        ])

    else:
        plan["instructions"].extend([
            "### 本地同步",
            "",
            "platform=local，不执行远程同步。",
            "如需同步到外部平台，请在 domain_config.yaml 中配置 sync.platform。",
        ])

    return plan


def main():
    parser = argparse.ArgumentParser(description="KnowledgeGraph — 多平台同步")
    parser.add_argument("--config", required=True, help="领域配置文件路径")
    parser.add_argument("--data-root", required=True, help="数据根目录")
    parser.add_argument("--scope", nargs="+", default=["wiki", "mappings"],
                        help="同步范围: wiki, mappings, sources")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅生成同步计划，不执行同步")
    parser.add_argument("--output-plan", type=str, default=None,
                        help="将同步计划保存为 JSON 文件")
    args = parser.parse_args()

    config = load_config(args.config)
    data_root = Path(args.data_root).resolve()

    print(f"KnowledgeGraph — 同步")
    sync_cfg = config.get("sync", {})
    platform = sync_cfg.get("platform", "local")
    print(f"  平台: {platform}")
    print(f"  范围: {', '.join(args.scope)}")
    print(f"  数据目录: {data_root}")
    print("")

    # 1. 收集待同步项
    items = collect_sync_items(data_root, args.scope, config)
    print(f"[OK] 收集到 {len(items)} 个待同步项")

    # 2. 生成同步计划
    plan = generate_sync_plan(items, config)
    print(f"[OK] 同步计划已生成（平台: {plan['platform']}）")
    print(f"  - Wiki/映射页面: {plan['wiki_pages']}")
    print(f"  - 原始文件: {plan['source_files']}")

    # 3. 输出同步计划
    print("")
    print("=== 同步计划 ===")
    for line in plan["instructions"]:
        print(line)

    if args.dry_run or args.output_plan:
        if args.output_plan:
            plan_path = Path(args.output_plan)
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
            print(f"\n[OK] 同步计划已保存到: {plan_path}")
        else:
            print("\n[INFO] Dry-run 模式，未执行同步。")
            print("同步计划（JSON）:")
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    # 4. 执行提示
    print("")
    print("--- 同步说明 ---")
    print("实际同步需要通过对应平台的 MCP 工具执行。")
    print("请在 WorkBuddy 中使用对应的 MCP 连接器调用同步工具。")
    print("")
    print("乐享: mcp__lexiang__entry_import_content, mcp__lexiang__file_apply_upload")
    print("IMA:  mcp__ima-mcp__*")
    print("WPS:  mcp__kdocs__*")


if __name__ == "__main__":
    main()
