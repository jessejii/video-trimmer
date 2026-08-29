import json
import os
import subprocess
import sys


def get_audio_streams(video_file):
    """
    获取视频文件中的所有音轨信息

    参数:
        video_file: 视频文件路径

    返回:
        音轨信息列表，每个元素为字典，包含:
          - index:        流索引
          - codec_name:   编码名称（小写）
          - channels:     声道数
          - language:     语言标签（可能为空）
          - title:        标题（可能为空）
        失败时返回 None
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index,codec_name,channels:stream_tags=language,title",
        "-of", "json",
        video_file,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])

        audio_streams = []
        for s in streams:
            tags = s.get("tags", {})
            audio_streams.append({
                "index": s.get("index"),
                "codec_name": (s.get("codec_name") or "").lower(),
                "channels": s.get("channels"),
                "language": tags.get("language", ""),
                "title": tags.get("title", ""),
            })
        return audio_streams
    except subprocess.CalledProcessError as e:
        print(f"获取音轨信息失败: {e}")
        if e.stderr:
            print(f"  ffprobe stderr: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"获取音轨信息失败: {e}")
        return None


def find_video_root(path):
    """
    从给定路径向上查找名为 video 的目录，作为音频输出根目录

    参数:
        path: 文件或目录路径

    返回:
        找到的 video 目录绝对路径；找不到返回 None
    """
    current = path
    if os.path.isfile(current):
        current = os.path.dirname(current)
    current = os.path.abspath(current)

    while True:
        if os.path.basename(current).lower() == "video":
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def extract_audio(input_file, output_dir=None):
    """
    提取视频文件中的所有音轨，每条音轨重编码为 MP3 输出为单独文件

    使用 libmp3lame 重编码，VBR 最高压缩模式 (-q:a 9) 以尽量减小体积。
    默认输出到输入文件所在目录；若指定 output_dir 则统一输出到该目录。
    输出文件命名:原文件名.mp3

    参数:
        input_file: 输入视频文件
        output_dir: 音频输出目录；为 None 时输出到输入文件所在目录

    返回:
        是否成功（至少成功提取一条音轨）
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False

    base_name = os.path.splitext(os.path.basename(input_file))[0]

    if not output_dir:
        # 默认输出目录固定为输入文件所在目录
        output_dir = os.path.dirname(input_file) if os.path.dirname(input_file) else "."

    # 获取所有音轨
    audio_streams = get_audio_streams(input_file)
    if audio_streams is None:
        return False

    if not audio_streams:
        print(f"错误: 文件 '{os.path.basename(input_file)}' 中没有找到音轨")
        return False

    print(f"\n输入文件: {os.path.basename(input_file)}")
    print(f"找到 {len(audio_streams)} 条音轨:")
    for i, s in enumerate(audio_streams, 1):
        lang = s["language"] or "und"
        title = f" - {s['title']}" if s["title"] else ""
        ch = s["channels"] or "?"
        print(f"  音轨 {i}: 编码={s['codec_name'] or '未知'}, 声道={ch}, 语言={lang}{title}")

    # 辅助函数：运行 ffmpeg 命令，失败时打印完整错误信息
    def run_ffmpeg(cmd, description=""):
        print(f"\n{description}: {' '.join(cmd)}")
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg 执行失败 (返回码 {e.returncode}):")
            if e.stdout:
                print("  stdout:", e.stdout.strip())
            if e.stderr:
                print("  stderr:", e.stderr.strip())
            return False

    # 逐条提取音轨
    success_count = 0
    for i, s in enumerate(audio_streams):
        track_num = i + 1

        # 语言标签用于文件名，清理非法字符
        lang_part = s["language"] if s["language"] else "und"
        safe_lang = "".join(c for c in lang_part if c not in r'\/:*?"<>|') or "und"

        if len(audio_streams) > 1:
            output_file = os.path.join(
                output_dir, f"{base_name}_track{track_num}_{safe_lang}.mp3"
            )
        else:
            output_file = os.path.join(
                output_dir, f"{base_name}.mp3"
            )

        # -map 0:a:i 选择第 i 条音轨
        # -vn 丢弃视频
        # -c:a libmp3lame 重编码为 MP3
        # -q:a 9 VBR 最高压缩模式（体积最小，约 65-85 kbps）
        # 注意：不使用 aresample=async=1，避免因 TS 文件视频流 PTS 不连续
        #       导致音频时长被错误拉伸/压缩
        cmd = [
            "ffmpeg", "-y",
            "-i", input_file,
            "-map", f"0:a:{i}",
            "-vn",
            "-c:a", "libmp3lame",
            "-q:a", "9",
            "-map_metadata", "0",
            "-id3v2_version", "3",
            output_file,
        ]

        desc = f"提取音轨 {track_num}/{len(audio_streams)}"
        if run_ffmpeg(cmd, description=desc):
            print(f"  输出文件: {output_file}")
            success_count += 1
        else:
            print(f"  提取音轨 {track_num} 失败")

    print(f"\n提取完成! 成功: {success_count} 条, 失败: {len(audio_streams) - success_count} 条")
    return success_count > 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract_audio.py <输入视频/文件夹>")
        print("\n功能: 提取视频中的所有音轨，每条音轨重编码为 MP3 输出为单独文件")
        print("      音频统一输出到上层名为 video 的目录（找不到则输出到输入目录）")
        print("\n示例:")
        print("  # 处理单个文件，输出到同目录")
        print("  python extract_audio.py video.mp4")
        print()
        print("  # 批量处理文件夹中的所有视频（递归查找子目录）")
        print("  python extract_audio.py video_folder")
        print("\n输出命名: {原文件名}.mp3")
        print("\n说明:")
        print("  - 使用 libmp3lame 重编码为 MP3 格式")
        print("  - 使用 VBR 最高压缩模式 (-q:a 9)，尽量减小体积（约 65-85 kbps）")
        sys.exit(1)

    input_path = sys.argv[1]

    # 支持的视频格式
    video_extensions = (
        ".mp4", ".avi", ".mov", ".mkv", ".flv",
        ".wmv", ".m4v", ".webm", ".ts", ".mpg", ".mpeg",
        ".vob", ".m2ts", ".mts", ".3gp", ".rmvb",
    )

    # 检查输入是文件还是文件夹
    if os.path.isfile(input_path):
        # 单个文件处理
        out_root = find_video_root(input_path)
        if out_root:
            print(f"音频输出目录: {out_root}")
        extract_audio(input_path, out_root)
    elif os.path.isdir(input_path):
        # 批量处理文件夹（递归查找子目录）
        print(f"批量处理模式: 递归扫描文件夹 '{input_path}'")

        # 音频统一输出到上层 video 目录（找不到则输出到输入目录）
        out_root = find_video_root(input_path) or input_path
        print(f"音频输出目录: {out_root}")

        # 获取所有视频文件
        video_files = []
        for root, dirs, files in os.walk(input_path):
            for filename in files:
                if filename.lower().endswith(video_extensions):
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

            if extract_audio(video_file, out_root):
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
