import os
import re
import subprocess
import sys


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
    解析要删除的时间段字符串

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


def calculate_keep_segments(remove_segments, duration):
    """
    根据要删除的时间段，计算要保留的时间段

    参数:
        remove_segments: 要删除的时间段列表 [(start, end), ...]
        duration: 视频总时长

    返回:
        要保留的时间段列表 [(start, end), ...]
    """
    keep_segments = []
    current_time = 0

    for start, end in remove_segments:
        # 添加删除段之前的保留段
        if current_time < start:
            keep_segments.append((current_time, start))
        current_time = max(current_time, end)

    # 添加最后一个保留段
    if current_time < duration:
        keep_segments.append((current_time, duration))

    return keep_segments


def remove_video_segments(
    input_file, remove_segments_str, output_file=None, output_dir=None
):
    """
    删除视频中的指定时间段并合并剩余部分

    参数:
        input_file: 输入视频文件
        remove_segments_str: 要删除的时间段字符串，例如 "1:00-2:00,5:00-6:00"
        output_file: 输出文件名，默认为 input_trimmed.mp4
        output_dir: 输出文件夹，默认为输入文件所在文件夹
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False

    # 设置输出文件名
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    input_dir = os.path.dirname(input_file) if os.path.dirname(input_file) else "."

    # 标记是否需要替换原文件
    replace_original = False

    if output_file is None:
        if output_dir:
            # 指定了输出文件夹，直接输出
            output_file = os.path.join(output_dir, f"{base_name}.mp4")
        else:
            # 没有指定输出文件夹，使用临时文件，稍后替换原文件
            import tempfile

            temp_fd, output_file = tempfile.mkstemp(suffix=".mp4", dir=input_dir)
            os.close(temp_fd)
            replace_original = True

    # 创建输出文件夹
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建输出文件夹: {output_dir}")

    # 获取视频时长（需要在解析时间段之前获取，以支持"结尾"关键字）
    duration = get_video_duration(input_file)
    if duration is None:
        return False

    print(f"\n视频总时长: {duration:.2f}s ({duration / 60:.2f}min)")

    # 解析要删除的时间段
    try:
        remove_segments = parse_segments(remove_segments_str, duration)
    except Exception as e:
        print(f"解析时间段失败: {e}")
        return False

    if not remove_segments:
        print("错误: 没有有效的时间段需要删除")
        return False

    print(f"\n要删除的时间段:")
    for start, end in remove_segments:
        end_label = f"{end:.2f}s ({end / 60:.2f}min)"
        if abs(end - duration) < 0.001:
            end_label += " [结尾]"
        print(f"  {start:.2f}s - {end:.2f}s ({start / 60:.2f}min - {end / 60:.2f}min)")

    def format_time_ms(seconds, duration=None, use_end_label=False):
        """将秒数格式化为 HH:MM:SS.mmm。"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        if use_end_label and (abs(seconds - duration) < 0.001 if duration else False):
            return "结尾"
        return f"{h:02d}:{m:02d}:{s:06.3f}"

    def segments_to_csv(segments, duration=None, use_end_label=False):
        """将时间段列表格式化为逗号分隔字符串: start-end,start-end"""
        return ",".join(
            f"{format_time_ms(start, duration, use_end_label=False)}-"
            f"{format_time_ms(end, duration, use_end_label=use_end_label)}"
            for start, end in segments
        )

    def run_srt_sync_with_actual_removed_csv(actual_removed_csv):
        """
        自动同步同名字幕（优先 .srt，其次 .srt.txt）。
        使用 remove_srt_segments.py，并将“实际删除片段CSV”作为 ranges 传入。
        """
        base_no_ext = os.path.splitext(input_file)[0]
        candidate_srt_files = [f"{base_no_ext}.srt", f"{base_no_ext}.srt.txt"]
        srt_file = next((p for p in candidate_srt_files if os.path.exists(p)), None)
        if not srt_file:
            print(
                f"未找到同名字幕，跳过自动同步: {candidate_srt_files[0]} 或 {candidate_srt_files[1]}"
            )
            return

        # 输出字幕命名：与最终输出视频同目录，文件名与最终输出视频同名，后缀 .srt
        # 若最终输出视频是 xxx_processed.mp4，则字幕输出 xxx_processed.srt
        final_video_for_srt = (
            os.path.join(input_dir, f"{base_name}_processed.mp4")
            if replace_original
            else output_file
        )
        output_srt = os.path.splitext(final_video_for_srt)[0] + ".srt"

        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "remove_srt_segments.py"
        )
        cmd_srt = [
            sys.executable,
            script_path,
            srt_file,
            actual_removed_csv,
            "-o",
            output_srt,
        ]

        print(f"自动同步字幕命令: {' '.join(cmd_srt)}")
        try:
            subprocess.run(cmd_srt, check=True, capture_output=True, text=True)
            print(f"字幕已同步输出: {output_srt}")
        except subprocess.CalledProcessError as e:
            print("自动同步字幕失败:")
            if e.stdout:
                print(e.stdout.strip())
            if e.stderr:
                print(e.stderr.strip())
        except FileNotFoundError:
            print("自动同步字幕失败: 未找到 Python 或 remove_srt_segments.py")

    segments_str = ",".join(
        f"{format_time_ms(start)} - {format_time_ms(end, duration)}"
        for start, end in remove_segments
    )
    print(f"要删除的时间段2: {segments_str}")

    # 计算要保留的时间段
    keep_segments = calculate_keep_segments(remove_segments, duration)
    print(
        f"保留片段边界CSV(计划): {segments_to_csv(keep_segments, duration, use_end_label=True)}"
    )

    if not keep_segments:
        print("错误: 删除所有时间段后没有剩余内容")
        return False

    print(f"\n要保留的时间段:")
    for start, end in keep_segments:
        print(f"  {start:.2f}s - {end:.2f}s ({start / 60:.2f}min - {end / 60:.2f}min)")

    # 如果只有一个保留段，使用 TS 流方式裁剪
    if len(keep_segments) == 1:
        start, end = keep_segments[0]
        duration_seg = end - start

        # 先转为 TS 格式裁剪（TS 天然支持流级拼接，避免关键帧问题）
        # 注意: -ss 放在 -i 之后（output seeking），确保精确裁切，与字幕时间对齐
        temp_ts = os.path.join(input_dir, f"{base_name}_temp.ts")
        cmd_ts = [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-ss",
            str(start),
            "-t",
            str(duration_seg),
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

        # 再将 TS 转回 MP4（remux，不重编码）
        cmd_mp4 = [
            "ffmpeg",
            "-y",
            "-i",
            temp_ts,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_file,
        ]

        print(f"\n执行命令 (TS裁剪): {' '.join(cmd_ts)}")
        print(f"执行命令 (TS转MP4): {' '.join(cmd_mp4)}")
        try:
            subprocess.run(cmd_ts, check=True, capture_output=True)
            # 先探测 TS 片段实际时长，再转 MP4/清理临时文件
            actual_single_duration = get_video_duration(temp_ts)
            subprocess.run(cmd_mp4, check=True, capture_output=True)

            # 清理临时 TS 文件
            if os.path.exists(temp_ts):
                os.remove(temp_ts)

            # 输出单片段模式下的实际保留片段边界 CSV
            if actual_single_duration is not None:
                actual_single_segments = [(start, start + actual_single_duration)]
            else:
                actual_single_segments = [(start, end)]
            print(f"保留片段边界CSV(实际): {segments_to_csv(actual_single_segments)}")

            # 输出单片段模式下的实际删除片段边界 CSV
            actual_removed_segments = []
            if actual_single_segments and actual_single_segments[0][0] > 0:
                actual_removed_segments.append((0.0, actual_single_segments[0][0]))
            if actual_single_segments and actual_single_segments[0][1] < duration:
                actual_removed_segments.append((actual_single_segments[0][1], duration))
            actual_removed_csv = segments_to_csv(
                actual_removed_segments, duration, use_end_label=False
            )
            print(f"删除片段边界CSV(实际): {actual_removed_csv}")
            run_srt_sync_with_actual_removed_csv(actual_removed_csv)

            # 如果需要替换原文件
            if replace_original:
                final_output = os.path.join(input_dir, f"{base_name}_processed.mp4")
                # 不删除原文件，直接重命名输出文件
                # if os.path.exists(input_file):
                #     os.remove(input_file)
                try:
                    os.replace(output_file, final_output)
                except PermissionError:
                    import time

                    time.sleep(0.5)
                    os.replace(output_file, final_output)
                print(f"\n视频处理成功! 输出文件: {final_output}")
                print(f"原始文件已保留: {input_file}")
            else:
                print(f"\n视频处理成功! 输出文件: {output_file}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"视频处理失败: {e}")
            if os.path.exists(temp_ts):
                os.remove(temp_ts)
            if replace_original and os.path.exists(output_file):
                os.remove(output_file)
            return False

    # 多个保留段，使用 TS 流无损拼接
    temp_dir = os.path.join(input_dir, "trimmed")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    temp_ts_files = []
    temp_concat_ts = os.path.join(temp_dir, f"{base_name}_concat.ts")
    concat_list_file = os.path.join(temp_dir, f"{base_name}_concat_list.txt")

    try:
        # 提取每个保留段为 TS 格式
        # 注意: -ss 放在 -i 之后（output seeking），确保精确裁切，与字幕时间对齐
        print(f"\n开始提取视频片段 (TS流模式)...")
        for i, (start, end) in enumerate(keep_segments):
            temp_ts = os.path.join(temp_dir, f"segment_{i:03d}.ts")
            duration_seg = end - start

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                input_file,
                "-ss",
                str(start),
                "-t",
                str(duration_seg),
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

            print(f"  提取片段 {i + 1}/{len(keep_segments)}: {start:.2f}s - {end:.2f}s")
            subprocess.run(cmd, check=True, capture_output=True)
            temp_ts_files.append(temp_ts)

            # 输出每个片段的实际时长（ffmpeg copy 后）
            actual_duration = get_video_duration(temp_ts)
            if actual_duration is not None:
                actual_end = start + actual_duration
                print(
                    f"  实际片段边界 {i + 1}: "
                    f"{format_time_ms(start)}-{format_time_ms(actual_end)}"
                )

        # 使用 concat demuxer 拼接所有 TS 文件（确保时间戳正确累加）
        print(f"\n开始合并视频片段 (TS流无损拼接)...")
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for ts_file in temp_ts_files:
                f.write(f"file '{os.path.abspath(ts_file)}'\n")
        cmd_concat = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list_file,
            "-c",
            "copy",
            "-f",
            "mpegts",
            temp_concat_ts,
        ]

        subprocess.run(cmd_concat, check=True, capture_output=True)

        # 将合并后的 TS 转回 MP4（remux，不重编码）
        print(f"正在转换为 MP4...")
        cmd_mp4 = [
            "ffmpeg",
            "-y",
            "-i",
            temp_concat_ts,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_file,
        ]

        subprocess.run(cmd_mp4, check=True, capture_output=True)

        # 输出合并后实际保留片段边界 CSV（基于每段实际时长累计）
        actual_keep_segments = []
        for i, (start, _end) in enumerate(keep_segments):
            if i < len(temp_ts_files):
                seg_duration = get_video_duration(temp_ts_files[i])
                if seg_duration is None:
                    seg_duration = 0.0
            else:
                seg_duration = 0.0
            actual_start = start
            actual_end = start + seg_duration
            actual_keep_segments.append((actual_start, actual_end))

        print(f"保留片段边界CSV(实际): {segments_to_csv(actual_keep_segments)}")

        # 基于“实际保留片段边界”反推“实际删除片段边界”
        actual_removed_segments = []
        current = 0.0
        for ks, ke in actual_keep_segments:
            if current < ks:
                actual_removed_segments.append((current, ks))
            current = max(current, ke)
        if current < duration:
            actual_removed_segments.append((current, duration))

        actual_removed_csv = segments_to_csv(
            actual_removed_segments, duration, use_end_label=False
        )
        print(f"删除片段边界CSV(实际): {actual_removed_csv}")
        run_srt_sync_with_actual_removed_csv(actual_removed_csv)

        # 如果需要替换原文件
        if replace_original:
            final_output = os.path.join(input_dir, f"{base_name}_processed.mp4")
            # 不删除原文件，直接重命名输出文件
            # if os.path.exists(input_file):
            #     os.remove(input_file)
            try:
                os.replace(output_file, final_output)
            except PermissionError:
                import time

                time.sleep(0.5)
                os.replace(output_file, final_output)
            print(f"\n视频处理成功! 输出文件: {final_output}")
            print(f"原始文件已保留: {input_file}")
        else:
            print(f"\n视频处理成功! 输出文件: {output_file}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"视频处理失败: {e}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False
    finally:
        # 清理临时文件
        for temp_file in temp_ts_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        if os.path.exists(temp_concat_ts):
            os.remove(temp_concat_ts)
        if os.path.exists(concat_list_file):
            os.remove(concat_list_file)
        # 清理临时目录
        try:
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except OSError:
            pass
        print(f"已清理临时文件")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "用法: python remove_segments.py <输入视频/文件夹> <删除时间段> [输出文件/文件夹]"
        )
        print("\n示例:")
        print("  # 处理单个文件，输出到同一文件夹")
        print('  python remove_segments.py video.mp4 "1:00-2:00,5:00-6:00"')
        print()
        print('  # 使用"结尾"代替具体时间，表示到视频末尾')
        print('  python remove_segments.py video.mp4 "1:00:00-结尾"')
        print()
        print("  # 多行格式（逗号分隔）")
        print(
            '  python remove_segments.py video.mp4 "01:03:34.000-01:05:14.000, 01:25:41.000-结尾"'
        )
        print()
        print("  # 处理单个文件，指定输出文件")
        print('  python remove_segments.py video.mp4 "1:00-2:00,5:00-6:00" output.mp4')
        print()
        print("  # 批量处理文件夹中的所有视频")
        print('  python remove_segments.py video_folder "1:00-2:00,5:00-结尾"')
        print()
        print("  # 批量处理并指定输出文件夹")
        print(
            '  python remove_segments.py video_folder "1:00-2:00,5:00-6:00" output_folder'
        )
        print("\n时间格式支持:")
        print("  - HH:MM:SS (例如: 1:30:45)")
        print("  - HH:MM:SS.mmm (例如: 01:03:34.000)")
        print("  - MM:SS (例如: 1:30)")
        print("  - SS (例如: 90)")
        print("  - 结尾 (表示视频末尾)")
        sys.exit(1)

    input_path = sys.argv[1]
    remove_segments_str = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    # 检查输入是文件还是文件夹
    if os.path.isfile(input_path):
        # 单个文件处理
        remove_video_segments(input_path, remove_segments_str, output_path)
    elif os.path.isdir(input_path):
        # 批量处理文件夹
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
        if output_path and os.path.isdir(output_path):
            output_dir = output_path
        elif output_path:
            # 如果指定了输出路径但不存在，创建它
            output_dir = output_path
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

            if remove_video_segments(
                video_file, remove_segments_str, output_dir=output_dir
            ):
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
