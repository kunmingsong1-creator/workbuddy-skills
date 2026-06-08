"""
github_sync.py — 双向同步 ~/.workbuddy/skills/ ←→ GitHub
支持：推送本地变更 + 拉取 GitHub 最新版本

使用方法：
  python ~/.workbuddy/skills/skm-skill-manager/scripts/github_sync.py [push|pull|sync]
  - 无参数：自动判断（本地版本落后则 pull，否则 push）
  - push：仅推送
  - pull：仅拉取
  - sync：先 pull 再 push（推荐）

PAT 配置优先级（高→低）：
  1. 环境变量   GITHUB_PAT
  2. 配置文件   ~/.workbuddy/skill-sync.conf（GITHUB_PAT=xxx）
  3. Key Vault   skm-key-vault skill（github-pat）

版本判断：比较本地 skm-skill-manager/SKILL.md 中 version 字段 vs GitHub 最新 commit
来源：skm-skill-manager/scripts/github_sync.py（复制自 skm-skill-sync）
"""

import os
import sys
import base64
import json
import urllib.request
import urllib.error
import re
from datetime import datetime

# ========== 基本配置 ==========
SKILLS_DIR = os.path.expanduser("~/.workbuddy/skills")
OWNER = "kunmingsong1-creator"
REPO = "workbuddy-skills"
BRANCH = "main"
API_BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".idea", ".vscode"}
SKIP_EXTS = {".db", ".zip", ".tar", ".gz", ".7z", ".exe", ".dll"}
SKIP_FILES = {"server.log", "server_output.txt", "skill-sync.conf", ".DS_Store"}
# ===============================


def load_token():
    """按优先级读取 PAT

    优先级（高→低）：
      1. 环境变量   GITHUB_PAT
      2. 配置文件   ~/.workbuddy/skill-sync.conf（GITHUB_PAT=xxx）
      3. Key Vault   key-vault skill（github-pat）— 仅当前两者都没命中时尝试
    """
    # 1. 环境变量
    token = os.environ.get("GITHUB_PAT", "").strip()
    if token:
        return token, "环境变量"

    # 2. 配置文件
    conf = os.path.expanduser("~/.workbuddy/skill-sync.conf")
    if os.path.exists(conf):
        with open(conf, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GITHUB_PAT=") and not line.startswith("#"):
                    t = line.split("=", 1)[1].strip()
                    if t:
                        return t, "配置文件"

    # 3. Key Vault（兜底，短超时防 hang）
    try:
        import subprocess
        vault_script = os.path.expanduser("~/.workbuddy/skills/skm-key-vault/scripts/vault.py")
        if os.path.exists(vault_script):
            r = subprocess.run(
                ["python3", vault_script, "get", "1235", "github-pat"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                t = r.stdout.strip()
                if t and not t.startswith("错误") and not t.startswith("未找到"):
                    return t, "Key Vault"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    print("  ❌ 未找到 GitHub PAT")
    print("  💡 请在 ~/.workbuddy/skill-sync.conf 中写入 GITHUB_PAT=ghp_xxx")
    sys.exit(1)


def api_req(method, endpoint, data=None, timeout=30):
    """发送 GitHub API 请求"""
    url = f"{API_BASE}{endpoint}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "skill-sync/2.0"
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ API Error {e.code} {method} {endpoint}")
        print(f"     {err_body[:300]}")
        raise
    except Exception as e:
        print(f"  ❌ 网络错误：{e}")
        raise


def get_remote_version():
    """获取 GitHub 上 skm-skill-manager/SKILL.md 的 version 字段"""
    try:
        content = api_req("GET", f"/contents/skm-skill-manager/SKILL.md?ref={BRANCH}")
        decoded = base64.b64decode(content["content"]).decode("utf-8")
        m = re.search(r'^version:\s*["\']?([^\s"\'\\n]+)', decoded, re.MULTILINE)
        if m:
            return m.group(1), content["sha"]
    except Exception as e:
        print(f"  ⚠️  无法读取远程版本：{e}")
    return None, None


def get_local_version():
    """获取本地 skm-skill-manager/SKILL.md 的 version 字段"""
    path = os.path.join(SKILLS_DIR, "skm-skill-manager", "SKILL.md")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'^version:\s*["\']?([^\s"\'\\n]+)', content, re.MULTILINE)
    return m.group(1) if m else None


def version_compare(local, remote):
    """比较版本号，返回 -1/0/1"""
    def parse(v):
        return [int(x) for x in (v or "0").split(".")]
    lp = parse(local)
    rp = parse(remote)
    return (lp > rp) - (lp < rp)  # -1, 0, 1


def pull_from_github(target_skills=None):
    """从 GitHub 拉取最新 skills

    target_skills: 可选，指定只拉取哪些 skill 目录（如 ['skill-sync']）
                   为 None 则拉取全部（慎用，文件多会很慢）
    """
    if target_skills:
        print(f"\n⬇️  拉取指定 skills：{', '.join(target_skills)}")
    else:
        print("\n⬇️  从 GitHub 拉取最新 Skills（全量）...")

    # 获取远程 tree
    ref = api_req("GET", f"/git/ref/heads/{BRANCH}")
    commit = api_req("GET", f"/git/commits/{ref['object']['sha']}")
    tree_sha = commit["tree"]["sha"]
    tree = api_req("GET", f"/git/trees/{tree_sha}?recursive=1")

    files_pulled = 0
    for item in tree.get("tree", []):
        if item["type"] != "blob":
            continue
        path = item["path"]
        # 跳过配置文件
        if path == "skill-sync.conf":
            continue
        # 如果指定了 skill，只拉取对应路径
        if target_skills:
            if not any(path.startswith(s + "/") or path == s + "/SKILL.md" for s in target_skills):
                continue

        local_path = os.path.join(SKILLS_DIR, path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # 获取文件内容
        try:
            blob = api_req("GET", f"/git/blobs/{item['sha']}", timeout=15)
            content = base64.b64decode(blob["content"]).decode("utf-8")
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(content)
            files_pulled += 1
        except Exception as e:
            print(f"  ⚠️  跳过 {path}：{e}")

    print(f"   ✅ 拉取完成：{files_pulled} 个文件")
    return files_pulled


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


def get_remote_tree():
    """获取远程仓库完整文件树（path → sha 映射）"""
    ref = api_req("GET", f"/git/ref/heads/{BRANCH}")
    commit = api_req("GET", f"/git/commits/{ref['object']['sha']}")
    tree = api_req("GET", f"/git/trees/{commit['tree']['sha']}?recursive=1")
    remote_files = {}
    for item in tree.get("tree", []):
        if item["type"] == "blob":
            remote_files[item["path"]] = item["sha"]
    return remote_files, ref["object"]["sha"], commit["tree"]["sha"]


def compute_local_shas(files):
    """计算本地文件的 git blob SHA（无需 API 调用）"""
    import hashlib

    def git_blob_sha(content_bytes):
        """计算 git blob SHA-1（与 GitHub 一致）"""
        header = f"blob {len(content_bytes)}\0".encode()
        return hashlib.sha1(header + content_bytes).hexdigest()

    result = {}
    for path, content in files.items():
        result[path] = git_blob_sha(content)
    return result


def push_to_github():
    """增量推送本地 skills 到 GitHub（仅上传变化的文件）"""
    print("\n⬆️  推送本地 Skills → GitHub...")

    files, skipped = collect_files()
    if skipped:
        print(f"   跳过 {len(skipped)} 个文件（二进制/临时文件）")

    if not files:
        print("  ⚠️  没有找到任何文件")
        return 0

    # 获取远程 tree
    print("   🔍 对比远程仓库...")
    remote_files, base_commit_sha, base_tree_sha = get_remote_tree()

    # 计算本地文件 SHA
    local_shas = compute_local_shas(files)

    # 找出变化的文件（新增 + 修改）
    changed = {}
    for path, local_sha in local_shas.items():
        if path not in remote_files or remote_files[path] != local_sha:
            changed[path] = files[path]

    # 找出远程有但本地没有的文件（需要从 tree 中移除）
    deleted_paths = [p for p in remote_files if p not in local_shas]

    if not changed and not deleted_paths:
        print("   ✅ 本地与远程一致，无需推送")
        return 0

    print(f"   📝 变化：{len(changed)} 个文件更新，{len(deleted_paths)} 个文件删除")

    # 构建 tree items（变化的文件上传 blob，删除的文件标记移除）
    tree_items = []
    for i, (path, content) in enumerate(sorted(changed.items())):
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
            print(f"     上传进度：{i+1}/{len(changed)}")

    # 删除的文件：从 tree 中移除
    for path in sorted(deleted_paths):
        tree_items.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": None  # null sha = 从 tree 中移除
        })

    # 创建 tree + commit
    tree = api_req("POST", "/git/trees", {
        "base_tree": base_tree_sha,
        "tree": tree_items
    })
    commit_msg = f"sync: {datetime.now().strftime('%Y-%m-%d %H:%M')} ({len(changed)} changed, {len(deleted_paths)} deleted)"
    commit = api_req("POST", "/git/commits", {
        "message": commit_msg,
        "tree": tree["sha"],
        "parents": [base_commit_sha]
    })

    # 更新分支指针
    api_req("PATCH", f"/git/refs/heads/{BRANCH}", {
        "sha": commit["sha"],
        "force": False
    })

    print(f"   ✅ 推送成功！Commit: {commit['sha'][:8]}（{len(changed)} 变更 + {len(deleted_paths)} 删除）")
    return len(changed)


def save_token_to_conf(token):
    """将 PAT 写入配置文件"""
    conf = os.path.expanduser("~/.workbuddy/skill-sync.conf")
    lines = []
    found = False
    if os.path.exists(conf):
        with open(conf, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GITHUB_PAT="):
                    lines.append(f"GITHUB_PAT={token}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"GITHUB_PAT={token}\n")

    with open(conf, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"   ✅ PAT 已写入 {conf}")


# ========== 主流程 ==========

print("=" * 55)
print("🚀 skill-sync v2.0 — 双向同步")
print("=" * 55)

# 加载 token
TOKEN, token_source = load_token()
print(f"🔑 PAT 来源：{token_source}")

mode = sys.argv[1] if len(sys.argv) > 1 else "sync"

# 版本检查（仅 sync / pull 模式）
if mode in ("sync", "pull"):
    print("\n🔍 检查版本...")
    local_ver = get_local_version()
    remote_ver, remote_sha = get_remote_version()
    print(f"   本地版本：{local_ver or '未知'}")
    print(f"   远程版本：{remote_ver or '未知'}")

    if remote_ver and local_ver:
        cmp = version_compare(local_ver, remote_ver)
        if cmp < 0:
            print(f"   ⬇️  本地 {local_ver} < 远程 {remote_ver}，需要拉取")
            # 只拉取 skm-skill-manager 自身（版本号在 skm-skill-manager/SKILL.md 中）
            pull_from_github(target_skills=["skm-skill-manager"])
        elif cmp > 0:
            print(f"   ⬆️  本地 {local_ver} > 远程 {remote_ver}，需要推送")
        else:
            print(f"   ✅ 版本一致 ({local_ver})")

if mode in ("sync", "push"):
    if mode == "sync":
        # sync 模式：pull 完再 push
        n = push_to_github()
    else:
        n = push_to_github()
    print(f"\n📊 推送完成：{n} 个文件")

if mode == "pull":
    # pull 单独调用时上面已经拉过了（版本检查里）
    pass

print("\n" + "=" * 55)
print("✅ 同步完成！")
print(f"   🔗 https://github.com/{OWNER}/{REPO}")
print("=" * 55)
