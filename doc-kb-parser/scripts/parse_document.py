#!/usr/bin/env python3
"""
doc-kb-parser 统一入口：格式检测与分发解析

支持格式：PPTX, DOCX, PDF, XLSX, XLS, CSV, JSON, TXT, HTML, HTM,
          EPUB, PNG, JPG, JPEG, GIF, BMP, WEBP, MP4, AVI, MOV, MKV, WMV
用法：
    python3 parse_document.py input.pptx -o output.md
    python3 parse_document.py input.mp4 -o output.md
    python3 parse_document.py ./documents/ -o ./output/ --batch
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 格式分类
# ---------------------------------------------------------------------------
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}
PPTX_EXTS = {".pptx"}
MARKITDOWN_EXTS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".json", ".txt", ".rtf",
    ".xml", ".html", ".htm", ".epub",
}

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def detect_format(file_path: str) -> str:
    """根据扩展名检测文件格式类别"""
    ext = Path(file_path).suffix.lower()
    if ext in PPTX_EXTS:
        return "pptx"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in MARKITDOWN_EXTS:
        return "markitdown"
    return "unknown"


def format_duration(seconds: float) -> str:
    """秒数转为 HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_seconds_to_hms(seconds: float) -> str:
    """将秒数浮点转为 HH:MM:SS 格式（视频时间戳用）"""
    return format_duration(seconds)


def guess_vendor_from_filename(filename: str) -> str:
    """从文件名猜测厂商名称（简单启发式）"""
    known_vendors = [
        "西门子", "Siemens", "Teamcenter",
        "达索", "Dassault", "ENOVIA", "Solidworks", "CATIA",
        "PTC", "Windchill", "Creo",
        "SAP", "SAP PLM",
        "Oracle", "Agile",
        "智橙", "OrangePLM", "CRDE",
        "用友", "金蝶", "浪潮",
        "华为", "Huawei",
        "开目", "KM",
        "CAX", "华天", "艾克斯特",
        "神州数码", "DCS",
        "Aras", "Arena", " Propel",
    ]
    name_lower = filename.lower()
    for vendor in known_vendors:
        if vendor.lower() in name_lower:
            return vendor
    return ""


def guess_doc_type_from_filename(filename: str) -> str:
    """从文件名猜测文档类型"""
    type_keywords = {
        "产品介绍": ["产品介绍", "产品白皮书", "白皮书", "overview", "product"],
        "竞品分析": ["竞品分析", "竞品对比", "对比分析", "comparison"],
        "培训": ["培训", "教程", "tutorial", "training", "演示", "demo"],
        "方案": ["解决方案", "方案", "solution", "proposal"],
        "案例": ["案例", "客户案例", "case", "成功案例"],
        "功能": ["功能", "功能说明", "feature", "功能列表"],
        "架构": ["架构", "技术架构", "architecture"],
        "API": ["API", "接口", "接口文档"],
        "安装": ["安装", "部署", "install", "deploy", "实施"],
        "手册": ["手册", "使用手册", "手册", "guide", "user guide"],
    }
    name_lower = filename.lower()
    for doc_type, keywords in type_keywords.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                return doc_type
    return ""


def _ensure_c_ext_stubs():
    """WorkBuddy sandbox 环境中，pip 安装的 C 扩展（magika、charset_normalizer 等）
    因 macOS 代码签名限制无法加载。此函数在 import markitdown 子模块之前
    注入必要的 stub 模块，使 markitdown 的纯 Python converter 可以正常工作。
    """
    import types

    # Stub magika（markitdown 用它做文件类型检测，但我们用扩展名替代）
    if "magika" not in sys.modules:
        try:
            import magika
            magika.Magika()
        except Exception:
            stub = types.ModuleType("magika")
            class _MagikaStub:
                def identify_stream(self, s): return None
                def identify_path(self, p): return None
            stub.Magika = lambda: _MagikaStub()
            sys.modules["magika"] = stub

    # Stub charset_normalizer（requests 库用它做编码检测）
    if "charset_normalizer" not in sys.modules:
        try:
            import charset_normalizer
        except Exception:
            stub = types.ModuleType("charset_normalizer")
            stub.from_bytes = lambda b, **kw: {"encoding": "utf-8"}
            stub.from_fp = lambda f, **kw: {"encoding": "utf-8"}
            stub.from_path = lambda p, **kw: {"encoding": "utf-8"}
            stub.is_binary = lambda b: False
            sys.modules["charset_normalizer"] = stub

    # Stub chardet（requests 的另一个编码检测备选）
    if "chardet" not in sys.modules:
        try:
            import chardet
        except Exception:
            pass  # requests 没有 chardet 也能工作


def _convert_with_converter(file_path: str, converter_class) -> str:
    """用 markitdown 的单个 Converter 直接转换文件（绕过 MarkItDown 类）"""
    from markitdown._stream_info import StreamInfo

    ext = Path(file_path).suffix.lower().lstrip(".")
    stream_info = StreamInfo(
        extension=ext,
        filename=os.path.basename(file_path),
        local_path=str(file_path),
    )

    converter = converter_class()
    with open(file_path, "rb") as f:
        result = converter.convert(f, stream_info=stream_info)
    return result.text_content


# 扩展名 → converter 映射
_EXT_CONVERTER_MAP = None

def _get_ext_converter_map():
    """延迟初始化扩展名→converter映射"""
    global _EXT_CONVERTER_MAP
    if _EXT_CONVERTER_MAP is not None:
        return _EXT_CONVERTER_MAP

    _ensure_c_ext_stubs()

    # 直接 import 各 converter（不经过 MarkItDown 类）
    try:
        from markitdown.converters import (
            PptxConverter, DocxConverter, PdfConverter,
            XlsxConverter, XlsConverter, CsvConverter,
            HtmlConverter, EpubConverter, PlainTextConverter,
            ImageConverter, ZipConverter,
        )
        _EXT_CONVERTER_MAP = {
            ".pptx": PptxConverter,
            ".docx": DocxConverter,
            ".pdf": PdfConverter,
            ".xlsx": XlsxConverter,
            ".xls": XlsConverter,
            ".csv": CsvConverter,
            ".html": HtmlConverter,
            ".htm": HtmlConverter,
            ".epub": EpubConverter,
            ".txt": PlainTextConverter,
            ".json": PlainTextConverter,
            ".xml": PlainTextConverter,
            ".rtf": PlainTextConverter,
            ".png": ImageConverter,
            ".jpg": ImageConverter,
            ".jpeg": ImageConverter,
            ".gif": ImageConverter,
            ".bmp": ImageConverter,
            ".webp": ImageConverter,
        }
    except ImportError as e:
        print(f"警告: markitdown converter 导入失败: {e}")
        print("请运行: pip install 'markitdown[all]'")
        _EXT_CONVERTER_MAP = {}

    return _EXT_CONVERTER_MAP


def parse_markitdown_file(file_path: str) -> str:
    """使用 markitdown 的单个 Converter 解析文件（不触发 MarkItDown 类初始化）"""
    cmap = _get_ext_converter_map()
    ext = Path(file_path).suffix.lower()

    if ext in cmap:
        return _convert_with_converter(file_path, cmap[ext])
    else:
        # 回退到 PlainTextConverter
        from markitdown.converters import PlainTextConverter
        return _convert_with_converter(file_path, PlainTextConverter)


def parse_image_file(file_path: str) -> str:
    """使用 MarkItDown OCR 解析图片"""
    return parse_markitdown_file(file_path)


def parse_single_file(input_path: str, output_path: str = None,
                      extract_images: bool = False,
                      screenshot_fallback: bool = False,
                      whisper_model: str = "large-v3",
                      whisper_device: str = "cpu") -> dict:
    """
    解析单个文件，返回元数据字典

    Args:
        input_path: 输入文件路径
        output_path: 输出MD文件路径（None则自动生成）
        extract_images: 是否提取PPT中的图片
        screenshot_fallback: 是否对PPT启用LibreOffice截图兜底
        whisper_model: faster-whisper 模型大小
        whisper_device: faster-whisper 设备 (cuda/cpu)

    Returns:
        dict: 包含 md_text 和 metadata 的字典
    """
    input_path = os.path.abspath(input_path)
    file_name = os.path.basename(input_path)
    file_ext = Path(input_path).suffix.lower()
    file_format = detect_format(input_path)
    file_size = os.path.getsize(input_path)

    # 默认输出路径
    if output_path is None:
        stem = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{stem}.md")

    # 基础元数据
    metadata = {
        "source": file_name,
        "format": file_ext.lstrip("."),
        "vendor": guess_vendor_from_filename(file_name),
        "doc_type": guess_doc_type_from_filename(file_name),
        "file_size_bytes": file_size,
        "parsed_at": datetime.now().strftime("%Y-%m-%d"),
        "parser_version": "1.0.0",
    }

    # 按格式分发
    if file_format == "pptx":
        from parse_pptx import parse_pptx_enhanced
        result = parse_pptx_enhanced(
            input_path, output_path,
            extract_images=extract_images,
            screenshot_fallback=screenshot_fallback,
        )
        metadata.update(result.get("metadata", {}))
        md_text = result.get("md_text", "")

    elif file_format == "video":
        from parse_video import transcribe_video
        result = transcribe_video(
            input_path, output_path,
            model_size=whisper_model,
            device=whisper_device,
        )
        metadata.update(result.get("metadata", {}))
        md_text = result.get("md_text", "")

    elif file_format == "image":
        md_text = parse_image_file(input_path)

    elif file_format in ("markitdown", "unknown"):
        # unknown 格式也尝试 MarkItDown
        md_text = parse_markitdown_file(input_path)

    else:
        md_text = parse_markitdown_file(input_path)

    # 组装最终 MD：YAML frontmatter + 正文
    frontmatter = build_frontmatter(metadata)
    final_md = frontmatter + "\n\n" + md_text.strip() + "\n"

    # 写入文件
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"[OK] {input_path} -> {output_path}")
    return {"md_text": final_md, "metadata": metadata, "output_path": output_path}


def build_frontmatter(metadata: dict) -> str:
    """构建 YAML frontmatter 块"""
    # 过滤掉不需要写入 frontmatter 的内部字段
    skip_keys = {"file_size_bytes"}
    filtered = {k: v for k, v in metadata.items() if v and k not in skip_keys}

    lines = ["---"]
    for key, value in filtered.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - \"{item}\"")
        elif isinstance(value, str) and any(c in value for c in ':{}[],"'):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def batch_parse(input_dir: str, output_dir: str, **kwargs):
    """
    批量解析目录中的所有文件

    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        **kwargs: 传递给 parse_single_file 的参数
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_supported = PPTX_EXTS | MARKITDOWN_EXTS | IMAGE_EXTS | VIDEO_EXTS

    files = [f for f in input_dir.rglob("*")
             if f.is_file() and f.suffix.lower() in all_supported]

    if not files:
        print(f"在 {input_dir} 中未找到可解析的文件")
        return []

    print(f"找到 {len(files)} 个文件待解析")
    print("=" * 60)

    results = []
    success_count = 0
    fail_count = 0

    for file_path in sorted(files):
        rel_path = file_path.relative_to(input_dir)
        # 保持子目录结构，改为 .md 后缀
        out_path = output_dir / rel_path.with_suffix(".md")

        try:
            result = parse_single_file(
                str(file_path), str(out_path), **kwargs
            )
            results.append(result)
            success_count += 1
        except Exception as e:
            print(f"[FAIL] {file_path}: {e}")
            fail_count += 1

    print("=" * 60)
    print(f"完成: 成功 {success_count}, 失败 {fail_count}")

    # 自动生成索引
    if success_count > 0:
        try:
            from build_index import build_master_index
            index_path = output_dir / "MASTER_INDEX.csv"
            build_master_index(str(output_dir), str(index_path))
            print(f"[INDEX] 总索引已生成: {index_path}")
        except Exception as e:
            print(f"[WARN] 索引生成失败: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="doc-kb-parser: 知识库文档批量解析与索引化"
    )
    parser.add_argument("input", help="输入文件或目录路径")
    parser.add_argument("-o", "--output", help="输出MD文件或目录路径")
    parser.add_argument("--batch", action="store_true", help="批量解析目录")
    parser.add_argument("--extract-images", action="store_true",
                        help="提取PPT中的嵌入图片")
    parser.add_argument("--screenshot-fallback", action="store_true",
                        help="对PPT启用LibreOffice截图兜底")
    parser.add_argument("--whisper-model", default="medium",
                        help="faster-whisper 模型大小 (tiny/base/small/medium/large-v3)")
    parser.add_argument("--whisper-device", default="cpu",
                        help="faster-whisper 设备 (cuda/cpu)")

    args = parser.parse_args()

    common_kwargs = {
        "extract_images": args.extract_images,
        "screenshot_fallback": args.screenshot_fallback,
        "whisper_model": args.whisper_model,
        "whisper_device": args.whisper_device,
    }

    if args.batch or os.path.isdir(args.input):
        output_dir = args.output or str(Path(args.input) + "_parsed")
        batch_parse(args.input, output_dir, **common_kwargs)
    else:
        parse_single_file(args.input, args.output, **common_kwargs)


if __name__ == "__main__":
    main()
