import os
import sys
import subprocess
import re

def parse_time(time_str):
    """
    解析时间字符串为秒数
    支持格式: HH:MM:SS, MM:SS, SS
    
    参数:
        time_str: 时间字符串，例如 "1:30", "1:30:45"
    
    返回:
        秒数（浮点数）
    """
    parts = time_str.strip().split(':')
    parts = [float(p) for p in parts]
    
    if len(parts) == 1:  # SS
        return parts[0]
    elif len(parts) == 2:  # MM:SS
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:  # HH:MM:SS
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError(f"无效的时间格式: {time_str}")

def parse_segments(segments_str):
    """
    解析要删除的时间段字符串
    
    参数:
        segments_str: 时间段字符串，例如 "1:00-2:00,5:00-6:00"
    
    返回:
        时间段列表，例如 [(60, 120), (300, 360)]
    """
    segments = []
    for segment in segments_str.split(','):
        segment = segment.strip()
        if '-' not in segment:
            print(f"警告: 跳过无效的时间段格式: {segment}")
            continue
        
        start_str, end_str = segment.split('-', 1)
        start = parse_time(start_str)
        end = parse_time(end_str)
        
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
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_file
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

def remove_video_segments(input_file, remove_segments_str, output_file=None, output_dir=None):
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
    input_dir = os.path.dirname(input_file) if os.path.dirname(input_file) else '.'
    
    # 标记是否需要替换原文件
    replace_original = False
    
    if output_file is None:
        if output_dir:
            # 指定了输出文件夹，直接输出
            output_file = os.path.join(output_dir, f"{base_name}.mp4")
        else:
            # 没有指定输出文件夹，使用临时文件，稍后替换原文件
            import tempfile
            temp_fd, output_file = tempfile.mkstemp(suffix='.mp4', dir=input_dir)
            os.close(temp_fd)
            replace_original = True
    
    # 创建输出文件夹
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建输出文件夹: {output_dir}")
    
    # 解析要删除的时间段
    try:
        remove_segments = parse_segments(remove_segments_str)
    except Exception as e:
        print(f"解析时间段失败: {e}")
        return False
    
    if not remove_segments:
        print("错误: 没有有效的时间段需要删除")
        return False
    
    print(f"\n要删除的时间段:")
    for start, end in remove_segments:
        print(f"  {start:.2f}s - {end:.2f}s ({start/60:.2f}min - {end/60:.2f}min)")
    
    # 获取视频时长
    duration = get_video_duration(input_file)
    if duration is None:
        return False
    
    print(f"\n视频总时长: {duration:.2f}s ({duration/60:.2f}min)")
    
    # 计算要保留的时间段
    keep_segments = calculate_keep_segments(remove_segments, duration)
    
    if not keep_segments:
        print("错误: 删除所有时间段后没有剩余内容")
        return False
    
    print(f"\n要保留的时间段:")
    for start, end in keep_segments:
        print(f"  {start:.2f}s - {end:.2f}s ({start/60:.2f}min - {end/60:.2f}min)")
    
    # 如果只有一个保留段，直接裁剪
    if len(keep_segments) == 1:
        start, end = keep_segments[0]
        duration_seg = end - start
        
        cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-ss', str(start),
            '-t', str(duration_seg),
            '-c', 'copy',
            output_file
        ]
        
        print(f"\n执行命令: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
            
            # 如果需要替换原文件
            if replace_original:
                final_output = os.path.join(input_dir, f"{base_name}_processed.mp4")
                # 不删除原文件，直接重命名输出文件
                # if os.path.exists(input_file):
                #     os.remove(input_file)
                os.rename(output_file, final_output)
                print(f"\n视频处理成功! 输出文件: {final_output}")
                print(f"原始文件已保留: {input_file}")
            else:
                print(f"\n视频处理成功! 输出文件: {output_file}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"视频处理失败: {e}")
            if replace_original and os.path.exists(output_file):
                os.remove(output_file)
            return False
    
    # 多个保留段，需要分别提取然后合并
    temp_dir = 'trimmed'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    temp_files = []
    list_file = 'segments_list.txt'
    
    try:
        # 提取每个保留段
        print(f"\n开始提取视频片段...")
        for i, (start, end) in enumerate(keep_segments):
            temp_file = os.path.join(temp_dir, f"segment_{i:03d}.mp4")
            duration_seg = end - start
            
            cmd = [
                'ffmpeg', '-i', input_file,
                '-ss', str(start),
                '-t', str(duration_seg),
                '-c', 'copy',
                '-y',
                temp_file
            ]
            
            print(f"  提取片段 {i+1}/{len(keep_segments)}: {start:.2f}s - {end:.2f}s")
            subprocess.run(cmd, check=True, capture_output=True)
            temp_files.append(temp_file)
        
        # 创建合并列表文件
        with open(list_file, 'w', encoding='utf-8') as f:
            for temp_file in temp_files:
                f.write(f"file '{temp_file}'\n")
        
        # 合并所有片段
        print(f"\n开始合并视频片段...")
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_file
        ]
        
        subprocess.run(cmd, check=True)
        
        # 如果需要替换原文件
        if replace_original:
            final_output = os.path.join(input_dir, f"{base_name}_processed.mp4")
            # 不删除原文件，直接重命名输出文件
            # if os.path.exists(input_file):
            #     os.remove(input_file)
            os.rename(output_file, final_output)
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
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        if os.path.exists(list_file):
            os.remove(list_file)
        print(f"已清理临时文件")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python remove_segments.py <输入视频/文件夹> <删除时间段> [输出文件/文件夹]")
        print("\n示例:")
        print("  # 处理单个文件，输出到同一文件夹")
        print("  python remove_segments.py video.mp4 \"1:00-2:00,5:00-6:00\"")
        print()
        print("  # 处理单个文件，指定输出文件")
        print("  python remove_segments.py video.mp4 \"1:00-2:00,5:00-6:00\" output.mp4")
        print()
        print("  # 批量处理文件夹中的所有视频")
        print("  python remove_segments.py video_folder \"1:00-2:00,5:00-6:00\"")
        print()
        print("  # 批量处理并指定输出文件夹")
        print("  python remove_segments.py video_folder \"1:00-2:00,5:00-6:00\" output_folder")
        print("\n时间格式支持:")
        print("  - HH:MM:SS (例如: 1:30:45)")
        print("  - MM:SS (例如: 1:30)")
        print("  - SS (例如: 90)")
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
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm', '.ts')
        
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
            print(f"\n{'='*60}")
            print(f"处理 [{i}/{len(video_files)}]: {os.path.basename(video_file)}")
            print(f"{'='*60}")
            
            if remove_video_segments(video_file, remove_segments_str, output_dir=output_dir):
                success_count += 1
            else:
                fail_count += 1
        
        print(f"\n{'='*60}")
        print(f"批量处理完成!")
        print(f"成功: {success_count} 个, 失败: {fail_count} 个")
        print(f"{'='*60}")
    else:
        print(f"错误: 路径 '{input_path}' 不存在")
        sys.exit(1)
