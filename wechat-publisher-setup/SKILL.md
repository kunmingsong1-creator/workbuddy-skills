---
name: wechat-publisher-setup
description: "微信公众号文章排版美化与自动发布 — 封面设计、排版美化、API发布、数据统计，全部在 WorkBuddy 内实现，无需外部 Agent。"
license: MIT
version: 2.0.0
---

# 微信公众号排版发布 — WorkBuddy 原生实现

当用户调用 `/wechat-publisher-setup` 时，执行以下工作流。所有操作在 WorkBuddy 内部完成，无需 OpenClaw / 外部 Agent。

## 概述

将微信发布流水线的全部能力集成到 WorkBuddy 中，分为三大模块：

| 模块 | 能力 | 依赖工具 |
|------|------|---------|
| **视觉设计** | 封面图生成、文章 HTML 排版美化 | ImageGen、HTML/SVG 输出 |
| **API 发布** | 凭证管理、素材上传、草稿创建、发布 | `wechat_publish.cjs` (Node.js 内置模块) |
| **数据分析** | 阅读数据拉取、对比分析、复盘报告 | `wechat_publish.cjs data` + WorkBuddy 分析 |

发布脚本位置：`{baseDir}/scripts/wechat_publish.cjs`

---

## 模块一：凭证配置（首次使用）

### 获取用户凭证
向用户说明：API 对接用于自动化发布和数据拉取。

依次询问：
1. **账号类型**：订阅号 / 服务号
2. **AppID**（公众平台后台 → 开发 → 基本配置）
3. **AppSecret**
4. **是否已将服务器 IP 加入白名单？**

### 写入配置文件

```bash
mkdir -p ~/.openclaw/workspace-wechat-publisher
cat > ~/.openclaw/workspace-wechat-publisher/.env << 'EOF'
WECHAT_APP_ID=用户输入的AppID
WECHAT_APP_SECRET=用户输入的AppSecret
WECHAT_API_BASE=https://api.weixin.qq.com
WECHAT_ACCOUNT_TYPE=用户选择的账号类型
EOF
chmod 600 ~/.openclaw/workspace-wechat-publisher/.env 2>/dev/null || true
```

### 验证连通性
```bash
node {baseDir}/scripts/wechat_publish.cjs token
```

### 错误处理
- token 获取失败 → 检查 AppID/AppSecret、IP 白名单
- 首次配置后即持久化，后续无需重复配置

---

## 模块二：视觉设计（画境能力）

### 2.1 封面图设计

使用 **ImageGen**（文生图能力）或 **SVG/HTML 直接构建**生成公众号封面。

**规格要求：**
- 大图（头条）：**900×383px**（2.35:1）
- 小图（次条）：**200×200px**（1:1）
- 缩略图尺寸下仍有辨识度
- 配色与品牌调性一致

**工作流：**
1. 根据文章标题/摘要确定封面核心视觉元素
2. 确定配色方案（参考已建立的品牌色板）
3. 使用 ImageGen 生成封面图：`ImageGen({ prompt: "..." })`
4. 保存到工作目录：`封面图_文章标题_日期_900x383.png`
5. 检查缩略图效果

### 2.2 文章排版美化

将定稿 Markdown 转化为公众号 HTML 排版方案。

**排版规范：**
| 要素 | 规范 |
|------|------|
| 正文字号 | 16px |
| 行距 | 1.75 |
| 段距 | 15px |
| 背景色 | #FFFFFF |
| 正文色 | #333333 |
| 标题 H1 | 20px, bold, #000000, 居中 |
| 标题 H2 | 18px, bold, #333333 |
| 标题 H3 | 16px, bold, #555555 |
| 引用块 | 左 4px 边框, #DDD, 灰色背景 #F8F8F8, 字号 15px |
| 重点高亮 | 橙色标记或加粗 + 品牌色 |
| 图片 | 100% 宽度或居中 80% |
| 代码块 | 等宽字体, 灰底 #F5F5F5, 圆角 4px |
| 分隔线 | `---` → 浅灰 1px + 居中 |

**输出格式：** 生成完整 HTML 文件供后续发布使用。

**排版原则：**
- **对比**：通过大小、色彩、粗细创造视觉层次
- **对齐**：元素间保持一致对齐方式
- **重复**：品牌元素在各处保持一致
- **亲密性**：相关内容视觉上靠近
- 确保移动端阅读体验（公众号 90%+ 流量来自手机）

---

## 模块三：API 发布（数澜能力）

### 3.1 发布前检查清单

在执行发布操作前逐项确认：
- [ ] 标题无错别字
- [ ] 封面图已生成（大图 900×383px）
- [ ] 文章 HTML 排版已完成，手机端无异常
- [ ] 摘要/简介已填写（64 字以内）
- [ ] `.env` 文件中微信 API 凭证已配置

### 3.2 发布执行流程

**Step 1：验证 API 连通性**
```bash
node {baseDir}/scripts/wechat_publish.cjs token
```

**Step 2：上传封面图**
```bash
node {baseDir}/scripts/wechat_publish.cjs upload-thumb <封面图路径>
```
→ 记录返回的 `thumb_media_id`

正文配图（如有）：
```bash
node {baseDir}/scripts/wechat_publish.cjs upload-image <配图路径>
```
→ 获取图片 URL，替换到 HTML 正文中

**Step 3：组装文章 JSON 并创建草稿**
```json
{
  "articles": [{
    "title": "最终标题",
    "author": "作者名",
    "content": "<p>HTML 格式正文</p>",
    "thumb_media_id": "Step 2 获得的 media_id",
    "digest": "文章摘要（64字以内）",
    "need_open_comment": 1,
    "only_fans_can_comment": 0
  }]
}
```
```bash
node {baseDir}/scripts/wechat_publish.cjs create-draft draft.json
```
→ 记录返回的草稿 `media_id`

**Step 4：用户确认后发布**
向用户展示发布信息（标题、摘要），**获得明确确认后**执行：
```bash
node {baseDir}/scripts/wechat_publish.cjs publish <草稿media_id>
```

**Step 5：确认发布状态**
```bash
node {baseDir}/scripts/wechat_publish.cjs get-status <publish_id>
```

### 安全约束
- **发布操作必须获得用户明确确认**，不可自动发布
- API 凭证存储在 `.env` 文件（权限 600），不泄露
- 不将 AppID/AppSecret 写入任何 Markdown 文件

---

## 模块四：数据分析与复盘（数澜能力）

### 4.1 24h 初步数据报告

发布后 24 小时拉取数据：
```bash
node {baseDir}/scripts/wechat_publish.cjs get-stats <发布日期> <发布日期>
```

分析维度：
| 指标 | 说明 | 健康参考值 |
|------|------|-----------|
| 阅读量 | 文章曝光和点开的总次数 | — |
| 完读率 | 读完全文的读者占比 | > 30% |
| 分享率 | 分享次数/阅读量 | > 3% |
| 新增关注 | 因本篇关注的用户数 | — |

输出评估：超预期 / 符合预期 / 低于预期

### 4.2 48h 完整复盘报告

产出完整分析报告，包含：
- **核心数据全景**：本篇 vs 近 10 篇均值 vs 历史最佳
- **数据洞察**：哪些指标突出/欠缺，可能原因
- **优化建议**：至少 3 条可执行建议，按优先级排序
- **下一篇文章建议**：选题方向、标题策略、发布时间

### 4.3 增长策略建议（月度）

基于累积数据周期性输出：
- **内容维度**：什么类型/话题/标题风格效果最好
- **时间维度**：最佳发布时间段是否有变化
- **读者维度**：读者画像变化趋势、互动行为特征

**分析输出模板：**
```
## 48h 数据复盘 - [文章标题] - [日期]

### 核心数据全景
| 指标 | 本篇 | 近 10 篇均值 | 历史最佳 | 评价 |
|------|------|-------------|---------|------|
| 阅读量 | | | | |
| 完读率 | | | | |
| 分享率 | | | | |
| 收藏率 | | | | |
| 新增关注 | | | | |

### 数据洞察
1. ...
2. ...
3. ...

### 优化建议（按优先级排序）
1. ...
2. ...
3. ...

### 对下一篇文章的建议
- 选题方向：
- 标题策略：
- 发布时间：
```

---

## 调用方式

| 命令 | 功能 |
|------|------|
| `/wechat-publish-setup` | 触发本流水线（凭证配置或进入工作流） |
| `wechat_publish.cjs token` | 验证/刷新 API 凭证 |
| `wechat_publish.cjs upload-thumb <路径>` | 上传封面图 |
| `wechat_publish.cjs upload-image <路径>` | 上传正文配图 |
| `wechat_publish.cjs create-draft <JSON>` | 创建草稿 |
| `wechat_publish.cjs publish <media_id>` | 发布草稿（需用户确认） |
| `wechat_publish.cjs get-status <publish_id>` | 查询发布状态 |
| `wechat_publish.cjs get-stats <开始> <结束>` | 图文数据统计 |

## 错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| token 获取失败 | AppID/AppSecret 错误或 IP 未白名单 | 检查公众平台配置 |
| 素材上传失败 | 文件不存在或格式不符 | 确认图片路径和格式 |
| 草稿创建失败 | JSON 格式错误或必填字段缺失 | 检查 JSON 结构 |
| 发布失败 | 草稿 media_id 错误或权限不足 | 确认草稿状态和账号类型 |
