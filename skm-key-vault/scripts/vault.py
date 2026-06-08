#!/usr/bin/env python3
"""
Key Vault - 加密密钥管理工具
使用 Fernet 对称加密 + PBKDF2 密钥派生，安全存储 API Keys、密码、Token 等。

用法:
  python3 vault.py init <master_password>           # 初始化保险库
  python3 vault.py add <master_password> <name> <value> [--category cat] [--note note]  # 添加条目
  python3 vault.py get <master_password> <name>     # 获取条目
  python3 vault.py list <master_password> [--category cat]  # 列出条目（值脱敏）
  python3 vault.py delete <master_password> <name>   # 删除条目
  python3 vault.py search <master_password> <keyword> # 搜索条目
  python3 vault.py export <master_password>          # 导出所有（含明文值）
"""

import sys
import os
import json
import base64
import hashlib
from datetime import datetime

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    print("ERROR: cryptography library not installed. Run: pip3 install cryptography")
    sys.exit(1)

# 保险库文件路径（与脚本同目录）
VAULT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_FILE = os.path.join(VAULT_DIR, "vault.enc")
SALT_FILE = os.path.join(VAULT_DIR, "salt.bin")
META_FILE = os.path.join(VAULT_DIR, "meta.json")

# PBKDF2 参数
ITERATIONS = 600_000  # OWASP 推荐


def derive_key(password: str, salt: bytes = None) -> tuple:
    """从主密码派生加密密钥，返回 (key, salt)"""
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    return key, salt


def encrypt_data(data: dict, password: str) -> None:
    """加密并保存数据到文件"""
    key, salt = derive_key(password)
    fernet = Fernet(key)
    plaintext = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    ciphertext = fernet.encrypt(plaintext)

    with open(SALT_FILE, "wb") as f:
        f.write(salt)
    with open(VAULT_FILE, "wb") as f:
        f.write(ciphertext)


def decrypt_data(password: str) -> dict:
    """解密并读取数据"""
    if not os.path.exists(VAULT_FILE) or not os.path.exists(SALT_FILE):
        return {"entries": {}}

    with open(SALT_FILE, "rb") as f:
        salt = f.read()
    with open(VAULT_FILE, "rb") as f:
        ciphertext = f.read()

    key, _ = derive_key(password, salt)
    fernet = Fernet(key)

    try:
        plaintext = fernet.decrypt(ciphertext)
    except Exception:
        print("ERROR: 主密码错误或保险库文件已损坏")
        sys.exit(1)

    return json.loads(plaintext.decode("utf-8"))


def load_meta() -> dict:
    """加载元数据（未加密，仅存条目名称列表和统计）"""
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(meta: dict) -> None:
    """保存元数据"""
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def mask_value(value: str) -> str:
    """脱敏显示：只显示前4位和后4位"""
    if len(value) <= 8:
        return value[:2] + "***" + value[-2:] if len(value) > 4 else "****"
    return value[:4] + "****" + value[-4:]


def cmd_init(password: str) -> None:
    """初始化保险库"""
    if os.path.exists(VAULT_FILE):
        print("WARNING: 保险库已存在。如需重置请先删除 vault.enc 和 salt.bin")
        sys.exit(1)

    data = {"entries": {}, "created_at": datetime.now().isoformat()}
    encrypt_data(data, password)

    meta = {"entry_count": 0, "created_at": datetime.now().isoformat(), "names": []}
    save_meta(meta)

    print("OK: 保险库已初始化")


def cmd_add(password: str, name: str, value: str, category: str = "default", note: str = "") -> None:
    """添加条目"""
    data = decrypt_data(password)

    if name in data["entries"]:
        print(f"WARNING: 条目 '{name}' 已存在，将覆盖更新")

    data["entries"][name] = {
        "value": value,
        "category": category,
        "note": note,
        "updated_at": datetime.now().isoformat(),
    }

    encrypt_data(data, password)

    # 更新 meta
    meta = load_meta()
    meta["entry_count"] = len(data["entries"])
    meta["names"] = sorted(data["entries"].keys())
    save_meta(meta)

    print(f"OK: 已添加条目 '{name}' [分类: {category}]")


def cmd_get(password: str, name: str) -> None:
    """获取条目（显示明文值）"""
    data = decrypt_data(password)

    if name not in data["entries"]:
        # 模糊匹配
        matches = [k for k in data["entries"] if name.lower() in k.lower()]
        if matches:
            print(f"未找到 '{name}'，相似条目：")
            for m in matches:
                entry = data["entries"][m]
                print(f"  - {m} [{entry.get('category', 'default')}]")
            sys.exit(1)
        print(f"ERROR: 条目 '{name}' 不存在")
        sys.exit(1)

    entry = data["entries"][name]
    print(json.dumps({
        "name": name,
        "value": entry["value"],
        "category": entry.get("category", "default"),
        "note": entry.get("note", ""),
        "updated_at": entry.get("updated_at", ""),
    }, ensure_ascii=False, indent=2))


def cmd_list(password: str, category: str = None) -> None:
    """列出所有条目（值脱敏）"""
    data = decrypt_data(password)

    entries = data.get("entries", {})
    if not entries:
        print("保险库为空")
        return

    result = []
    for name, entry in sorted(entries.items()):
        if category and entry.get("category", "default") != category:
            continue
        result.append({
            "name": name,
            "value_masked": mask_value(entry["value"]),
            "category": entry.get("category", "default"),
            "note": entry.get("note", ""),
        })

    if not result:
        print(f"分类 '{category}' 下无条目")
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n共 {len(result)} 条")


def cmd_delete(password: str, name: str) -> None:
    """删除条目"""
    data = decrypt_data(password)

    if name not in data["entries"]:
        print(f"ERROR: 条目 '{name}' 不存在")
        sys.exit(1)

    del data["entries"][name]
    encrypt_data(data, password)

    meta = load_meta()
    meta["entry_count"] = len(data["entries"])
    meta["names"] = sorted(data["entries"].keys())
    save_meta(meta)

    print(f"OK: 已删除条目 '{name}'")


def cmd_search(password: str, keyword: str) -> None:
    """搜索条目"""
    data = decrypt_data(password)

    results = []
    for name, entry in data["entries"].items():
        searchable = f"{name} {entry.get('category', '')} {entry.get('note', '')} {entry['value']}"
        if keyword.lower() in searchable.lower():
            results.append({
                "name": name,
                "value_masked": mask_value(entry["value"]),
                "category": entry.get("category", "default"),
                "note": entry.get("note", ""),
            })

    if not results:
        print(f"未找到匹配 '{keyword}' 的条目")
        return

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n找到 {len(results)} 条")


def cmd_export(password: str) -> None:
    """导出所有条目（含明文值）"""
    data = decrypt_data(password)
    print(json.dumps(data["entries"], ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "init":
        if len(sys.argv) < 3:
            print("Usage: vault.py init <master_password>")
            sys.exit(1)
        cmd_init(sys.argv[2])

    elif command == "add":
        if len(sys.argv) < 5:
            print("Usage: vault.py add <master_password> <name> <value> [--category cat] [--note note]")
            sys.exit(1)
        pw, name, value = sys.argv[2], sys.argv[3], sys.argv[4]
        category = "default"
        note = ""
        i = 5
        while i < len(sys.argv):
            if sys.argv[i] == "--category" and i + 1 < len(sys.argv):
                category = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--note" and i + 1 < len(sys.argv):
                note = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        cmd_add(pw, name, value, category, note)

    elif command == "get":
        if len(sys.argv) < 4:
            print("Usage: vault.py get <master_password> <name>")
            sys.exit(1)
        cmd_get(sys.argv[2], sys.argv[3])

    elif command == "list":
        category = None
        if len(sys.argv) >= 4 and sys.argv[3]:
            category = sys.argv[3]
        if len(sys.argv) < 3:
            print("Usage: vault.py list <master_password> [--category cat]")
            sys.exit(1)
        # parse optional --category
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--category" and i + 1 < len(sys.argv):
                category = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        cmd_list(sys.argv[2], category)

    elif command == "delete":
        if len(sys.argv) < 4:
            print("Usage: vault.py delete <master_password> <name>")
            sys.exit(1)
        cmd_delete(sys.argv[2], sys.argv[3])

    elif command == "search":
        if len(sys.argv) < 4:
            print("Usage: vault.py search <master_password> <keyword>")
            sys.exit(1)
        cmd_search(sys.argv[2], sys.argv[3])

    elif command == "export":
        if len(sys.argv) < 3:
            print("Usage: vault.py export <master_password>")
            sys.exit(1)
        cmd_export(sys.argv[2])

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
