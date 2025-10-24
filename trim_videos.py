import os
import sys
import subprocess
import json

def get_video_duration(video_path):
    """
    获取视频时长（秒）
    
    参数:
        video_path: 视频文件路径
    
    返回:
        视频时长（秒），失败返回 None
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        return None

def parse_time(time_str):
    """
    解析时间字符串为秒数
    支持格式: "1:30", "90", "1:30:00"
    
    参数:
        time_str: 时间字符串
    
    返回:
        秒数
    """
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return int(time_str)

def trim_video(input_file, output_file, start_trim=0, end_trim=0):
    """
    裁剪视频，去掉开头和结尾
    
    参数:
        input_file: 输入视频文件
        output_file: 输出视频文件
        start_trim: 开头去掉的秒数
        end_trim: 结尾去掉的秒数
    
    返回:
        是否成功
    """
    # 获取视频总时长
    duration = get_video_duration(input_file)
    if duration is None:
        return False
    
    # 计算裁剪后的时长
    new_duration = duration - start_trim - end_trim
    
    if new_duration <= 0:
        print(f"错误: 裁剪时间过长，视频时长 {duration:.2f}秒，裁剪后为 {new_duration:.2f}秒")
        return False
    
    print(f"  原始时长: {duration:.2f}秒")
    print(f"  裁剪后时长: {new_duration:.2f}秒")
    
    # 构建 ffmpeg 命令
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-ss', str(start_trim),
        '-t', str(new_duration),
        '-c', 'copy',
        '-y',
        output_file
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  ✓ 裁剪成功: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ 裁剪失败: {e}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False

def get_video_files(folder='video'):
    """
    从指定文件夹获取所有视频文件并按名称排序
    """
    if not os.path.exists(folder):
        print(f"错误: 文件夹 '{folder}' 不存在")
        return []
    
    video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm')
    video_files = []
    
    for filename in os.listdir(folder):
        if filename.lower().endswith(video_extensions):
            video_files.append(os.path.join(folder, filename))
    
    video_files.sort()
    return video_files

def trim_all_videos(input_folder='video', output_folder='trimmed', start_trim=0, end_trim=0):
    """
    批量裁剪文件夹中的所有视频
    """
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"已创建输出文件夹: {output_folder}")
    
    # 获取所有视频文件
    video_files = get_video_files(input_folder)
    
    if not video_files:
        print("未找到任何视频文件")
        return
    
    print(f"\n找到 {len(video_files)} 个视频文件")
    print(f"开头裁剪: {start_trim}秒")
    print(f"结尾裁剪: {end_trim}秒\n")
    
    success_count = 0
    
    for i, video_path in enumerate(video_files, 1):
        filename = os.path.basename(video_path)
        output_path = os.path.join(output_folder, filename)
        
        print(f"[{i}/{len(video_files)}] 处理: {filename}")
        
        if trim_video(video_path, output_path, start_trim, end_trim):
            success_count += 1
        
        print()
    
    print(f"完成! 成功裁剪 {success_count}/{len(video_files)} 个视频")

if __name__ == '__main__':
    input_folder = 'video'
    output_folder = 'trimmed'
    start_trim = 0  # 开头去掉的秒数
    end_trim = 0    # 结尾去掉的秒数
    
    # 命令行参数
    if len(sys.argv) > 1:
        start_trim = parse_time(sys.argv[1])
    if len(sys.argv) > 2:
        end_trim = parse_time(sys.argv[2])
    if len(sys.argv) > 3:
        input_folder = sys.argv[3]
    if len(sys.argv) > 4:
        output_folder = sys.argv[4]
    
    if start_trim == 0 and end_trim == 0:
        print("用法:")
        print("  python trim_videos.py <开头秒数> <结尾秒数> [输入文件夹] [输出文件夹]")
        print("\n示例:")
        print("  python trim_videos.py 60 120          # 去掉开头1分钟，结尾2分钟")
        print("  python trim_videos.py 1:30 2:00       # 去掉开头1分30秒，结尾2分钟")
        print("  python trim_videos.py 10 10 video trimmed  # 指定输入输出文件夹")
        sys.exit(1)
    
    trim_all_videos(input_folder, output_folder, start_trim, end_trim)
