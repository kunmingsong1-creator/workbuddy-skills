#!/usr/bin/env python3
"""
KnowledgeGraph — ingest.py
文档摄入：将文档导入系统，完成 L1(原始) → L2(Markdown) 转换。

用法：
    python3 scripts/ingest.py --source "/path/to/doc.pdf" --category technical --data-root ./my-data

流程：
    1. 计算源文件 SHA-256 哈希
    2. 复制到 sources/{category}/ 并锁定
    3. 追加到 manifest.jsonl
    4. 运行 MarkItDown 转换为 Markdown
    5. 记录到 Wiki 操作日志
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: 需要 PyYAML。请运行: pip install pyyaml")
    sys.exit(1)


def compute_sha256(file_path: Path) -> str:
    """计算文件的 SHA-256 哈希"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest_path: Path) -> list:
    """加载 manifest.jsonl"""
    if not manifest_path.exists():
        return []
    records = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def append_manifest(manifest_path: Path, record: dict):
    """追加一条记录到 manifest.jsonl"""
    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_markitdown(source_file: Path, output_dir: Path) -> Path:
    """
    运行 MarkItDown 将文档转为 Markdown。
    优先使用 CLI，失败时回退到 Python API。
    返回输出的 Markdown 文件路径。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / (source_file.stem + ".md")

    # 策略1: CLI
    cli_cmd = [
        "markitdown",
        "--all-conversions",
        "--code-blocks",
        "--full-paths",
        str(source_file),
        "-o", str(output_file),
    ]

    try:
        result = subprocess.run(
            cli_cmd, capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0 and output_file.exists():
            return output_file
        print(f"[WARN] MarkItDown CLI 失败 (rc={result.returncode}): {result.stderr[:200]}")
    except FileNotFoundError:
        print("[WARN] MarkItDown CLI 不可用，尝试 Python API...")
    except subprocess.TimeoutExpired:
        print("[WARN] MarkItDown CLI 超时，尝试 Python API...")

    # 策略2: Python API
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(str(source_file))
        output_file.write_text(result.text_content, encoding="utf-8")
        return output_file
    except ImportError:
        print("ERROR: MarkItDown 未安装。请运行: pip install 'markitdown[all]'")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: MarkItDown Python API 失败: {e}")
        sys.exit(1)


def append_to_wiki_log(data_root: Path, action: str, details: dict):
    """追加到 Wiki 操作日志"""
    log_path = data_root / "wiki" / "log.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "",
        f"## [{timestamp}] {action}",
        "",
    ]
    for k, v in details.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def load_config(data_root: Path) -> dict:
    """加载全局配置"""
    config_path = data_root / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def main():
    parser = argparse.ArgumentParser(description="KnowledgeGraph — 文档摄入")
    parser.add_argument("--source", required=True, help="源文件路径")
    parser.add_argument("--category", required=True, help="文档分类（对应 domain_config 中的 categories）")
    parser.add_argument("--data-root", required=True, help="数据根目录")
    args = parser.parse_args()

    source_file = Path(args.source).resolve()
    data_root = Path(args.data_root).resolve()
    category = args.category

    # 校验
    if not source_file.exists():
        print(f"ERROR: 源文件不存在: {source_file}")
        sys.exit(1)

    if not (data_root / "sources" / "manifest.jsonl").exists():
        print(f"ERROR: 数据目录未初始化。请先运行: python3 scripts/init.py")
        sys.exit(1)

    file_size_mb = source_file.stat().st_size / (1024 * 1024)
    print(f"KnowledgeGraph — 文档摄入")
    print(f"  源文件: {source_file.name} ({file_size_mb:.1f} MB)")
    print(f"  分类: {category}")
    print("")

    # 1. 计算哈希
    sha = compute_sha256(source_file)
    print(f"[OK] SHA-256: {sha[:16]}...")

    # 2. 检查是否已存在
    manifest = load_manifest(data_root / "sources" / "manifest.jsonl")
    for record in manifest:
        if record.get("sha256") == sha:
            print(f"[SKIP] 文件已存在（哈希匹配）: {record.get('original_name')}")
            print(f"       已转换到: {record.get('converted_dir')}")
            sys.exit(0)

    # 3. 复制到 sources/
    category_dir = data_root / "sources" / category
    category_dir.mkdir(parents=True, exist_ok=True)
    target_file = category_dir / source_file.name
    shutil.copy2(str(source_file), str(target_file))

    # 4. 追加 manifest
    record = {
        "sha256": sha,
        "original_name": source_file.name,
        "category": category,
        "target_path": str(target_file.relative_to(data_root)),
        "size_bytes": source_file.stat().st_size,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "converted": False,
    }
    append_manifest(data_root / "sources" / "manifest.jsonl", record)
    print(f"[OK] 已复制到: sources/{category}/{source_file.name}")

    # 5. MarkItDown 转换
    converted_dir = data_root / "converted" / sha
    print(f"[...] 转换中 (MarkItDown)...")
    output_file = run_markitdown(target_file, converted_dir)

    if output_file.exists():
        record["converted"] = True
        record["converted_dir"] = str(converted_dir.relative_to(data_root))
        record["converted_file"] = str(output_file.relative_to(data_root))
        print(f"[OK] 已转换到: {record['converted_dir']}")
    else:
        print(f"[FAIL] 转换失败: {source_file.name}")

    # 更新 manifest（追加更新记录）
    append_manifest(data_root / "sources" / "manifest.jsonl", {
        "sha256": sha,
        "action": "converted",
        "converted": record["converted"],
        "converted_dir": record.get("converted_dir", ""),
        "converted_at": datetime.now(timezone.utc).isoformat(),
    })

    # 6. 记录日志
    append_to_wiki_log(data_root, "文档摄入", {
        "文件名": source_file.name,
        "分类": category,
        "SHA-256": sha[:16] + "...",
        "大小": f"{file_size_mb:.1f} MB",
        "转换状态": "成功" if record["converted"] else "失败",
    })

    print("")
    print("--- 摄入完成 ---")
    print(f"  源文件: sources/{category}/{source_file.name}")
    if record["converted"]:
        print(f"  转换产物: {record['converted_dir']}/")
    print("")
    print("下一步: python3 scripts/extract-entities.py --config domain_config.yaml --input converted/ --output graphify-out/entities.json")


if __name__ == "__main__":
    main()
