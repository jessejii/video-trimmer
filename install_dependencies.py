#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依赖安装脚本
自动安装视频剪辑工具所需的依赖库
"""

import subprocess
import sys
import os

def run_command(command):
    """运行命令并显示输出"""
    print(f"执行命令: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True,
                              capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {e}")
        if e.stderr:
            print(f"错误信息: {e.stderr}")
        return False

def check_pip():
    """检查pip是否可用"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"],
                      check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def install_dependencies():
    """安装所需依赖"""
    print("🚀 开始安装依赖...")
    print("=" * 50)

    # 检查pip
    if not check_pip():
        print("❌ pip 不可用，请先安装pip")
        return False

    # 升级pip
    print("📦 升级pip...")
    if not run_command(f"{sys.executable} -m pip install --upgrade pip"):
        print("⚠️  pip升级失败，继续安装依赖...")

    # 安装moviepy
    print("🎬 安装moviepy...")
    if not run_command(f"{sys.executable} -m pip install moviepy"):
        print("❌ moviepy安装失败")
        return False

    # 验证安装
    print("✅ 验证安装...")
    try:
        import moviepy
        print(f"✅ moviepy 安装成功，版本: {moviepy.__version__}")
        return True
    except ImportError:
        print("❌ moviepy 安装验证失败")
        return False

def main():
    print("🎬 视频剪辑工具 - 依赖安装器")
    print("=" * 50)

    # 检查Python版本
    if sys.version_info < (3, 6):
        print("❌ 需要Python 3.6或更高版本")
        print(f"当前版本: {sys.version}")
        return

    print(f"✅ Python版本: {sys.version}")

    # 安装依赖
    if install_dependencies():
        print("=" * 50)
        print("🎉 所有依赖安装完成！")
        print("现在可以运行 python batch_trim_videos.py 来处理视频")
    else:
        print("=" * 50)
        print("❌ 依赖安装失败")
        print("请手动运行: pip install moviepy")

if __name__ == "__main__":
    main()
