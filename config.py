# -*- coding: utf-8 -*-
"""
PetFactory 共享配置与常量
所有模块通过此模块读取 .env、定义路径、加载角色 config.json。
"""
import os
import sys
import json

# 项目根目录：frozen 时为 exe 所在目录，否则为源码目录
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CHARACTERS_DIR = os.path.join(ROOT_DIR, 'characters')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'output')
TOOLS_DIR = os.path.join(ROOT_DIR, 'tools')

# 帧名称清单（15帧，同 V3）
FRAME_NAMES = [
    'idle', 'blink', 'happy', 'sleepy', 'curious', 'content',
    'type_l', 'type_r', 'busy_l', 'busy_r',
    'mouse', 'click', 'urgent_click', 'tired_a', 'tired_b',
]

# 默认固定构图坐标（基于 2048x2048 正方形画布，桌沿在 y≈1600）
# 这些是"固定构图模板"下的常量坐标，所有角色共用
DEFAULT_KEYBOARD = {
    'y_num': 1635, 'y_q': 1715, 'y_a': 1790, 'y_z': 1865, 'y_bot': 1940,
    'dx': 84,
    'row_offsets': {'num': 350, 'q': 365, 'a': 380, 'z': 410},
    'space_x': 800,
}
DEFAULT_SPECIAL_POS = {
    'esc': [250, 1635], 'backspace': [1480, 1635],
    'enter': [1460, 1820],
    'shift_l': [250, 1865], 'shift_r': [1380, 1865],
    'ctrl_l': [150, 1940], 'alt_l': [275, 1940], 'cmd': [400, 1940],
    'ctrl_r': [150, 1940], 'alt_r': [275, 1940],
    'up': [1290, 1940], 'left': [1380, 1940],
    'down': [1470, 1940], 'right': [1560, 1940],
}
DEFAULT_MOUSE = {'left': [1735, 1690], 'right': [1865, 1690], 'mid': [1800, 1600]}
DEFAULT_LEFT_CHARS = '12345qwertasdfgzxcvb'
DEFAULT_RIGHT_CHARS = '67890yuiophjklnm'
DEFAULT_LEFT_SPOTS = [[365, 1715], [533, 1715], [464, 1790], [632, 1790], [494, 1865],
                      [662, 1865], [434, 1635], [602, 1635], [300, 1940]]
DEFAULT_RIGHT_SPOTS = [[869, 1715], [1037, 1715], [884, 1790], [968, 1790], [914, 1865],
                       [830, 1865], [938, 1635], [1106, 1635], [1050, 1940]]


def load_env():
    """从项目根目录 .env 加载环境变量（不依赖 python-dotenv）。"""
    env_path = os.path.join(ROOT_DIR, '.env')
    if not os.path.isfile(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def get_ark_key():
    return os.environ.get('ARK_API_KEY', '')


def get_deepseek_key():
    return os.environ.get('DEEPSEEK_API_KEY', '')


def get_aigate_key():
    return os.environ.get('AIGATE_API_KEY', '')


def get_aigate_base():
    return os.environ.get('AIGATE_BASE_URL', 'https://llm.chudian.site/v1')


def get_aigate_model():
    return os.environ.get('AIGATE_MODEL', 'glm-5.3-flash')


def get_aigate_video_model():
    return os.environ.get('AIGATE_VIDEO_MODEL', 'agnes-video-v2.0')


def save_env_key(key_name, key_value):
    """将 API key 写入 .env 文件（保留已有键）。"""
    env_path = os.path.join(ROOT_DIR, '.env')
    lines = []
    found = False
    if os.path.isfile(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    with open(env_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.strip().startswith(key_name + '='):
                f.write(f'{key_name}={key_value}\n')
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f'{key_name}={key_value}\n')
    os.environ[key_name] = key_value


def default_config():
    """返回默认 config.json 字典（固定构图模板下的标准配置）。"""
    return {
        'character_name': 'NewPet',
        'frame_width': 2048,
        'frame_height': 2048,
        'keyboard': {
            'y_num': 1635, 'y_q': 1715, 'y_a': 1790, 'y_z': 1865, 'y_bot': 1940,
            'dx': 84,
            'row_offsets': {'num': 350, 'q': 365, 'a': 380, 'z': 410},
            'space_x': 800,
        },
        'special_pos': DEFAULT_SPECIAL_POS,
        'mouse': DEFAULT_MOUSE,
        'left_chars': DEFAULT_LEFT_CHARS,
        'right_chars': DEFAULT_RIGHT_CHARS,
        'left_spots': DEFAULT_LEFT_SPOTS,
        'right_spots': DEFAULT_RIGHT_SPOTS,
        'colors': {
            'keyboard_ripple': [120, 195, 255],
            'mouse_ripple': [255, 92, 92],
        },
        'thresholds': {
            'busy_rate': 5.5,
            'urgent_rate': 4.0,
            'tired_after': 6.0,
            'tired_recover': 2.6,
            'tired_switch': 0.42,
        },
        'dialogues': [
            "在忙什么呀~", "敲键盘好快！", "需要咖啡吗？",
            "一起加油吧！", "鼠标用得真溜~", "休息一下嘛",
            "我在陪你哦", "今天也要元气满满！", "工作好认真~",
            "要不要吃点东西？", "加油呀~", "别太累啦",
            "你真棒！", "继续冲！", "有我陪着你呢",
            "打字速度惊人！", "这波操作满分", "摸摸头~",
            "加油加油！", "咔哒咔哒~",
        ],
        'tired_dialogues': [
            "呼……累死了……", "手好酸呀~", "歇会儿嘛……",
            "喘口气……", "拼不动啦……", "让我缓一缓~",
        ],
        'idle_emotes': ['happy', 'sleepy', 'curious', 'content'],
    }


def load_character_config(char_dir):
    """加载角色目录下的 config.json，缺失字段用默认值补齐。"""
    cfg_path = os.path.join(char_dir, 'config.json')
    cfg = default_config()
    if os.path.isfile(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            user_cfg = json.load(f)
        _deep_update(cfg, user_cfg)
    cfg['_assets_dir'] = os.path.join(char_dir, 'assets')
    return cfg


def save_character_config(char_dir, cfg):
    """保存 config.json 到角色目录。"""
    os.makedirs(char_dir, exist_ok=True)
    out = {k: v for k, v in cfg.items() if not k.startswith('_')}
    with open(os.path.join(char_dir, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def _deep_update(base, override):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def list_characters():
    """列出所有已生成的角色目录。"""
    if not os.path.isdir(CHARACTERS_DIR):
        return []
    result = []
    for name in sorted(os.listdir(CHARACTERS_DIR)):
        d = os.path.join(CHARACTERS_DIR, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, 'config.json')):
            result.append(name)
    return result
