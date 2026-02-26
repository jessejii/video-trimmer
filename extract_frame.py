import os
import sys
import subprocess

def parse_time_to_seconds(time_str):
    """
    将时间字符串转换为秒数
    
    支持格式:
        30 -> 30秒
        1:30 -> 1分30秒 = 90秒
        1:2:3 -> 1小时2分3秒 = 3723秒
    
    参数:
        time_str: 时间字符串
    
    返回:
        秒数（浮点数）
    """
    parts = time_str.split(':')
    
    if len(parts) == 1:
        # 只有秒数
        return float(parts[0])
    elif len(parts) == 2:
        # 分:秒
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    elif len(parts) == 3:
        # 时:分:秒
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"无效的时间格式: {time_str}")

def extract_frame(input_file, time_position=0, output_file=None):
    """
    截取视频指定时间点的截图
    
    参数:
        input_file: 输入视频文件
        time_position: 时间位置（秒），默认第0秒
        output_file: 输出图片文件，默认为 input_timeXXs.jpg
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False
    
    # 设置输出文件名
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    input_dir = os.path.dirname(input_file)
    
    if output_file is None:
        # 格式化时间用于文件名
        time_str = f"{int(time_position)}s"
        if time_position >= 60:
            minutes = int(time_position // 60)
            seconds = int(time_position % 60)
            time_str = f"{minutes}m{seconds}s"
        
        if input_dir:
            output_file = os.path.join(input_dir, f"{base_name}_time{time_str}.jpg")
        else:
            output_file = f"{base_name}_time{time_str}.jpg"
    
    # 使用 ffmpeg 截取指定时间点的截图
    # -ss 指定时间位置
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(time_position),
        '-i', input_file,
        '-frames:v', '1',
        '-q:v', '2',  # 高质量
        output_file
    ]
    
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"截取时间: {time_position}秒")
    print(f"\n执行命令: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"\n✓ 成功截取 {time_position}秒 的截图!")
        print(f"图片已保存到: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ 截取失败: {e}")
        if e.stderr:
            print(f"错误信息: {e.stderr.decode('utf-8', errors='ignore')}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python extract_frame.py <输入视频/文件夹> [时间]")
        print("\n时间格式:")
        print("  30      -> 30秒")
        print("  1:30    -> 1分30秒")
        print("  1:2:3   -> 1小时2分3秒")
        print("\n示例:")
        print("  # 处理单个文件，截取第0秒（默认）")
        print("  python extract_frame.py video.mp4")
        print()
        print("  # 处理单个文件，截取第30秒")
        print("  python extract_frame.py video.mp4 30")
        print()
        print("  # 处理单个文件，截取1分30秒")
        print("  python extract_frame.py video.mp4 1:30")
        print()
        print("  # 批量处理文件夹中的所有视频，截取第0秒")
        print("  python extract_frame.py video_folder")
        print()
        print("  # 批量处理文件夹中的所有视频，截取1小时2分3秒")
        print("  python extract_frame.py video_folder 1:2:3")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    # 解析时间，默认为0秒
    time_arg = sys.argv[2] if len(sys.argv) >= 3 else "0"
    
    # 容错处理：允许传入等号或空字符作为占位符（表示默认值）
    if time_arg in ("=", ""):
        time_position = 0
    else:
        try:
            time_position = parse_time_to_seconds(time_arg)
        except (ValueError, IndexError) as e:
            print(f"错误: 无效的时间格式 '{time_arg}'")
            print("支持格式: 30 (秒) | 1:30 (分:秒) | 1:2:3 (时:分:秒)")
            sys.exit(1)
    
    if time_position < 0:
        print("错误: 时间必须大于等于0")
        sys.exit(1)
    
    # 检查输入是文件还是文件夹
    if os.path.isfile(input_path):
        # 单个文件处理
        extract_frame(input_path, time_position)
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
        output_dir = input_path
        
        print(f"\n开始批量处理...")
        success_count = 0
        fail_count = 0
        
        for i, video_file in enumerate(video_files, 1):
            print(f"\n{'='*60}")
            print(f"处理 [{i}/{len(video_files)}]: {os.path.basename(video_file)}")
            print(f"{'='*60}")
            
            if extract_frame(video_file, time_position):
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
