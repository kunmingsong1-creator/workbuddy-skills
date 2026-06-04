# skm-publisher — 多平台内容发布 Skill

> **设计目标**：最快速、最稳定、最少 token、多平台文章发布
> **核心工具**：Playwright MCP + macOS pbcopy/pbpaste
> **迭代基础**：基于 multi-platform-publisher-claw 分析 + 实际测试经验打造

## 触发词

### 批量发布（所有平台）
| 触发词 | 场景 |
|--------|------|
| `批量发布`、`全平台发布`、`一键发所有平台`、`publish-all` | 同时发布到所有已配置平台 |
| `矩阵分发`、`矩阵发布`、`分发到全平台` | 文章 → 全平台适配 + 批量发布 |

### 单平台发布
| 触发词 | 场景 |
|--------|------|
| `发布到知乎`、`知乎发文章`、`发知乎草稿` | 发布/存草稿到知乎 |
| `发布到CSDN`、`CSDN发文章` | 发布到CSDN |
| `发布到掘金`、`掘金发文章` | 发布到掘金 |
| `发布到百家号`、`百家号发文章` | 发布到百家号 |
| `发布到头条`、`头条发文章` | 发布到头条号 |
| `发布到搜狐`、`搜狐发文章` | 发布到搜狐号 |
| `发布到网易`、`网易发文章` | 发布到网易号 |
| `发布到小红书`、`小红书发笔记` | 发布图文笔记到小红书 |
| `发布到公众号`、`公众号发文章` | 发布到微信公众号 |

### 指定平台子集
| 触发词 | 场景 |
|--------|------|
| `发布到 [平台1] [平台2] ...` | 发布到指定组合平台 |
| `发知乎和CSDN`、`发图文平台` | 常见平台组合快捷触发 |

### 格式适配（不发布）
| 触发词 | 场景 |
|--------|------|
| `适配 [平台名]`、`format-for [平台名]` | 将文章转为指定平台版本（仅生成本地文件） |
| `生成全平台版本`、`生成矩阵版本` | 一次生成所有平台适配版本 |
| `对比版本`、`diff-platforms` | 对比同一内容在2+平台的改编差异 |

### 状态检查
| 触发词 | 场景 |
|--------|------|
| `检查发布`、`publish-check` | 检查最近发布状态 |
| `发布报告`、`publish-report` | 生成发布汇总报告 |

## ⛔ 关键铁律（违反必败）

1. **绝不**对 Draft.js 编辑器多次调用 `execCommand('insertHTML')` — 内容会重复/丢失
2. **绝不**直接使用 `innerHTML` 注入 Draft.js 编辑器 — 状态不会同步
3. **每次操作前**先 `page.evaluate` 检测编辑器类型，选择对应注入策略
4. **发布后必须检查**：截图 + 内容验证，不假设成功

## 平台总览

| 平台 | 编辑器类型 | 注入策略 | 工具 | 稳定性 |
|------|-----------|---------|------|--------|
| 知乎 | Draft.js | 剪贴板粘贴 + 文件导入 | Playwright | ★★★★☆ |
| CSDN | 富文本 | execCommand 单次注入 | Playwright | ★★★★★ |
| 掘金 | Markdown | 直接粘贴Markdown | Playwright | ★★★★★ |
| 搜狐号 | 富文本 | 剪贴板粘贴 | Playwright | ★★★★☆ |
| 网易号 | 富文本 | 剪贴板粘贴 | Playwright | ★★★★☆ |
| 百家号 | 富文本 | 剪贴板粘贴 | Playwright | ★★★★☆ |
| 头条号 | 富文本 | 剪贴板粘贴 | Playwright | ★★★★☆ |
| 小红书 | 笔记编辑器 | 手动/API | 蚁小二 | ★★★☆☆ |
| 微信公众号 | 微信编辑器 | 逐个block写入 | Playwright | ★★★☆☆ |
| 抖音/视频号 | 短视频 | 蚁小二 | 蚁小二 | ★★★☆☆ |

## 工作流程

### 批量发布（全平台）

收到 `批量发布` / `矩阵分发` 等触发词时，按以下流程执行：

```
阶段 0：确认（10s）
  ├── 列出所有目标平台及当前登录状态
  ├── 确认内容源文件路径
  └── 等待用户确认「继续」

阶段 1：生成适配版本（并行，20-30s）
  ├── 知乎版 → 5000字，个人判断视角
  ├── 百家号版 → 3000字，关键词驱动，FAQ收尾
  ├── 搜狐号版 → 2000字，通俗化
  ├── 网易号版 → 2000字，观点强化
  ├── 头条号版 → 2000字，故事化
  ├── CSDN版 → 3000字，技术视角
  ├── 掘金版 → 2000字，克制专业
  ├── 小红书版 → 800字，知识卡片
  └── 公众号版 → 全文，排版优化

阶段 2：依次发布（串行，每个1-3分钟）
  知乎 → CSDN → 掘金 → 搜狐号 → 网易号 → 百家号 → 头条号 → 小红书 → 公众号
  ├── 每平台：导航 → 粘贴/导入 → 验证 → 下一个
  └── 遇到错误：记录 → 跳过 → 继续下一平台

阶段 3：汇总报告
  ├── 成功/失败/草稿列表
  ├── 各平台链接
  └── 失败重试建议
```

**发布优先级（按搜索收录价值）**：
1. 知乎（GEO核心引用源）→ 2. 百家号（百度生态）→ 3. 搜狐号（搜索收录）→ 4. 公众号（品牌主阵地）→ 5. 网易号 → 6. 头条号 → 7. CSDN → 8. 掘金 → 9. 小红书 → 10. 抖音

**时间窗口策略**：
- 各平台发布间隔 ≥5 分钟（避免搜索引擎判定批量垃圾内容）
- 知乎首发 → 5min → 百家号 → 5min → 搜狐号 → ...以此类推
- 如用户要求「立即全部发布」，则跳过间隔，直接串行

### 阶段 1：准备（单平台发布亦适用）

```
1. 读取内容Markdown文件
2. 根据目标平台调用 references/platform-adapters.md 规则生成适配版本
3. 将适配后内容保存到临时文件，并写入 macOS 剪贴板（pbcopy）
4. 准备标题（根据平台规则改写）
```

### 阶段 2：发布（按平台）

#### 知乎（Draft.js — 最具挑战性）

**最可靠流程（已验证）**：

```javascript
// Step 1: 导航到写文章页面
page.goto('https://zhuanlan.zhihu.com/write');

// Step 2: 设置标题（直接设置textContent）
page.evaluate(() => {
  const title = document.querySelector('[placeholder="请输入标题"]');
  if (title) title.textContent = '文章标题';
});

// Step 3: 关闭创作助手
page.evaluate(() => {
  const btns = document.querySelectorAll('button');
  for (const b of btns) {
    if (b.textContent.includes('关闭创作助手')) { b.click(); break; }
  }
});

// Step 4: 聚焦编辑器
page.evaluate(() => {
  const editor = document.querySelector('[contenteditable="true"]');
  if (editor) editor.focus();
});

// Step 5: 粘贴（必须已在macOS剪贴板）
page.keyboard.press('Meta+V');

// Step 6: 等待知乎弹出「Markdown语法识别」提示（约2-3秒）
// 点击「文档导入」按钮

// Step 7: 触发文件上传
page.evaluate(() => {
  const dialog = document.querySelector('[role="dialog"]');
  if (dialog) {
    const fileInput = dialog.querySelector('input[type="file"]');
    if (fileInput) fileInput.click();
  }
});

// Step 8: 上传Markdown文件（文件必须在Playwright sandbox可访问目录）
browser_file_upload({ paths: ['/path/to/article.md'] });

// Step 9: 等待导入完成（5-8秒）
page.evaluate(() => new Promise(r => setTimeout(r, 6000)));

// Step 10: 删除顶部raw文本残留（如存在）
// 手动完成此步骤最可靠
```

**关键参数**：
- 标题字数：≤100字
- 导入文件格式：`.md`（推荐，Zhihu原生支持）
- 导入等待时间：5-8秒
- 话题标签：通过「添加话题」按钮手动添加

#### CSDN（富文本编辑器）

```javascript
// Step 1: 导航到CSDN写文章
page.goto('https://editor.csdn.net/md?not_checkout=1');

// Step 2: CSDN支持Markdown直接编辑，直接粘贴并发布
// 具体流程参考 references/csdn-workflow.md
```

### 阶段 3：验证（必须执行）

```javascript
// 内容完整性检查
const check = await page.evaluate(() => {
  const editor = document.querySelector('[contenteditable="true"]');
  if (!editor) return { error: 'no editor' };
  const text = editor.innerText;
  return {
    length: text.length,
    hasTitle: text.includes('预期标题关键词'),
    hasAllSections: [...], // 检查所有章节
    noRawMD: !text.includes('## '), // 确保无raw Markdown
  };
});
```

## 平台适配速查

详见 `references/platform-adapters.md`，核心规则：

| 转换维度 | 规则 |
|---------|------|
| 公众号 → 知乎 | 保留全文，增加个人判断视角，添加互动引导 |
| 知乎 → 百家号 | 简化至2000-3000字，标题嵌入搜索词，加FAQ |
| 知乎 → 小红书 | 提取核心结论→知识卡片，800字以内，口语化 |
| 知乎 → 头条号 | 故事化改写，悬念标题，3-5行分段 |
| 通用 → 抖音 | 拆分为5-8条30-90秒口播脚本 |

## 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `browser_file_upload` denied | 文件不在sandbox根目录 | 将文件写入 Playwright allowed root |
| 知乎编辑器无响应 | Draft.js状态锁定 | 刷新页面重试 |
| 导入后格式错误 | MD语法不被支持 | 使用纯文本版 + 手动格式化 |
| 话题搜索无结果 | 知乎搜索API延迟 | 手动添加话题 |

## 依赖

- Playwright MCP（所有浏览器操作）
- macOS pbcopy/pbpaste（剪贴板操作）
- 蚁小二（可选，用于视频/小红书分发）
- 无Python依赖（纯Agent执行，零安装）

---

> **版本**：v1.1 | 基于 2026-06-04 实践验证，新增批量发布能力
> **参考 Skill**：multi-platform-publisher-claw（分析来源）、skm-蚁小二（视频分发）
> **触发词数量**：30+ 个，覆盖批量/单平台/适配/检查全场景

## 批量发布进度追踪

执行批量发布时，使用 TaskCreate 为每个平台创建子任务，实时追踪进度：

```
Task: 批量发布 - 知乎      [in_progress] → [completed] ✅
Task: 批量发布 - 百家号    [pending]
Task: 批量发布 - 搜狐号    [pending]
...
```

每完成一个平台立即更新 Task 状态，让用户看到实时进度。
