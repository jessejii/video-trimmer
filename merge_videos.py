import os
import subprocess
import sys

def get_video_files(directory):
    """获取目录中的所有视频文件并按名称排序"""
    video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.ts')
    files = [f for f in os.listdir(directory) if f.lower().endswith(video_extensions)]
    files.sort()
    return files

def convert_to_mp4(input_file, output_file, encoder='cpu'):
    """将视频转换为标准 MP4 格式
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        encoder: 编码器类型 ('cpu' 或 'gpu')
    """
    if encoder == 'gpu':
        # AMD 显卡加速
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-c:v', 'h264_amf',
            '-quality', 'balanced',
            '-rc', 'cqp',
            '-qp', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            output_file
        ]
    else:
        # CPU 编码
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            output_file
        ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    
    return result.returncode == 0

def merge_videos_fast(directory, video_files, output_file):
    """模式1：快速合并（直接复制流）"""
    list_file = os.path.join(directory, "filelist.txt")
    
    try:
        # 写入文件列表
        with open(list_file, 'w', encoding='utf-8') as f:
            for video in video_files:
                video_path = os.path.join(directory, video)
                escaped_path = video_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        print(f"\n🚀 开始快速合并视频...")
        
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
        
        return result.returncode == 0, result.stderr
        
    except Exception as e:
        if os.path.exists(list_file):
            os.remove(list_file)
        raise e

def merge_videos_convert(directory, video_files, output_file, encoder='cpu'):
    """模式2/3：转换后合并（先转换为标准格式再合并）
    
    Args:
        directory: 视频目录
        video_files: 视频文件列表
        output_file: 输出文件路径
        encoder: 编码器类型 ('cpu' 或 'gpu')
    """
    temp_dir = os.path.join(directory, "temp")
    
    # 创建临时目录
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    try:
        converted_files = []
        
        encoder_name = "AMD 显卡加速 (h264_amf)" if encoder == 'gpu' else "CPU (libx264)"
        print(f"\n🔄 开始转换视频为标准 MP4 格式 [{encoder_name}]...")
        
        # 转换每个视频
        for i, video in enumerate(video_files, 1):
            input_path = os.path.join(directory, video)
            temp_output = os.path.join(temp_dir, f"temp_{i:03d}.mp4")
            
            print(f"  [{i}/{len(video_files)}] 转换中: {video}")
            
            if convert_to_mp4(input_path, temp_output, encoder):
                converted_files.append(temp_output)
                print(f"  ✅ 完成")
            else:
                print(f"  ❌ 转换失败: {video}")
                raise Exception(f"转换失败: {video}")
        
        # 创建文件列表
        list_file = os.path.join(temp_dir, "filelist.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for temp_file in converted_files:
                escaped_path = temp_file.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        print(f"\n🚀 开始合并转换后的视频...")
        
        # 合并转换后的文件
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            '-y',
            output_file
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        success = result.returncode == 0
        
        # 清理临时文件
        print(f"\n🧹 清理临时文件...")
        for temp_file in converted_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        if os.path.exists(list_file):
            os.remove(list_file)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        
        return success, result.stderr
        
    except Exception as e:
        # 清理临时文件
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        raise e

def merge_videos_direct_gpu(directory, video_files, output_file):
    """模式4：直接GPU合并（利用ffmpeg concat demuxer + GPU重编码，修复时间戳问题）"""
    list_file = os.path.join(directory, "filelist.txt")
    
    try:
        # 写入文件列表
        with open(list_file, 'w', encoding='utf-8') as f:
            for video in video_files:
                video_path = os.path.join(directory, video)
                escaped_path = video_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        print(f"\n🚀 开始直接使用 GPU 合并视频...")
        print(f"ℹ️ 该模式会重新编码整个视频流，可以修复卡顿问题，同时只需一次编码，效率更高。")
        
        # ffmpeg 命令 - 使用 concat demuxer 但进行 GPU 重编码
        # 使用与 convert_to_mp4 相同的参数以保持一致性
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c:v', 'h264_amf',
            '-quality', 'balanced',
            '-rc', 'cqp',
            '-qp', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            output_file
        ]
        
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
        
        return result.returncode == 0, result.stderr
        
    except Exception as e:
        if os.path.exists(list_file):
            os.remove(list_file)
        raise e

def merge_videos(directory, mode=1):
    """合并视频主函数
    
    Args:
        directory: 视频目录
        mode: 合并模式 (1=快速, 2=CPU转换, 3=GPU转换, 4=直接GPU合并)
    """
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
    
    print(f"📁 输出文件：{output_file}")
    
    try:
        # 根据模式选择合并方式
        if mode == 1:
            success, stderr = merge_videos_fast(directory, video_files, output_file)
        elif mode == 2:
            success, stderr = merge_videos_convert(directory, video_files, output_file, encoder='cpu')
        elif mode == 3:
            success, stderr = merge_videos_convert(directory, video_files, output_file, encoder='gpu')
        else:  # mode == 4
            success, stderr = merge_videos_direct_gpu(directory, video_files, output_file)
        
        if success:
            file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
            print(f"\n✅ 合并成功！")
            print(f"� 合文件大小：{file_size:.2f} MB")
            print(f"📂 保存位置：{output_file}")
            return True
        else:
            print(f"\n❌ 合并失败")
            # 只显示关键错误信息
            if stderr:
                error_lines = stderr.split('\n')
                for line in error_lines:
                    if 'error' in line.lower() or 'failed' in line.lower():
                        print(f"   {line.strip()}")
            return False
            
    except Exception as e:
        print(f"\n❌ 发生错误：{str(e)}")
        return False

def main():
    print("=" * 60)
    print("📹 视频合并工具")
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
    
    # 选择合并模式
    print("\n请选择合并模式：")
    print("  1. 快速合并（默认，直接合并，速度快但兼容性较差）")
    print("  2. CPU 转换合并（libx264，兼容性好但速度慢）")
    print("  3. GPU 转换合并（h264_amf，AMD 显卡加速，速度快，兼容性好）")
    print("  4. 直接 GPU 合并（不生成临时文件，直接合并重编码，强烈推荐！修复卡顿）")
    
    mode_input = input("\n请输入模式编号 (1/2/3/4，默认为1): ").strip()
    
    if mode_input == '2':
        mode = 2
        print("\n✨ 已选择：CPU 转换合并模式")
    elif mode_input == '3':
        mode = 3
        print("\n✨ 已选择：GPU 转换合并模式 (AMD 显卡加速)")
    elif mode_input == '4':
        mode = 4
        print("\n✨ 已选择：直接 GPU 合并模式 (推荐，修复卡顿)")
    else:
        mode = 1
        print("\n✨ 已选择：快速合并模式")
    
    # 执行合并
    merge_videos(directory, mode)

if __name__ == "__main__":
    main()
