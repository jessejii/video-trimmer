import os
import sys
import subprocess
import platform

def get_video_files(folder='video'):
    """
    从指定文件夹获取所有视频文件并按名称排序
    
    参数:
        folder: 视频文件夹路径，默认为 'video'
    
    返回:
        排序后的视频文件路径列表
    """
    if not os.path.exists(folder):
        print(f"错误: 文件夹 '{folder}' 不存在")
        return []
    
    # 支持的视频格式
    video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm', '.ts')
    
    # 获取所有视频文件
    video_files = []
    for filename in os.listdir(folder):
        if filename.lower().endswith(video_extensions):
            video_files.append(os.path.join(folder, filename))
    
    # 按文件名排序
    video_files.sort()
    
    return video_files

def merge_videos(video_files, output_file='output.mp4', list_file='list.txt'):
    """
    合并多个视频文件
    
    参数:
        video_files: 视频文件列表，例如 ['1.mp4', '2.mp4']
        output_file: 输出文件名，默认为 'output.mp4'
        list_file: 临时列表文件名，默认为 'list.txt'
    """
    
    # 检查视频文件是否存在
    for video in video_files:
        if not os.path.exists(video):
            print(f"错误: 文件 '{video}' 不存在")
            return False
    
    # 检查是否为 .ts 文件
    is_ts_format = video_files and video_files[0].lower().endswith('.ts')
    
    # 创建文件列表
    try:
        with open(list_file, 'w', encoding='utf-8') as f:
            for video in video_files:
                f.write(f"file '{video}'\n")
        print(f"已创建文件列表: {list_file}")
    except Exception as e:
        print(f"创建文件列表失败: {e}")
        return False
    
    # 执行 ffmpeg 命令
    # 对于 .ts 文件，使用 concat 协议更可靠
    if is_ts_format:
        # 使用 concat 协议直接合并 .ts 文件
        concat_string = 'concat:' + '|'.join(video_files)
        cmd = ['ffmpeg', '-i', concat_string, '-c', 'copy', output_file]
    else:
        # 其他格式使用 concat demuxer
        cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', output_file]
    
    try:
        print(f"开始合并视频...")
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"视频合并成功! 输出文件: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"视频合并失败: {e}")
        print(f"错误信息: {e.stderr}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH")
        return False
    finally:
        # 清理临时文件
        if os.path.exists(list_file):
            os.remove(list_file)
            print(f"已删除临时文件: {list_file}")

if __name__ == '__main__':
    # 从 video 文件夹读取所有视频文件
    folder = 'video'
    output_folder = 'out'
    output = os.path.join(output_folder, 'output.mp4')
    
    # 支持命令行参数指定文件夹
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    if len(sys.argv) > 2:
        output = os.path.join(output_folder, sys.argv[2])
    
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"已创建输出文件夹: {output_folder}")
    
    print(f"正在扫描文件夹: {folder}")
    video_files = get_video_files(folder)
    
    if not video_files:
        print("未找到任何视频文件")
        sys.exit(1)
    
    print(f"\n找到 {len(video_files)} 个视频文件:")
    for i, video in enumerate(video_files, 1):
        print(f"  {i}. {video}")
    
    print(f"\n输出文件: {output}")
    merge_videos(video_files, output)
