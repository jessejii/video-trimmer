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
    if not time_str:
        return 0.0
    
    parts = time_str.strip().split(':')
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"时间包含无效字符: {time_str}")
    
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

def trim_video(input_file, start_to_cut, end_to_cut, output_dir):
    """
    裁剪视频开头和结尾的指定时长
    
    参数:
        input_file: 输入视频文件
        start_to_cut: 开头要切掉的时长 (字符串)
        end_to_cut: 结尾要切掉的时长 (字符串)
        output_dir: 输出文件夹
    """
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False
    
    # 获取视频时长
    duration = get_video_duration(input_file)
    if duration is None:
        return False
    
    # 解析要切掉的时长
    try:
        start_cut_sec = parse_time(start_to_cut)
        end_cut_sec = parse_time(end_to_cut)
    except Exception as e:
        print(f"解析时间失败: {e}")
        return False
    
    # 计算实际保留的时间段
    keep_start = start_cut_sec
    keep_end = duration - end_cut_sec
    keep_duration = keep_end - keep_start
    
    if keep_duration <= 0:
        print(f"错误: 裁剪后的时长小于等于0 (总长: {duration:.2f}s, 切掉开头: {start_cut_sec:.2f}s, 切掉结尾: {end_cut_sec:.2f}s)")
        return False
    
    # 准备输出路径
    base_name = os.path.basename(input_file)
    output_file = os.path.join(output_dir, base_name)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # 执行 ffmpeg 裁剪 (使用 -c copy 以保持质量并提高速度，但裁剪点可能不精确)
    # 如果需要由于裁剪点导致的非常精确，可以使用重编码，但这里按惯例先用 copy
    cmd = [
        'ffmpeg', '-y', '-i', input_file,
        '-ss', str(keep_start),
        '-t', str(keep_duration),
        '-c', 'copy',
        output_file
    ]
    
    print(f"处理中: {base_name}")
    print(f"  保留范围: {keep_start:.2f}s 到 {keep_end:.2f}s ({keep_duration:.2f}s)")
    
    try:
        # 使用 subprocess.run 并在 Windows 下隐藏窗口 (如果需要)
        # 这里直接运行，因为是通过 bat 运行的，用户可以看到进度
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  成功: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  失败: {e}")
        if e.stderr:
            print(f"  错误信息: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python batch_trim_edges.py <文件夹路径> [开头切多少] [结尾切多少]")
        print("示例: python batch_trim_edges.py \"C:\\Videos\" 00:01:00 00:02:00")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    start_to_cut = sys.argv[2] if len(sys.argv) > 2 else "0"
    end_to_cut = sys.argv[3] if len(sys.argv) > 3 else "0"
    
    if not os.path.isdir(input_dir):
        print(f"错误: 文件夹 '{input_dir}' 不存在")
        sys.exit(1)
    
    # 输出文件夹
    output_dir = os.path.join(input_dir, "cut")
    
    # 扫描视频文件
    video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm', '.ts')
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(video_extensions)]
    
    if not files:
        print(f"文件夹中没有找到视频文件: {input_dir}")
        sys.exit(1)
    
    print(f"找到 {len(files)} 个视频文件")
    print(f"计划切掉开头: {start_to_cut}, 切掉结尾: {end_to_cut}")
    print(f"输出目录: {output_dir}")
    print("-" * 50)
    
    success = 0
    fail = 0
    
    for f in files:
        input_path = os.path.join(input_dir, f)
        if trim_video(input_path, start_to_cut, end_to_cut, output_dir):
            success += 1
        else:
            fail += 1
            
    print("-" * 50)
    print(f"完成! 成功: {success}, 失败: {fail}")

if __name__ == '__main__':
    main()
