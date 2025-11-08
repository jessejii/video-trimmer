import sys
import os
import re


def parse_srt_time(time_str):
    """将SRT时间格式转换为ASS时间格式"""
    # SRT格式: 00:00:20,000 -> ASS格式: 0:00:20.00
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = parts[1]
    seconds = parts[2]
    return f"{hours}:{minutes}:{seconds[:-1]}"  # 去掉最后一位毫秒


def srt_to_ass(srt_file, ass_file):
    """将SRT字幕文件转换为ASS格式"""
    
    # ASS文件头部
    ass_header = """[Script Info]
Title: Converted from SRT
ScriptType: v4.00+
WrapStyle: 1
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,3,2,30,30,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    try:
        with open(srt_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(srt_file, 'r', encoding='gbk') as f:
            content = f.read()
    
    # 分割字幕块
    subtitle_blocks = re.split(r'\n\s*\n', content.strip())
    
    dialogues = []
    
    for block in subtitle_blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        # 解析时间轴
        time_line = lines[1]
        time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_line)
        
        if time_match:
            start_time = parse_srt_time(time_match.group(1))
            end_time = parse_srt_time(time_match.group(2))
            
            # 获取字幕文本（可能有多行）
            text = '\\N'.join(lines[2:])
            
            # 创建ASS对话行
            dialogue = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
            dialogues.append(dialogue)
    
    # 写入ASS文件
    with open(ass_file, 'w', encoding='utf-8') as f:
        f.write(ass_header)
        f.write('\n'.join(dialogues))
    
    print(f"转换成功！")
    print(f"输入文件: {srt_file}")
    print(f"输出文件: {ass_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python srt_to_ass.py <srt文件路径>")
        sys.exit(1)
    
    srt_file = sys.argv[1]
    
    if not os.path.exists(srt_file):
        print(f"错误: 文件不存在 - {srt_file}")
        sys.exit(1)
    
    if not srt_file.lower().endswith('.srt'):
        print("错误: 请提供SRT格式的字幕文件")
        sys.exit(1)
    
    # 生成输出文件名
    ass_file = os.path.splitext(srt_file)[0] + '.ass'
    
    srt_to_ass(srt_file, ass_file)
