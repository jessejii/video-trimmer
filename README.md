# GPU优化视频剪辑工具

一个使用GPU加速的批量视频剪辑工具，可以快速去除视频开头和结尾的指定时间段。


## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

1. 将要处理的视频文件放入 `video` 文件夹
2. 运行脚本：
   ```bash
   python gpu_optimized_trim.py
   ```
3. 按提示输入要去掉的开头和结尾时间（秒）
4. 确认设置后开始处理
5. 处理完成的视频将保存在 `output` 文件夹中

## 使用示例

```
🎬 GPU优化批量视频剪辑工具
==================================================
✅ ffmpeg和ffprobe可用

⚙️ 请设置剪辑参数：
请输入要去掉的开头时间（秒）[默认: 29]: 30
请输入要去掉的结尾时间（秒）[默认: 25]: 20

📋 设置确认：
   开头去掉：30.0 秒
   结尾去掉：20.0 秒

是否开始处理？(y/N): y
```

## 文件结构

```
├── video/                  # 输入视频文件夹
├── output/                 # 输出视频文件夹
├── gpu_optimized_trim.py   # 主程序
├── requirements.txt        # 依赖包列表
└── README.md              # 说明文件
```


## 技术细节

- 使用 `h264_amf` 进行AMD GPU硬件编码(旧显卡需要替换ffmpeg,比如替换conda下bin的ffmpeg.exe: https://github.com/BtbN/FFmpeg-Builds/releases)
- 使用 `libx264` 作为CPU编码备用方案
