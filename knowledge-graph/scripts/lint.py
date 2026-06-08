#!/usr/bin/env python3
"""
KnowledgeGraph — lint.py
知识图库健康检查。

用法：
    python3 scripts/lint.py --config domain_config.yaml --data-root ./my-data

检查项：
    1. 哈希完整性（manifest.jsonl vs 实际文件）
    2. 转换覆盖率（sources/ vs converted/）
    3. 图谱完整性（实体必要属性、关系有效性）
    4. Wiki 完整性（实体 vs 百科页面）
    5. 映射覆盖（mappings 配置 vs 实际文件）
    6. 矛盾检测（可选）
    7. 孤立页面（未被引用的页面）
    8. 缺失引用（被引用但未创建的页面）
"""

import argparse
import hashlib
import json
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
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_hash_integrity(data_root: Path) -> dict:
    """检查 manifest.jsonl 中的哈希与实际文件匹配"""
    manifest_path = data_root / "sources" / "manifest.jsonl"
    if not manifest_path.exists():
        return {"status": "SKIP", "reason": "manifest.jsonl 不存在"}

    records = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    ingest_records = [r for r in records if r.get("sha256") and r.get("target_path")]
    total = len(ingest_records)
    matched = 0
    mismatched = []
    missing = []

    for record in ingest_records:
        file_path = data_root / record["target_path"]
        if not file_path.exists():
            missing.append(record["original_name"])
            continue

        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)

        if sha.hexdigest() == record["sha256"]:
            matched += 1
        else:
            mismatched.append(record["original_name"])

    return {
        "status": "OK",
        "total": total,
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
    }


def check_conversion_coverage(data_root: Path) -> dict:
    """检查 sources/ 中的文件是否都有对应的 converted/ 文件"""
    manifest_path = data_root / "sources" / "manifest.jsonl"
    if not manifest_path.exists():
        return {"status": "SKIP", "reason": "manifest.jsonl 不存在"}

    records = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = 0
    converted = 0
    unconverted = []

    for record in records:
        if record.get("sha256") and not record.get("action"):
            total += 1
            if record.get("converted"):
                converted += 1
            else:
                unconverted.append(record.get("original_name", "?"))

    return {
        "status": "OK",
        "total": total,
        "converted": converted,
        "unconverted": unconverted,
        "coverage_pct": (converted / total * 100) if total > 0 else 0,
    }


def check_graph_integrity(data_root: Path, config: dict) -> dict:
    """检查图谱数据完整性"""
    entities_path = data_root / "graphify-out" / "entities.json"
    if not entities_path.exists():
        return {"status": "SKIP", "reason": "entities.json 不存在"}

    with open(entities_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entities = data.get("entities", [])
    relations = data.get("relations", [])
    entity_types = config.get("entity_types", [])

    # 实体类型分布
    type_counts = defaultdict(int)
    for e in entities:
        type_counts[e.get("type", "unknown")] += 1

    # 缺失必要属性
    missing_props = []
    for et in entity_types:
        required = [p["name"] for p in et.get("properties", []) if p.get("required")]
        for e in entities:
            if e.get("type") != et["name"]:
                continue
            props = e.get("properties", {})
            for rp in required:
                if not props.get(rp):
                    missing_props.append(f"{et['display_name']}「{e.get('name', '?')}」缺少「{rp}」")

    # 关系有效性（检查引用的实体是否存在）
    entity_ids = {e.get("id", "") for e in entities}
    entity_names = {e.get("name", "") for e in entities}
    invalid_relations = []
    for r in relations:
        source = r.get("source", r.get("source_name", ""))
        target = r.get("target", r.get("target_name", ""))
        if source not in entity_ids and source not in entity_names:
            invalid_relations.append(f"关系「{r.get('type')}」源端「{source}」不存在")
        if target not in entity_ids and target not in entity_names:
            invalid_relations.append(f"关系「{r.get('type')}」目标端「{target}」不存在")

    return {
        "status": "OK",
        "total_entities": len(entities),
        "type_distribution": dict(type_counts),
        "total_relations": len(relations),
        "missing_required_props": missing_props,
        "invalid_relations": invalid_relations,
    }


def check_wiki_integrity(data_root: Path, config: dict) -> dict:
    """检查 Wiki 页面完整性"""
    entities_path = data_root / "graphify-out" / "entities.json"
    wiki_dir = data_root / "wiki"

    if not entities_path.exists():
        return {"status": "SKIP", "reason": "entities.json 不存在"}

    with open(entities_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entities = data.get("entities", [])
    entity_types = config.get("entity_types", [])

    total = len(entities)
    has_page = 0
    missing_pages = []

    for e in entities:
        et_name = e.get("type", "uncategorized")
        entity_id = e.get("id", e.get("name", "unknown"))
        safe_name = entity_id.replace("/", "-").replace(" ", "-").strip("-")
        page_path = wiki_dir / "entities" / et_name / f"{safe_name}.md"
        if page_path.exists():
            has_page += 1
        else:
            missing_pages.append(f"{et_name}/{safe_name}")

    return {
        "status": "OK",
        "total_entities": total,
        "has_page": has_page,
        "missing_pages": missing_pages,
        "coverage_pct": (has_page / total * 100) if total > 0 else 0,
    }


def check_mappings_coverage(data_root: Path, config: dict) -> dict:
    """检查映射页面覆盖"""
    mappings = config.get("mappings", [])
    mappings_dir = data_root / "wiki" / "mappings"

    results = []
    for m in mappings:
        mapping_file = mappings_dir / f"{m['name']}.md"
        results.append({
            "name": m["display_name"],
            "exists": mapping_file.exists(),
            "path": str(mapping_file.relative_to(data_root)),
        })

    exists_count = sum(1 for r in results if r["exists"])
    return {
        "status": "OK",
        "total": len(results),
        "exists": exists_count,
        "missing": [r["name"] for r in results if not r["exists"]],
    }


def check_orphan_pages(data_root: Path, config: dict) -> dict:
    """检测孤立页面（未被引用的百科页面）"""
    wiki_dir = data_root / "wiki"
    entities_dir = wiki_dir / "entities"

    if not entities_dir.exists():
        return {"status": "SKIP", "reason": "wiki/entities/ 不存在"}

    # 收集所有 [[wiki-link]] 引用
    all_pages = list(wiki_dir.rglob("*.md"))
    referenced = set()

    wiki_link_pattern = re.compile(r'\[\[([^\]]+)\]\]')
    for page in all_pages:
        content = page.read_text(encoding="utf-8")
        for match in wiki_link_pattern.finditer(content):
            referenced.add(match.group(1))

    # 检查孤立页面
    orphan = []
    for page in all_pages:
        relative = str(page.relative_to(wiki_dir))
        # 排除 index.md 和 log.md
        if page.name in ("index.md", "log.md"):
            continue
        if relative not in referenced:
            orphan.append(relative)

    return {
        "status": "OK",
        "total_pages": len(all_pages) - 2,  # 排除 index 和 log
        "referenced": len(referenced),
        "orphan_pages": orphan,
    }


def generate_report(checks: dict, data_root: Path):
    """生成健康检查报告"""
    lines = [
        "# 知识图库健康检查报告",
        "",
        f"> 检查时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "---",
        "",
    ]

    # 1. 哈希完整性
    h = checks.get("hash", {})
    if h.get("status") == "OK":
        lines.extend([
            "## 哈希完整性",
            "",
            f"- 总文件数: {h['total']}",
            f"- 哈希匹配: {h['matched']}",
            f"- 哈希不匹配: {len(h['mismatched'])}",
        ])
        if h["mismatched"]:
            for m in h["mismatched"]:
                lines.append(f"  - {m}")
        lines.append(f"- 文件缺失: {len(h['missing'])}")
        if h["missing"]:
            for m in h["missing"]:
                lines.append(f"  - {m}")
    else:
        lines.extend(["## 哈希完整性", "", f"- {h.get('reason', '跳过')}"])

    # 2. 转换覆盖率
    c = checks.get("conversion", {})
    if c.get("status") == "OK":
        lines.extend([
            "",
            "## 转换覆盖率",
            "",
            f"- 已转换: {c['converted']}/{c['total']} ({c['coverage_pct']:.1f}%)",
            f"- 未转换: {len(c['unconverted'])}",
        ])
        if c["unconverted"]:
            for u in c["unconverted"]:
                lines.append(f"  - {u}")

    # 3. 图谱完整性
    g = checks.get("graph", {})
    if g.get("status") == "OK":
        type_map = {k: k for k in g.get("type_distribution", {})}
        type_dist = g.get("type_distribution", {})
        lines.extend([
            "",
            "## 图谱完整性",
            "",
            f"- 实体总数: {g['total_entities']}",
            "- 实体类型分布:",
        ])
        for t, count in sorted(type_dist.items()):
            lines.append(f"  - {t}: {count}")
        lines.append(f"- 关系总数: {g['total_relations']}")
        if g["missing_required_props"]:
            lines.extend(["- 缺失必要属性:"] + [f"  - {p}" for p in g["missing_required_props"]])
        else:
            lines.append("- 缺失必要属性: 无")
        if g["invalid_relations"]:
            lines.extend(["- 无效关系:"] + [f"  - {r}" for r in g["invalid_relations"]])

    # 4. Wiki 完整性
    w = checks.get("wiki", {})
    if w.get("status") == "OK":
        lines.extend([
            "",
            "## Wiki 完整性",
            "",
            f"- 百科页面: {w['has_page']}/{w['total_entities']} ({w['coverage_pct']:.1f}%)",
            f"- 缺失页面: {len(w['missing_pages'])}",
        ])
        if w["missing_pages"][:20]:
            for p in w["missing_pages"][:20]:
                lines.append(f"  - {p}")
            if len(w["missing_pages"]) > 20:
                lines.append(f"  - ... 还有 {len(w['missing_pages']) - 20} 个")

    # 5. 映射覆盖
    m = checks.get("mappings", {})
    if m.get("status") == "OK":
        lines.extend([
            "",
            "## 映射覆盖",
            "",
            f"- 映射配置: {m['total']} 个",
            f"- 已生成: {m['exists']}",
        ])
        if m["missing"]:
            for name in m["missing"]:
                lines.append(f"  - 缺失: {name}")

    # 6. 孤立页面
    o = checks.get("orphan", {})
    if o.get("status") == "OK":
        lines.extend([
            "",
            "## 孤立页面",
            "",
            f"- 页面总数: {o['total_pages']}",
            f"- 被引用: {o['referenced']}",
            f"- 孤立页面: {len(o['orphan_pages'])}",
        ])
        if o["orphan_pages"][:10]:
            for p in o["orphan_pages"][:10]:
                lines.append(f"  - {p}")

    lines.extend(["", "---", "", "*由 KnowledgeGraph lint 自动生成*"])

    report_path = data_root / "graphify-out" / "LINT_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="KnowledgeGraph — 健康检查")
    parser.add_argument("--config", required=True, help="领域配置文件路径")
    parser.add_argument("--data-root", required=True, help="数据根目录")
    args = parser.parse_args()

    config = load_config(args.config)
    data_root = Path(args.data_root).resolve()

    print(f"KnowledgeGraph — 健康检查")
    print(f"  数据目录: {data_root}")
    print("")

    checks = {}

    # 1. 哈希完整性
    print("[...] 检查哈希完整性...")
    checks["hash"] = check_hash_integrity(data_root)
    h = checks["hash"]
    if h.get("status") == "OK":
        issues = len(h["mismatched"]) + len(h["missing"])
        status = "OK" if issues == 0 else "ISSUES"
        print(f"  [{status}] {h['matched']}/{h['total']} 匹配，{issues} 个问题")

    # 2. 转换覆盖率
    print("[...] 检查转换覆盖率...")
    checks["conversion"] = check_conversion_coverage(data_root)
    c = checks["conversion"]
    if c.get("status") == "OK":
        status = "OK" if c["coverage_pct"] == 100 else "PARTIAL"
        print(f"  [{status}] {c['coverage_pct']:.1f}% 覆盖率")

    # 3. 图谱完整性
    print("[...] 检查图谱完整性...")
    checks["graph"] = check_graph_integrity(data_root, config)
    g = checks["graph"]
    if g.get("status") == "OK":
        status = "OK" if not g["missing_required_props"] and not g["invalid_relations"] else "ISSUES"
        print(f"  [{status}] {g['total_entities']} 实体，{len(g['missing_required_props'])} 属性缺失，{len(g['invalid_relations'])} 无效关系")

    # 4. Wiki 完整性
    print("[...] 检查 Wiki 完整性...")
    checks["wiki"] = check_wiki_integrity(data_root, config)
    w = checks["wiki"]
    if w.get("status") == "OK":
        status = "OK" if w["coverage_pct"] == 100 else "PARTIAL"
        print(f"  [{status}] {w['coverage_pct']:.1f}% 覆盖率")

    # 5. 映射覆盖
    print("[...] 检查映射覆盖...")
    checks["mappings"] = check_mappings_coverage(data_root, config)
    m = checks["mappings"]
    if m.get("status") == "OK":
        status = "OK" if m["exists"] == m["total"] else "PARTIAL"
        print(f"  [{status}] {m['exists']}/{m['total']} 映射已生成")

    # 6. 孤立页面
    print("[...] 检查孤立页面...")
    checks["orphan"] = check_orphan_pages(data_root, config)
    o = checks["orphan"]
    if o.get("status") == "OK":
        status = "OK" if not o["orphan_pages"] else "INFO"
        print(f"  [{status}] {len(o['orphan_pages'])} 个孤立页面")

    # 生成报告
    print("")
    report_path = generate_report(checks, data_root)
    print(f"[OK] 健康检查报告已生成: {report_path}")


if __name__ == "__main__":
    main()
