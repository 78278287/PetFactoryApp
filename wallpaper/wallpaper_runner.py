# -*- coding: utf-8 -*-
"""
wallpaper_runner.py — 动态壁纸完整流程编排

串联：分辨率检测 → AIGate 视频生成 → 壁纸引擎应用（Lively / Wallpaper Engine）。
供 GUI 在桌宠生成完成后可选调用。
"""
import os
import sys

# 确保能 import 项目模块
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from wallpaper.video_generator import AIGateVideoGenerator, generate_wallpaper
from wallpaper.resolution import ResolutionDetector
from wallpaper.applier import WallpaperApplier


def build_wallpaper_prompt(character_name, description, theme_color):
    """
    根据角色信息构建壁纸视频提示词。
    强调：无缝循环、动作轻柔、主体稳定、无抖动变形、无文字水印。
    """
    parts = [
        f'以{character_name}为主体的动态桌面壁纸',
    ]
    if description:
        parts.append(description)
    if theme_color:
        parts.append(f'整体色调{theme_color}')
    parts.extend([
        '画面可无缝循环播放（loop）',
        '动作轻柔缓慢、自然循环',
        '主体稳定不抖动不变形',
        '镜头缓慢推拉或轻微呼吸感',
        '氛围唯美治愈',
        '无文字、无水印、无字幕',
        '高画质、电影级光影',
    ])
    return '，'.join(parts)


def run_wallpaper_pipeline(image_path, character_name='', description='',
                           theme_color='', duration=6, resolution='1080p',
                           apply_after=True, progress_cb=None):
    """
    完整壁纸流程：检测分辨率 → 生成视频 → 应用壁纸。

    :param image_path: 参考图片路径（用户上传的人物图）
    :param character_name: 角色名
    :param description: 角色外貌/主题描述
    :param theme_color: 主题色描述
    :param duration: 视频时长（秒）
    :param resolution: 分辨率档位
    :param apply_after: 生成后是否自动尝试应用
    :param progress_cb: 进度回调 callback(stage, percent, message)
    :return: dict {video_path, applied, engine, message, ratio}
    """
    def _emit(stage, pct, msg=''):
        if progress_cb:
            try:
                progress_cb(stage, pct, msg)
            except Exception:
                pass

    # 1) 检测分辨率
    _emit('resolution', 2, '检测屏幕分辨率...')
    try:
        det = ResolutionDetector()
        primary = det.get_primary()
        ratio = primary.get('ratio_str', '16:9')
        _emit('resolution', 5, f'主屏 {primary["width"]}x{primary["height"]} 比例{ratio}')
    except Exception as e:
        ratio = '16:9'
        _emit('resolution', 5, f'分辨率检测失败({e})，使用默认 16:9')

    # 2) 生成视频
    prompt = build_wallpaper_prompt(character_name, description, theme_color)
    _emit('generating', 8, f'开始生成动态壁纸（{ratio}，{duration}秒）...')

    def _video_progress(stage, pct):
        _emit(stage, pct, f'壁纸视频：{stage}')

    video_path = generate_wallpaper(
        image_path, prompt, ratio=ratio, duration=duration,
        resolution=resolution, progress_cb=_video_progress,
    )
    _emit('generated', 92, f'视频已生成：{os.path.basename(video_path)}')

    # 3) 应用壁纸
    applied = False
    engine = ''
    message = ''
    if apply_after:
        _emit('applying', 95, '尝试应用壁纸...')
        applier = WallpaperApplier()
        ok, result = applier.apply(video_path)
        if ok:
            applied = True
            if 'Lively' in str(result):
                engine = 'lively'
            elif 'Wallpaper Engine' in str(result):
                engine = 'wallpaper_engine'
            message = str(result)
        else:
            # result 可能是安装指引字典
            if isinstance(result, dict):
                message = '未检测到壁纸引擎，请安装 Lively Wallpaper 或 Wallpaper Engine'
            else:
                message = str(result)
        _emit('done', 100, message or '壁纸流程完成')
    else:
        _emit('done', 100, '视频已生成，未自动应用')

    return {
        'video_path': video_path,
        'applied': applied,
        'engine': engine,
        'message': message,
        'ratio': ratio,
    }


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        result = run_wallpaper_pipeline(
            sys.argv[1],
            character_name=sys.argv[2] if len(sys.argv) > 2 else '角色',
            progress_cb=lambda s, p, m: print(f'[{s}] {p}% {m}'),
        )
        print('结果：', result)
    else:
        print('用法：python wallpaper_runner.py <image_path> [character_name]')
