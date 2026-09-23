# -*- coding: utf-8 -*-
"""
applier.py — 动态壁纸应用模块

负责把生成的视频设置为桌面动态壁纸。支持两种引擎：
  1) Lively Wallpaper（免费开源，支持命令行 --setwp）
  2) Wallpaper Engine（Steam 付费，无稳定 CLI，只能引导用户导入）

检测策略：
- Lively：常见安装路径 + 注册表卸载信息。
- Wallpaper Engine：Steam 注册表 AppPath（appid 431960）+ 常见 Steam 库路径。

幂等安全：本模块只「调用外部程序 / 打开网页」，不直接修改系统壁纸设置，
也不会删除任何文件；检测未安装时返回指引字典，不抛异常。
"""
import os
import sys
import shutil
import webbrowser
import subprocess

# Windows 注册表读取（仅 Windows 下使用）
try:
    import winreg
except Exception:  # 非 Windows 环境兜底
    winreg = None


# ---------- 安装指引常量 ----------
INSTALL_GUIDE = {
    'lively': {
        'name': 'Lively Wallpaper',
        'url': 'https://github.com/rocksdanister/lively',
        'description': '免费开源动态壁纸工具，支持视频/网页/动画壁纸；'
                       '也可在 Microsoft Store 搜索 "Lively Wallpaper" 安装。',
    },
    'wallpaper_engine': {
        'name': 'Wallpaper Engine',
        'url': 'https://store.steampowered.com/app/431960/Wallpaper_Engine/',
        'description': 'Steam 上的付费动态壁纸工具（appid 431960），'
                       '需在 Steam 中购买并安装后使用。',
    },
}


def _registry_query(hive, subkey, value_name):
    """安全读取一个注册表字符串值，失败返回 None。"""
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(hive, subkey) as k:
            val, _ = winreg.QueryValueEx(k, value_name)
            return val
    except Exception:
        return None


def _find_in_uninstall(display_name_keyword):
    """
    在注册表卸载信息里按显示名关键字查找安装路径（InstallLocation / DisplayIcon）。
    同时扫描 32 位与 64 位视图。
    """
    if winreg is None:
        return None

    # 常见卸载信息根路径
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
    ]
    for hive, base in roots:
        try:
            with winreg.OpenKey(hive, base) as root:
                count = winreg.QueryInfoKey(root)[0]
                for i in range(count):
                    try:
                        sub = winreg.EnumKey(root, i)
                    except OSError:
                        continue
                    with winreg.OpenKey(root, sub) as item:
                        try:
                            name, _ = winreg.QueryValueEx(item, 'DisplayName')
                        except OSError:
                            continue
                        if name and display_name_keyword.lower() in name.lower():
                            # 优先 InstallLocation
                            loc = None
                            try:
                                loc, _ = winreg.QueryValueEx(item, 'InstallLocation')
                            except OSError:
                                loc = None
                            if loc and os.path.isdir(loc):
                                exe = os.path.join(loc, 'Lively.exe')
                                if os.path.isfile(exe):
                                    return exe
                            # 退而求其次 DisplayIcon（通常指向 exe）
                            try:
                                icon, _ = winreg.QueryValueEx(item, 'DisplayIcon')
                                if icon and os.path.isfile(icon.strip('"')):
                                    return icon.strip('"')
                            except OSError:
                                pass
        except OSError:
            continue
    return None


class WallpaperApplier:
    """动态壁纸应用器：检测引擎并把视频设置为壁纸。"""

    # ---------- Lively 检测 ----------
    def detect_lively(self):
        """
        检测 Lively 是否已安装。
        :return: (installed: bool, path: str)，path 为 Lively.exe 全路径或空串。
        """
        local = os.environ.get('LOCALAPPDATA', '')
        candidates = []
        if local:
            candidates.append(os.path.join(local, r'Programs\Lively Wallpaper\Lively.exe'))
        candidates.append(r'C:\Program Files\Lively Wallpaper\Lively.exe')
        candidates.append(r'C:\Program Files (x86)\Lively Wallpaper\Lively.exe')

        for p in candidates:
            if os.path.isfile(p):
                return True, p

        # 注册表兜底
        reg = _find_in_uninstall('Lively')
        if reg:
            return True, reg

        return False, ''

    # ---------- Wallpaper Engine 检测 ----------
    def detect_wallpaper_engine(self):
        """
        检测 Wallpaper Engine（Steam appid 431960）是否已安装。
        :return: (installed: bool, path: str)
        """
        # 1) Steam 注册表 AppPath：HKCU\Software\Valve\Steam
        steam_path = _registry_query(winreg.HKEY_CURRENT_USER if winreg else None,
                                     r'Software\Valve\Steam', 'SteamPath') if winreg else None

        # 收集可能的 Steam 库路径
        library_paths = []
        if steam_path:
            steam_path = steam_path.replace('/', os.sep).replace('\\', os.sep)
            library_paths.append(steam_path)
            # 读取 libraryfolders.vdf 里的其它库
            vdf = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
            if os.path.isfile(vdf):
                try:
                    with open(vdf, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            # 形如  "path"  "D:\\Steam"
                            if '"path"' in line.lower():
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    library_paths.append(parts[3].replace('\\\\', os.sep))
                except Exception:
                    pass

        # 常见额外路径兜底
        library_paths.append(r'D:\Steam')
        library_paths.append(r'C:\Program Files (x86)\Steam')

        exe_names = ('wallpaper32.exe', 'wallpaper64.exe')
        for lib in library_paths:
            if not lib:
                continue
            we_dir = os.path.join(lib, 'steamapps', 'common', 'wallpaper_engine')
            for exe in exe_names:
                p = os.path.join(we_dir, exe)
                if os.path.isfile(p):
                    return True, p

        return False, ''

    # ---------- 应用：Lively ----------
    def apply_with_lively(self, video_path):
        """
        调用 Lively 命令行把视频设为壁纸。
        Lively 支持 `Lively.exe --setwp <path>`（不同版本参数略有差异，这里做容错）。
        :return: (success: bool, message: str)
        """
        installed, exe = self.detect_lively()
        if not installed:
            return False, '未检测到 Lively Wallpaper'
        if not os.path.isfile(video_path):
            return False, f'视频文件不存在：{video_path}'

        try:
            # --setwp 是官方提供的设置壁纸参数；部分版本使用 --setwallpaper
            proc = subprocess.run(
                [exe, '--setwp', video_path],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                return True, '已通过 Lively 设置壁纸'
            # 回退参数
            proc2 = subprocess.run(
                [exe, '--setwallpaper', video_path],
                capture_output=True, text=True, timeout=30,
            )
            if proc2.returncode == 0:
                return True, '已通过 Lively 设置壁纸'
            return False, f'Lively 调用失败：{proc.stderr or proc2.stderr}'
        except Exception as e:
            return False, f'调用 Lively 异常：{e}'

    # ---------- 应用：Wallpaper Engine ----------
    def apply_with_wallpaper_engine(self, video_path):
        """
        Wallpaper Engine 无稳定命令行，这里只负责：
        - 打开 WE
        - 返回指引让用户把视频拖入 WE「从文件打开」。
        :return: (success: bool, message: str)
        """
        installed, exe = self.detect_wallpaper_engine()
        if not installed:
            return False, '未检测到 Wallpaper Engine'

        # 尝试启动 WE（不阻塞）
        try:
            subprocess.Popen([exe])
        except Exception:
            pass

        msg = (
            'Wallpaper Engine 无命令行接口，已尝试启动 WE；'
            '请在 WE 中选择「创建或打开壁纸」→「打开本地文件」，'
            '选择视频：{0}'
        ).format(video_path)
        return False, msg

    # ---------- 安装指引 ----------
    def get_install_guide(self):
        """返回两种引擎的安装指引字典（名字/下载地址/说明）。"""
        return INSTALL_GUIDE

    def open_download_page(self, app_name):
        """
        用默认浏览器打开对应下载页。
        :param app_name: 'lively' 或 'wallpaper_engine'
        """
        info = INSTALL_GUIDE.get(app_name)
        if not info:
            return False
        webbrowser.open(info['url'])
        return True

    # ---------- 总入口 ----------
    def apply(self, video_path):
        """
        自动选择引擎把视频设为壁纸：
        - 优先 Lively（免费、可命令行）；
        - 其次 Wallpaper Engine（启动并引导）；
        - 都没装则返回 (False, guide_dict)。
        :return: (success: bool, message_or_guide)
        """
        lively_installed, _ = self.detect_lively()
        if lively_installed:
            ok, msg = self.apply_with_lively(video_path)
            if ok:
                return True, msg

        we_installed, _ = self.detect_wallpaper_engine()
        if we_installed:
            ok, msg = self.apply_with_wallpaper_engine(video_path)
            # WE 即使「启动+引导」也算完成流程
            return True, msg

        # 都没装：返回安装指引
        return False, self.get_install_guide()


# 简单自测
if __name__ == '__main__':
    applier = WallpaperApplier()
    print('Lively：', applier.detect_lively())
    print('Wallpaper Engine：', applier.detect_wallpaper_engine())
    print('安装指引：', applier.get_install_guide())
