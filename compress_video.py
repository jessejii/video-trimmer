"""
视频压缩工具 - 使用 FFmpeg 压缩视频文件

功能:
- 支持单个文件或整个文件夹的批量处理
- 使用 H.264 (h264_amf) 编码进行高效压缩（AMD 显卡加速）
- 提供三种质量预设: 低、中、高
- 自动计算合适的码率
- 输出文件保存到输入文件所在目录

用法:
    python compress_video.py <输入视频/文件夹> [质量预设]

示例:
    # 处理单个文件，使用中等质量
    python compress_video.py video.mp4

    # 处理单个文件，使用低质量（文件更小）
    python compress_video.py video.mp4 low

    # 批量处理文件夹中的所有视频
    python compress_video.py video_folder medium
"""

import os
import subprocess
import sys
from typing import Optional, Tuple


def get_video_info(video_file: str) -> Tuple[Optional[float], str, Optional[int]]:
    """获取视频时长、编码和码率（kbps）"""
    duration_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]
    codec_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]
    bitrate_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]

    duration = None
    codec = "unknown"
    bitrate = None

    try:
        result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
    except Exception as e:
        print(f"  获取视频时长失败: {e}")

    try:
        result = subprocess.run(codec_cmd, capture_output=True, text=True, check=True)
        codec = result.stdout.strip().lower()
    except Exception:
        pass

    try:
        result = subprocess.run(bitrate_cmd, capture_output=True, text=True, check=True)
        raw = result.stdout.strip()
        if raw and raw != "N/A":
            bitrate = int(raw) // 1000  # bps -> kbps
    except Exception:
        pass

    return duration, codec, bitrate


def compress_video(
    input_file: str,
    output_dir: str,
    quality: str = "low"
) -> bool:
    """
    压缩单个视频文件

    参数:
        input_file: 输入视频文件
        output_dir: 输出目录
        quality: 质量预设 (low/medium/high)

    返回:
        是否成功
    """
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False

    # 获取视频信息
    duration, codec, src_bitrate = get_video_info(input_file)
    if duration is None:
        print(f"错误: 无法获取视频信息: {input_file}")
        return False

    # 根据质量预设确定压缩参数
    # QP 值越低，质量越高，文件越大
    # preset 越慢，压缩效率越高
    quality_presets = {
        "low": {
            "crf": "28",
            "preset": "medium",
            "amf_quality": "speed",
        },
        "medium": {
            "crf": "23",
            "preset": "medium",
            "amf_quality": "balanced",
        },
        "high": {
            "crf": "18",
            "preset": "slow",
            "amf_quality": "quality",
        },
    }

    preset = quality_presets.get(quality, quality_presets["medium"])

    # 输出文件路径
    base_name = os.path.basename(input_file)
    name_without_ext, ext = os.path.splitext(base_name)
    output_file = os.path.join(output_dir, f"{name_without_ext}_compressed{ext}")

    # 若输出已存在则删除
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except Exception:
            pass

    print(f"  原编码: {codec} | 原码率: {src_bitrate if src_bitrate else '未知'} kbps")
    print(f"  质量预设: {quality} | QP: {preset['crf']}")
    print(f"  时长: {duration:.2f}s")

    # 构建 ffmpeg 命令
    # 使用 QP 模式（恒定质量）而不是固定码率，这样压缩效果更好
    # 使用 AMD 显卡加速编码器 h264_amf
    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-c:v", "h264_amf",
        "-qp", preset["crf"],
        "-quality", preset["amf_quality"],
        "-rc", "cqp",
        "-c:a", "copy",  # 音频直接复制，不重新编码
        "-movflags", "+faststart",  # 将 moov atom 放到文件开头，便于流式播放
        output_file,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  成功: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  失败: {e}")
        if e.stderr:
            stderr = e.stderr.decode("utf-8", errors="ignore") if isinstance(e.stderr, bytes) else e.stderr
            for line in stderr.splitlines():
                if "error" in line.lower() or "fail" in line.lower():
                    print(f"    {line.strip()}")
        # 清理失败产物
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception:
                pass
        return False
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: python compress_video.py <输入视频/文件夹> [质量预设]")
        print("\n功能: 使用 H.264 编码压缩视频文件，支持单个文件或批量处理")
        print("\n质量预设:")
        print("  low    - 低质量，文件最小 (QP 28，默认)")
        print("  medium - 中等质量，平衡大小和画质 (QP 23)")
        print("  high   - 高质量，文件较大 (QP 18)")
        print("\n示例:")
        print("  # 处理单个文件，使用中等质量")
        print("  python compress_video.py video.mp4")
        print()
        print("  # 处理单个文件，使用低质量")
        print("  python compress_video.py video.mp4 low")
        print()
        print("  # 批量处理文件夹中的所有视频")
        print("  python compress_video.py video_folder medium")
        print("\n输出: 压缩后的文件保存到输入文件所在目录，文件名添加 _compressed 后缀")
        sys.exit(1)

    input_path = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else "low"

    # 验证质量参数
    if quality not in ["low", "medium", "high"]:
        print(f"错误: 无效的质量预设 '{quality}'，可选: low, medium, high")
        sys.exit(1)

    # 支持的视频格式
    video_extensions = (
        ".mp4", ".avi", ".mov", ".mkv", ".flv",
        ".wmv", ".m4v", ".webm", ".ts", ".mpg", ".mpeg",
        ".vob", ".m2ts", ".mts", ".3gp", ".rmvb",
    )

    # 检查输入是文件还是文件夹
    if os.path.isfile(input_path):
        # 单个文件处理
        input_dir = os.path.dirname(input_path) if os.path.dirname(input_path) else "."
        if compress_video(input_path, input_dir, quality):
            print("\n压缩完成!")
        else:
            print("\n压缩失败!")
    elif os.path.isdir(input_path):
        # 批量处理文件夹（递归查找子目录）
        print(f"批量处理模式: 递归扫描文件夹 '{input_path}'")
        print(f"质量预设: {quality}")

        # 获取所有视频文件
        video_files = []
        for root, dirs, files in os.walk(input_path):
            for filename in files:
                if filename.lower().endswith(video_extensions):
                    # 排除已压缩的文件，避免重复处理
                    if "_compressed" not in filename:
                        video_files.append(os.path.join(root, filename))

        if not video_files:
            print(f"错误: 文件夹 '{input_path}' 中没有找到视频文件")
            sys.exit(1)

        video_files.sort()
        print(f"\n找到 {len(video_files)} 个视频文件:")
        for i, video in enumerate(video_files, 1):
            # 显示相对路径，便于区分子目录中的文件
            rel_path = os.path.relpath(video, input_path)
            print(f"  {i}. {rel_path}")

        print(f"\n开始批量处理...")
        success_count = 0
        fail_count = 0

        for i, video_file in enumerate(video_files, 1):
            print(f"\n{'=' * 60}")
            rel_path = os.path.relpath(video_file, input_path)
            print(f"处理 [{i}/{len(video_files)}]: {rel_path}")
            print(f"{'=' * 60}")

            # 获取视频所在目录
            video_dir = os.path.dirname(video_file)
            if compress_video(video_file, video_dir, quality):
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'=' * 60}")
        print(f"批量处理完成!")
        print(f"成功: {success_count} 个, 失败: {fail_count} 个")
        print(f"{'=' * 60}")
    else:
        print(f"错误: 路径 '{input_path}' 不存在")
        sys.exit(1)


if __name__ == "__main__":
    main()