from pathlib import Path
import os
import sys

from magika import Magika


DEFAULT_LANG = "txt"

# 在打包后的环境中，需要修复magika模型路径
def _get_magika_base_dir():
    """获取magika基础目录路径，支持打包后的环境"""
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的环境
        if hasattr(sys, '_MEIPASS'):
            meipass = Path(sys._MEIPASS)
            # 检查magika目录是否存在
            magika_base = meipass / 'magika'
            if magika_base.exists():
                # 返回基础目录，让magika自己查找models和config
                return str(magika_base)
        # 如果_MEIPASS中没有，尝试从环境变量获取
        if 'MAGIKA_MODEL_DIR' in os.environ:
            # 如果设置了MAGIKA_MODEL_DIR，尝试获取父目录
            model_dir = Path(os.environ['MAGIKA_MODEL_DIR'])
            if model_dir.parent.name == 'magika':
                return str(model_dir.parent)
            return str(model_dir)
    # 默认情况，让magika自己查找
    return None

# 初始化magika实例
magika = None
try:
    # 在打包后的环境中，magika需要能够找到models和config目录
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass = Path(sys._MEIPASS)
        magika_base = meipass / 'magika'
        magika_models = magika_base / 'models'
        magika_config = magika_base / 'config'
        
        # 检查必要的目录是否存在
        if magika_models.exists() and magika_config.exists():
            # 设置环境变量指向模型目录
            os.environ['MAGIKA_MODEL_DIR'] = str(magika_models)
            # magika会在模型目录的父目录（即magika_base）查找config
            # 尝试使用模型目录初始化
            try:
                magika = Magika(model_dir=magika_models)
            except Exception:
                # 如果失败，尝试默认初始化
                magika = Magika()
        elif magika_models.exists():
            # 只有models目录，尝试初始化
            os.environ['MAGIKA_MODEL_DIR'] = str(magika_models)
            try:
                magika = Magika(model_dir=magika_models)
            except Exception:
                magika = Magika()
        else:
            # 目录不存在，使用默认初始化
            magika = Magika()
    else:
        # 非打包环境，使用默认初始化
        magika = Magika()
except Exception as e:
    # 如果初始化失败，记录警告但继续
    import warnings
    try:
        warnings.warn(f"Failed to initialize magika: {e}", UserWarning)
    except Exception:
        pass
    # 尝试最后一次默认初始化
    try:
        magika = Magika()
    except Exception:
        magika = None

def guess_language_by_text(code):
    if magika is None:
        return DEFAULT_LANG
    try:
        codebytes = code.encode(encoding="utf-8")
        lang = magika.identify_bytes(codebytes).prediction.output.label
        return lang if lang != "unknown" else DEFAULT_LANG
    except Exception:
        return DEFAULT_LANG


def guess_suffix_by_bytes(file_bytes, file_path=None) -> str:
    if magika is None:
        # 如果magika不可用，尝试从文件路径推断
        if file_path:
            return Path(file_path).suffix.lstrip('.') or DEFAULT_LANG
        return DEFAULT_LANG
    try:
        suffix = magika.identify_bytes(file_bytes).prediction.output.label
        if file_path and suffix in ["ai"] and Path(file_path).suffix.lower() in [".pdf"]:
            suffix = "pdf"
        return suffix
    except Exception:
        # 如果magika失败，尝试从文件路径推断
        if file_path:
            return Path(file_path).suffix.lstrip('.') or DEFAULT_LANG
        return DEFAULT_LANG


def guess_suffix_by_path(file_path) -> str:
    if magika is None:
        # 如果magika不可用，从文件路径推断
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        return file_path.suffix.lstrip('.') or DEFAULT_LANG
    try:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        suffix = magika.identify_path(file_path).prediction.output.label
        if suffix in ["ai"] and file_path.suffix.lower() in [".pdf"]:
            suffix = "pdf"
        return suffix
    except Exception:
        # 如果magika失败，从文件路径推断
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        return file_path.suffix.lstrip('.') or DEFAULT_LANG