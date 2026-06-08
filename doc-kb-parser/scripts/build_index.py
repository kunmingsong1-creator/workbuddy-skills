#!/usr/bin/env python3
"""
build_index.py — 扫描 MD 文件，解析 YAML frontmatter，生成总索引表

用法：
    python3 build_index.py ./output/ -o ./output/MASTER_INDEX.csv
    python3 build_index.py ./output/ -o ./output/MASTER_INDEX.csv --json
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def parse_frontmatter(md_path: str) -> dict:
    """
    从 MD 文件中解析 YAML frontmatter

    Args:
        md_path: MD 文件路径

    Returns:
        dict: frontmatter 中的键值对，不含解析失败的
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {}

    # 匹配 YAML frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    yaml_text = match.group(1)
    metadata = {"_source_md": str(md_path)}

    for line in yaml_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # key: value 格式
        kv_match = re.match(r'^(\w[\w-]*)\s*:\s*(.*)$', line)
        list_match = re.match(r'^-\s+(.+)$', line)

        if kv_match and not list_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip()

            # 清理引号
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            # 数字类型转换
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass

            metadata[key] = value

        elif list_match and metadata:
            # 添加到上一个 key 对应的列表
            last_key = list(metadata.keys())[-1]
            if last_key != "_source_md":
                item_value = list_match.group(1).strip().strip('"').strip("'")
                if isinstance(metadata[last_key], list):
                    metadata[last_key].append(item_value)
                elif metadata.get(last_key) in (None, "", []):
                    # key 后面是空值或空字符串，初始化为列表
                    metadata[last_key] = [item_value]
                else:
                    # key 已有非空值，转为列表
                    metadata[last_key] = [metadata[last_key], item_value]

    return metadata


def build_master_index(output_dir: str, index_path: str,
                       format: str = "csv") -> list:
    """
    扫描目录中的所有 MD 文件，解析 frontmatter，生成总索引表

    Args:
        output_dir: MD 文件所在目录
        index_path: 索引文件输出路径
        format: "csv" 或 "json"

    Returns:
        list: 索引记录列表
    """
    output_dir = Path(output_dir)

    # 标准索引字段（保持一致的列顺序）
    STANDARD_FIELDS = [
        "id",
        "source",           # 原始文件名
        "vendor",           # 厂商
        "doc_type",         # 文档类型
        "format",           # 文件格式
        "slides",           # 幻灯片数（PPT）
        "duration",         # 时长（视频）
        "extracted_images",  # 提取图片数
        "smartart_pages",   # SmartArt 页码
        "slide_screenshots",# 截图数
        "keyframes",        # 关键帧数
        "key_topics",       # 主题关键词
        "language",         # 语言（视频）
        "tables_count",     # 表格数
        "charts_count",     # 图表数
        "resolution",       # 分辨率（视频）
        "codec",            # 编码（视频）
        "transcription_model",  # 转录模型（视频）
        "transcription_date",   # 转录日期（视频）
        "parsed_at",        # 解析日期
        "parser_version",   # 解析器版本
        "_source_md",       # MD 文件路径（内部用，不导出）
    ]

    # 查找所有 MD 文件（排除 MASTER_INDEX 自身）
    md_files = []
    for f in output_dir.rglob("*.md"):
        if f.name == "MASTER_INDEX.md" or f.name.startswith("MASTER_INDEX"):
            continue
        md_files.append(f)

    if not md_files:
        print(f"在 {output_dir} 中未找到 MD 文件")
        return []

    # 解析所有 MD 文件的 frontmatter
    records = []
    for idx, md_path in enumerate(sorted(md_files), start=1):
        metadata = parse_frontmatter(str(md_path))
        metadata["id"] = idx

        # 将列表转为管道分隔字符串（CSV 兼容）
        for key, value in metadata.items():
            if isinstance(value, list):
                metadata[key] = "|".join(str(v) for v in value)

        # 将 SmartArt 页码列表转为逗号分隔字符串
        if "smartart_pages" in metadata:
            val = metadata["smartart_pages"]
            if isinstance(val, str):
                # 已经是字符串了
                pass
            elif isinstance(val, list):
                metadata["smartart_pages"] = ",".join(str(v) for v in val)

        records.append(metadata)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(index_path)), exist_ok=True)

    if format == "json":
        # JSON 格式
        export_records = []
        for rec in records:
            export = {k: v for k, v in rec.items() if k != "_source_md"}
            export_records.append(export)

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(export_records, f, ensure_ascii=False, indent=2)

        print(f"[JSON] 索引已生成: {index_path}")

    else:
        # CSV 格式
        # 收集所有出现的字段（标准字段 + 额外字段）
        all_keys = set()
        for rec in records:
            all_keys.update(rec.keys())

        # 排序：标准字段在前，其余按字母序
        ordered_fields = [f for f in STANDARD_FIELDS if f in all_keys]
        extra_fields = sorted(k for k in all_keys if k not in STANDARD_FIELDS and k != "_source_md")
        fieldnames = ordered_fields + extra_fields

        # 移除 _source_md（内部字段）
        fieldnames = [f for f in fieldnames if f != "_source_md"]

        # 写入 CSV
        with open(index_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for rec in records:
                row = {k: v for k, v in rec.items() if k in fieldnames}
                writer.writerow(row)

        print(f"[CSV] 索引已生成: {index_path}")
        print(f"  文件数: {len(records)}")
        print(f"  字段数: {len(fieldnames)}")

    return records


def main():
    parser = argparse.ArgumentParser(description="生成总索引表")
    parser.add_argument("input_dir", help="MD 文件所在目录")
    parser.add_argument("-o", "--output", help="索引文件输出路径")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式（默认 CSV）")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)

    # 默认输出路径
    if args.output is None:
        fmt = "json" if args.json else "csv"
        args.output = str(input_dir / f"MASTER_INDEX.{fmt}")

    fmt = "json" if args.json else "csv"
    build_master_index(str(input_dir), args.output, format=fmt)


if __name__ == "__main__":
    main()
