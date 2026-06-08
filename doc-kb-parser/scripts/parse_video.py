#!/usr/bin/env python3
"""
parse_video.py — 视频转录（faster-whisper + ffmpeg）

功能：
  1. ffmpeg 提取音频轨道
  2. faster-whisper 语音转录（中文优化）
  3. ffmpeg 按段落截取关键帧
  4. 输出带时间戳的 Markdown

用法：
    python3 parse_video.py input.mp4 -o output.md --model medium --device cpu
    python3 parse_video.py input.mp4 -o output.md --model large-v3 --device cuda
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def format_timestamp(seconds: float) -> str:
    """秒数浮点转为 HH:MM:SS 格式"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_video_duration(video_path: str) -> float:
    """使用 ffprobe 获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return 0.0


def get_video_info(video_path: str) -> dict:
    """获取视频元信息"""
    info = {"duration": 0.0, "width": 0, "height": 0, "codec": "", "fps": 0}

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name,r_frame_rate",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            # format.duration
            if "format" in data:
                info["duration"] = float(data["format"].get("duration", 0))
            # stream info
            if "streams" in data and data["streams"]:
                stream = data["streams"][0]
                info["width"] = stream.get("width", 0)
                info["height"] = stream.get("height", 0)
                info["codec"] = stream.get("codec_name", "")
                fps_str = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = fps_str.split("/")
                    info["fps"] = round(int(num) / int(den), 1)
                except (ValueError, ZeroDivisionError):
                    pass
    except Exception:
        pass

    return info


def check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_ffprobe() -> bool:
    """检查 ffprobe 是否可用"""
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# 音频提取
# ---------------------------------------------------------------------------

def extract_audio(video_path: str, output_audio: str) -> bool:
    """
    使用 ffmpeg 从视频中提取音频

    Args:
        video_path: 视频文件路径
        output_audio: 输出音频文件路径（.wav）

    Returns:
        bool: 是否成功
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-i", video_path,
                "-vn",                      # 去除视频轨
                "-acodec", "pcm_s16le",     # WAV 格式
                "-ar", "16000",             # 16kHz 采样率（whisper 推荐）
                "-ac", "1",                 # 单声道
                "-y",                       # 覆盖输出
                output_audio,
            ],
            capture_output=True, text=True, timeout=300,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"音频提取失败: {e}")
        return False


# ---------------------------------------------------------------------------
# faster-whisper 转录
# ---------------------------------------------------------------------------

def check_faster_whisper() -> bool:
    """检查 faster-whisper 是否可用"""
    try:
        import faster_whisper
        return True
    except ImportError:
        return False


def transcribe_audio(audio_path: str, model_size: str = "medium",
                      device: str = "cpu", language: str = "zh") -> dict:
    """
    使用 faster-whisper 进行语音转录

    Args:
        audio_path: 音频文件路径
        model_size: 模型大小 (tiny/base/small/medium/large-v3)
        device: 设备 (cuda/cpu)
        language: 语言代码

    Returns:
        dict: {
            "segments": [{"start": float, "end": float, "text": str}],
            "text": str,
            "language": str,
            "language_probability": float,
        }
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("错误: 未安装 faster-whisper")
        print("  安装: pip install faster-whisper")
        sys.exit(1)

    # 选择计算类型
    if device == "cuda":
        compute_type = "float16"
    else:
        compute_type = "int8"  # CPU 使用 int8 量化

    print(f"  加载模型: {model_size} ({device}/{compute_type})...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print(f"  开始转录: {audio_path}")
    segments_iter, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        word_timestamps=False,
    )

    segments = []
    for seg in segments_iter:
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })

    # 合并全文
    full_text = " ".join(seg["text"] for seg in segments)

    return {
        "segments": segments,
        "text": full_text,
        "language": info.language,
        "language_probability": info.language_probability,
    }


# ---------------------------------------------------------------------------
# 关键帧截取
# ---------------------------------------------------------------------------

def extract_keyframes(video_path: str, output_frames_dir: str,
                     segment_starts: list = None,
                     interval_seconds: int = 300) -> list:
    """
    从视频中截取关键帧

    两种模式：
    1. 基于段落起始时间截取（如果提供了 segment_starts）
    2. 固定间隔截取（默认每5分钟）

    Args:
        video_path: 视频文件路径
        output_frames_dir: 输出目录
        segment_starts: 段落起始时间列表（秒）
        interval_seconds: 固定间隔秒数

    Returns:
        list: 截取的帧文件路径列表
    """
    os.makedirs(output_frames_dir, exist_ok=True)
    frame_paths = []

    timestamps = []

    if segment_starts:
        # 基于段落起始时间 + 固定间隔混合
        timestamps.extend(segment_starts)
        # 补充固定间隔
        duration = get_video_duration(video_path)
        t = interval_seconds
        while t < duration:
            # 找最近的段落时间，如果差距 < 60s 则跳过
            is_close = any(abs(t - s) < 60 for s in segment_starts)
            if not is_close:
                timestamps.append(t)
            t += interval_seconds
        timestamps.sort()
    else:
        # 纯固定间隔
        duration = get_video_duration(video_path)
        t = 0
        while t < duration:
            timestamps.append(t)
            t += interval_seconds

    for ts in timestamps:
        filename = f"frame_{int(ts):06d}.jpg"
        filepath = os.path.join(output_frames_dir, filename)

        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-ss", str(ts),
                    "-i", video_path,
                    "-frames:v", "1",
                    "-q:v", "2",  # 高质量
                    filepath,
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and os.path.exists(filepath):
                frame_paths.append({
                    "timestamp": ts,
                    "time_formatted": format_timestamp(ts),
                    "path": f"frames/{filename}",
                })
        except (subprocess.TimeoutExpired, Exception):
            pass

    return frame_paths


# ---------------------------------------------------------------------------
# 组装 Markdown
# ---------------------------------------------------------------------------

def segments_to_markdown(segments: list, frames: list = None) -> str:
    """
    将转录段落转换为带时间戳的 Markdown

    按语义分段（每 ~60 秒或自然停顿处分段）
    """
    if not segments:
        return "（未检测到语音内容）"

    # 分段逻辑：每 60 秒或相邻段落间隔 > 10 秒时换段落
    SEGMENT_DURATION = 60  # 秒
    PAUSE_THRESHOLD = 10   # 秒

    current_group = []
    groups = []

    for seg in segments:
        if not current_group:
            current_group.append(seg)
        else:
            last = current_group[-1]
            gap = seg["start"] - last["end"]
            group_duration = seg["end"] - current_group[0]["start"]

            if gap > PAUSE_THRESHOLD or group_duration > SEGMENT_DURATION:
                groups.append(current_group)
                current_group = [seg]
            else:
                current_group.append(seg)

    if current_group:
        groups.append(current_group)

    # 建立时间戳到帧的映射
    frame_map = {}
    if frames:
        for f in frames:
            frame_map[f["timestamp"]] = f

    # 生成 Markdown
    lines = []

    for group_idx, group in enumerate(groups, start=1):
        start_time = group[0]["start"]
        end_time = group[-1]["end"]

        # 段落标题
        lines.append(
            f"### {format_timestamp(start_time)} - {format_timestamp(end_time)}"
        )

        # 检查是否有对应的关键帧
        nearest_frame = None
        min_dist = float("inf")
        for ts, frame in frame_map.items():
            dist = abs(ts - start_time)
            if dist < min_dist and dist < 30:  # 30 秒内
                min_dist = dist
                nearest_frame = frame

        if nearest_frame:
            lines.append("")
            lines.append(
                f"![关键帧 {nearest_frame['time_formatted']}]({nearest_frame['path']})"
            )
            lines.append("")

        # 段落内容
        for seg in group:
            ts = format_timestamp(seg["start"])
            lines.append(f"**[{ts}]** {seg['text']}")

        lines.append("")

    return "\n".join(lines)


def transcribe_video(video_path: str, output_path: str,
                     model_size: str = "medium",
                     device: str = "cpu",
                     extract_keyframes: bool = True,
                     keyframe_interval: int = 300) -> dict:
    """
    视频转录主函数

    Args:
        video_path: 视频文件路径
        output_path: 输出 MD 文件路径
        model_size: faster-whisper 模型大小
        device: 设备 (cuda/cpu)
        extract_keyframes: 是否截取关键帧
        keyframe_interval: 关键帧间隔（秒）

    Returns:
        dict: {"md_text": str, "metadata": dict}
    """
    video_path = os.path.abspath(video_path)
    output_dir = os.path.dirname(os.path.abspath(output_path))
    file_name = os.path.basename(video_path)
    frames_dir = os.path.join(output_dir, "frames")

    # 获取视频信息
    video_info = get_video_info(video_path)
    duration = video_info["duration"]

    metadata = {
        "source": file_name,
        "format": Path(video_path).suffix.lstrip("."),
        "duration": format_timestamp(duration),
        "resolution": f"{video_info['width']}x{video_info['height']}" if video_info['width'] else "",
        "codec": video_info['codec'],
        "transcription_model": f"faster-whisper-{model_size}",
        "transcription_date": datetime.now().strftime("%Y-%m-%d"),
        "parser_version": "1.0.0",
    }

    # 检查依赖
    if not check_ffmpeg():
        print("错误: ffmpeg 未安装")
        print("  安装: brew install ffmpeg")
        return {"md_text": "", "metadata": metadata}

    if not check_faster_whisper():
        print("错误: faster-whisper 未安装")
        print("  安装: pip install faster-whisper")
        return {"md_text": "", "metadata": metadata}

    print(f"[INFO] 视频信息: {file_name}")
    print(f"  时长: {format_timestamp(duration)}")
    print(f"  分辨率: {video_info.get('width', '?')}x{video_info.get('height', '?')}")
    print(f"  模型: {model_size} ({device})")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: 提取音频
        audio_path = os.path.join(tmpdir, "audio.wav")
        print(f"[Step 1] 提取音频轨道...")
        if not extract_audio(video_path, audio_path):
            print("错误: 音频提取失败")
            return {"md_text": "", "metadata": metadata}

        # Step 2: 转录
        print(f"[Step 2] faster-whisper 转录中（可能需要几分钟）...")
        result = transcribe_audio(audio_path, model_size, device)

        segments = result["segments"]
        metadata["language"] = result.get("language", "zh")
        metadata["language_probability"] = round(
            result.get("language_probability", 0), 4
        )

        print(f"  检测语言: {metadata['language']} "
              f"({metadata['language_probability']:.1%})")
        print(f"  转录段落: {len(segments)} 段")

    # Step 3: 截取关键帧
    frames = []
    if extract_keyframes and segments:
        print(f"[Step 3] 截取关键帧...")
        segment_starts = [seg["start"] for seg in segments[::5]]  # 每5段取一个
        frames = extract_keyframes(
            video_path, frames_dir,
            segment_starts=segment_starts,
            interval_seconds=keyframe_interval,
        )
        metadata["keyframes"] = len(frames)

    # Step 4: 组装 Markdown
    print(f"[Step 4] 生成 Markdown...")
    md_body = segments_to_markdown(segments, frames)

    # 标题
    title = Path(video_path).stem
    title_section = f"# {title}\n"

    # 元信息摘要
    meta_lines = ["> **元信息**"]
    meta_lines.append(f"> - 时长: {metadata['duration']}")
    meta_lines.append(f"> - 转录段落: {len(segments)}")
    if frames:
        meta_lines.append(f"> - 关键帧: {len(frames)}")
    meta_lines.append(
        f"> - 检测语言: {metadata['language']} "
        f"({metadata['language_probability']:.1%})"
    )
    meta_section = "\n".join(meta_lines) + "\n"

    # 全文
    full_text_section = "## 全文转录\n\n"
    if result.get("text"):
        full_text_section += result["text"] + "\n"

    # 段落详情
    detail_section = "## 段落详情\n\n" + md_body

    md_text = title_section + "\n" + meta_section + "\n" + detail_section

    return {
        "md_text": md_text,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="视频转录（faster-whisper）")
    parser.add_argument("input", help="视频文件路径")
    parser.add_argument("-o", "--output", help="输出MD文件路径")
    parser.add_argument("--model", default="medium",
                        help="faster-whisper 模型 (tiny/base/small/medium/large-v3)")
    parser.add_argument("--device", default="cpu",
                        help="设备 (cuda/cpu)")
    parser.add_argument("--no-keyframes", action="store_true",
                        help="不截取关键帧")
    parser.add_argument("--keyframe-interval", type=int, default=300,
                        help="关键帧间隔秒数（默认300=5分钟）")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 文件不存在: {args.input}")
        sys.exit(1)

    if args.output is None:
        args.output = str(Path(args.input).with_suffix(".md"))

    # 导入 frontmatter 构建函数
    from parse_document import build_frontmatter

    result = transcribe_video(
        args.input, args.output,
        model_size=args.model,
        device=args.device,
        extract_keyframes=not args.no_keyframes,
        keyframe_interval=args.keyframe_interval,
    )

    # 组装最终 MD
    frontmatter = build_frontmatter(result["metadata"])
    final_md = frontmatter + "\n\n" + result["md_text"].strip() + "\n"

    # 写入
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"\n[OK] {args.input} -> {args.output}")
    print(f"  时长: {result['metadata'].get('duration', '?')}")
    print(f"  段落: {len(result['md_text'].split('### ')) - 1}")
    print(f"  关键帧: {result['metadata'].get('keyframes', 0)}")


if __name__ == "__main__":
    main()
