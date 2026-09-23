# -*- coding: utf-8 -*-
"""
video_generator.py — 动态壁纸视频生成模块（AIGate 视频 API）

接口：
  1) POST /v1/files          上传参考图片，返回 file_id
  2) POST /v1/videos         提交图生视频任务（mode=keyframe，first_frame=file_id）
  3) GET  /v1/videos/{id}    轮询任务状态；completed → metadata.url 下载
  4) 流式下载 mp4 到输出目录

模型默认 agnes-video-v2.0（支持单图生视频/关键帧，480P/720P/1080P）。
备选：agnes-video-2.5 / minimax-h3 / wan3.0-video。

API key 从 config.get_aigate_key() / 环境变量 AIGATE_API_KEY 读取，不硬编码。
"""
import os
import sys
import time
import uuid
import datetime

import requests

# 共享配置
try:
    from config import OUTPUT_DIR, get_aigate_key, get_aigate_base, get_aigate_video_model
except Exception:
    OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')

    def get_aigate_key():
        return os.environ.get('AIGATE_API_KEY', '')

    def get_aigate_base():
        return os.environ.get('AIGATE_BASE_URL', 'https://llm.chudian.site/v1')

    def get_aigate_video_model():
        return os.environ.get('AIGATE_VIDEO_MODEL', 'agnes-video-v2.0')


# 默认视频模型
DEFAULT_VIDEO_MODEL = 'agnes-video-v2.0'

# 轮询参数
POLL_INTERVAL = 4        # 轮询间隔（秒）
POLL_TIMEOUT = 300       # 最长等待（秒）

# AIGate 支持的宽高比
SUPPORTED_RATIOS = ('16:9', '9:16', '1:1', '4:3', '3:4')

# 分辨率档位（agnes-v2.0 支持 480p/720p/1080p）
SUPPORTED_RESOLUTIONS = ('480p', '720p', '1080p')


def _base_url():
    """获取 AIGate base URL，去掉末尾斜杠。"""
    return get_aigate_base().rstrip('/')


class AIGateVideoGenerator:
    """AIGate 图生视频生成器：上传图片 → 提交任务 → 轮询 → 下载。"""

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key or get_aigate_key() or os.environ.get('AIGATE_API_KEY', '')
        self.base_url = (base_url or _base_url()).rstrip('/')
        self.model = model or os.environ.get('AIGATE_VIDEO_MODEL', get_aigate_video_model())

    # ---------- 内部工具 ----------
    def _headers(self, idempotency_key=None):
        h = {
            'Authorization': f'Bearer {self.api_key}',
        }
        if idempotency_key:
            h['Idempotency-Key'] = idempotency_key
        return h

    @staticmethod
    def _safe_ratio(ratio):
        """规范化宽高比：AIGate 不支持 16:10，回退到最接近的 16:9。"""
        if ratio in SUPPORTED_RATIOS:
            return ratio
        # 16:10 → 16:9（最接近的宽屏比例）
        if ratio == '16:10':
            return '16:9'
        return '16:9'

    @staticmethod
    def _safe_resolution(resolution):
        if resolution in SUPPORTED_RESOLUTIONS:
            return resolution
        return '1080p'

    @staticmethod
    def _emit(progress_cb, stage, percent):
        if progress_cb is not None:
            try:
                progress_cb(stage, percent)
            except Exception:
                pass

    # ---------- 文件上传 ----------
    def upload_file(self, image_path):
        """
        上传图片到 AIGate，返回 file_id。
        POST /v1/files，multipart 字段名 file。
        """
        if not self.api_key:
            raise RuntimeError('未配置 AIGATE_API_KEY，请在设置中填写。')
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f'图片不存在：{image_path}')

        url = f'{self.base_url}/files'
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f, 'image/png')}
            resp = requests.post(url, headers=self._headers(), files=files, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        file_id = body.get('id') or body.get('file_id') or (body.get('data') or {}).get('id')
        if not file_id:
            raise RuntimeError(f'文件上传未返回 file_id，响应：{body}')
        return file_id

    # ---------- 主流程 ----------
    def generate(self, image_path, prompt, ratio='16:9', duration=5,
                 resolution='1080p', progress_cb=None):
        """
        提交图生视频任务并等待完成，返回本地视频文件路径。

        :param image_path: 参考图片本地路径（作为首帧/关键帧）
        :param prompt: 视频运动/氛围描述（强调无缝循环、主体稳定）
        :param ratio: 宽高比（16:9/9:16/1:1/4:3/3:4），16:10 自动回退 16:9
        :param duration: 视频时长（秒），agnes-v2.0 支持 1~18 秒
        :param resolution: 分辨率档位（480p/720p/1080p）
        :param progress_cb: 进度回调 callback(stage, percent)
        :return: 生成的 mp4 文件本地路径
        """
        if not self.api_key:
            raise RuntimeError('未配置 AIGATE_API_KEY，请在设置中填写。')

        ratio = self._safe_ratio(ratio)
        resolution = self._safe_resolution(resolution)
        duration = max(1, min(int(duration), 18))

        # 1) 上传参考图
        self._emit(progress_cb, 'uploading', 5)
        file_id = self.upload_file(image_path)

        # 2) 提交视频任务
        self._emit(progress_cb, 'submitted', 10)
        payload = {
            'model': self.model,
            'mode': 'keyframe',
            'first_frame': file_id,
            'prompt': prompt,
            'aspect_ratio': ratio,
            'duration': duration,
            'resolution': resolution,
        }
        idem_key = str(uuid.uuid4())
        submit_url = f'{self.base_url}/videos'
        resp = requests.post(submit_url, headers=self._headers(idem_key),
                             json=payload, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f'提交视频任务失败({resp.status_code}): {resp.text[:300]}')
        body = resp.json()
        video_id = body.get('id') or body.get('video_id') or (body.get('data') or {}).get('id')
        if not video_id:
            raise RuntimeError(f'提交任务未返回 video_id，响应：{body}')

        # 3) 轮询任务状态
        poll_url = f'{self.base_url}/videos/{video_id}'
        start = time.time()
        poll_span = 85 - 10
        while True:
            elapsed = time.time() - start
            if elapsed > POLL_TIMEOUT:
                raise TimeoutError(f'视频生成超时（>{POLL_TIMEOUT}s），video_id={video_id}')

            r = requests.get(poll_url, headers=self._headers(), timeout=60)
            r.raise_for_status()
            data = r.json()

            status = (data.get('status')
                      or (data.get('data') or {}).get('status')
                      or 'unknown')
            pct = 10 + int(poll_span * min(elapsed / POLL_TIMEOUT, 1.0))
            self._emit(progress_cb, 'generating', pct)

            if status in ('completed', 'succeeded', 'success'):
                break
            if status in ('failed', 'error'):
                err = (data.get('error')
                       or (data.get('data') or {}).get('error')
                       or {})
                if isinstance(err, dict):
                    err = err.get('message', str(err))
                raise RuntimeError(f'视频生成失败：{err}')
            time.sleep(POLL_INTERVAL)

        # 4) 取出视频 URL（兼容多种返回结构）
        video_url = None
        metadata = data.get('metadata') or (data.get('data') or {}).get('metadata') or {}
        if isinstance(metadata, dict):
            video_url = metadata.get('url') or metadata.get('video_url')
        if not video_url:
            video_url = (data.get('video_url')
                         or (data.get('data') or {}).get('video_url')
                         or (data.get('output') or {}).get('url'))
        if not video_url:
            raise RuntimeError(f'生成成功但未找到视频地址，响应：{data}')

        # 5) 下载视频
        self._emit(progress_cb, 'downloading', 90)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(OUTPUT_DIR, f'wallpaper_{ts}.mp4')

        with requests.get(video_url, stream=True, timeout=180) as dr:
            dr.raise_for_status()
            with open(out_path, 'wb') as f:
                for chunk in dr.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)

        self._emit(progress_cb, 'done', 100)
        return out_path


# 便捷函数
def generate_wallpaper(image_path, prompt, ratio='16:9', duration=5,
                       resolution='1080p', progress_cb=None):
    """顶层便捷函数：创建生成器并执行。"""
    gen = AIGateVideoGenerator()
    return gen.generate(image_path, prompt, ratio=ratio, duration=duration,
                        resolution=resolution, progress_cb=progress_cb)


# 简单自测
if __name__ == '__main__':
    if len(sys.argv) >= 3:
        img = sys.argv[1]
        p = sys.argv[2]
        out = generate_wallpaper(img, p, ratio='16:9', duration=5,
                                 progress_cb=lambda s, pct: print(f'[{s}] {pct}%'))
        print('生成完成：', out)
    else:
        print('用法：python video_generator.py <image_path> <prompt>')
