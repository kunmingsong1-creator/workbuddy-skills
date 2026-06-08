#!/usr/bin/env python3
"""
skm-skill-manager 统一编排脚本 v2.0.0
=====================================
将 skill-trend-analyzer + skm-skill-sync 的能力封装为统一入口。

用法：
  python skill_ctl.py list                    # 列出所有 Skill
  python skill_ctl.py stats                   # 统计汇总
  python skill_ctl.py check <skill-name>      # 质量检查
  python skill_ctl.py check --batch           # 批量质量检查
  python skill_ctl.py optimize <skill-name>   # 触发词优化
  python skill_ctl.py scan                    # 深度扫描
  python skill_ctl.py trend                   # 趋势分析
  python skill_ctl.py sync [push|pull|sync]   # GitHub 同步
  python skill_ctl.py clean <skill-name>      # 深度卸载
  python skill_ctl.py clean --list            # 列出可卸载
"""

import sys
import os
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime

SKILLS_DIR = Path.home() / ".workbuddy" / "skills"
ANALYZER_SCRIPTS = SKILLS_DIR / "skill-trend-analyzer" / "scripts"
SYNC_SCRIPTS = SKILLS_DIR / "skm-skill-sync" / "scripts"
MANAGER_SCRIPTS = SKILLS_DIR / "skm-skill-manager" / "scripts"

SKIP_DIRS = {"_removed", ".git", "__pycache__", "node_modules"}


def run_script(script_path, *args, timeout=60):
    """安全调用 Python 脚本"""
    cmd = [sys.executable, str(script_path)] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=False, timeout=timeout)
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"  ⚠️  脚本执行超时（{timeout}s）：{script_path.name}")
        return 1
    except FileNotFoundError:
        print(f"  ❌ 脚本不存在：{script_path}")
        return 1


def cmd_list():
    """列出所有 Skill 摘要"""
    print("\n📋 Skill 清单\n" + "=" * 80)

    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue

        # 解析 frontmatter
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        fm = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    line = line.strip()
                    if ":" in line:
                        key, val = line.split(":", 1)
                        fm[key.strip()] = val.strip().strip('"').strip("'")

        name = fm.get("name", d.name)
        version = fm.get("version", "-")
        desc = fm.get("description", "-")
        agent_created = fm.get("agent_created", "").lower() == "true"
        tags = fm.get("tags", "").strip("[]").replace('"', '')

        # 分类
        if name.startswith("skm-") and agent_created:
            stype = "🏠自建"
        elif "connector" in tags.lower() or "connector" in name.lower():
            stype = "🔌连接器"
        else:
            stype = "📦第三方"

        skills.append((name, version, stype, desc[:50], tags))

    # 排序：自建在前
    skills.sort(key=lambda x: (0 if "自建" in x[2] else 1, x[0]))

    print(f"{'名称':<35} {'版本':<8} {'类型':<10} {'描述':<52} Tags")
    print("-" * 120)
    for name, ver, stype, desc, tags in skills:
        print(f"{name:<35} {ver:<8} {stype:<10} {desc:<52} {tags}")

    # 统计
    self_built = sum(1 for s in skills if "自建" in s[2])
    third = sum(1 for s in skills if "第三方" in s[2])
    connector = sum(1 for s in skills if "连接器" in s[2])
    print(f"\n总计: {len(skills)} 个 Skill")
    print(f"  🏠 自建（skm-前缀）: {self_built} 个")
    print(f"  📦 第三方: {third} 个")
    print(f"  🔌 连接器: {connector} 个")
    print("=" * 80)


def cmd_stats():
    """仅统计"""
    self_built = 0
    third_party = 0
    connector = 0
    total = 0

    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
            continue
        if not (d / "SKILL.md").exists():
            continue
        total += 1

        content = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        is_self = False
        is_agt = False
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k, v = k.strip(), v.strip()
                        if k == "name" and v.startswith("skm-"):
                            is_self = True
                        if k == "agent_created" and v.lower() == "true":
                            is_agt = True
                        if k == "tags" and "connector" in v.lower():
                            connector += 1

        if is_self and is_agt:
            self_built += 1
        elif "connector" in content[:200].lower():
            connector += 1
        else:
            third_party += 1

    print(f"\n📊 Skill 统计")
    print(f"  总计: {total} 个 Skill")
    print(f"  🏠 自建: {self_built} 个")
    print(f"  📦 第三方: {third_party} 个")
    print(f"  🔌 连接器: {connector} 个")


def cmd_check(skill_name=None, batch=False, deps=False, fix=False):
    """质量检查 — 委托给 skill-trend-analyzer"""
    script = ANALYZER_SCRIPTS / "skill_quality_checker.py"
    args = []
    if batch:
        args.append("--batch")
    elif skill_name:
        skill_path = SKILLS_DIR / skill_name
        if not skill_path.exists():
            print(f"  ❌ Skill 不存在：{skill_name}")
            return 1
        args.append(str(skill_path))
    else:
        args.append(str(ANALYZER_SCRIPTS.parent))  # 默认检查自身

    if deps:
        args.append("--deps")
    if fix:
        args.append("--fix")

    return run_script(script, *args)


def cmd_optimize(skill_name=None, batch=False):
    """触发词优化 — 委托给 skill-trend-analyzer"""
    script = ANALYZER_SCRIPTS / "skill_optimizer.py"
    args = []
    if batch:
        args.append("--batch")
    elif skill_name:
        skill_path = SKILLS_DIR / skill_name
        args.append(str(skill_path))
    return run_script(script, *args)


def cmd_scan(verbose=False):
    """深度扫描"""
    script = ANALYZER_SCRIPTS / "local_skill_scanner.py"
    args = ["--verbose"] if verbose else []
    return run_script(script, *args)


def cmd_trend():
    """趋势分析"""
    script = ANALYZER_SCRIPTS / "trend_analyzer.py"
    return run_script(script)


def cmd_sync(mode="sync"):
    """GitHub 同步"""
    script = MANAGER_SCRIPTS / "github_sync.py"
    return run_script(script, mode)


def cmd_clean(skill_name=None, dry_run=False, deep=False, list_only=False):
    """深度卸载"""
    script = ANALYZER_SCRIPTS / "skill_cleaner.py"
    args = []
    if list_only:
        args.append("--list")
    elif skill_name:
        args.append(skill_name)
        if dry_run:
            args.append("--dry-run")
        if deep:
            args.append("--deep-scan")
            args.append("--clean")
    return run_script(script, *args)


def print_usage():
    print(__doc__)


# ========== Main ==========

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "list": lambda: cmd_list(),
        "stats": lambda: cmd_stats(),
        "check": lambda: cmd_check(
            skill_name=args[0] if args and not args[0].startswith("--") else None,
            batch="--batch" in args,
            deps="--deps" in args,
            fix="--fix" in args,
        ),
        "optimize": lambda: cmd_optimize(
            skill_name=args[0] if args and not args[0].startswith("--") else None,
            batch="--batch" in args,
        ),
        "scan": lambda: cmd_scan(verbose="--verbose" in args),
        "trend": lambda: cmd_trend(),
        "sync": lambda: cmd_sync(mode=args[0] if args else "sync"),
        "clean": lambda: cmd_clean(
            skill_name=args[0] if args and not args[0].startswith("--") else None,
            dry_run="--dry-run" in args,
            deep="--deep-scan" in args,
            list_only="--list" in args,
        ),
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"  ❌ 未知命令：{cmd}")
        print_usage()
        sys.exit(1)
