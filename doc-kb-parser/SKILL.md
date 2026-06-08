---
name: doc-kb-parser
version: 1.0.0
description: |
  知识库文档批量解析与索引化工具。将 PPT/Word/PDF/Excel/图片/视频
  解析为 AI 友好的 Markdown 文件，提取文本、表格、图片、架构图截图、
  视频转录（带时间戳），生成 YAML frontmatter 元数据 + 总索引表。
  触发词：解析文档、批量转换、文档索引、知识库解析、视频转录、doc parser、
  parse documents、parse knowledge base。
agent_created: true
tags:
  - document-parsing
  - markdown
  - pptx
  - video-transcription
  - knowledge-base
---

# doc-kb-parser — 知识库文档批量解析与索引化

将多种格式文档解析为 AI 友好的 Markdown，附带 YAML frontmatter 元数据和总索引表。

## 触发条件

当用户提到以下意图时触发：
- "解析文档"、"批量转换"、"文档索引"
- "知识库解析"、"PPT转Markdown"
- "视频转录"、"视频转文字"
- "doc parser"、"parse documents"

## 支持格式

| 格式 | 引擎 | 输出 |
|------|------|------|
| PPTX | MarkItDown + python-pptx + LibreOffice截图 | MD + images/ + slides/ |
| DOCX | MarkItDown | MD + images/ |
| PDF | MarkItDown + OCR | MD + images/ |
| XLSX/XLS | MarkItDown | MD表格 |
| 图片 (PNG/JPG) | MarkItDown OCR | alt文本MD |
| 视频 (MP4/AVI/MOV) | faster-whisper + ffmpeg | 带时间戳MD + frames/ |

## 安装（首次使用）

> ⚠️ **重要**：本 Skill 的 Python 脚本包含 C 扩展依赖（lxml、numpy 等），
> 需要在**本地终端**（非 WorkBuddy sandbox）运行安装和解析。
> WorkBuddy sandbox 的 macOS 代码签名限制会阻止 pip 安装的 C 扩展加载。

### 一键安装

在本地终端执行：

```bash
cd ~/.workbuddy/skills/doc-kb-parser
bash scripts/install.sh
```

或手动安装：

```bash
cd ~/.workbuddy/skills/doc-kb-parser
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

### 系统依赖（可选）

| 依赖 | 用途 | 安装 |
|------|------|------|
| ffmpeg | 音频提取、视频截帧 | `brew install ffmpeg` |
| LibreOffice | PPT整页截图兜底 | `brew install --cask libreoffice` |
| tesseract | OCR | `brew install tesseract` |

## Agent 使用指南

Agent 通过以下方式调用本 Skill：

### 方式一：生成命令供用户在本地终端执行

```python
# 1. 先用乐享 MCP 下载文件到本地
# mcp__lexiang__file_download_file → 获取 download_url

# 2. 生成解析命令，用户复制到终端执行
SKILL_DIR = "~/.workbuddy/skills/doc-kb-parser"
VENV_PY = f"{SKILL_DIR}/.venv/bin/python3"
SCRIPTS = f"{SKILL_DIR}/scripts"

cmd = f"{VENV_PY} {SCRIPTS}/parse_document.py /path/to/input.pptx -o /path/to/output.md"
```

### 方式二：通过 osascript 在新终端窗口执行（macOS）

```bash
osascript -e 'tell application "Terminal" to do script "cd ~/.workbuddy/skills/doc-kb-parser && .venv/bin/python3 scripts/parse_document.py /path/to/input.pptx -o /path/to/output.md"'
```

### 方式三：批量解析

```bash
# 解析整个目录
osascript -e 'tell application "Terminal" to do script "cd ~/.workbuddy/skills/doc-kb-parser && .venv/bin/python3 scripts/parse_document.py /path/to/documents/ -o /path/to/output/ --batch --extract-images --screenshot-fallback"'
```

### 从乐享知识库下载并解析

通过乐享 MCP 工具下载文件后，再调用本 Skill 解析：

1. `mcp__lexiang__file_describe_file` → 获取文件信息
2. `mcp__lexiang__file_download_file` → 获取下载 URL
3. 用 curl 下载到本地临时目录
4. 在本地终端执行解析命令
5. 读取生成的 MD 文件和索引

## PPT 解析策略（三层递进）

1. **第一层：MarkItDown PptxConverter** — 提取文本、表格、GROUP递归文本、图表数据、演讲者备注
2. **第二层：python-pptx** — 提取嵌入图片blob保存为PNG；检测SmartArt标记为截图页
3. **第三层：LibreOffice截图** — SmartArt/架构图页面整页转PNG截图兜底

## 视频转录策略

- **引擎**：faster-whisper（large-v3，中文CER~3%）
- **时间戳**：HH:MM:SS 格式，按语义段落分组
- **关键帧**：每5分钟 + 段落起始处自动截取
- **元数据**：检测语言、说话人数、视频时长

## 输出 MD 结构

每份文档生成的 MD 文件头部带 YAML frontmatter：

```yaml
---
source: "原始文件名.pptx"
vendor: "厂商名称（如能识别）"
doc_type: "产品介绍/竞品分析/培训等"
source_entry_id: "乐享条目ID（如有）"
slides: 48
duration: "00:45:30"
extracted_images: 23
key_topics: ["PLM", "协同设计"]
parsed_at: "2026-06-03"
parser_version: "1.0.0"
---
```

## 总索引表

生成 `MASTER_INDEX.csv`，支持以下检索维度：
- **厂商**（vendor）— 按厂商聚合
- **文档类型**（doc_type）— 区分产品介绍/竞品分析/培训等
- **主题**（key_topics）— 关键词横向检索
- **格式**（format）— 按文件类型筛选
- **时长**（duration）— 视频时长筛选

## 脚本说明

| 脚本 | 功能 |
|------|------|
| `scripts/install.sh` | 一键安装脚本 |
| `scripts/parse_document.py` | 统一入口，格式检测与分发 |
| `scripts/parse_pptx.py` | PPT 三层增强解析 |
| `scripts/parse_video.py` | 视频转录（faster-whisper） |
| `scripts/build_index.py` | 扫描MD生成总索引CSV |
| `scripts/requirements.txt` | Python依赖清单 |

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| WorkBuddy 中 ImportError（签名） | 在本地终端运行，不通过 WorkBuddy bash |
| faster-whisper 无 GPU | 降级到 medium 模型或使用 CPU int8 模式 |
| LibreOffice 未安装 | 跳过截图兜底层，仅输出文本+提取的图片 |
| SmartArt 文字丢失 | python-pptx 的已知限制，截图兜底层会保留视觉信息 |
| 视频转录太慢 | 缩小模型到 medium（CER~3.2%，速度提升3倍） |

---

*版本：v1.0.0 | 创建：2026-06-03*
