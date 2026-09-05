# -*- coding: utf-8 -*-
"""端到端冒烟验证脚本：对每个工具跑一次真实 ffmpeg 调用。

用法: python e2e_check.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from video_process.core.models import LogLevel, Settings, ToolContext
from video_process.core.probe import get_duration, check_amf_support

WORK = os.path.join(tempfile.gettempdir(), "vp-e2e")
PASS, FAIL = [], []


def mkctx(quiet=True):
    def log(msg, lvl=LogLevel.INFO):
        if not quiet or lvl in (LogLevel.ERROR, LogLevel.WARNING):
            print(f"    | {msg}")
    return ToolContext(
        on_log=log,
        on_progress=lambda p: None,
        is_cancelled=lambda: False,
        settings=Settings(overwrite=True),
    )


def make_video(path, duration=12, freq=440):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"testsrc=duration={duration}:size=320x240:rate=25",
         "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", path],
        capture_output=True,
    )
    return path


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")


def duration_of(p):
    d = get_duration(p)
    return d if d else 0.0


def main():
    if os.path.exists(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    print(f"工作目录: {WORK}\n")

    amf = check_amf_support()
    print(f"AMF 编码器: {amf or '无（跳过 AMD 相关用例）'}\n")

    # ---------- 准备素材 ----------
    src1 = make_video(os.path.join(WORK, "a.mp4"), 12)
    src2 = make_video(os.path.join(WORK, "b.mp4"), 8, 880)
    mergedir = os.path.join(WORK, "merge")
    os.makedirs(mergedir)
    shutil.copy(src1, os.path.join(mergedir, "01.mp4"))
    shutil.copy(src2, os.path.join(mergedir, "02.mp4"))

    # ---------- 1. merge ----------
    print("\n[1] 视频合并 (TS 快速模式)")
    from video_process.tools.merge import merge_videos
    r = merge_videos(mergedir, mode=1, ctx=mkctx())
    out = os.path.join(mergedir, "01_02_merge_videos.mp4")
    check("merge 成功", r.success, r.message)
    check("merge 输出存在", os.path.exists(out))
    if os.path.exists(out):
        d = duration_of(out)
        check("merge 时长 ≈ 20s", 18.5 < d < 21.5, f"(实际 {d:.2f}s)")

    # 有 AMF 时补测模式3（concat + AMF 重编码），这条分支只能靠真机覆盖。
    # 用独立目录：merge 会扫描输入目录下的全部视频，混进上一次产物会算错时长
    if check_amf_support():
        amd_dir = os.path.join(WORK, "merge-amd")
        os.makedirs(amd_dir)
        for name in ("a.mp4", "b.mp4"):
            subprocess.run(["ffmpeg", "-y", "-i", src1, "-c", "copy",
                            os.path.join(amd_dir, name)], capture_output=True)
        cout = os.path.join(amd_dir, "gpu_merge.mp4")
        r = merge_videos(amd_dir, mode=3, output_file=cout, ctx=mkctx())
        check("merge 模式3(AMF) 成功", r.success, r.message)
        if os.path.exists(cout):
            d = duration_of(cout)
            check("merge 模式3 时长 ≈ 24s", 22 < d < 26, f"(实际 {d:.2f}s)")

    # ---------- 2. trim_edges ----------
    print("\n[2] 开头结尾裁剪（时间点语义，保留 2s-8s）")
    from video_process.tools.trim_edges import trim_edges
    r = trim_edges(src1, start="2", end="8", ctx=mkctx())
    check("trim_edges 成功", r.success, r.message)
    if r.outputs:
        d = duration_of(r.outputs[0])
        check("trim 时长 ≈ 6s", 5.0 < d < 7.5, f"(实际 {d:.2f}s)")
        check("trim 命名 _trim_edges", "_trim_edges" in r.outputs[0])

    # ---------- 3. batch_trim ----------
    print("\n[3] 批量裁剪（时长语义，切开头2s + 结尾2s）")
    from video_process.tools.batch_trim import batch_trim
    bd = os.path.join(WORK, "batch")
    os.makedirs(bd)
    shutil.copy(src1, os.path.join(bd, "a.mp4"))
    r = batch_trim(bd, start_cut="2", end_cut="2", ctx=mkctx())
    check("batch_trim 成功", r.success, r.message)
    cut = os.path.join(bd, "cut", "a.mp4")
    check("batch_trim 输出到 cut/", os.path.exists(cut))
    if os.path.exists(cut):
        d = duration_of(cut)
        check("batch 时长 ≈ 8s", 7.0 < d < 9.5, f"(实际 {d:.2f}s)")

    # ---------- 4. remove_segments ----------
    print("\n[4] 片段删除（删 3s-5s 与 8s-10s）+ 字幕同步")
    from video_process.tools.remove_segments import remove_segments
    # 造一条同名 SRT
    srt_src = os.path.join(WORK, "a.srt")
    with open(srt_src, "w", encoding="utf-8") as f:
        for i, (s, e) in enumerate([(0, 2), (2, 3), (5, 8), (10, 12)], 1):
            f.write(f"{i}\n00:00:{s:02d},000 --> 00:00:{e:02d},000\n字幕{i}\n\n")
    r = remove_segments(src1, segments="3-5,8-10", sync_srt=True, ctx=mkctx())
    check("remove_segments 成功", r.success, r.message)
    proc = os.path.join(WORK, "a_processed.mp4")
    check("输出 _processed.mp4", os.path.exists(proc))
    if os.path.exists(proc):
        d = duration_of(proc)
        check("删除后时长 ≈ 8s", 7.0 < d < 9.5, f"(实际 {d:.2f}s)")
    check("字幕同步产物存在", os.path.exists(os.path.join(WORK, "a_processed.srt")))

    if check_amf_support():
        print("\n[4b] 片段删除 AMD 模式（删 3s-5s 与 8s-10s）")
        rad = os.path.join(WORK, "remove-amd")
        os.makedirs(rad)
        shutil.copy(src1, os.path.join(rad, "a.mp4"))
        r = remove_segments(os.path.join(rad, "a.mp4"), segments="3-5,8-10",
                            mode="amd", sync_srt=False, ctx=mkctx())
        check("remove_segments AMD 模式成功", r.success, r.message)
        amd_proc = os.path.join(rad, "a_processed.mp4")
        check("remove AMD 输出 _processed.mp4", os.path.exists(amd_proc))
        if os.path.exists(amd_proc):
            d = duration_of(amd_proc)
            check("remove AMD 删除后时长 ≈ 8s", 7.5 < d < 8.6, f"(实际 {d:.2f}s)")

    # ---------- 5. extract_segments ----------
    print("\n[5] 片段提取（提取 开头-2s 与 6s-结尾）")
    from video_process.tools.extract_segments import extract_segments
    ed = os.path.join(WORK, "extract")
    r = extract_segments(src1, segments="开头-2,6-结尾", output_dir=ed, ctx=mkctx())
    check("extract_segments 成功", r.success, r.message)
    check("extract 输出 2 个片段", len(r.outputs) == 2, f"(实际 {len(r.outputs)})")
    if len(r.outputs) == 2:
        d1, d2 = duration_of(r.outputs[0]), duration_of(r.outputs[1])
        check("extract 片段1 ≈ 2s", 1.5 < d1 < 3.0, f"(实际 {d1:.2f}s)")
        check("extract 片段2 ≈ 6s", 5.0 < d2 < 7.5, f"(实际 {d2:.2f}s)")

    # ---------- 6. split_video ----------
    print("\n[6] 视频分割（在 4s 处切开）")
    from video_process.tools.split_video import split_video
    sd = os.path.join(WORK, "split")
    os.makedirs(sd, exist_ok=True)
    shutil.copy(src1, os.path.join(sd, "s.mp4"))
    r = split_video(os.path.join(sd, "s.mp4"), split_points="4",
                    mode="fast", output_dir=sd, ctx=mkctx())
    check("split 成功", r.success, r.message)
    p1, p2 = os.path.join(sd, "s_1.mp4"), os.path.join(sd, "s_2.mp4")
    check("split 输出 2 段", os.path.exists(p1) and os.path.exists(p2))
    if os.path.exists(p1) and os.path.exists(p2):
        d1, d2 = duration_of(p1), duration_of(p2)
        check("split 时长合理", 3.0 < d1 < 5.5 and 6.5 < d2 < 9.0,
              f"({d1:.2f}s + {d2:.2f}s)")

    # ---------- 7. compress ----------
    print("\n[7] 视频压缩（medium）")
    from video_process.tools.compress import compress_video
    cd = os.path.join(WORK, "compress")
    os.makedirs(cd)
    shutil.copy(src1, os.path.join(cd, "c.mp4"))
    if amf:
        r = compress_video(cd, quality="medium", ctx=mkctx())
        check("compress 成功", r.success, r.message)
        comp = os.path.join(cd, "c_compressed.mp4")
        check("compress 输出 _compressed", os.path.exists(comp))
        if os.path.exists(comp):
            # 再次运行：只应压缩原始 c.mp4，不得对已压缩产物二次压缩
            r2 = compress_video(cd, quality="medium", ctx=mkctx())
            nested = os.path.join(cd, "c_compressed_compressed.mp4")
            check("compress 不重复压缩已压缩文件", not os.path.exists(nested))
            check("compress 二次运行仅处理原文件",
                  r2.success and len(r2.outputs) == 1, r2.message)
    else:
        check("compress 跳过（无 AMF）", True, "(环境无 AMF)")

    # ---------- 8. convert ----------
    print("\n[8] 转换 MP4（极速模式）")
    from video_process.tools.convert import convert_to_mp4
    vd = os.path.join(WORK, "convert")
    os.makedirs(vd)
    mkv = os.path.join(vd, "v.mkv")
    subprocess.run(["ffmpeg", "-y", "-i", src1, "-c", "copy", mkv],
                   capture_output=True)
    r = convert_to_mp4(mkv, mode=1, ctx=mkctx())
    check("convert 成功", r.success, r.message)
    check("convert 输出 .mp4", os.path.exists(os.path.join(vd, "v.mp4")))

    if check_amf_support():
        amd = os.path.join(WORK, "convert-amd")
        os.makedirs(amd)
        subprocess.run(["ffmpeg", "-y", "-i", src1, "-c", "copy",
                        os.path.join(amd, "v.mkv")], capture_output=True)
        r = convert_to_mp4(os.path.join(amd, "v.mkv"), mode=3, ctx=mkctx())
        check("convert 模式3(AMF) 成功", r.success, r.message)
        amd_out = [p for p in r.outputs if os.path.exists(p)]
        check("convert 模式3 输出存在", bool(amd_out), str(r.outputs))
        if amd_out:
            d = duration_of(amd_out[0])
            check("convert 模式3 时长 ≈ 12s", 10.5 < d < 13.5, f"(实际 {d:.2f}s)")

    # ---------- 9. extract_audio ----------
    print("\n[9] 音轨提取")
    from video_process.tools.extract_audio import extract_audio
    ad = os.path.join(WORK, "audio")
    os.makedirs(ad)
    r = extract_audio(src1, output_dir=ad, ctx=mkctx())
    check("audio 成功", r.success, r.message)
    check("audio 输出 .mp3", os.path.exists(os.path.join(ad, "a.mp3")))

    # ---------- 10. extract_frame ----------
    print("\n[10] 视频截图")
    from video_process.tools.extract_frame import extract_frame
    fd = os.path.join(WORK, "frame")
    os.makedirs(fd)
    r = extract_frame(src1, time_position="5", output_dir=fd, ctx=mkctx())
    check("frame 成功", r.success, r.message)
    check("frame 输出 .jpg", os.path.exists(os.path.join(fd, "a_time5s.jpg")))

    # ---------- 11. srt_to_ass ----------
    print("\n[11] SRT 转 ASS")
    from video_process.tools.srt_to_ass import srt_to_ass
    subd = os.path.join(WORK, "sub")
    os.makedirs(subd)
    shutil.copy(srt_src, os.path.join(subd, "a.srt"))
    r = srt_to_ass(os.path.join(subd, "a.srt"), ctx=mkctx())
    check("srt2ass 成功", r.success, r.message)
    ass = os.path.join(subd, "a.ass")
    check("ass 输出存在", os.path.exists(ass))
    if os.path.exists(ass):
        txt = open(ass, encoding="utf-8").read()
        check("ass 含文泉驿正黑", "文泉驿正黑" in txt)
        check("ass 含 Dialogue", "Dialogue:" in txt)

    # ---------- 12. remove_srt ----------
    print("\n[12] SRT 时间段删除")
    from video_process.tools.remove_srt import remove_srt_segments
    r = remove_srt_segments(srt_src, "2-5", ctx=mkctx())
    check("srt-remove 成功", r.success, r.message)
    removed = os.path.join(WORK, "a_removed.srt")
    check("输出 _removed.srt", os.path.exists(removed))
    if os.path.exists(removed):
        txt = open(removed, encoding="utf-8").read()
        # 原 10-12 段应前移 3s -> 07-09
        check("时间已前移 (10->07)", "00:00:07,000" in txt, "")

    # ---------- 13. rename_subtitle ----------
    print("\n[13] 字幕重命名")
    from video_process.tools.rename_subtitle import rename_subtitles
    rd = os.path.join(WORK, "rename")
    os.makedirs(rd)
    shutil.copy(srt_src, os.path.join(rd, "r.srt"))
    r = rename_subtitles(os.path.join(rd, "r.srt"), ctx=mkctx())
    check("rename 成功", r.success, r.message)
    check("rename 生成 .srt.txt", os.path.exists(os.path.join(rd, "r.srt.txt")))

    # ---------- 14. timeline ----------
    print("\n[14] 时间线计算器")
    from video_process.tools.timeline import calculate_timeline
    tl = ("00:00 开场\n02:10 正片\n01:33:00 [广告] 广告\n01:35:00 继续")
    r = calculate_timeline(tl, ctx=mkctx())
    check("timeline 成功", r.success, r.message)
    if r.outputs:
        check("timeline 移除广告行", "[广告]" not in r.outputs[0])
        check("timeline 前移 2 分钟", "01:33:00 继续" in r.outputs[0])

    # ---------- 15. zh_convert ----------
    print("\n[15] 文本繁简转换（OpenCC）")
    try:
        import opencc  # noqa: F401
    except ImportError:
        check("zh_convert 跳过（未安装 opencc）", True,
              "(pip install opencc-python-reimplemented)")
    else:
        from video_process.tools.zh_convert import convert_text
        src = "我们使用鼠标和软件，里面有个窗口"
        r = convert_text(src, "s2twp", ctx=mkctx())
        check("zh_convert 成功", r.success, r.message)
        tw = r.outputs[0] if r.outputs else ""
        check("zh_convert 转台湾正体", tw == "我們使用滑鼠和軟體，裡面有個視窗", tw)
        check("zh_convert 转繁体标准",
              convert_text(src, "s2t").outputs[0] == "我們使用鼠標和軟件，裏面有個窗口")
        check("zh_convert 转回简体",
              convert_text(tw, "tw2sp").outputs[0] == src)
        check("zh_convert 空文本报错", not convert_text("  ").success)
        check("zh_convert 无效配置报错", not convert_text(src, "bogus").success)

    # ---------- 汇总 ----------
    print("\n" + "=" * 60)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("\n失败项:")
        for f in FAIL:
            print(f"  - {f}")
    print("=" * 60)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
