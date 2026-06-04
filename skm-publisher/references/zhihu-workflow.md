# 知乎发布实战工作流（Draft.js 编辑器）

> **核心发现（2026-06-04）**：Draft.js 编辑器无法通过多次 `execCommand('insertHTML')` 可靠注入内容。
> 每次注入都会导致编辑器内部状态混乱，前序内容被覆盖、标记重复或丢失。

## 可靠方案：剪贴板粘贴 + 文件导入

### 前置条件
- macOS 剪贴板已有 Markdown 内容（`pbcopy` 写入）
- Markdown 文件存在于 Playwright sandbox 可访问目录
- 已登录知乎账号

### 完整步骤

```
1. 导航 → https://zhuanlan.zhihu.com/write
2. 设置标题（evaluate: 找到 placeholder 含"标题"的 input，设置 textContent）
3. 关闭创作助手（evaluate: 点击文本含"关闭创作助手"的按钮）
4. 聚焦编辑器（evaluate: 找到 [contenteditable="true"] 元素，focus()）
5. 粘贴（keyboard: Meta+V）
6. 等待知乎弹出黄色提示「暂不支持直接识别 Markdown 语法」
7. 点击提示中的「文档导入」按钮
   - evaluate: 遍历所有 button，找到 textContent 含"文档导入"的按钮并点击
8. 触发文件选择器
   - evaluate: 在 [role="dialog"] 中找 input[type="file"] 并 click()
9. 上传 Markdown 文件
   - browser_file_upload({ paths: ['绝对路径'] })
   - ⚠️ 文件必须在 Playwright sandbox root 内
10. 等待导入完成（5-8秒）
   - evaluate: setTimeout(() => resolve(), 6000)
11. 验证结果
    - 检查 h2/h3 标签数量 ≥12
    - 检查 innerText 不包含 '## '（确认无 raw MD）
12. 清理（如存在 raw 文本残留）
    - 手动方式：选中顶部多余文本删除

### 方案 B（纯HTML注入 — 备选）

仅当导入不可用时使用。原理：单次 `execCommand('insertHTML')` 

```javascript
// ⚠️ 必须单次调用！绝不分段！
page.evaluate(() => {
  const allHTML = '<p>...</p><h2>...</h2>...'; // 完整HTML
  const editor = document.querySelector('[contenteditable="true"]');
  editor.focus();
  document.execCommand('insertHTML', false, allHTML);
});
```

缺点：HTML 需预生成，格式可能不完全匹配；较长内容（>5000字）可能截断。

## 已废弃的方案（不可用）

| 方案 | 失败原因 |
|------|---------|
| 多次 execCommand | 每次调用导致前序内容状态混乱/重复/丢失 |
| 直接 innerHTML = html | Draft.js 内部状态不同步，编辑时不更新 |
| 键盘逐字输入 | Token 消耗巨大，速度极慢 |
| execCommand('paste') | 浏览器安全限制，无法编程触发粘贴 |

## 方案 C（保留文本 — 最简备选）

当以上方案均失败时，使用纯文本粘贴（无 Markdown 渲染）：

```bash
pbcopy < article.md  # 复制Markdown源文本
```

在编辑器中 Cmd+V 粘贴。知乎会保留原文（包含 `**bold**`、`## heading` 等语法），
用户可在知乎编辑器内手动格式化。虽然不精美，但内容100%完整。
