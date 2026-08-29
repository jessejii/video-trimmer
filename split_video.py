import os
import subprocess
import sys
from typing import List, Optional, Tuple


def parse_time(time_str: str) -> float:
    """
    解析时间字符串为秒数
    支持格式: HH:MM:SS, MM:SS, SS
    """
    try:
        parts = time_str.strip().split(":")
        parts = [float(p) for p in parts]

        if len(parts) == 1:  # SS
            return parts[0]
        elif len(parts) == 2:  # MM:SS
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:  # HH:MM:SS
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            raise ValueError(f"无效的时间格式: {time_str}")
    except Exception:
        raise ValueError(f"无效的时间格式: {time_str}")


def format_time(seconds: float) -> str:
    """
    秒转 HH:MM:SS.mmm
    """
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def get_video_duration(video_file: str) -> Optional[float]:
    """
    获取视频时长（秒）
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
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        return None


def get_video_info(video_file: str) -> Tuple[Optional[float], str]:
    """
    获取视频信息（时长、视频编码）
    """
    # 获取时长
    duration_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]
    # 获取视频编码
    codec_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]

    try:
        result = subprocess.run(
            duration_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True
        )
        duration = float(result.stdout.strip())
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        duration = None

    try:
        result = subprocess.run(codec_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        codec = result.stdout.strip()
    except Exception:
        codec = "unknown"

    return duration, codec


def get_keyframes(video_file: str) -> List[float]:
    """
    使用 ffprobe 获取视频关键帧时间点（秒）
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-skip_frame",
        "nokey",
        "-show_frames",
        "-show_entries",
        "frame=best_effort_timestamp_time,pkt_pts_time",
        "-of",
        "csv=p=0",
        video_file,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    except Exception as e:
        print(f"获取关键帧失败: {e}")
        return []

    keyframes: List[float] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # csv 可能是 "12.345" 或 "12.345,12.345"
        first = line.split(",")[0].strip()
        try:
            t = float(first)
            if t >= 0:
                keyframes.append(t)
        except Exception:
            continue

    # 去重排序
    keyframes = sorted(set(keyframes))
    return keyframes


def align_cut_points_to_keyframes(
    requested_points: List[float],
    keyframes: List[float],
    duration: float,
    mode: str = "previous",
    tolerance: float = 0.30,
) -> Tuple[List[float], List[Tuple[float, float, float]]]:
    """
    把请求切点对齐到关键帧。

    mode:
      - previous: 向前对齐（<=请求点的最近关键帧，保证 copy 切割稳定）
      - nearest : 最近关键帧（可能前后）
      - strict  : 仅允许在容差范围内关键帧，否则报错

    返回:
      aligned_points, mapping[(requested, aligned, delta)]
    """
    if not keyframes:
        raise ValueError("未检测到关键帧，无法执行关键帧对齐。")

    aligned: List[float] = []
    mapping: List[Tuple[float, float, float]] = []

    for req in requested_points:
        if req <= 0 or req >= duration:
            raise ValueError(f"分割时间 {req:.3f}s 超出有效范围 (0, {duration:.3f})")

        prev_kf = None
        next_kf = None

        # 二分可优化，这里数量通常可接受，使用线性扫描简单稳定
        for kf in keyframes:
            if kf <= req:
                prev_kf = kf
            if kf >= req:
                next_kf = kf
                break

        if mode == "previous":
            if prev_kf is None:
                raise ValueError(f"{req:.3f}s 之前没有可用关键帧，无法向前对齐。")
            chosen = prev_kf
        elif mode == "nearest":
            candidates = []
            if prev_kf is not None:
                candidates.append(prev_kf)
            if next_kf is not None:
                candidates.append(next_kf)
            if not candidates:
                raise ValueError(f"{req:.3f}s 附近无可用关键帧。")
            chosen = min(candidates, key=lambda x: abs(x - req))
        elif mode == "strict":
            candidates = []
            if prev_kf is not None:
                candidates.append(prev_kf)
            if next_kf is not None and next_kf != prev_kf:
                candidates.append(next_kf)
            if not candidates:
                raise ValueError(f"{req:.3f}s 附近无可用关键帧。")
            chosen = min(candidates, key=lambda x: abs(x - req))
            if abs(chosen - req) > tolerance:
                raise ValueError(
                    f"严格关键帧模式: 请求点 {req:.3f}s 与最近关键帧 {chosen:.3f}s "
                    f"偏差 {abs(chosen - req):.3f}s 超过容差 {tolerance:.3f}s"
                )
        else:
            raise ValueError(f"未知关键帧对齐模式: {mode}")

        aligned.append(chosen)
        mapping.append((req, chosen, chosen - req))

    # 去重排序，防止多个请求点映射到同一关键帧
    aligned = sorted(set(aligned))
    return aligned, mapping


def split_video(
    input_file: str,
    split_point_strs: List[str],
    precise: bool = False,
    keyframe_mode: str = "off",
    keyframe_tolerance: float = 0.30,
) -> bool:
    """
    在指定时间点分割视频（支持多分割点）

    参数:
      precise: True=精确分割（帧级精确，重编码视频）
               False=快速无损分割（copy，关键帧对齐更稳）
      keyframe_mode:
               off      = 不做关键帧探测/对齐（沿用原行为）
               previous = 对齐到请求点之前最近关键帧（推荐用于无损）
               nearest  = 对齐到最近关键帧
               strict   = 要求请求点附近必须有关键帧（受 tolerance 约束）
      keyframe_tolerance:
               strict 模式下最大允许偏差（秒）
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False

    # 获取视频信息
    duration, codec = get_video_info(input_file)
    if duration is None:
        return False

    # 解析分割点（先仅检查格式和正数，暂不检查时长）
    requested_points: List[float] = []
    for sp_str in split_point_strs:
        try:
            t = parse_time(sp_str)
        except ValueError as e:
            print(f"错误: {e}")
            return False
        if t <= 0:
            print(f"错误: 分割时间必须大于 0，got {sp_str}")
            return False
        requested_points.append(t)

    # 先对分割时间从小到大排序去重
    requested_points = sorted(set(requested_points))

    # 再统一检查是否超过视频时长
    if requested_points and requested_points[-1] >= duration:
        print(
            f"错误: 最大分割时间 {format_time(requested_points[-1])} "
            f"({requested_points[-1]:.3f}s) 超过或等于视频总时长 "
            f"{format_time(duration)} ({duration:.3f}s)"
        )
        return False
    split_times = requested_points[:]
    mapping: List[Tuple[float, float, float]] = []

    # 可选关键帧对齐（通常用于快速无损分割）
    if keyframe_mode != "off":
        print("\n正在检测关键帧...")
        keyframes = get_keyframes(input_file)
        if not keyframes:
            print("⚠️ 未能获取关键帧，回退为不对齐模式。")
        else:
            try:
                split_times, mapping = align_cut_points_to_keyframes(
                    requested_points,
                    keyframes,
                    duration,
                    mode=keyframe_mode,
                    tolerance=keyframe_tolerance,
                )
            except ValueError as e:
                print(f"错误: {e}")
                return False

    mode_str = "精确分割（帧级精确）" if precise else "快速无损分割（关键帧对齐更稳）"
    print("\n视频信息:")
    print(f"  文件: {input_file}")
    print(f"  时长: {duration:.2f}s ({duration / 60:.2f}min)")
    print(f"  编码: {codec}")
    print(f"  请求分割点: {', '.join(f'{t:.2f}s' for t in requested_points)}")
    print(f"  实际分割点: {', '.join(f'{t:.2f}s' for t in split_times)}")
    print(f"  模式: {mode_str}")
    print(f"  关键帧对齐: {keyframe_mode}")

    if mapping:
        print("\n关键帧对齐详情（请求 -> 实际, 偏差）:")
        for req, actual, delta in mapping:
            sign = "+" if delta >= 0 else ""
            print(f"  {format_time(req)} -> {format_time(actual)} ({sign}{delta:.3f}s)")

    # 构建输出文件名
    dir_name = os.path.dirname(input_file)
    base_name = os.path.basename(input_file)
    name_without_ext, ext = os.path.splitext(base_name)

    num_parts = len(split_times) + 1
    output_files = [
        os.path.join(dir_name, f"{name_without_ext}_{i}{ext}")
        for i in range(1, num_parts + 1)
    ]

    # 构建各段时间范围
    segments: List[Tuple[float, float]] = []
    prev = 0.0
    for t in split_times:
        segments.append((prev, t))
        prev = t
    segments.append((prev, duration))

    if precise:
        return _split_precise(input_file, segments, output_files, num_parts, codec)
    else:
        return _split_fast(
            input_file,
            segments,
            output_files,
            num_parts,
            dir_name,
            name_without_ext,
        )


def _split_precise(
    input_file: str,
    segments: List[Tuple[float, float]],
    output_files: List[str],
    num_parts: int,
    codec: str,
) -> bool:
    """
    精确分割：-ss 放在 -i 后面，确保帧级精确
    对非关键帧起始点重编码视频，保证画面精确
    """
    print("\n使用精确分割模式（帧级精确，非关键帧处重编码视频）...")

    # 根据编码选择重编码参数
    if codec in ("hevc", "h265", "libx265"):
        vcodec = "libx265"
        extra_args = ["-crf", "18", "-preset", "medium"]
    elif codec in ("vp9", "libvpx-vp9"):
        vcodec = "libvpx-vp9"
        extra_args = ["-crf", "18", "-b:v", "0"]
    else:
        vcodec = "libx264"
        extra_args = ["-crf", "18", "-preset", "medium"]

    try:
        for i, (start, end) in enumerate(segments):
            print(f"  生成第 {i + 1}/{num_parts} 部分 ({start:.2f}s - {end:.2f}s)...")
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                input_file,
                "-t",
                str(max(0.0, end - start)),
                "-c:v",
                vcodec,
                *extra_args,
                "-c:a",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                output_files[i],
            ]
            subprocess.run(cmd, check=True, capture_output=True)

        print(f"\n✅ 分割完成! 共 {num_parts} 段")
        print("输出文件:")
        for i, f in enumerate(output_files):
            start, end = segments[i]
            print(f"  {i + 1}. {f} ({start:.2f}s - {end:.2f}s)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ 处理失败: {e}")
        _cleanup_files(output_files)
        return False
    except FileNotFoundError:
        print("\n错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False


def _split_fast(
    input_file: str,
    segments: List[Tuple[float, float]],
    output_files: List[str],
    num_parts: int,
    dir_name: str,
    name_without_ext: str,
) -> bool:
    """
    快速无损分割：参考 remove_segments 的 TS 流方式
    逐段裁剪为 TS，再逐段转封装为目标文件（不重编码）
    """
    temp_dir = os.path.join(dir_name if dir_name else ".", "trimmed_split")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    temp_ts_files: List[str] = []
    try:
        print("\n使用 TS 流逐段裁剪 + 逐段转封装进行快速无损分割...")
        _cleanup_files(output_files)

        # 先逐段裁剪为 TS（copy，-ss 在 -i 后确保时间更贴近请求点）
        for i, (start, end) in enumerate(segments):
            print(f"  提取第 {i + 1}/{num_parts} 段 TS ({start:.2f}s - {end:.2f}s)...")
            temp_ts = os.path.join(temp_dir, f"{name_without_ext}_seg_{i:03d}.ts")
            cmd_ts = [
                "ffmpeg",
                "-y",
                "-i",
                input_file,
                "-ss",
                str(start),
                "-t",
                str(max(0.0, end - start)),
                "-c",
                "copy",
                "-bsf:v",
                "h264_mp4toannexb",
                "-f",
                "mpegts",
                "-avoid_negative_ts",
                "make_zero",
                temp_ts,
            ]
            subprocess.run(cmd_ts, check=True, capture_output=True)
            temp_ts_files.append(temp_ts)

        # 再把每段 TS 转封装为目标输出文件（不重编码）
        for i, ts_file in enumerate(temp_ts_files):
            print(f"  转封装第 {i + 1}/{num_parts} 段 -> {output_files[i]} ...")
            cmd_mux = [
                "ffmpeg",
                "-y",
                "-i",
                ts_file,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                output_files[i],
            ]
            subprocess.run(cmd_mux, check=True, capture_output=True)

        print(f"\n✅ 分割完成! 共 {num_parts} 段")
        print("输出文件:")
        for i, f in enumerate(output_files):
            start, end = segments[i]
            print(f"  {i + 1}. {f} ({start:.2f}s - {end:.2f}s)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ 处理失败: {e}")
        _cleanup_files(output_files)
        return False
    except FileNotFoundError:
        print("\n错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False
    finally:
        # 清理临时 TS 文件与目录
        for ts_file in temp_ts_files:
            if os.path.exists(ts_file):
                try:
                    os.remove(ts_file)
                except Exception:
                    pass
        try:
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except OSError:
            pass


def _cleanup_files(files: List[str]) -> None:
    for f in files:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


def print_usage() -> None:
    print("用法: python split_video.py <视频文件> <分割时间> [可选参数]")
    print("  多个时间点用逗号分隔")
    print("")
    print("可选参数:")
    print("  --precise                 精确分割（重编码视频，慢但精确）")
    print("  --keyframe-mode <mode>    关键帧对齐模式:")
    print("                            off(默认) / previous / nearest / strict")
    print("  --keyframe-tolerance <s>  strict 模式容差秒数（默认 0.30）")
    print("")
    print("说明:")
    print("  - 默认是快速无损分割（copy）")
    print("  - 推荐快速可回拼: --keyframe-mode previous")
    print("")
    print("示例:")
    print("  python split_video.py video.mp4 1:30")
    print("  python split_video.py video.mp4 1:30,3:00,5:20 --keyframe-mode previous")
    print(
        "  python split_video.py video.mp4 1:30,3:00 --keyframe-mode strict --keyframe-tolerance 0.2"
    )
    print("  python split_video.py video.mp4 0:30,1:00:00 --precise")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    args = sys.argv[1:]

    # 解析标志位
    precise_mode = False
    keyframe_mode = "off"
    keyframe_tolerance = 0.30

    i = 0
    positional: List[str] = []
    while i < len(args):
        a = args[i]
        if a == "--precise":
            precise_mode = True
            i += 1
        elif a == "--keyframe-mode":
            if i + 1 >= len(args):
                print("错误: --keyframe-mode 缺少参数")
                sys.exit(1)
            keyframe_mode = args[i + 1].strip().lower()
            if keyframe_mode not in ("off", "previous", "nearest", "strict"):
                print(f"错误: 无效的 keyframe mode: {keyframe_mode}")
                sys.exit(1)
            i += 2
        elif a == "--keyframe-tolerance":
            if i + 1 >= len(args):
                print("错误: --keyframe-tolerance 缺少参数")
                sys.exit(1)
            try:
                keyframe_tolerance = float(args[i + 1])
                if keyframe_tolerance < 0:
                    raise ValueError
            except Exception:
                print("错误: --keyframe-tolerance 必须是非负数")
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

    ok = split_video(
        input_file,
        split_point_strs,
        precise=precise_mode,
        keyframe_mode=keyframe_mode,
        keyframe_tolerance=keyframe_tolerance,
    )
    sys.exit(0 if ok else 2)
