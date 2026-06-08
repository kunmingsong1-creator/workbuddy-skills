---
name: skm-密钥保险库
version: 1.0.0
description: 加密密钥保险库 — 用主密码保护所有 API Key、密码、Token，支持分类管理和快速检索
author: agent_created
agent_created: true
tags:
  - security
  - secrets
  - api-key
  - password
  - vault
disable: false
---

# Key Vault — 密钥保险库

用主密码保护所有 API Key、密码、Token 等敏感信息，支持分类管理和快速检索。

## 触发条件

用户提到以下关键词时激活此 Skill：
- "密钥"、"密码"、"key"、"secret"、"token"、"api key"、"凭据"、"凭证"
- "我的 xxx key 是什么"、"查一下 xxx 的密码"
- "存一下这个 key"、"添加一个密钥"

## 核心参数

- **主密码**: `1235`（用户授权密码，解密保险库时必须提供）
- **保险库位置**: `~/.workbuddy/skills/key-vault/scripts/vault.enc`
- **脚本位置**: `~/.workbuddy/skills/key-vault/scripts/vault.py`

## 操作流程

### 1. 初始化（仅首次）

```bash
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py init 1235
```

### 2. 添加条目

```bash
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py add 1235 <名称> <值> --category <分类> --note <备注>
```

**分类建议**：
- `api-key` — API 密钥（如 DeepSeek、OpenAI）
- `password` — 账号密码
- `token` — 访问令牌（如 OAuth Token）
- `database` — 数据库连接串
- `ssh` — SSH 密钥
- `other` — 其他

**示例**：
```bash
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py add 1235 "DeepSeek API Key" "sk-12ad045723154aec99f3b09d1e9e523a" --category api-key --note "DeepSeek大模型API"
```

### 3. 获取条目（返回明文值）

```bash
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py get 1235 <名称>
```

支持模糊匹配，如果名称不完全匹配会提示相似条目。

### 4. 列出所有条目（值脱敏显示）

```bash
# 列出全部
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py list 1235

# 按分类筛选
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py list 1235 --category api-key
```

### 5. 搜索条目

```bash
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py search 1235 <关键词>
```

### 6. 删除条目

```bash
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py delete 1235 <名称>
```

### 7. 导出全部（含明文值，谨慎使用）

```bash
python3 ~/.workbuddy/skills/key-vault/scripts/vault.py export 1235
```

## 安全说明

- 使用 PBKDF2-SHA256（600K 次迭代）从主密码派生加密密钥
- 使用 Fernet（AES-128-CBC + HMAC-SHA256）对称加密
- `meta.json` 仅存储条目名称列表，不含敏感值
- `vault.enc` 为加密文件，无主密码无法读取
- 主密码 `1235` 硬编码在 Skill 中方便使用，如需更高安全性可修改为每次手动输入

## Agent 行为规范

1. 用户要求存储密钥时，**直接使用 `add` 命令存储**，不需要确认
2. 用户要求查询密钥时，**直接使用 `get` 或 `search` 命令**，显示完整值
3. 用户要求列出密钥时，**使用 `list` 命令**，显示脱敏值
4. 主密码已在 Skill 中记录，**不需要每次询问用户**
5. 查询结果中包含敏感值时，**仅在对话中展示，不写入文件**
6. 如果用户提供了新的密钥但没给名称，**智能推断名称**（如根据内容判断是哪个服务的 key）
