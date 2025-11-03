import os
import subprocess
import sys

def get_video_files(directory):
    """获取目录中的所有视频文件并按名称排序"""
    video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm')
    files = []
    
    for file in os.listdir(directory):
        if file.lower().endswith(video_extensions):
            files.append(file)
    
    # 按文件名排序
    files.sort()
    return files

def merge_videos_ffmpeg(directory):
    """使用 ffmpeg concat demuxer 快速合并视频"""
    video_files = get_video_files(directory)
    
    if len(video_files) == 0:
        print("错误：目录中没有找到视频文件")
        return False
    
    if len(video_files) == 1:
        print("警告：只找到一个视频文件，无需合并")
        return False
    
    print(f"找到 {len(video_files)} 个视频文件：")
    for i, file in enumerate(video_files, 1):
        print(f"  {i}. {file}")
    
    # 创建临时文件列表
    list_file = os.path.join(directory, "filelist.txt")
    try:
        with open(list_file, 'w', encoding='utf-8') as f:
            for video in video_files:
                # 使用相对路径，并转义特殊字符
                video_path = os.path.join(directory, video)
                # ffmpeg concat 格式要求
                f.write(f"file '{video_path}'\n")
        
        # 输出文件路径
        output_file = os.path.join(directory, "merged_output.mp4")
        
        # 如果输出文件已存在，询问是否覆盖
        if os.path.exists(output_file):
            response = input(f"\n输出文件 '{output_file}' 已存在，是否覆盖？(y/n): ")
            if response.lower() != 'y':
                print("操作已取消")
                os.remove(list_file)
                return False
        
        print(f"\n开始合并视频到：{output_file}")
        print("使用 ffmpeg 快速合并模式（concat demuxer）...")
        
        # 使用 ffmpeg concat demuxer 进行快速合并
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',  # 直接复制流，不重新编码
            '-y',  # 覆盖输出文件
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 删除临时文件列表
        os.remove(list_file)
        
        if result.returncode == 0:
            print(f"\n✓ 合并成功！输出文件：{output_file}")
            return True
        else:
            print(f"\n✗ 合并失败")
            print(f"错误信息：{result.stderr}")
            return False
            
    except Exception as e:
        print(f"发生错误：{str(e)}")
        if os.path.exists(list_file):
            os.remove(list_file)
        return False

def main():
    print("=" * 60)
    print("视频合并工具 - FFmpeg 快速合并模式")
    print("=" * 60)
    
    # 获取用户输入的路径
    directory = input("\n请输入包含视频文件的文件夹路径：").strip()
    
    # 移除路径两端的引号（如果有）
    directory = directory.strip('"').strip("'")
    
    # 检查路径是否存在
    if not os.path.exists(directory):
        print(f"错误：路径不存在 - {directory}")
        return
    
    if not os.path.isdir(directory):
        print(f"错误：路径不是一个文件夹 - {directory}")
        return
    
    # 执行合并
    merge_videos_ffmpeg(directory)

if __name__ == "__main__":
    main()
