"""
使用 AMD 显卡（AMF 硬件加速）批量裁剪视频的开头和结尾。
- 帧级精确，无需关键帧对齐
- 硬件解码 + 硬件编码，速度极快
- 与 batch_trim_edges.py 的目录扫描与参数语义保持一致

用法:
    python batch_trim_edges_amd.py <文件夹路径> [开头切多少] [结尾切多少]
示例:
    python batch_trim_edges_amd.py "C:\Videos" 00:01:00 00:02:00
"""

import os
import subprocess
import sys
from typing import List, Optional, Tuple


# ============================================================================
# 时间解析与格式化
# ============================================================================

def parse_time(time_str: str) -> float:
    """解析时间字符串为秒数，支持 HH:MM:SS / MM:SS / SS"""
    try:
        parts = time_str.strip().split(":")
        parts = [float(p) for p in parts]
    except Exception:
        raise ValueError(f"时间包含无效字符: {time_str}")

    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError(f"无效的时间格式: {time_str}")


def format_time(seconds: float) -> str:
    """秒转 HH:MM:SS.mmm"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ============================================================================
# 视频信息获取
# ============================================================================

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


# ============================================================================
# AMD AMF 支持检测
# ============================================================================

def check_amf_support() -> Tuple[bool, List[str]]:
    """检查可用 AMF 编码器"""
    supported: List[str] = []
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


def get_amf_encoder(codec: str, available: List[str]) -> str:
    """根据原视频编码选择对应 AMF 编码器（带回退）"""
    preferred = None
    if codec in ("hevc", "h265", "libx265"):
        preferred = "hevc_amf"
    elif codec in ("av1", "libaom-av1"):
        preferred = "av1_amf"
    else:
        preferred = "h264_amf"

    if preferred in available:
        return preferred
    if "h264_amf" in available:
        return "h264_amf"
    if available:
        return available[0]
    return "h264_amf"


# ============================================================================
# 核心：使用 AMF 硬件加速裁剪单文件
# ============================================================================

def trim_video_amd(
    input_file: str,
    start_to_cut: float,
    end_to_cut: float,
    output_dir: str,
    amf_encoders: List[str],
    quality: str = "balanced",
    usage: str = "transcoding",
) -> bool:
    """使用 AMD AMF 硬件加速裁剪单个视频的开头/结尾"""
    if not os.path.exists(input_file):
        print(f"  错误: 文件 '{input_file}' 不存在")
        return False

    duration, codec, src_bitrate = get_video_info(input_file)
    if duration is None:
        return False

    keep_start = start_to_cut
    keep_end = duration - end_to_cut
    keep_duration = keep_end - keep_start

    if keep_duration <= 0:
        print(
            f"  错误: 裁剪后的时长小于等于0 "
            f"(总长: {duration:.2f}s, 切开头: {start_to_cut:.2f}s, 切结尾: {end_to_cut:.2f}s)"
        )
        return False

    amf_encoder = get_amf_encoder(codec, amf_encoders)
    if amf_encoder != get_amf_encoder(codec, amf_encoders):
        pass  # 已在 get_amf_encoder 中处理

    quality_map = {"balanced": 0, "speed": 1, "quality": 2}
    quality_val = quality_map.get(quality, 0)

    usage_map = {"transcoding": 0, "lowlatency": 1, "ultralowlatency": 2}
    usage_val = usage_map.get(usage, 0)

    # 目标码率策略：优先使用原视频码率 * 0.9，否则 4000 kbps 保守值
    if src_bitrate is not None:
        target_bitrate = max(500, int(src_bitrate * 0.9))
    else:
        target_bitrate = 4000

    rate_control_args = [
        "-rc", "vbr_peak",
        "-b:v", f"{target_bitrate}k",
        "-maxrate", f"{int(target_bitrate * 1.5)}k",
    ]

    # 输出路径
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.basename(input_file)
    name_without_ext, ext = os.path.splitext(base_name)
    output_file = os.path.join(output_dir, base_name)

    # 若输出已存在则删除，避免 ffmpeg 询问
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except Exception:
            pass

    print(f"  原编码: {codec} | 原码率: {src_bitrate if src_bitrate else '未知'} kbps")
    print(f"  AMF 编码器: {amf_encoder} | 码率: {target_bitrate} kbps VBR | 质量: {quality}")
    print(f"  保留区间: {format_time(keep_start)} - {format_time(keep_end)} (时长 {keep_duration:.2f}s)")

    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "amf",
        "-hwaccel_output_format", "d3d11",
        "-i", input_file,
        "-ss", str(keep_start),
        "-t", str(keep_duration),
        "-c:v", amf_encoder,
        "-quality", str(quality_val),
        "-usage", str(usage_val),
        *rate_control_args,
        "-c:a", "copy",
        "-avoid_negative_ts", "make_zero",
        output_file,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  成功 (AMD AMF 硬件加速): {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  失败: {e}")
        if e.stderr:
            stderr = e.stderr.decode("utf-8", errors="ignore") if isinstance(e.stderr, bytes) else e.stderr
            for line in stderr.splitlines():
                ll = line.lower()
                if "amf" in ll or "d3d11" in ll or "error" in ll:
                    print(f"    {line.strip()}")
        # 清理失败产物
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception:
                pass
        return False
    except FileNotFoundError:
        print("  错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False


# ============================================================================
# 主流程
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python batch_trim_edges_amd.py <文件夹路径> [开头切多少] [结尾切多少] [可选参数]")
        print("示例: python batch_trim_edges_amd.py \"C:\\Videos\" 00:01:00 00:02:00")
        print()
        print("可选参数:")
        print("  --quality <preset>   AMF 质量预设 (balanced / speed / quality)，默认 balanced")
        print("  --usage <mode>       AMF 用途预设 (transcoding / lowlatency / ultralowlatency)，默认 transcoding")
        sys.exit(1)

    args = sys.argv[1:]

    # 解析位置参数与可选参数
    positional: List[str] = []
    quality = "balanced"
    usage = "transcoding"

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--quality":
            if i + 1 >= len(args):
                print("错误: --quality 缺少参数")
                sys.exit(1)
            quality = args[i + 1].strip().lower()
            if quality not in ("balanced", "speed", "quality"):
                print(f"错误: 无效的 quality 值: {quality}，可选: balanced/speed/quality")
                sys.exit(1)
            i += 2
        elif a == "--usage":
            if i + 1 >= len(args):
                print("错误: --usage 缺少参数")
                sys.exit(1)
            usage = args[i + 1].strip().lower()
            if usage not in ("transcoding", "lowlatency", "ultralowlatency"):
                print(f"错误: 无效的 usage 值: {usage}")
                sys.exit(1)
            i += 2
        else:
            positional.append(a)
            i += 1

    if not positional:
        print("错误: 请提供文件夹路径")
        sys.exit(1)

    input_dir = positional[0]
    start_to_cut_str = positional[1] if len(positional) > 1 else "0"
    end_to_cut_str = positional[2] if len(positional) > 2 else "0"

    if not os.path.isdir(input_dir):
        print(f"错误: 文件夹 '{input_dir}' 不存在")
        sys.exit(1)

    # 解析时间
    try:
        start_to_cut = parse_time(start_to_cut_str)
        end_to_cut = parse_time(end_to_cut_str)
    except ValueError as e:
        print(f"解析时间失败: {e}")
        sys.exit(1)

    # 检测 AMF 支持
    amf_ok, amf_encoders = check_amf_support()
    if not amf_ok:
        print("错误: 未检测到 AMD AMF 编码器！")
        print("请确保:")
        print("  1. 已安装 AMD 显卡驱动（含 AMF 运行时）")
        print("  2. 使用的 ffmpeg 版本编译了 AMF 支持")
        print("  3. 使用 `ffmpeg -encoders | findstr amf` 确认编码器可用")
        sys.exit(2)

    print(f"检测到 AMD AMF 编码器: {', '.join(amf_encoders)}")

    # 输出文件夹
    output_dir = os.path.join(input_dir, "cut")

    # 扫描视频文件
    video_extensions = (".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".m4v", ".webm", ".ts")
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(video_extensions)]

    if not files:
        print(f"文件夹中没有找到视频文件: {input_dir}")
        sys.exit(1)

    print(f"找到 {len(files)} 个视频文件")
    print(f"计划切掉开头: {start_to_cut_str}, 切掉结尾: {end_to_cut_str}")
    print(f"输出目录: {output_dir}")
    print(f"质量预设: {quality} | 用途: {usage}")
    print("-" * 60)

    success = 0
    fail = 0

    for idx, f in enumerate(files, 1):
        input_path = os.path.join(input_dir, f)
        print(f"[{idx}/{len(files)}] 处理: {f}")
        if trim_video_amd(
            input_path,
            start_to_cut,
            end_to_cut,
            output_dir,
            amf_encoders,
            quality=quality,
            usage=usage,
        ):
            success += 1
        else:
            fail += 1
        print("-" * 60)

    print("=" * 60)
    print(f"完成! 成功: {success}, 失败: {fail}")
    print("=" * 60)


if __name__ == "__main__":
    main()
