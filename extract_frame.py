import os
import sys
import subprocess

def extract_frame(input_file, frame_number=1, output_file=None):
    """
    截取视频的指定帧作为图片
    
    参数:
        input_file: 输入视频文件
        frame_number: 要截取的帧号（从1开始），默认第1帧
        output_file: 输出图片文件，默认为 input_frame1.jpg
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return False
    
    # 设置输出文件名
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    input_dir = os.path.dirname(input_file)
    
    if output_file is None:
        if input_dir:
            output_file = os.path.join(input_dir, f"{base_name}_frame{frame_number}.jpg")
        else:
            output_file = f"{base_name}_frame{frame_number}.jpg"
    
    # 使用 ffmpeg 截取指定帧
    # select='eq(n\,X)' 选择第X帧（索引从0开始，所以frame_number-1）
    cmd = [
        'ffmpeg', '-y', '-i', input_file,
        '-vf', f"select='eq(n\\,{frame_number-1})'",
        '-vsync', 'vfr',
        '-frames:v', '1',
        '-q:v', '2',  # 高质量
        output_file
    ]
    
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"截取帧号: 第{frame_number}帧")
    print(f"\n执行命令: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"\n✓ 成功截取第{frame_number}帧!")
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
        print("用法: python extract_frame.py <输入视频/文件夹> [帧号]")
        print("\n示例:")
        print("  # 处理单个文件，截取第1帧（默认）")
        print("  python extract_frame.py video.mp4")
        print()
        print("  # 处理单个文件，截取第5帧")
        print("  python extract_frame.py video.mp4 5")
        print()
        print("  # 批量处理文件夹中的所有视频，截取第1帧")
        print("  python extract_frame.py video_folder")
        print()
        print("  # 批量处理文件夹中的所有视频，截取第10帧")
        print("  python extract_frame.py video_folder 10")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    # 解析帧号，默认为1
    # 解析帧号，默认为1
    frame_arg = sys.argv[2] if len(sys.argv) >= 3 else "1"
    
    # 容错处理：允许传入等号或空字符作为占位符（表示默认值）
    if frame_arg in ("=", ""):
        frame_number = 1
    else:
        try:
            frame_number = int(frame_arg)
        except ValueError:
            print(f"错误: 帧号必须是整数，得到 '{frame_arg}'")
            sys.exit(1)
    
    if frame_number < 1:
        print("错误: 帧号必须大于等于1")
        sys.exit(1)
    
    # 检查输入是文件还是文件夹
    if os.path.isfile(input_path):
        # 单个文件处理
        extract_frame(input_path, frame_number)
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
            
            if extract_frame(video_file, frame_number):
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
