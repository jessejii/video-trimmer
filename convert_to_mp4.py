#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频转 MP4 格式工具"""

import os
import sys
import subprocess
from pathlib import Path


def check_ffmpeg():
    """检查 ffmpeg 是否安装"""
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_output_path(input_path):
    """生成输出文件路径"""
    input_file = Path(input_path)
    output_path = input_file.with_suffix('.mp4')
    
    # 如果输出文件已存在且不是输入文件本身
    if output_path.exists() and output_path != input_file:
        output_path = input_file.with_name(f"{input_file.stem}_converted.mp4")
        print(f"注意: 目标文件已存在，将保存为 {output_path.name}")
    
    return output_path


def convert_video(input_path, mode):
    """转换视频"""
    output_path = get_output_path(input_path)
    
    print(f"\n开始转换...")
    print(f"输入: {input_path}")
    print(f"输出: {output_path}\n")
    
    # 构建 ffmpeg 命令
    if mode == 1:
        print("使用快速模式...")
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c', 'copy',
            '-y', str(output_path)
        ]
    elif mode == 2:
        print("使用 CPU 编码模式 (libx264)...")
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
            '-c:a', 'aac', '-b:a', '128k',
            '-y', str(output_path)
        ]
    elif mode == 3:
        print("使用 AMD 显卡加速模式 (h264_amf)...")
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c:v', 'h264_amf', '-quality', 'balanced', '-rc', 'cqp', '-qp', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-y', str(output_path)
        ]
    else:
        print("无效模式，使用快速模式...")
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c', 'copy',
            '-y', str(output_path)
        ]
    
    # 执行转换
    try:
        result = subprocess.run(cmd, check=True)
        return output_path if output_path.exists() else None
    except subprocess.CalledProcessError as e:
        print(f"\n错误: 转换失败 (退出码: {e.returncode})")
        return None


def main():
    """主函数"""
    print("=" * 40)
    print("视频转 MP4 格式工具")
    print("=" * 40)
    print()
    
    # 检查 ffmpeg
    if not check_ffmpeg():
        print("错误: 未找到 ffmpeg")
        print("请先安装 ffmpeg 并添加到系统 PATH")
        input("\n按回车键退出...")
        sys.exit(1)
    
    while True:
        # 获取输入文件
        print("请输入视频文件路径 (支持拖拽文件):")
        print("提示: 可以直接拖拽文件，或输入完整路径")
        print()
        
        input_path = input("文件路径: ").strip().strip('"')
        
        if not input_path:
            print("\n错误: 未输入文件路径\n")
            continue
        
        # 检查文件是否存在
        if not os.path.exists(input_path):
            print(f"\n错误: 文件不存在: {input_path}\n")
            continue
        
        input_file = Path(input_path)
        print(f"\n文件名: {input_file.name}")
        print(f"文件位置: {input_file.parent}")
        print()
        
        # 如果已经是 mp4 格式
        if input_file.suffix.lower() == '.mp4':
            print("注意: 文件已经是 MP4 格式")
            reencode = input("是否重新编码? (y/n): ").strip().lower()
            if reencode != 'y':
                print("已取消\n")
                continue
        
        # 选择转换模式
        print("选择转换模式:")
        print("1. 快速模式 (只转换容器，不重新编码，速度快)")
        print("2. CPU 编码 (libx264，兼容性最好但速度慢)")
        print("3. AMD 显卡加速 (h264_amf，速度快，需要 AMD 显卡)")
        print()
        
        mode_input = input("请选择 (1/2/3，默认1): ").strip()
        mode = int(mode_input) if mode_input in ['1', '2', '3'] else 1
        
        # 执行转换
        output_path = convert_video(input_path, mode)
        
        # 显示结果
        print("\n" + "=" * 40)
        if output_path:
            print("✓ 转换成功!")
            print(f"输出文件: {output_path}")
        else:
            print("✗ 转换失败")
        print("=" * 40)
        print()
        
        # 询问是否继续
        continue_input = input("是否继续转换其他文件? (Y/n，默认Y): ").strip().lower()
        if continue_input == 'n':
            break
        
        print("\n" + "=" * 40 + "\n")
    
    print("\n感谢使用!")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(0)
