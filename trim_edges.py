import os
import sys
import subprocess

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

def trim_video_edges(input_file, start_trim, end_trim, output_file=None, output_dir=None):
    """
    裁剪视频的开头和结尾
    
    参数:
        input_file: 输入视频文件
        start_trim: 开头裁剪时间点（从0:00到该时间点的内容会被删除）
        end_trim: 结尾裁剪时间点（从该时间点到结束的内容会被删除）
        output_file: 输出文件名
        output_dir: 输出文件夹
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False
    
    # 获取视频时长
    duration = get_video_duration(input_file)
    if duration is None:
        return False
    
    print(f"\n视频总时长: {duration:.2f}s ({duration/60:.2f}min)")
    
    # 解析时间
    try:
        start_time = parse_time(start_trim) if start_trim else 0
        end_time = parse_time(end_trim) if end_trim else duration
    except Exception as e:
        print(f"解析时间失败: {e}")
        return False
    
    # 验证时间
    if start_time < 0:
        print(f"错误: 开头时间不能为负数")
        return False
    
    if end_time > duration:
        print(f"警告: 结尾时间 {end_time:.2f}s 超过视频时长 {duration:.2f}s，将使用视频时长")
        end_time = duration
    
    if start_time >= end_time:
        print(f"错误: 开头时间 {start_time:.2f}s 必须小于结尾时间 {end_time:.2f}s")
        return False
    
    # 计算保留的时间段
    keep_duration = end_time - start_time
    
    print(f"\n裁剪信息:")
    print(f"  删除开头: 0:00 - {start_time:.2f}s ({start_time/60:.2f}min)")
    print(f"  保留片段: {start_time:.2f}s - {end_time:.2f}s ({start_time/60:.2f}min - {end_time/60:.2f}min)")
    print(f"  删除结尾: {end_time:.2f}s - {duration:.2f}s ({end_time/60:.2f}min - {duration/60:.2f}min)")
    print(f"  保留时长: {keep_duration:.2f}s ({keep_duration/60:.2f}min)")
    
    # 设置输出文件名
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    input_dir = os.path.dirname(input_file) if os.path.dirname(input_file) else '.'
    
    if output_file is None:
        if output_dir:
            output_file = os.path.join(output_dir, f"{base_name}_trimmed.mp4")
        else:
            output_file = os.path.join(input_dir, f"{base_name}_trimmed.mp4")
    
    # 创建输出文件夹
    output_dir_path = os.path.dirname(output_file)
    if output_dir_path and not os.path.exists(output_dir_path):
        os.makedirs(output_dir_path)
        print(f"已创建输出文件夹: {output_dir_path}")
    
    # 使用 ffmpeg 裁剪视频
    cmd = [
        'ffmpeg', '-y', '-i', input_file,
        '-ss', str(start_time),
        '-t', str(keep_duration),
        '-c', 'copy',
        output_file
    ]
    
    print(f"\n执行命令: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print(f"\n视频处理成功! 输出文件: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"视频处理失败: {e}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python trim_edges.py <输入视频/文件夹> [开头时间] [结尾时间] [输出文件/文件夹]")
        print("\n示例:")
        print("  # 裁剪开头1分钟和结尾从32分钟开始的部分")
        print("  python trim_edges.py video.mp4 1:00 32:00")
        print()
        print("  # 只裁剪开头")
        print("  python trim_edges.py video.mp4 1:00")
        print()
        print("  # 只裁剪结尾")
        print("  python trim_edges.py video.mp4 0 32:00")
        print()
        print("  # 指定输出文件")
        print("  python trim_edges.py video.mp4 1:00 32:00 output.mp4")
        print()
        print("  # 批量处理文件夹")
        print("  python trim_edges.py video_folder 1:00 32:00")
        print()
        print("  # 批量处理并指定输出文件夹")
        print("  python trim_edges.py video_folder 1:00 32:00 output_folder")
        print("\n时间格式支持:")
        print("  - HH:MM:SS (例如: 1:30:45)")
        print("  - MM:SS (例如: 1:30)")
        print("  - SS (例如: 90)")
        sys.exit(1)
    
    input_path = sys.argv[1]
    start_trim = sys.argv[2] if len(sys.argv) > 2 else "0"
    end_trim = sys.argv[3] if len(sys.argv) > 3 else None
    output_path = sys.argv[4] if len(sys.argv) > 4 else None
    
    # 检查输入是文件还是文件夹
    if os.path.isfile(input_path):
        # 单个文件处理
        trim_video_edges(input_path, start_trim, end_trim, output_path)
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
            output_dir = output_path
            os.makedirs(output_dir, exist_ok=True)
            print(f"\n已创建输出文件夹: {output_dir}")
        else:
            output_dir = input_path
        
        print(f"\n开始批量处理...")
        success_count = 0
        fail_count = 0
        
        for i, video_file in enumerate(video_files, 1):
            print(f"\n{'='*60}")
            print(f"处理 [{i}/{len(video_files)}]: {os.path.basename(video_file)}")
            print(f"{'='*60}")
            
            if trim_video_edges(video_file, start_trim, end_trim, output_dir=output_dir):
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
