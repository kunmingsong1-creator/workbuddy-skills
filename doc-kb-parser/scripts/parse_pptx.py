#!/usr/bin/env python3
"""
parse_pptx.py — PPT 三层增强解析

第一层：MarkItDown 结构化提取（文本、表格、GROUP递归、图表、备注）
第二层：python-pptx 增强提取（嵌入图片、SmartArt检测、背景图片）
第三层：LibreOffice 整页截图兜底（SmartArt页、架构图页）

用法：
    python3 parse_pptx.py input.pptx -o output.md --extract-images --screenshot-fallback
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Sandbox magika stub（WorkBuddy 环境中 C 扩展签名兼容）
# ---------------------------------------------------------------------------

def _ensure_c_ext_stubs():
    """注入 C 扩展 stub 绕过 WorkBuddy sandbox 中的代码签名问题"""
    import types
    if "magika" not in sys.modules:
        try:
            import magika; magika.Magika()
        except Exception:
            stub = types.ModuleType("magika")
            class _S:
                def identify_stream(self, s): return None
                def identify_path(self, p): return None
            stub.Magika = lambda: _S()
            sys.modules["magika"] = stub
    if "charset_normalizer" not in sys.modules:
        try:
            import charset_normalizer
        except Exception:
            stub2 = types.ModuleType("charset_normalizer")
            stub2.from_bytes = lambda b, **kw: {"encoding": "utf-8"}
            stub2.from_fp = lambda f, **kw: {"encoding": "utf-8"}
            stub2.from_path = lambda p, **kw: {"encoding": "utf-8"}
            stub2.is_binary = lambda b: False
            sys.modules["charset_normalizer"] = stub2

_ensure_c_ext_stubs()

# ---------------------------------------------------------------------------
# 第一层：MarkItDown 基础提取
# ---------------------------------------------------------------------------

def markitdown_extract(pptx_path: str) -> str:
    """使用 MarkItDown 的 PptxConverter 提取 PPT 的文本结构（绕过 MarkItDown 类）"""
    try:
        from markitdown.converters import PptxConverter
        from markitdown._stream_info import StreamInfo

        stream_info = StreamInfo(
            extension="pptx",
            filename=os.path.basename(pptx_path),
            local_path=os.path.abspath(pptx_path),
        )
        converter = PptxConverter()
        with open(pptx_path, "rb") as f:
            result = converter.convert(f, stream_info=stream_info)
        return result.text_content
    except ImportError:
        print("警告: 未安装 markitdown，跳过第一层提取")
        return ""
    except Exception as e:
        print(f"警告: MarkItDown PPT 提取失败: {e}")
        return ""


# ---------------------------------------------------------------------------
# 第二层：python-pptx 增强提取
# ---------------------------------------------------------------------------

def extract_pptx_images(pptx_path: str, output_images_dir: str) -> dict:
    """
    使用 python-pptx 提取 PPT 中的所有嵌入图片

    Returns:
        dict: {
            "images": [{"slide": 1, "shape_name": "Picture 5", "path": "images/slide_01_pic_05.png", "content_type": "image/png"}],
            "smartart_slides": [3, 7, 15],  # 含 SmartArt 的页码
            "tables_count": 5,
            "charts_count": 2,
        }
    """
    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
    except ImportError:
        print("警告: 未安装 python-pptx，跳过第二层提取")
        return {"images": [], "smartart_slides": [], "tables_count": 0, "charts_count": 0}

    os.makedirs(output_images_dir, exist_ok=True)

    prs = Presentation(pptx_path)
    images = []
    smartart_slides = []
    tables_count = 0
    charts_count = 0

    for slide_idx, slide in enumerate(prs.slides, start=1):
        slide_image_count = 0
        slide_has_smartart = False

        for shape in slide.shapes:
            shape_type = shape.shape_type

            # 直接图片
            if shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    img = shape.image
                    ext = img.ext
                    blob = img.blob
                    safe_name = re.sub(r'[^a-zA-Z0-9_\-.]', '_', shape.name)
                    filename = f"slide_{slide_idx:02d}_pic_{safe_name}.{ext}"
                    filepath = os.path.join(output_images_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(blob)
                    images.append({
                        "slide": slide_idx,
                        "shape_name": shape.name,
                        "path": f"images/{filename}",
                        "content_type": img.content_type,
                    })
                    slide_image_count += 1
                except Exception as e:
                    pass  # 某些图片形状可能没有 .image 属性

            # 链接图片
            elif shape_type == MSO_SHAPE_TYPE.LINKED_PICTURE:
                pass  # 链接图片无法提取 blob

            # 组合形状 — 递归提取内部图片
            elif shape_type == MSO_SHAPE_TYPE.GROUP:
                group_images = _extract_group_images(
                    shape, slide_idx, output_images_dir
                )
                images.extend(group_images)
                slide_image_count += len(group_images)

            # SmartArt
            elif shape_type == MSO_SHAPE_TYPE.IGX_GRAPHIC:
                slide_has_smartart = True
                # 尝试底层 XML 提取文本
                smartart_text = _extract_smartart_text_from_xml(shape)
                if smartart_text:
                    images.append({
                        "slide": slide_idx,
                        "shape_name": shape.name,
                        "path": None,
                        "smartart_text": smartart_text,
                        "content_type": "smartart",
                    })

            # 表格统计
            elif shape_type == MSO_SHAPE_TYPE.TABLE:
                tables_count += 1

            # 图表统计
            elif shape_type == MSO_SHAPE_TYPE.CHART:
                charts_count += 1

            # 填充背景图片（实验性）
            elif hasattr(shape, "fill"):
                try:
                    fill = shape.fill
                    if fill.type is not None:
                        # 尝试 XML 层提取
                        bg_img = _extract_fill_image(shape, slide_idx, output_images_dir)
                        if bg_img:
                            images.append(bg_img)
                            slide_image_count += 1
                except Exception:
                    pass

        if slide_has_smartart:
            smartart_slides.append(slide_idx)

    return {
        "images": images,
        "smartart_slides": smartart_slides,
        "tables_count": tables_count,
        "charts_count": charts_count,
    }


def _extract_group_images(group_shape, slide_idx: int, output_dir: str) -> list:
    """递归提取组合形状中的图片"""
    images = []
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    try:
        shapes = group_shape.shapes
    except AttributeError:
        return images

    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            try:
                img = shape.image
                ext = img.ext
                blob = img.blob
                safe_name = re.sub(r'[^a-zA-Z0-9_\-.]', '_', shape.name)
                filename = f"slide_{slide_idx:02d}_group_{safe_name}.{ext}"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(blob)
                images.append({
                    "slide": slide_idx,
                    "shape_name": shape.name,
                    "path": f"images/{filename}",
                    "content_type": img.content_type,
                })
            except Exception:
                pass
        elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            images.extend(_extract_group_images(shape, slide_idx, output_dir))

    return images


def _extract_smartart_text_from_xml(shape) -> str:
    """
    从 SmartArt 的原始 XML 中尝试提取文本节点
    注意：这是非公开 API，结果不可靠
    """
    try:
        element = shape._graphicFrame
        if element is None:
            return ""
        xml_str = element.xml
        # 尝试提取 <a:t> 标签内的文本
        texts = re.findall(r'<a:t[^>]*>([^<]+)</a:t>', xml_str)
        if texts:
            return " ".join(texts)
    except Exception:
        pass
    return ""


def _extract_fill_image(shape, slide_idx: int, output_dir: str) -> dict | None:
    """尝试提取形状的填充图片（XML层）"""
    try:
        xml_str = shape._element.xml
        # 查找 r:embed 属性（嵌入图片ID）
        embed_match = re.search(r'r:embed="([^"]+)"', xml_str)
        if not embed_match:
            return None

        # 通过 zipfile 从 PPTX 包中提取图片
        pptx_path = None
        # 需要外部传入 pptx_path，这里跳过
        return None
    except Exception:
        return None


def count_slides(pptx_path: str) -> int:
    """统计 PPT 幻灯片数量"""
    try:
        from pptx import Presentation
        prs = Presentation(pptx_path)
        return len(prs.slides)
    except Exception:
        return 0


def extract_speaker_notes(pptx_path: str) -> list:
    """提取所有幻灯片的演讲者备注"""
    try:
        from pptx import Presentation
        prs = Presentation(pptx_path)
        notes = []
        for idx, slide in enumerate(prs.slides, start=1):
            if slide.has_notes_slide:
                text = slide.notes_slide.notes_text_frame.text.strip()
                if text:
                    notes.append({"slide": idx, "text": text})
        return notes
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 第三层：LibreOffice 截图兜底
# ---------------------------------------------------------------------------

def check_libreoffice() -> bool:
    """检查 LibreOffice 是否可用"""
    try:
        result = subprocess.run(
            ["soffice", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_pdftoppm() -> bool:
    """检查 pdftoppm 是否可用"""
    try:
        result = subprocess.run(
            ["pdftoppm", "-v"],
            capture_output=True, text=True, timeout=10
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def screenshot_pptx_pages(pptx_path: str, output_slides_dir: str,
                          specific_pages: list = None, dpi: int = 150) -> list:
    """
    使用 LibreOffice 将 PPT 页面截图为 PNG

    Args:
        pptx_path: PPTX 文件路径
        output_slides_dir: 输出目录
        specific_pages: 仅截取指定页码列表（None则截取所有页）
        dpi: 输出分辨率

    Returns:
        list: 成功截图的文件路径列表
    """
    os.makedirs(output_slides_dir, exist_ok=True)

    if not check_libreoffice():
        print("警告: LibreOffice 未安装，跳过截图兜底")
        print("  安装: brew install --cask libreoffice")
        return []

    has_pdftoppm = check_pdftoppm()
    if not has_pdftoppm:
        print("警告: pdftoppm 未安装，跳过截图兜底")
        print("  安装: brew install poppler")
        return []

    screenshots = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: PPTX -> PDF
        try:
            result = subprocess.run(
                [
                    "soffice", "--headless",
                    "--convert-to", "pdf:impress_pdf_Export",
                    "--outdir", tmpdir,
                    pptx_path,
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                print(f"警告: LibreOffice 转换失败: {result.stderr}")
                return []
        except subprocess.TimeoutExpired:
            print("警告: LibreOffice 转换超时")
            return []

        # 找到生成的 PDF
        pdf_files = list(Path(tmpdir).glob("*.pdf"))
        if not pdf_files:
            print("警告: 未生成 PDF 文件")
            return []

        pdf_path = pdf_files[0]

        # Step 2: PDF -> PNG
        try:
            result = subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r", str(dpi),
                    str(pdf_path),
                    os.path.join(output_slides_dir, "slide"),
                ],
                capture_output=True, text=True, timeout=120,
            )

            # 收集截图文件
            png_files = sorted(Path(output_slides_dir).glob("slide-*.png"))
            screenshots = [str(f) for f in png_files]

        except subprocess.TimeoutExpired:
            print("警告: pdftoppm 转换超时")
        except Exception as e:
            print(f"警告: 截图失败: {e}")

    return screenshots


# ---------------------------------------------------------------------------
# 组装最终 MD
# ---------------------------------------------------------------------------

def parse_pptx_enhanced(pptx_path: str, output_path: str,
                        extract_images: bool = True,
                        screenshot_fallback: bool = True) -> dict:
    """
    PPT 三层增强解析主函数

    Args:
        pptx_path: PPTX 文件路径
        output_path: 输出 MD 文件路径
        extract_images: 是否提取嵌入图片
        screenshot_fallback: 是否启用 LibreOffice 截图兜底

    Returns:
        dict: {"md_text": str, "metadata": dict}
    """
    pptx_path = os.path.abspath(pptx_path)
    output_dir = os.path.dirname(os.path.abspath(output_path))
    file_name = os.path.basename(pptx_path)

    # 附件目录
    images_dir = os.path.join(output_dir, "images")
    slides_dir = os.path.join(output_dir, "slides")

    metadata = {
        "source": file_name,
        "format": "pptx",
        "parsed_at": "",
        "parser_version": "1.0.0",
    }

    # 统计幻灯片数
    slide_count = count_slides(pptx_path)
    metadata["slides"] = slide_count

    # ---- 第一层：MarkItDown 基础提取 ----
    print(f"[Layer 1] MarkItDown 提取: {file_name}")
    md_text = markitdown_extract(pptx_path)

    # ---- 第二层：python-pptx 增强 ----
    image_info = {"images": [], "smartart_slides": [], "tables_count": 0, "charts_count": 0}
    if extract_images:
        print(f"[Layer 2] python-pptx 图片提取: {file_name}")
        image_info = extract_pptx_images(pptx_path, images_dir)

    metadata["extracted_images"] = len(image_info["images"])
    metadata["tables_count"] = image_info["tables_count"]
    metadata["charts_count"] = image_info["charts_count"]
    metadata["smartart_pages"] = image_info["smartart_slides"]

    # 生成图片引用补充段落
    image_supplement = _build_image_supplement(image_info)

    # ---- 第三层：LibreOffice 截图兜底 ----
    screenshot_files = []
    need_screenshot = False

    if screenshot_fallback and image_info["smartart_slides"]:
        print(f"[Layer 3] LibreOffice 截图兜底: SmartArt页 {image_info['smartart_slides']}")
        need_screenshot = True

    if need_screenshot:
        all_screenshots = screenshot_pptx_pages(pptx_path, slides_dir)
        # 只保留 SmartArt 页的截图（节省空间）
        for ss_path in all_screenshots:
            ss_name = os.path.basename(ss_path)
            # slide-NN.png 格式，提取页码
            match = re.match(r"slide-(\d+)\.png", ss_name)
            if match:
                page_num = int(match.group(1))
                if page_num in image_info["smartart_slides"]:
                    screenshot_files.append(ss_path)

        metadata["slide_screenshots"] = len(screenshot_files)

    # 生成截图引用补充
    screenshot_supplement = _build_screenshot_supplement(
        image_info["smartart_slides"], screenshot_files
    )

    # 提取演讲者备注
    notes = extract_speaker_notes(pptx_path)
    notes_supplement = _build_notes_supplement(notes)

    # 组装最终 MD
    final_parts = []

    if md_text:
        final_parts.append(md_text)

    if image_supplement:
        final_parts.append("\n---\n## 提取的图片\n" + image_supplement)

    if screenshot_supplement:
        final_parts.append("\n---\n## SmartArt/架构图截图\n" + screenshot_supplement)

    if notes_supplement:
        final_parts.append("\n---\n## 演讲者备注\n" + notes_supplement)

    final_md_text = "\n".join(final_parts)

    return {
        "md_text": final_md_text,
        "metadata": metadata,
    }


def _build_image_supplement(image_info: dict) -> str:
    """构建图片引用的 Markdown 段落"""
    real_images = [img for img in image_info["images"] if img.get("path")]
    smartart_texts = [img for img in image_info["images"] if img.get("smartart_text")]

    lines = []

    if real_images:
        lines.append(f"共提取 {len(real_images)} 张嵌入图片：\n")
        for img in real_images:
            alt = f"Slide {img['slide']} - {img['shape_name']}"
            lines.append(f"![{alt}]({img['path']})")

    if smartart_texts:
        lines.append(f"\n### SmartArt 文本提取（XML层，可能不完整）\n")
        for item in smartart_texts:
            lines.append(f"**Slide {item['slide']}: {item['shape_name']}**")
            lines.append(f"> {item['smartart_text']}\n")

    return "\n".join(lines)


def _build_screenshot_supplement(smartart_slides: list,
                                   screenshot_files: list) -> str:
    """构建截图引用的 Markdown 段落"""
    if not smartart_slides:
        return ""

    lines = [f"以下 {len(smartart_slides)} 页包含 SmartArt/架构图，已生成整页截图：\n"]

    # 建立页码到截图文件的映射
    page_to_screenshot = {}
    for ss_path in screenshot_files:
        ss_name = os.path.basename(ss_path)
        match = re.match(r"slide-(\d+)\.png", ss_name)
        if match:
            page_num = int(match.group(1))
            page_to_screenshot[page_num] = f"slides/{ss_name}"

    for page in smartart_slides:
        ss_ref = page_to_screenshot.get(page)
        if ss_ref:
            lines.append(f"### Slide {page}")
            lines.append(f"> 📸 [整页截图]({ss_ref}) — 包含 SmartArt/架构图\n")
        else:
            lines.append(f"### Slide {page}")
            lines.append(f"> ⚠️ SmartArt 页截图未生成（LibreOffice 不可用或转换失败）\n")

    return "\n".join(lines)


def _build_notes_supplement(notes: list) -> str:
    """构建演讲者备注的 Markdown 段落"""
    if not notes:
        return ""

    lines = [f"共 {len(notes)} 页含演讲者备注：\n"]
    for note in notes:
        lines.append(f"### Slide {note['slide']} 备注")
        lines.append(f"> {note['text']}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PPT 三层增强解析")
    parser.add_argument("input", help="PPTX 文件路径")
    parser.add_argument("-o", "--output", help="输出MD文件路径")
    parser.add_argument("--extract-images", action="store_true",
                        help="提取嵌入图片（默认启用）")
    parser.add_argument("--no-images", action="store_true",
                        help="不提取图片")
    parser.add_argument("--screenshot-fallback", action="store_true",
                        help="启用LibreOffice截图兜底")
    parser.add_argument("--dpi", type=int, default=150,
                        help="截图DPI（默认150）")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 文件不存在: {args.input}")
        sys.exit(1)

    if args.output is None:
        args.output = str(Path(args.input).with_suffix(".md"))

    # 导入 parse_document 中的 frontmatter 构建函数
    from parse_document import build_frontmatter, format_seconds_to_hms

    result = parse_pptx_enhanced(
        args.input, args.output,
        extract_images=not args.no_images,
        screenshot_fallback=args.screenshot_fallback,
    )

    # 组装最终 MD
    frontmatter = build_frontmatter(result["metadata"])
    final_md = frontmatter + "\n\n" + result["md_text"].strip() + "\n"

    # 写入文件
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"\n[OK] {args.input} -> {args.output}")
    print(f"  幻灯片: {result['metadata'].get('slides', '?')}")
    print(f"  提取图片: {result['metadata'].get('extracted_images', 0)}")
    print(f"  SmartArt页: {result['metadata'].get('smartart_pages', [])}")


if __name__ == "__main__":
    main()
