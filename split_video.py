import os
import sys
import subprocess

def parse_time(time_str):
    """
    解析时间字符串为秒数
    支持格式: HH:MM:SS, MM:SS, SS
    """
    try:
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
    except Exception:
        raise ValueError(f"无效的时间格式: {time_str}")

def get_video_duration(video_file):
    """
    获取视频时长（秒）
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

def split_video(input_file, split_point_str):
    """
    在指定时间点分割视频
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False
        
    # 获取时长
    duration = get_video_duration(input_file)
    if duration is None:
        return False
        
    # 解析分割点
    try:
        split_time = parse_time(split_point_str)
    except ValueError as e:
        print(f"错误: {e}")
        return False
        
    if split_time <= 0:
        print(f"错误: 分割时间必须大于 0")
        return False
        
    if split_time >= duration:
        print(f"错误: 分割时间 {split_time}s 超过或等于视频总时长 {duration}s")
        return False
        
    print(f"\n视频信息:")
    print(f"  文件: {input_file}")
    print(f"  时长: {duration:.2f}s ({duration/60:.2f}min)")
    print(f"  分割点: {split_time:.2f}s ({split_time/60:.2f}min)")
    
    # 构建输出文件名
    dir_name = os.path.dirname(input_file)
    base_name = os.path.basename(input_file)
    name_without_ext, ext = os.path.splitext(base_name)
    
    output_1 = os.path.join(dir_name, f"{name_without_ext}_1{ext}")
    output_2 = os.path.join(dir_name, f"{name_without_ext}_2{ext}")
    
    # Part 1: 开头 -> 分割点
    cmd1 = [
        'ffmpeg', '-y', '-i', input_file,
        '-t', str(split_time),
        '-c', 'copy',
        output_1
    ]
    
    # Part 2: 分割点 -> 结尾
    cmd2 = [
        'ffmpeg', '-y', '-i', input_file,
        '-ss', str(split_time),
        '-c', 'copy',
        output_2
    ]
    
    try:
        print(f"\n正在生成第一部分 ({output_1})...")
        subprocess.run(cmd1, check=True)
        
        print(f"正在生成第二部分 ({output_2})...")
        subprocess.run(cmd2, check=True)
        
        print(f"\n分割完成!")
        print(f"输出文件:")
        print(f"  1. {output_1}")
        print(f"  2. {output_2}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n处理失败: {e}")
        return False
    except FileNotFoundError:
        print("\n错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python split_video.py <视频文件> <分割时间>")
        print("示例: python split_video.py video.mp4 1:30")
        sys.exit(1)
        
    split_video(sys.argv[1], sys.argv[2])
