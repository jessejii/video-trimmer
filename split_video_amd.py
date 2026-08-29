import os
import subprocess
import sys
from typing import List, Optional, Tuple


def parse_time(time_str: str) -> float:
    """解析时间字符串为秒数，支持 HH:MM:SS / MM:SS / SS"""
    try:
        parts = time_str.strip().split(":")
        parts = [float(p) for p in parts]
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            raise ValueError
    except Exception:
        raise ValueError(f"无效的时间格式: {time_str}")


def format_time(seconds: float) -> str:
    """秒转 HH:MM:SS.mmm"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


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
        print(f"获取视频时长失败: {e}")

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


def get_amf_encoder(codec: str) -> str:
    """根据原视频编码选择对应 AMF 编码器"""
    if codec in ("hevc", "h265", "libx265"):
        return "hevc_amf"
    elif codec in ("av1", "libaom-av1"):
        return "av1_amf"
    else:
        return "h264_amf"


def split_video_amd(
    input_file: str,
    split_point_strs: List[str],
    quality: str = "balanced",
    bitrate: Optional[int] = None,
    cqp: bool = False,
    qp: int = 22,
    usage: str = "transcoding",
) -> bool:
    """
    使用 AMD AMF 硬件加速分割视频（帧级精确，无需关键帧对齐）

    参数:
      quality:  AMF 质量预设 (balanced / speed / quality)
      bitrate:  目标视频码率 (kbps)，None 时自动取原视频码率 * 0.9
      cqp:      是否使用 CQP 恒定质量模式（默认 VBR 匹配原码率）
      qp:       CQP 模式下的量化参数 (0-51, 越小质量越好)
      usage:    AMF 用途预设 (transcoding / lowlatency / ultralowlatency)
    """
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

    # 获取视频信息
    duration, codec, src_bitrate = get_video_info(input_file)
    if duration is None:
        return False

    # 第一步：解析所有分割时间
    raw_points: List[float] = []
    for sp_str in split_point_strs:
        try:
            t = parse_time(sp_str)
        except ValueError as e:
            print(f"错误: {e}")
            return False
        raw_points.append(t)

    # 第二步：从小到大排序并去重
    split_times = sorted(set(raw_points))

    # 第三步：统一验证
    for i, t in enumerate(split_times):
        if t <= 0:
            print(f"错误: 分割时间必须大于 0")
            return False
        if t >= duration:
            print(
                f"错误: 分割时间 {t:.2f}s 超出视频总时长 {duration:.2f}s"
            )
            return False

    # 如果去重后数量减少，提示用户
    if len(split_times) < len(raw_points):
        print(f"  📌 检测到重复分割时间，已自动去重，实际分割点: "
              f"{', '.join(format_time(t) for t in split_times)}")
    else:
        print(f"  分割点: {', '.join(format_time(t) for t in split_times)}")

    amf_encoder = get_amf_encoder(codec)
    if amf_encoder not in amf_encoders:
        if "h264_amf" in amf_encoders:
            print(f"⚠️ 不支持 {amf_encoder}，回退使用 h264_amf")
            amf_encoder = "h264_amf"
        elif amf_encoders:
            print(f"⚠️ 不支持 {amf_encoder}，回退使用 {amf_encoders[0]}")
            amf_encoder = amf_encoders[0]
        else:
            print("错误: 没有可用的 AMF 编码器")
            return False

    quality_map = {"balanced": 0, "speed": 1, "quality": 2}
    quality_val = quality_map.get(quality, 0)

    usage_map = {"transcoding": 0, "lowlatency": 1, "ultralowlatency": 2}
    usage_val = usage_map.get(usage, 0)

    # 码率策略：默认 VBR 匹配原视频码率
    if cqp:
        rc_mode = "CQP"
        rc_desc = f"CQP={qp}"
        rate_control_args = ["-qp_i", str(qp), "-qp_p", str(qp)]
    else:
        rc_mode = "VBR"
        if bitrate is not None:
            target_bitrate = bitrate
        elif src_bitrate is not None:
            target_bitrate = max(500, int(src_bitrate * 0.9))
            print(f"\n  检测到原视频码率: {src_bitrate} kbps，目标码率: {target_bitrate} kbps")
        else:
            # 无法检测原码率时使用保守值
            target_bitrate = 4000
            print(f"\n  无法检测原视频码率，使用默认目标码率: {target_bitrate} kbps")
        rc_desc = f"{target_bitrate} kbps VBR"
        rate_control_args = [
            "-rc", "vbr_peak",
            "-b:v", f"{target_bitrate}k",
            "-maxrate", f"{int(target_bitrate * 1.5)}k",
        ]

    # 构建各段时间范围
    segments: List[Tuple[float, float]] = []
    prev = 0.0
    for t in split_times:
        segments.append((prev, t))
        prev = t
    segments.append((prev, duration))

    # 输出文件名
    dir_name = os.path.dirname(input_file)
    base_name = os.path.basename(input_file)
    name_without_ext, ext = os.path.splitext(base_name)
    num_parts = len(split_times) + 1
    output_files = [
        os.path.join(dir_name, f"{name_without_ext}_{i}{ext}")
        for i in range(1, num_parts + 1)
    ]

    print(f"\nAMD 显卡加速分割")
    print(f"{'=' * 50}")
    print(f"  文件: {input_file}")
    print(f"  时长: {duration:.2f}s ({duration / 60:.2f}min)")
    print(f"  原编码: {codec}")
    print(f"  原码率: {src_bitrate if src_bitrate else '未知'} kbps")
    print(f"  AMF 编码器: {amf_encoder}")
    print(f"  码率控制: {rc_mode} ({rc_desc})")
    print(f"  质量预设: {quality}")
    print(f"  输出段数: {num_parts}")
    print(f"  注意: 使用 GPU 硬件编码，帧级精确，无需关键帧对齐")
    print(f"{'=' * 50}")

    # 删除旧输出文件
    _cleanup_files(output_files)

    try:
        for i, (start, end) in enumerate(segments):
            duration_seg = max(0.0, end - start)
            print(f"\n  处理第 {i + 1}/{num_parts} 段 ({start:.2f}s - {end:.2f}s)...")

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
                output_files[i],
            ]

            print(f"    ffmpeg {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)

            out_dur = _get_duration(output_files[i])
            if out_dur is not None:
                print(f"    输出时长: {out_dur:.2f}s (期望: {duration_seg:.2f}s)")

        print(f"\n{'=' * 50}")
        print(f"✅ 分割完成! 共 {num_parts} 段")
        print("输出文件:")
        for i, f in enumerate(output_files):
            start, end = segments[i]
            print(f"  {i + 1}. {f} ({start:.2f}s - {end:.2f}s)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ 处理失败: {e}")
        if e.stderr:
            stderr = e.stderr.decode("utf-8", errors="ignore") if isinstance(e.stderr, bytes) else e.stderr
            for line in stderr.splitlines():
                if "amf" in line.lower() or "d3d11" in line.lower() or "error" in line.lower():
                    print(f"  {line.strip()}")
        _cleanup_files(output_files)
        return False
    except FileNotFoundError:
        print("\n错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False


def _get_duration(file_path: str) -> Optional[float]:
    """获取视频文件时长"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return None


def _cleanup_files(files: List[str]) -> None:
    for f in files:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


def print_usage() -> None:
    print("用法: python split_video_amd.py <视频文件> <分割时间> [可选参数]")
    print("  多个时间点用逗号分隔")
    print()
    print("功能: 使用 AMD 显卡硬件加速分割视频（帧级精确，无需关键帧对齐）")
    print()
    print("可选参数:")
    print("  --quality <preset>    AMF 质量预设 (balanced / speed / quality)")
    print("                        默认 balanced")
    print("  --bitrate <kbps>     目标视频码率 (kbps)，默认自动匹配原视频码率*0.9")
    print("  --cqp                使用 CQP 恒定质量模式（默认 VBR）")
    print("  --qp <value>         CQP 模式下量化参数 0-51 (越小质量越好，默认 22)")
    print("  --usage <mode>       AMF 用途预设 (transcoding / lowlatency / ultralowlatency)")
    print("                        默认 transcoding")
    print()
    print("说明:")
    print("  - 默认 VBR 模式：自动检测原视频码率，确保输出文件大小与原视频接近")
    print("  - CQP 模式 (--cqp)：恒定质量，文件大小不可控（可能比原视频大）")
    print("  - 使用 ffmpeg 的 AMF 硬件加速（需要 AMD 显卡）")
    print("  - 硬件解码 + 硬件编码，速度极快")
    print("  - 帧级精确分割，无需关键帧对齐！")
    print()
    print("示例:")
    print("  python split_video_amd.py video.mp4 1:30")
    print("  python split_video_amd.py video.mp4 1:30,3:00,5:20")
    print("  python split_video_amd.py video.mp4 1:30 --bitrate 5000")
    print('  python split_video_amd.py video.mp4 1:30 --cqp --quality quality --qp 18')


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    args = sys.argv[1:]

    quality = "balanced"
    bitrate = None
    cqp = False
    qp = 22
    usage = "transcoding"

    positional: List[str] = []
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
            i += 2
        elif a == "--cqp":
            cqp = True
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

    if len(positional) < 2:
        print_usage()
        sys.exit(1)

    input_file = positional[0]
    split_point_strs = [
        s.strip() for arg in positional[1:] for s in arg.split(",") if s.strip()
    ]

    ok = split_video_amd(
        input_file,
        split_point_strs,
        quality=quality,
        bitrate=bitrate,
        cqp=cqp,
        qp=qp,
        usage=usage,
    )
    sys.exit(0 if ok else 2)
