"""
github_push.py — 将 ~/.workbuddy/skills/ 全量推送到 GitHub

使用方法：
  python ~/.workbuddy/skills/skill-sync/scripts/github_push.py

无需任何参数。自动扫描 skills 目录，通过 GitHub Git Data API 创建 commit 并推送。
适合在 git push 直连失败（网络超时）时使用。

PAT 配置（三选一，优先级从高到低）：
  1. 环境变量：set GITHUB_PAT=ghp_xxx  （Windows）
  2. 配置文件：~/.workbuddy/skill-sync.conf（写入 GITHUB_PAT=ghp_xxx）
  3. 脚本运行时提示输入
"""
import os
import sys
import base64
import json
import urllib.request
import urllib.error
from datetime import datetime

# ========== 基本配置 ==========
SKILLS_DIR = os.path.expanduser("~/.workbuddy/skills")
OWNER = "kunmingsong1-creator"
REPO = "workbuddy-skills"
BRANCH = "main"
API_BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".idea", ".vscode"}
SKIP_EXTS = {".db", ".zip", ".tar", ".gz", ".7z", ".exe", ".dll"}
SKIP_FILES = {"server.log", "server_output.txt", "skill-sync.conf"}
# ==============================


def load_token():
    """从环境变量或配置文件读取 PAT，不在代码中硬编码"""
    # 1. 环境变量
    token = os.environ.get("GITHUB_PAT", "").strip()
    if token:
        return token
    # 2. 配置文件
    conf = os.path.expanduser("~/.workbuddy/skill-sync.conf")
    if os.path.exists(conf):
        with open(conf, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GITHUB_PAT=") and not line.startswith("#"):
                    t = line.split("=", 1)[1].strip()
                    if t:
                        return t
    # 3. 交互输入
    print("  ⚠️  未找到 GitHub PAT")
    print("  💡 建议：在 ~/.workbuddy/skill-sync.conf 中写入 GITHUB_PAT=ghp_xxx")
    token = input("  请输入 GitHub PAT：").strip()
    if not token:
        print("  ❌ PAT 为空，退出")
        sys.exit(1)
    return token


# 加载 token（模块级，全局可用）
_TOKEN = load_token()


def api_req(method, endpoint, data=None, timeout=30):
    """发送 GitHub API 请求"""
    url = f"{API_BASE}{endpoint}"
    headers = {
        "Authorization": f"token {_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "skill-sync/1.0"
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ API Error {method} {endpoint}: {e.code}")
        print(f"     {err_body[:400]}")
        raise
    except Exception as e:
        print(f"  ❌ 网络错误：{e}")
        raise


def collect_files():
    """扫描本地 skills 目录，收集所有需要同步的文件"""
    files = {}
    skipped = []
    for root, dirs, names in os.walk(SKILLS_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if name in SKIP_FILES:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in SKIP_EXTS:
                skipped.append(name)
                continue
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, SKILLS_DIR).replace("\\", "/")
            try:
                with open(full_path, "rb") as f:
                    files[rel_path] = f.read()
            except Exception as e:
                skipped.append(f"{rel_path} (读取失败: {e})")
    return files, skipped


def push_to_github():
    print("=" * 55)
    print("🚀 skill-sync: 开始同步 Skills → GitHub")
    print(f"   本地路径：{SKILLS_DIR}")
    print(f"   目标仓库：https://github.com/{OWNER}/{REPO}")
    print("=" * 55)

    # 1. 收集文件
    print("\n📦 扫描本地文件...")
    files, skipped = collect_files()
    print(f"   发现 {len(files)} 个文件")
    if skipped:
        print(f"   跳过 {len(skipped)} 个（大文件/临时文件）")

    if not files:
        print("  ⚠️  没有找到任何文件，退出")
        sys.exit(1)

    # 2. 获取远程 HEAD
    print("\n🔍 获取远程 HEAD...")
    ref = api_req("GET", f"/git/ref/heads/{BRANCH}")
    base_commit_sha = ref["object"]["sha"]
    base_tree_sha = api_req("GET", f"/git/commits/{base_commit_sha}")["tree"]["sha"]
    print(f"   HEAD: {base_commit_sha[:8]}")

    # 3. 创建 blobs
    print(f"\n📝 上传文件（{len(files)} 个）...")
    tree_items = []
    for i, (path, content) in enumerate(sorted(files.items())):
        blob = api_req("POST", "/git/blobs", {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64"
        })
        tree_items.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"]
        })
        if (i + 1) % 50 == 0:
            print(f"   进度：{i+1}/{len(files)}")

    print(f"   ✅ 全部上传完成")

    # 4. 创建 tree
    print("\n🌲 创建 Git tree...")
    tree = api_req("POST", "/git/trees", {
        "base_tree": base_tree_sha,
        "tree": tree_items
    })

    # 5. 创建 commit
    commit_msg = f"sync: {datetime.now().strftime('%Y-%m-%d %H:%M')} ({len(files)} files)"
    print(f"\n📋 创建 commit...")
    commit = api_req("POST", "/git/commits", {
        "message": commit_msg,
        "tree": tree["sha"],
        "parents": [base_commit_sha]
    })
    print(f"   Commit: {commit['sha'][:8]}")

    # 6. 更新分支
    print(f"\n🔄 更新 {BRANCH} 分支指针...")
    api_req("PATCH", f"/git/refs/heads/{BRANCH}", {
        "sha": commit["sha"],
        "force": True
    })

    print("\n" + "=" * 55)
    print("✅ 同步成功！")
    print(f"   🔗 仓库：https://github.com/{OWNER}/{REPO}")
    print(f"   📊 文件数：{len(files)}")
    print(f"   📌 提交：{commit['sha'][:8]}")
    print(f"   💬 消息：{commit_msg}")
    print("=" * 55)
    return {"files": len(files), "commit": commit["sha"][:8]}


if __name__ == "__main__":
    try:
        push_to_github()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 同步失败：{e}")
        sys.exit(1)
