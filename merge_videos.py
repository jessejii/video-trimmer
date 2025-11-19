import os
import subprocess
import sys

def get_video_files(directory):
    """获取目录中的所有视频文件并按名称排序"""
    video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.ts')
    files = [f for f in os.listdir(directory) if f.lower().endswith(video_extensions)]
    files.sort()
    return files

def merge_videos(directory):
    """使用 ffmpeg 快速合并视频"""
    video_files = get_video_files(directory)
    
    if len(video_files) == 0:
        print("❌ 错误：目录中没有找到视频文件")
        return False
    
    if len(video_files) == 1:
        print("⚠️  只找到一个视频文件，无需合并")
        return False
    
    print(f"\n找到 {len(video_files)} 个视频文件：")
    for i, file in enumerate(video_files, 1):
        print(f"  {i}. {file}")
    
    # 输出文件路径
    output_file = os.path.join(directory, "merged_output.mp4")
    
    # 检查输出文件是否已存在
    if os.path.exists(output_file):
        response = input(f"\n⚠️  输出文件已存在，是否覆盖？(y/n): ").strip().lower()
        if response != 'y':
            print("操作已取消")
            return False
    
    # 创建临时文件列表
    list_file = os.path.join(directory, "filelist.txt")
    
    try:
        # 写入文件列表
        with open(list_file, 'w', encoding='utf-8') as f:
            for video in video_files:
                video_path = os.path.join(directory, video)
                # 转义单引号和反斜杠
                escaped_path = video_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        print(f"\n🚀 开始合并视频...")
        print(f"📁 输出文件：{output_file}")
        
        # ffmpeg 命令 - 使用快速复制模式
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            '-y',
            output_file
        ]
        
        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 清理临时文件
        if os.path.exists(list_file):
            os.remove(list_file)
        
        if result.returncode == 0:
            file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
            print(f"\n✅ 合并成功！")
            print(f"📦 文件大小：{file_size:.2f} MB")
            print(f"📂 保存位置：{output_file}")
            return True
        else:
            print(f"\n❌ 合并失败")
            # 只显示关键错误信息
            if result.stderr:
                error_lines = result.stderr.split('\n')
                for line in error_lines:
                    if 'error' in line.lower() or 'failed' in line.lower():
                        print(f"   {line.strip()}")
            return False
            
    except Exception as e:
        print(f"\n❌ 发生错误：{str(e)}")
        if os.path.exists(list_file):
            os.remove(list_file)
        return False

def main():
    print("=" * 60)
    print("📹 视频合并工具 - FFmpeg 快速模式")
    print("=" * 60)
    
    # 获取用户输入的路径
    directory = input("\n请输入视频文件夹路径：").strip().strip('"').strip("'")
    
    # 检查路径
    if not os.path.exists(directory):
        print(f"❌ 错误：路径不存在 - {directory}")
        return
    
    if not os.path.isdir(directory):
        print(f"❌ 错误：不是有效的文件夹 - {directory}")
        return
    
    # 执行合并
    merge_videos(directory)

if __name__ == "__main__":
    main()
