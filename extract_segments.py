import os
import subprocess
import sys
from typing import List, Optional, Tuple


def format_time(seconds: float) -> str:
    """秒转 HH:MM:SS.mmm"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def parse_time(time_str, duration=None):
    """
    解析时间字符串为秒数
    支持格式: HH:MM:SS, MM:SS, SS, "结尾"（替换为视频总时长）

    参数:
        time_str: 时间字符串，例如 "1:30", "1:30:45", "结尾"
        duration: 视频总时长（秒），当 time_str 为"结尾"时使用

    返回:
        秒数（浮点数）
    """
    time_str = time_str.strip()
    if time_str == "结尾":
        if duration is None:
            raise ValueError('使用"结尾"时需要提供视频总时长')
        return duration

    parts = time_str.split(":")
    parts = [float(p) for p in parts]

    if len(parts) == 1:  # SS
        return parts[0]
    elif len(parts) == 2:  # MM:SS
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:  # HH:MM:SS
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError(f"无效的时间格式: {time_str}")


def parse_segments(segments_str, duration=None):
    """
    解析要提取的时间段字符串

    参数:
        segments_str: 时间段字符串，例如 "1:00-2:00,5:00-结尾"
        duration: 视频总时长（秒），用于解析"结尾"关键字

    返回:
        时间段列表，例如 [(60, 120), (300, duration)]
    """
    segments = []
    for segment in segments_str.split(","):
        segment = segment.strip()
        if not segment:
            continue
        if "-" not in segment:
            print(f"警告: 跳过无效的时间段格式: {segment}")
            continue

        start_str, end_str = segment.split("-", 1)
        start = parse_time(start_str, duration)
        end = parse_time(end_str, duration)

        if start >= end:
            print(f"警告: 跳过无效的时间段（开始时间 >= 结束时间）: {segment}")
            continue

        segments.append((start, end))

    # 按开始时间排序
    segments.sort(key=lambda x: x[0])
    return segments


def get_video_duration(video_file):
    """
    获取视频时长（秒）

    参数:
        video_file: 视频文件路径

    返回:
        视频时长（秒）
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        return None


def get_video_codec(video_file):
    """
    获取视频的视频编码格式

    参数:
        video_file: 视频文件路径

    返回:
        视频编码名称（小写），例如 "h264", "hevc", "vp9"；无视频流则返回 None
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        codec = result.stdout.strip().lower()
        return codec if codec else None
    except Exception as e:
        print(f"获取视频编码失败: {e}")
        return None


def get_video_bitrate(video_file):
    """
    获取视频的视频码率（kbps）

    参数:
        video_file: 视频文件路径

    返回:
        码率（kbps），无法检测时返回 None
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw = result.stdout.strip()
        if raw and raw != "N/A":
            return int(raw) // 1000  # bps -> kbps
    except Exception:
        pass
    return None


def check_amf_support() -> Tuple[bool, List[str]]:
    """检查可用 AMF 编码器"""
    supported = []
    cmd = ["ffmpeg", "-encoders"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout
        for enc in ["h264_amf", "hevc_amf", "av1_amf"]:
            if f" {enc} " in output or f"\n{enc} " in output:
                supported.append(enc)
    except Exception:
        pass
    return len(supported) > 0, supported


def get_amf_encoder(codec) -> str:
    """根据原视频编码选择对应 AMF 编码器"""
    if codec in ("hevc", "h265", "libx265"):
        return "hevc_amf"
    elif codec in ("av1", "libaom-av1"):
        return "av1_amf"
    else:
        return "h264_amf"


# 辅助函数：运行 ffmpeg 命令，失败时打印完整错误信息
def run_ffmpeg(cmd, description=""):
    print(f"\n{description}: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 执行失败 (返回码 {e.returncode}):")
        if e.stdout:
            print("  stdout:", e.stdout.strip())
        if e.stderr:
            print("  stderr:", e.stderr.strip())
        raise
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        raise


def extract_video_segments(
    input_file, extract_segments_str, output_dir=None
):
    """
    快速模式：直接流复制提取视频中的指定时间段，每个段输出为单独文件（无损、速度极快）

    参数:
        input_file: 输入视频文件
        extract_segments_str: 要提取的时间段字符串，例如 "1:00-2:00,5:00-6:00"
        output_dir: 输出文件夹，默认为输入文件所在文件夹
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    input_dir = os.path.dirname(input_file) if os.path.dirname(input_file) else "."

    if output_dir is None:
        output_dir = input_dir

    # 创建输出文件夹
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建输出文件夹: {output_dir}")

    # 获取视频时长（需要在解析时间段之前获取，以支持"结尾"关键字）
    duration = get_video_duration(input_file)
    if duration is None:
        return False

    print(f"\n视频总时长: {duration:.2f}s ({duration / 60:.2f}min)")

    # 获取视频编码（用于诊断信息）
    video_codec = get_video_codec(input_file)
    if video_codec:
        print(f"视频编码: {video_codec}")
    else:
        print("警告: 无法检测视频编码，可能没有视频流")

    # 解析要提取的时间段
    try:
        extract_segments = parse_segments(extract_segments_str, duration)
    except Exception as e:
        print(f"解析时间段失败: {e}")
        return False

    if not extract_segments:
        print("错误: 没有有效的时间段需要提取")
        return False

    print(f"\n要提取的时间段:")
    for start, end in extract_segments:
        end_label = f"{end:.2f}s ({end / 60:.2f}min)"
        if abs(end - duration) < 0.001:
            end_label += " [结尾]"
        print(f"  {start:.2f}s - {end:.2f}s ({start / 60:.2f}min - {end / 60:.2f}min)")

    # 逐个提取每个时间段为独立文件
    success_count = 0
    for i, (start, end) in enumerate(extract_segments):
        duration_seg = end - start

        # 生成输出文件名：原文件名_序号_开始时间-结束时间.mp4
        start_label = format_time(start).replace(":", ".")
        end_label = format_time(end).replace(":", ".")
        output_file = os.path.join(
            output_dir, f"{base_name}_{i + 1:03d}_{start_label}-{end_label}.mp4"
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", input_file,
            "-t", str(duration_seg),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_file,
        ]

        try:
            run_ffmpeg(
                cmd,
                description=f"提取片段 {i + 1}/{len(extract_segments)}: {start:.2f}s - {end:.2f}s",
            )
            print(f"  输出文件: {output_file}")
            success_count += 1
        except subprocess.CalledProcessError:
            print(f"  提取片段 {i + 1} 失败")
        except FileNotFoundError:
            return False

    print(f"\n提取完成! 成功: {success_count} 个, 失败: {len(extract_segments) - success_count} 个")
    return success_count > 0


def extract_video_segments_amd(
    input_file: str,
    extract_segments_str: str,
    output_dir: Optional[str] = None,
    quality: str = "balanced",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
    usage: str = "transcoding",
) -> bool:
    """
    AMD AMF 模式：使用硬件加速重新编码提取指定时间段，帧级精确分割

    参数:
        input_file: 输入视频文件
        extract_segments_str: 要提取的时间段字符串，例如 "1:00-2:00,5:00-6:00"
        output_dir: 输出文件夹，默认为输入文件所在文件夹
        quality:    AMF 质量预设 (balanced / speed / quality)
        bitrate:    目标视频码率 (kbps)，None 时自动取原视频码率 * 0.9
        cqp:        是否使用 CQP 恒定质量模式（默认 VBR 匹配原码率）
        qp:         CQP 模式下的量化参数 (0-51, 越小质量越好)
        usage:      AMF 用途预设 (transcoding / lowlatency / ultralowlatency)
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False

    # 检测 AMF 支持
    amf_ok, amf_encoders = check_amf_support()
    if not amf_ok:
        print("错误: 未检测到 AMD AMF 编码器！")
        print("请确保:")
        print("  1. 已安装 AMD 显卡驱动（含 AMF 运行时）")
        print("  2. 使用的 ffmpeg 版本编译了 AMF 支持")
        print("  3. 使用 `ffmpeg -encoders | findstr amf` 确认编码器可用")
        return False

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    input_dir = os.path.dirname(input_file) if os.path.dirname(input_file) else "."

    if output_dir is None:
        output_dir = input_dir

    # 创建输出文件夹
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建输出文件夹: {output_dir}")

    # 获取视频信息（需要在解析时间段之前获取，以支持"结尾"关键字）
    duration = get_video_duration(input_file)
    if duration is None:
        return False

    video_codec = get_video_codec(input_file)
    src_bitrate = get_video_bitrate(input_file)

    print(f"\n视频总时长: {duration:.2f}s ({duration / 60:.2f}min)")
    print(f"视频编码: {video_codec if video_codec else 'unknown'}")

    # 解析要提取的时间段
    try:
        extract_segments = parse_segments(extract_segments_str, duration)
    except Exception as e:
        print(f"解析时间段失败: {e}")
        return False

    if not extract_segments:
        print("错误: 没有有效的时间段需要提取")
        return False

    print(f"\n要提取的时间段:")
    for start, end in extract_segments:
        print(f"  {format_time(start)} - {format_time(end)} ({start / 60:.2f}min - {end / 60:.2f}min)")

    # 选择 AMF 编码器
    amf_encoder = get_amf_encoder(video_codec)
    if amf_encoder not in amf_encoders:
        if "h264_amf" in amf_encoders:
            print(f"警告: 不支持 {amf_encoder}，回退使用 h264_amf")
            amf_encoder = "h264_amf"
        elif amf_encoders:
            print(f"警告: 不支持 {amf_encoder}，回退使用 {amf_encoders[0]}")
            amf_encoder = amf_encoders[0]
        else:
            print("错误: 没有可用的 AMF 编码器")
            return False

    # 码率策略：默认 VBR 匹配原视频码率
    if cqp:
        rc_desc = f"CQP={qp}"
        rate_control_args = ["-qp_i", str(qp), "-qp_p", str(qp)]
    else:
        if bitrate is not None:
            target_bitrate = bitrate
        elif src_bitrate is not None:
            target_bitrate = max(500, int(src_bitrate * 0.9))
            print(f"检测到原视频码率: {src_bitrate} kbps，目标码率: {target_bitrate} kbps")
        else:
            target_bitrate = 4000
            print(f"无法检测原视频码率，使用默认目标码率: {target_bitrate} kbps")
        rc_desc = f"{target_bitrate} kbps VBR"
        rate_control_args = [
            "-rc", "vbr_peak",
            "-b:v", f"{target_bitrate}k",
            "-maxrate", f"{int(target_bitrate * 1.5)}k",
        ]

    quality_map = {"balanced": 0, "speed": 1, "quality": 2}
    quality_val = quality_map.get(quality, 0)

    usage_map = {"transcoding": 0, "lowlatency": 1, "ultralowlatency": 2}
    usage_val = usage_map.get(usage, 0)

    # 逐个提取每个时间段为独立文件
    success_count = 0
    for i, (start, end) in enumerate(extract_segments):
        duration_seg = end - start

        # 生成输出文件名：原文件名_序号_开始时间-结束时间.mp4
        start_label = format_time(start).replace(":", ".")
        end_label = format_time(end).replace(":", ".")
        output_file = os.path.join(
            output_dir, f"{base_name}_{i + 1:03d}_{start_label}-{end_label}.mp4"
        )

        cmd = [
            "ffmpeg", "-y",
            "-hwaccel", "amf",
            "-hwaccel_output_format", "d3d11",
            "-i", input_file,
            "-ss", str(start),
            "-t", str(duration_seg),
            "-c:v", amf_encoder,
            "-quality", str(quality_val),
            "-usage", str(usage_val),
            *rate_control_args,
            "-c:a", "copy",
            "-avoid_negative_ts", "make_zero",
            output_file,
        ]

        try:
            run_ffmpeg(
                cmd,
                description=f"提取片段 {i + 1}/{len(extract_segments)}: {format_time(start)} - {format_time(end)} [{rc_desc}]",
            )
            print(f"  输出文件: {output_file}")
            success_count += 1
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"  提取片段 {i + 1} 失败")

    print(f"\n提取完成! 成功: {success_count} 个, 失败: {len(extract_segments) - success_count} 个")
    return success_count > 0


def process_batch(input_path, extract_segments_str, output_dir, extract_func):
    """
    批量处理文件夹中的所有视频

    参数:
        input_path: 输入文件夹
        extract_segments_str: 要提取的时间段字符串
        output_dir: 输出文件夹
        extract_func: 单文件提取函数 extract_func(video_file, segments_str, output_dir)

    返回:
        是否全部成功
    """
    print(f"批量处理模式: 扫描文件夹 '{input_path}'")

    # 支持的视频格式
    video_extensions = (
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".flv",
        ".wmv",
        ".m4v",
        ".webm",
        ".ts",
    )

    # 获取所有视频文件
    video_files = []
    for filename in os.listdir(input_path):
        if filename.lower().endswith(video_extensions):
            video_files.append(os.path.join(input_path, filename))

    if not video_files:
        print(f"错误: 文件夹 '{input_path}' 中没有找到视频文件")
        sys.exit(1)

    video_files.sort()
    print(f"\n找到 {len(video_files)} 个视频文件:")
    for i, video in enumerate(video_files, 1):
        print(f"  {i}. {os.path.basename(video)}")

    # 确定输出文件夹
    if output_dir and os.path.isdir(output_dir):
        pass  # 使用已有文件夹
    elif output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"\n已创建输出文件夹: {output_dir}")
    else:
        # 默认输出到输入文件夹
        output_dir = input_path

    print(f"\n开始批量处理...")
    success_count = 0
    fail_count = 0

    for i, video_file in enumerate(video_files, 1):
        print(f"\n{'=' * 60}")
        print(f"处理 [{i}/{len(video_files)}]: {os.path.basename(video_file)}")
        print(f"{'=' * 60}")

        if extract_func(video_file, extract_segments_str, output_dir=output_dir):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'=' * 60}")
    print(f"批量处理完成!")
    print(f"成功: {success_count} 个, 失败: {fail_count} 个")
    print(f"{'=' * 60}")
    return fail_count == 0


def print_usage() -> None:
    print("用法: python extract_segments.py <输入视频/文件夹> <提取时间段> [输出文件夹] [可选参数]")
    print("\n示例:")
    print("  # 处理单个文件，提取指定时间段（输出到同目录，默认快速模式）")
    print('  python extract_segments.py video.mp4 "1:00-2:00,5:00-6:00"')
    print()
    print("  # 每个段输出为单独文件，文件名包含序号和时间范围")
    print('  # 例如: video_001_01.00.00-02.00.00.mp4')
    print()
    print('  # 使用"结尾"代替具体时间，表示到视频末尾')
    print('  python extract_segments.py video.mp4 "1:00:00-结尾"')
    print()
    print("  # 多段提取（逗号分隔）")
    print(
        '  python extract_segments.py video.mp4 "01:03:34.000-01:05:14.000, 01:25:41.000-结尾"'
    )
    print()
    print("  # 指定输出文件夹")
    print(
        '  python extract_segments.py video.mp4 "1:00-2:00,5:00-6:00" output_folder'
    )
    print()
    print("  # 批量处理文件夹中的所有视频")
    print('  python extract_segments.py video_folder "1:00-2:00,5:00-结尾"')
    print()
    print("  # 批量处理并指定输出文件夹")
    print(
        '  python extract_segments.py video_folder "1:00-2:00,5:00-6:00" output_folder'
    )
    print()
    print("  # 使用 AMD 硬件加速模式（重新编码，帧级精确分割）")
    print('  python extract_segments.py --amd video.mp4 "1:00-2:00,5:00-6:00"')
    print("\n时间格式支持:")
    print("  - HH:MM:SS (例如: 1:30:45)")
    print("  - HH:MM:SS.mmm (例如: 01:03:34.000)")
    print("  - MM:SS (例如: 1:30)")
    print("  - SS (例如: 90)")
    print("  - 结尾 (表示视频末尾)")
    print("\n可选参数:")
    print("  --amd                使用 AMD AMF 硬件加速（默认不启用，使用快速流复制模式）")
    print("  --quality <preset>   AMF 质量预设 (balanced / speed / quality)")
    print("  --bitrate <kbps>     目标视频码率 (kbps)，默认自动匹配原视频码率*0.9")
    print("  --cqp                使用 CQP 恒定质量模式（默认 VBR）")
    print("  --qp <value>         CQP 模式下量化参数 0-51 (越小质量越好，默认 22)")
    print("  --usage <mode>       AMF 用途预设 (transcoding / lowlatency / ultralowlatency)")
    print("\n说明:")
    print("  - 默认快速模式: 直接流复制（-c copy），无损且速度极快，切点对齐关键帧")
    print("  - --amd 模式: AMD 硬件解码+编码重新压缩，帧级精确，需要 AMD 显卡")


def parse_args(args: List[str]):
    """
    解析命令行参数

    返回:
        (options 字典, 位置参数列表)
    """
    options = {
        "amd": False,
        "quality": "balanced",
        "bitrate": None,
        "cqp": False,
        "qp": 22,
        "usage": "transcoding",
    }

    positional: List[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--amd":
            options["amd"] = True
            i += 1
        elif a == "--quality":
            if i + 1 >= len(args):
                print("错误: --quality 缺少参数")
                sys.exit(1)
            quality = args[i + 1].strip().lower()
            if quality not in ("balanced", "speed", "quality"):
                print(f"错误: 无效的 quality 值: {quality}，可选: balanced/speed/quality")
                sys.exit(1)
            options["quality"] = quality
            i += 2
        elif a == "--bitrate":
            if i + 1 >= len(args):
                print("错误: --bitrate 缺少参数")
                sys.exit(1)
            try:
                bitrate = int(args[i + 1])
                if bitrate < 100:
                    print("错误: bitrate 过小，最少 100 kbps")
                    sys.exit(1)
            except Exception:
                print("错误: --bitrate 必须是整数 (kbps)")
                sys.exit(1)
            options["bitrate"] = bitrate
            i += 2
        elif a == "--cqp":
            options["cqp"] = True
            i += 1
        elif a == "--qp":
            if i + 1 >= len(args):
                print("错误: --qp 缺少参数")
                sys.exit(1)
            try:
                qp = int(args[i + 1])
                if qp < 0 or qp > 51:
                    raise ValueError
            except Exception:
                print("错误: --qp 必须是 0-51 的整数")
                sys.exit(1)
            options["qp"] = qp
            i += 2
        elif a == "--usage":
            if i + 1 >= len(args):
                print("错误: --usage 缺少参数")
                sys.exit(1)
            usage = args[i + 1].strip().lower()
            if usage not in ("transcoding", "lowlatency", "ultralowlatency"):
                print(f"错误: 无效的 usage 值: {usage}")
                sys.exit(1)
            options["usage"] = usage
            i += 2
        elif a.startswith("--"):
            print(f"错误: 未知参数: {a}")
            sys.exit(1)
        else:
            positional.append(a)
            i += 1

    return options, positional


def main() -> None:
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    options, positional = parse_args(sys.argv[1:])

    if len(positional) < 2:
        print_usage()
        sys.exit(1)

    input_path = positional[0]
    extract_segments_str = positional[1]
    output_dir = positional[2] if len(positional) > 2 else None

    def extract_single(video_file, segments_str, out_dir=None):
        if options["amd"]:
            return extract_video_segments_amd(
                video_file,
                segments_str,
                out_dir,
                quality=options["quality"],
                bitrate=options["bitrate"],
                cqp=options["cqp"],
                qp=options["qp"],
                usage=options["usage"],
            )
        return extract_video_segments(video_file, segments_str, out_dir)

    # 检查输入是文件还是文件夹
    if os.path.isfile(input_path):
        # 单个文件处理
        ok = extract_single(input_path, extract_segments_str, output_dir)
        sys.exit(0 if ok else 2)
    elif os.path.isdir(input_path):
        # 批量处理文件夹
        ok = process_batch(input_path, extract_segments_str, output_dir, extract_single)
        sys.exit(0 if ok else 2)
    else:
        print(f"错误: 路径 '{input_path}' 不存在")
        sys.exit(1)


if __name__ == "__main__":
    main()
