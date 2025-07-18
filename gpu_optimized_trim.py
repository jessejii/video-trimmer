#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU优化的视频剪辑脚本
使用ffmpeg直接调用，最大化GPU利用率
"""

import os
import subprocess
import sys
import re
import time
from pathlib import Path

def show_progress(process, total_duration):
    """显示ffmpeg处理进度"""
    last_time = 0
    start_time = time.time()
    
    while True:
        # ffmpeg的进度信息通常在stderr中
        output = process.stderr.readline()
        if output == '' and process.poll() is not None:
            break
        
        if output:
            # 解析时间进度 (格式: out_time_us=123456789 或 out_time=00:01:23.45)
            time_match = re.search(r'out_time_us=(\d+)', output)
            if not time_match:
                time_match = re.search(r'out_time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', output)
                if time_match:
                    hours, minutes, seconds, centiseconds = map(int, time_match.groups())
                    current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
                else:
                    continue
            else:
                current_time_us = int(time_match.group(1))
                current_time = current_time_us / 1000000.0  # 转换为秒
            
            if current_time > last_time:
                progress = min(current_time / total_duration * 100, 100)
                elapsed = time.time() - start_time
                
                if progress > 0 and elapsed > 0:
                    eta = (elapsed / progress * 100) - elapsed
                    speed = current_time / elapsed if elapsed > 0 else 0
                    
                    # 创建进度条
                    bar_length = 30
                    filled_length = int(bar_length * progress / 100)
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    
                    print(f"\r   📊 [{bar}] {progress:.1f}% | "
                          f"速度: {speed:.1f}x | "
                          f"剩余: {eta:.0f}s", end='', flush=True)
                    
                    last_time = current_time
    
    print()  # 换行

def get_video_duration(video_path):
    """获取视频时长"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            return float(result.stdout.strip())
        return None
    except Exception:
        return None

def trim_video_gpu(input_path, output_path, start_trim=10, end_trim=10):
    """
    使用GPU加速剪辑视频
    """
    try:
        # 获取视频时长
        duration = get_video_duration(input_path)
        if not duration:
            print(f"❌ 无法获取视频时长：{os.path.basename(input_path)}")
            return False
        
        # 检查视频时长是否足够
        if duration <= (start_trim + end_trim):
            print(f"⚠️  警告：{os.path.basename(input_path)} 视频时长过短，跳过处理")
            return False
        
        # 计算剪辑后的时长
        output_duration = duration - start_trim - end_trim
        
        print(f"   📊 原时长: {duration:.1f}s, 剪辑后: {output_duration:.1f}s")
        
        # 构建ffmpeg命令 - 完全GPU加速
        cmd = [
            'ffmpeg', '-y',  # 覆盖输出文件
            '-progress', 'pipe:2',  # 输出进度到stderr
            '-hwaccel', 'auto',  # 自动硬件加速解码
            '-i', input_path,
            '-ss', str(start_trim),  # 开始时间
            '-t', str(output_duration),  # 持续时间
            '-c:v', 'h264_amf',  # AMD硬件编码
            '-rc', 'cqp',        # 恒定量化参数
            '-qp_i', '23',       # I帧质量
            '-qp_p', '23',       # P帧质量
            '-quality', 'speed', # 优先速度
            '-c:a', 'aac',       # 音频编码
            '-b:a', '128k',      # 音频码率
            '-avoid_negative_ts', 'make_zero',  # 避免负时间戳
            output_path
        ]
        
        print(f"   🚀 启动GPU加速处理...")
        print(f"   📊 预计处理时长: {output_duration:.1f}秒")
        
        # 执行ffmpeg命令 - 显示实时进度
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 实时显示进度
        show_progress(process, output_duration)
        
        # 等待进程完成
        process.wait()
        result = process
        
        if result.returncode == 0:
            print(f"✅ GPU加速成功：{os.path.basename(input_path)}")
            return True
        else:
            print(f"⚠️  GPU编码失败，尝试CPU备用方案...")
            # 备用CPU方案
            return trim_video_cpu_fallback(input_path, output_path, start_trim, end_trim, output_duration)
            
    except subprocess.TimeoutExpired:
        print(f"❌ 处理超时：{os.path.basename(input_path)}")
        return False
    except Exception as e:
        print(f"❌ 处理失败：{os.path.basename(input_path)} - {str(e)}")
        return False

def trim_video_cpu_fallback(input_path, output_path, start_trim, end_trim, output_duration):
    """CPU备用方案"""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-progress', 'pipe:2',  # 显示进度
            '-i', input_path,
            '-ss', str(start_trim),
            '-t', str(output_duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-avoid_negative_ts', 'make_zero',
            output_path
        ]
        
        print(f"   💻 使用CPU编码...")
        
        # 执行ffmpeg命令 - 显示实时进度
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 实时显示进度
        show_progress(process, output_duration)
        
        # 等待进程完成
        process.wait()
        result = process
        
        if result.returncode == 0:
            print(f"✅ CPU编码成功：{os.path.basename(input_path)}")
            return True
        else:
            print(f"❌ CPU编码也失败：{result.stderr[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ CPU备用方案失败：{str(e)}")
        return False

def batch_trim_videos_gpu(input_dir, output_dir, start_trim=29, end_trim=25):
    """批量GPU加速处理"""
    
    # 支持的视频格式
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}
    
    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 获取视频文件
    input_path = Path(input_dir)
    video_files = [f for f in input_path.iterdir()
                   if f.is_file() and f.suffix.lower() in video_extensions]
    
    if not video_files:
        print("❌ 在指定目录中没有找到视频文件")
        return
    
    print(f"📁 找到 {len(video_files)} 个视频文件")
    print(f"📂 输入目录：{input_dir}")
    print(f"📂 输出目录：{output_dir}")
    print(f"⏱️  将去掉开头 {start_trim} 秒和结尾 {end_trim} 秒")
    print("🚀 使用GPU直接加速模式")
    print("=" * 50)
    
    success_count = 0
    failed_count = 0
    
    for i, video_file in enumerate(video_files, 1):
        print(f"[{i}/{len(video_files)}] 正在处理：{video_file.name}")
        
        output_file = Path(output_dir) / f"trimmed_{video_file.name}"
        
        if trim_video_gpu(str(video_file), str(output_file), start_trim, end_trim):
            success_count += 1
        else:
            failed_count += 1
        
        print("-" * 30)
    
    print("=" * 50)
    print(f"✅ 处理完成！成功：{success_count} 个，失败：{failed_count} 个")

def get_user_input():
    """获取用户输入的时间参数"""
    print("\n⚙️  请设置剪辑参数：")
    
    while True:
        try:
            start_trim = input("请输入要去掉的开头时间（秒）[默认: 29]: ").strip()
            if not start_trim:
                start_trim = 29
            else:
                start_trim = float(start_trim)
            
            if start_trim < 0:
                print("❌ 开头时间不能为负数，请重新输入")
                continue
            break
        except ValueError:
            print("❌ 请输入有效的数字")
    
    while True:
        try:
            end_trim = input("请输入要去掉的结尾时间（秒）[默认: 25]: ").strip()
            if not end_trim:
                end_trim = 25
            else:
                end_trim = float(end_trim)
            
            if end_trim < 0:
                print("❌ 结尾时间不能为负数，请重新输入")
                continue
            break
        except ValueError:
            print("❌ 请输入有效的数字")
    
    return start_trim, end_trim

def main():
    print("🎬 GPU优化批量视频剪辑工具")
    print("=" * 50)
    
    # 检查ffmpeg和ffprobe
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        subprocess.run(['ffprobe', '-version'], capture_output=True, timeout=5)
        print("✅ ffmpeg和ffprobe可用")
    except Exception:
        print("❌ 需要安装ffmpeg和ffprobe")
        return
    
    # 配置参数
    input_directory = "video"
    output_directory = "output"
    
    if not os.path.exists(input_directory):
        print(f"❌ 输入目录不存在：{input_directory}")
        return
    
    # 获取用户输入的时间参数
    start_trim_seconds, end_trim_seconds = get_user_input()
    
    print(f"\n📋 设置确认：")
    print(f"   开头去掉：{start_trim_seconds} 秒")
    print(f"   结尾去掉：{end_trim_seconds} 秒")
    
    confirm = input("\n是否开始处理？(y/N): ").strip().lower()
    if confirm not in ['y', 'yes', '是']:
        print("❌ 操作已取消")
        return
    
    batch_trim_videos_gpu(
        input_dir=input_directory,
        output_dir=output_directory,
        start_trim=start_trim_seconds,
        end_trim=end_trim_seconds
    )

if __name__ == "__main__":
    main()