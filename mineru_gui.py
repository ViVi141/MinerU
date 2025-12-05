# -*- coding: utf-8 -*-
"""
MinerU PDF转Markdown GUI应用程序
功能完备且美观的图形界面 - 支持任务队列版本
"""
import os
import sys
import threading
import time
import tkinter.filedialog as filedialog
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List

# 修复打包后 sys.stderr 和 sys.stdout 为 None 的问题
# 这会导致 doclayout_yolo 等库在访问 encoding 属性时出错
if getattr(sys, 'frozen', False):
    # 打包后的exe模式，console=False 时 sys.stderr 和 sys.stdout 可能为 None
    # 使用 os.devnull 创建虚拟流，确保有 encoding 属性
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8', errors='replace')
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8', errors='replace')
    if sys.stdin is None:
        sys.stdin = open(os.devnull, 'r', encoding='utf-8', errors='replace')
    
    # 修复打包后 inspect.getsource() 无法获取源代码的问题
    # transformers 等库会使用 inspect 获取源代码，但打包后源代码不可用
    try:
        import inspect

        # 保存原始函数
        _original_getsource = inspect.getsource
        _original_getsourcelines = inspect.getsourcelines
        _original_findsource = inspect.findsource

        def patched_getsource(object):
            """修补的 getsource，在无法获取源代码时返回默认源代码"""
            try:
                return _original_getsource(object)
            except (OSError, TypeError):
                # 无法获取源代码时返回一个默认的函数定义字符串
                # transformers 的 docstring_decorator 期望至少有一行代码
                if hasattr(object, '__name__'):
                    # 返回一个简单的函数定义字符串，包含至少一行代码
                    return f"def {object.__name__}(self, *args, **kwargs):\n    \"\"\"Function definition\"\"\"\n    pass\n"
                else:
                    # 返回一个基本的函数定义，包含至少一行代码
                    return "def dummy_function(self, *args, **kwargs):\n    \"\"\"Dummy function\"\"\"\n    pass\n"

        def patched_getsourcelines(object):
            """修补的 getsourcelines，在无法获取源代码时返回默认内容"""
            try:
                return _original_getsourcelines(object)
            except (OSError, TypeError):
                # 返回一个包含至少一行的列表
                return (["def dummy_function(self, *args, **kwargs):", "    \"\"\"Dummy function\"\"\"", "    pass"], 1)

        def patched_findsource(object):
            """修补的 findsource，在无法获取源代码时返回默认内容"""
            try:
                return _original_findsource(object)
            except (OSError, TypeError):
                # 返回一个模拟的文件对象
                class MockFile:
                    def readlines(self):
                        return ["def dummy_function(self, *args, **kwargs):", "    \"\"\"Dummy function\"\"\"", "    pass"]
                return (MockFile(), 1)

        # 应用修补
        inspect.getsource = patched_getsource
        inspect.getsourcelines = patched_getsourcelines
        inspect.findsource = patched_findsource

        # 额外修复 transformers 的 get_docstring_indentation_level 函数
        try:
            from transformers.utils import doc
            if hasattr(doc, 'get_docstring_indentation_level'):
                original_get_docstring_indentation_level = doc.get_docstring_indentation_level

                def patched_get_docstring_indentation_level(fn):
                    """修补 transformers 的 get_docstring_indentation_level 函数"""
                    try:
                        return original_get_docstring_indentation_level(fn)
                    except (IndexError, OSError, TypeError):
                        # 如果源代码为空或无法获取，返回默认缩进级别
                        return 0

                doc.get_docstring_indentation_level = patched_get_docstring_indentation_level
        except Exception:
            pass

    except Exception:
        pass  # 如果修补失败，继续执行
    
    # 修复SSL证书路径（PyInstaller打包后certifi证书路径会改变）
    # 必须在导入任何网络库（requests, urllib3等）之前设置
    try:
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller临时解压目录
            meipass = Path(sys._MEIPASS)
            # 尝试多个可能的证书路径
            cert_paths = [
                meipass / 'certifi' / 'cacert.pem',  # 打包后的证书文件
                meipass / 'certifi' / 'cacert.pem',  # 如果certifi目录存在
            ]
            
            cert_path = None
            for path in cert_paths:
                if path.exists():
                    cert_path = path
                    break
            
            # 如果还没找到，尝试导入certifi并查找
            if not cert_path:
                try:
                    import certifi
                    certifi_dir = Path(certifi.__file__).parent
                    cert_path = certifi_dir / 'cacert.pem'
                    if not cert_path.exists():
                        # 尝试查找certifi包中的证书
                        cert_path = None
                except Exception:
                    pass
            
            if cert_path and cert_path.exists():
                cert_path_str = str(cert_path.resolve())
                # 设置环境变量，让requests等库使用正确的证书路径
                os.environ['REQUESTS_CA_BUNDLE'] = cert_path_str
                os.environ['SSL_CERT_FILE'] = cert_path_str
                os.environ['CURL_CA_BUNDLE'] = cert_path_str
                
                # 设置certifi的证书路径（通过monkey patch）
                # 必须在导入certifi之前或之后立即设置
                try:
                    import certifi.core
                    # 保存原始函数
                    if not hasattr(certifi.core, '_original_where'):
                        certifi.core._original_where = certifi.core.where
                    
                    # 创建新的where函数
                    def patched_where():
                        if cert_path.exists():
                            return cert_path_str
                        # 回退到原始函数
                        if hasattr(certifi.core, '_original_where'):
                            return certifi.core._original_where()
                        return certifi.core.where.__wrapped__() if hasattr(certifi.core.where, '__wrapped__') else certifi.core.where()
                    
                    certifi.core.where = patched_where
                except Exception:
                    pass
                
                # 也尝试直接修改urllib3的SSL上下文（如果已导入）
                try:
                    import ssl
                    import urllib3
                    # 创建使用指定证书的SSL上下文
                    ssl_context = ssl.create_default_context(cafile=cert_path_str)
                    urllib3.util.ssl_.create_urllib3_context = lambda: ssl_context
                except Exception:
                    pass
    except Exception as e:
        # 记录错误但不中断程序
        try:
            import logging
            logging.warning(f"SSL证书路径设置失败: {e}")
        except Exception:
            pass

import customtkinter as ctk
from loguru import logger

# 必须在导入 mineru 模块之前设置环境变量
# 支持打包后的路径查找
if getattr(sys, 'frozen', False):
    # 打包后的exe模式
    project_dir = Path(sys.executable).parent
    # 修复magika模型和配置路径
    # PyInstaller会将magika/models和magika/config打包到_MEIPASS/magika/
    try:
        # 在导入magika之前，我们需要确保模型和配置路径正确
        # 使用sys._MEIPASS获取临时解压目录（PyInstaller使用）
        if hasattr(sys, '_MEIPASS'):
            meipass = Path(sys._MEIPASS)
            # 检查magika目录结构
            magika_models = meipass / 'magika' / 'models'
            magika_config = meipass / 'magika' / 'config'
            
            if magika_models.exists():
                # 设置环境变量，让magika知道模型位置
                os.environ['MAGIKA_MODEL_DIR'] = str(magika_models)
            
            # magika还需要config目录，它会在模型目录的父目录查找
            # 确保整个magika目录结构都在_MEIPASS下
            if not magika_config.exists():
                # 如果config目录不存在，尝试从magika包中复制
                try:
                    import magika
                    source_magika_dir = Path(magika.__file__).parent
                    source_config = source_magika_dir / 'config'
                    if source_config.exists() and not magika_config.exists():
                        # 在打包时应该已经包含了，这里只是备用检查
                        pass
                except Exception:
                    pass
    except Exception:
        pass  # 如果出错，继续执行
else:
    # 开发模式
    project_dir = Path(__file__).parent

config_file = project_dir / "mineru.json"

# 设置模型源为本地（优先使用本地模型，避免从网络下载）
# 必须在导入mineru模块之前设置
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # 打包后模式：优先使用打包后的模型
    meipass = Path(sys._MEIPASS)
    models_pipeline_path = meipass / 'models' / 'pipeline'
    
    if models_pipeline_path.exists():
        # 打包后的模型存在，强制使用本地模型
        os.environ['MINERU_MODEL_SOURCE'] = 'local'
        
        # 更新或创建配置文件，指向打包后的模型路径
        try:
            import json
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # 确保models-dir配置存在并指向打包后的模型
            if 'models-dir' not in config:
                config['models-dir'] = {}
            config['models-dir']['pipeline'] = str(models_pipeline_path.resolve())
            
            # 保存配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            os.environ['MINERU_TOOLS_CONFIG_JSON'] = str(config_file.resolve())
        except Exception:
            # 如果配置文件操作失败，至少设置环境变量
            os.environ['MINERU_MODEL_SOURCE'] = 'local'
            if config_file.exists():
                os.environ['MINERU_TOOLS_CONFIG_JSON'] = str(config_file.resolve())
elif config_file.exists():
    # 开发模式：使用配置文件
    os.environ['MINERU_MODEL_SOURCE'] = 'local'
    os.environ['MINERU_TOOLS_CONFIG_JSON'] = str(config_file.resolve())
else:
    # 开发模式：如果没有配置文件，检查是否有本地模型
    models_dir = project_dir / 'models' / 'pipeline'
    if models_dir.exists():
        os.environ['MINERU_MODEL_SOURCE'] = 'local'

# 现在才导入 mineru 模块
from mineru.cli.common import do_parse, read_fn  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402

# 设置CustomTkinter主题 - 跟随系统主题
ctk.set_appearance_mode("system")  # "system" 跟随系统主题, "light" 或 "dark" 固定主题
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"

# 支持的后端（仅Pipeline，本地运行，无需VLM相关依赖）
BACKENDS = ['pipeline']
# 已移除VLM后端选项以减小打包体积，Pipeline后端功能完整且兼容性更好

# 支持的语言（带说明的显示名称）
LANGUAGES_DISPLAY = {
    'ch': 'ch (中文，推荐)',
    'ch_server': 'ch_server (中文-服务器版，精度更高)',
    'ch_lite': 'ch_lite (中文-轻量版，速度更快)',
    'en': 'en (英文)',
    'korean': 'korean (韩文)',
    'japan': 'japan (日文)',
    'chinese_cht': 'chinese_cht (繁体中文)',
    'ta': 'ta (泰米尔语)',
    'te': 'te (泰卢固语)',
    'ka': 'ka (格鲁吉亚语)',
    'th': 'th (泰语)',
    'el': 'el (希腊语)',
    'latin': 'latin (拉丁语系)',
    'arabic': 'arabic (阿拉伯语)',
    'east_slavic': 'east_slavic (东斯拉夫语)',
    'cyrillic': 'cyrillic (西里尔语)',
    'devanagari': 'devanagari (天城文)'
}

# 支持的语言代码列表
LANGUAGES = list(LANGUAGES_DISPLAY.keys())

# 解析方法
METHODS = ['auto', 'txt', 'ocr']


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "等待中"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    FAILED = "失败"
    CANCELLED = "已取消"


class ErrorCategory(Enum):
    """错误类别枚举"""
    FILE_IO = "文件操作错误"
    CONFIGURATION = "配置错误"
    NETWORK = "网络错误"
    PERMISSION = "权限错误"
    MEMORY = "内存错误"
    MODEL = "模型错误"
    VALIDATION = "验证错误"
    UNKNOWN = "未知错误"


class MinerUErrorHandler:
    """统一的错误处理工具类"""
    
    @staticmethod
    def classify_exception(exc: Exception) -> tuple[ErrorCategory, str]:
        """分类异常并生成用户友好的错误消息"""
        error_msg = str(exc)
        
        # 文件操作错误
        if isinstance(exc, (FileNotFoundError, IOError, OSError)):
            if "No such file" in error_msg or "找不到文件" in error_msg:
                return ErrorCategory.FILE_IO, f"文件未找到: {error_msg}\n请检查文件路径是否正确"
            elif "Permission denied" in error_msg or "权限" in error_msg:
                return ErrorCategory.PERMISSION, f"权限不足: {error_msg}\n请检查文件或目录的读写权限"
            elif "Disk" in error_msg or "磁盘" in error_msg or "空间" in error_msg:
                return ErrorCategory.FILE_IO, f"磁盘空间不足: {error_msg}\n请清理磁盘空间后重试"
            else:
                return ErrorCategory.FILE_IO, f"文件操作失败: {error_msg}"
        
        # 配置错误
        elif isinstance(exc, (ValueError, KeyError, AttributeError)):
            if "config" in error_msg.lower() or "配置" in error_msg:
                return ErrorCategory.CONFIGURATION, f"配置错误: {error_msg}\n请检查配置文件或参数设置"
            elif "validation" in error_msg.lower() or "验证" in error_msg:
                return ErrorCategory.VALIDATION, f"参数验证失败: {error_msg}\n请检查输入参数"
            else:
                return ErrorCategory.VALIDATION, f"参数错误: {error_msg}"
        
        # 内存错误
        elif isinstance(exc, MemoryError):
            return ErrorCategory.MEMORY, f"内存不足: {error_msg}\n建议关闭其他程序或减小处理文件大小"
        
        # 网络错误（如果有）
        elif isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK, f"网络连接失败: {error_msg}\n请检查网络连接或稍后重试"
        
        # 模型相关错误
        elif "model" in error_msg.lower() or "模型" in error_msg or "torch" in error_msg.lower():
            return ErrorCategory.MODEL, f"模型加载/运行错误: {error_msg}\n请检查模型文件是否完整"
        
        # 默认未知错误
        else:
            error_type = type(exc).__name__
            return ErrorCategory.UNKNOWN, f"发生错误: {error_msg}\n错误类型: {error_type}"
    
    @staticmethod
    def format_error_message(exc: Exception, context: str = "") -> str:
        """格式化错误消息，包含上下文信息"""
        category, user_msg = MinerUErrorHandler.classify_exception(exc)
        
        result = f"【{category.value}】{user_msg}"
        if context:
            result += f"\n上下文: {context}"
        
        return result
    
    @staticmethod
    def should_retry(exc: Exception) -> bool:
        """判断错误是否可重试"""
        error_msg = str(exc).lower()
        
        # 网络错误通常可重试
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return True
        
        # 临时文件错误可能可重试
        if isinstance(exc, (IOError, OSError)):
            if "temporary" in error_msg or "临时" in error_msg:
                return True
        
        # 其他错误通常不可重试
        return False


@dataclass
class ConversionTask:
    """转换任务数据类"""
    file_path: Path
    file_name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    error_message: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    page_count: int = 0  # PDF页数
    total_time: float = 0.0  # 总处理时间（秒）
    time_per_page: float = 0.0  # 每页处理时间（秒）
    retry_count: int = 0  # 重试次数
    max_retries: int = 3  # 最大重试次数


class MinerUGUI(ctk.CTk):
    """MinerU GUI主窗口 - 支持任务队列版本"""
    
    def __init__(self):
        super().__init__()

        # 配置窗口
        self.title("MinerU - PDF转Markdown工具")
        self.geometry("1100x800")
        self.minsize(1000, 700)

        # 转换状态
        self.is_converting = False
        self.conversion_thread: Optional[threading.Thread] = None
        self.queue_lock = threading.Lock()

        # 任务队列
        self.task_queue: List[ConversionTask] = []
        self.current_task_index = -1

        # 队列更新控制
        self.queue_update_pending = False
        self.queue_update_id = None

        # 任务列表显示优化（虚拟滚动）
        self.max_visible_tasks = 50  # 最多同时显示50个任务
        self.task_display_start = 0  # 显示起始索引
        self.task_widgets_cache = {}  # 任务组件缓存

        # 文件列表显示优化（虚拟滚动）
        self.max_visible_files = 30  # 最多同时显示30个文件
        self.file_display_start = 0  # 文件显示起始索引
        self.selected_file_paths = []  # 存储已选择的文件路径列表
        self.file_widgets_cache = {}  # 文件组件缓存

        # 资源管理
        self._shutdown_event = threading.Event()
        self._resource_lock = threading.Lock()
        self._active_resources = set()  # 跟踪活跃资源

        # GUI更新队列（线程安全）
        self._gui_update_queue = []
        self._gui_update_lock = threading.Lock()
        self._gui_update_scheduled = False

        # 内存监控
        self._memory_check_interval = 30000  # 30秒检查一次内存
        self._memory_warning_threshold = 1024 * 1024 * 1024  # 1GB警告阈值
        self._last_memory_check = 0

        # 队列管理（动态从UI获取）
        self._auto_cleanup_interval = 60000  # 1分钟清理一次
        self._last_cleanup_check = 0
        self._cleanup_batch_size = 50  # 每次清理50个任务

        # 创建界面（必须先创建，因为setup_logging需要log_text）
        self.create_widgets()

        # 配置日志输出到GUI（在create_widgets之后，确保log_text已初始化）
        self.setup_logging()

        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _on_config_changed(self):
        """配置改变时的处理"""
        # 这里可以添加配置改变时的逻辑，比如更新UI提示等
        # 目前主要用于更新配置哈希的时机
        pass

    def on_closing(self):
        """窗口关闭时的清理工作"""
        try:
            self.log("正在关闭应用程序并清理资源...", switch_to_log=True)

            # 设置关闭标志
            self._shutdown_event.set()

            # 取消当前转换
            if self.is_converting:
                self.log("正在取消当前任务...", switch_to_log=True)
                self.is_converting = False

            # 等待线程结束（带超时）
            if self.conversion_thread and self.conversion_thread.is_alive():
                self.log("等待后台任务完成...", switch_to_log=True)
                self.conversion_thread.join(timeout=5.0)  # 最多等待5秒

                if self.conversion_thread.is_alive():
                    self.log("强制终止后台任务...", switch_to_log=True)

            # 清理资源
            self._cleanup_resources()

            # 清理任务组件缓存
            self._cleanup_task_widgets()

            # 清理文件组件缓存
            self._cleanup_file_widgets()

            # 清理队列更新定时器
            if self.queue_update_id:
                try:
                    self.after_cancel(self.queue_update_id)
                    self.queue_update_id = None
                except Exception:
                    pass

            # 清理文件更新定时器
            if hasattr(self, 'file_update_id') and self.file_update_id:
                try:
                    self.after_cancel(self.file_update_id)
                    self.file_update_id = None
                except Exception:
                    pass

            # 停止GUI更新处理器
            self._shutdown_event.set()

            # 特别的打包后清理（强制清理可能残留的进程和资源）
            if getattr(sys, 'frozen', False):
                self._force_cleanup_for_frozen_app()

            self.log("应用程序已安全关闭", switch_to_log=True)

        except Exception as e:
            logger.exception(f"关闭应用程序时发生错误: {e}")
        finally:
            # 确保窗口关闭
            try:
                self.quit()
                self.destroy()
            except Exception:
                pass

    def _cleanup_resources(self):
        """清理资源"""
        with self._resource_lock:
            # 清理活跃资源
            for resource in self._active_resources.copy():
                try:
                    if hasattr(resource, 'close'):
                        resource.close()
                    elif hasattr(resource, '__del__'):
                        resource.__del__()
                except Exception as e:
                    logger.warning(f"清理资源时出错: {e}")
                finally:
                    self._active_resources.discard(resource)

    def _calculate_queue_stats(self):
        """计算队列统计信息（优化：单次遍历）"""
        pending = processing = completed = failed = 0
        for task in self.task_queue:
            if task.status == TaskStatus.PENDING:
                pending += 1
            elif task.status == TaskStatus.PROCESSING:
                processing += 1
            elif task.status == TaskStatus.COMPLETED:
                completed += 1
            elif task.status == TaskStatus.FAILED:
                failed += 1
        return pending, processing, completed, failed
    
    def _extract_method_code(self, method_display: str) -> str:
        """从显示名称中提取实际的方法代码"""
        if 'auto' in method_display:
            return 'auto'
        elif 'txt' in method_display:
            return 'txt'
        elif 'ocr' in method_display:
            return 'ocr'
        else:
            return method_display
    
    def _extract_lang_code(self, lang_display: str) -> str:
        """从显示名称中提取实际的语言代码"""
        return lang_display.split()[0] if ' ' in lang_display else lang_display
    
    def _parse_page_range(self) -> tuple[int, Optional[int]]:
        """解析页码范围配置，并进行边界检查"""
        try:
            start_page_id = int(self.start_page_var.get()) if self.start_page_var.get() else 0
            # 边界检查：页码必须 >= 0
            if start_page_id < 0:
                start_page_id = 0
        except (ValueError, TypeError):
            start_page_id = 0
        
        try:
            end_page_id_str = self.end_page_var.get()
            if end_page_id_str:
                end_page_id = int(end_page_id_str)
                # 边界检查：结束页码必须 >= 开始页码
                if end_page_id < start_page_id:
                    end_page_id = None  # 无效范围，忽略
            else:
                end_page_id = None
        except (ValueError, TypeError):
            end_page_id = None
        
        return start_page_id, end_page_id
    
    def _get_task_config(self) -> dict:
        """获取任务配置参数（统一提取配置）"""
        method_display = self.method_var.get()
        lang_display = self.lang_var.get()
        start_page_id, end_page_id = self._parse_page_range()  # 只调用一次
        
        return {
            'output_dir': self.output_path_var.get(),
            'backend': self.backend_var.get(),
            'method': self._extract_method_code(method_display),
            'lang': self._extract_lang_code(lang_display),
            'formula_enable': self.formula_var.get(),
            'table_enable': self.table_var.get(),
            'start_page_id': start_page_id,
            'end_page_id': end_page_id,
            'device_mode': self.device_var.get().strip() or None,
        }

    def _update_queue_info_only(self):
        """仅更新队列统计信息，不重新创建组件"""
        try:
            with self.queue_lock:
                queue_size = len(self.task_queue)

                if queue_size == 0:
                    self.queue_info_var.set("队列为空")
                    self.page_info_var.set("")
                    self.prev_page_btn.configure(state="disabled")
                    self.next_page_btn.configure(state="disabled")
                else:
                    pending, processing, completed, failed = self._calculate_queue_stats()

                    self.queue_info_var.set(
                        f"队列: {queue_size} 个任务 | "
                        f"等待: {pending} | "
                        f"处理中: {processing} | "
                        f"完成: {completed} | "
                        f"失败: {failed}"
                    )

                    # 更新分页信息
                    if queue_size > self.max_visible_tasks:
                        total_pages = (queue_size + self.max_visible_tasks - 1) // self.max_visible_tasks
                        current_page = (self.task_display_start // self.max_visible_tasks) + 1
                        display_end = min(self.task_display_start + self.max_visible_tasks, queue_size)
                        self.page_info_var.set(f"显示 {self.task_display_start + 1}-{display_end} / {queue_size} (第 {current_page}/{total_pages} 页)")
                        self.prev_page_btn.configure(state="normal" if self.task_display_start > 0 else "disabled")
                        self.next_page_btn.configure(state="normal" if display_end < queue_size else "disabled")
                    else:
                        self.page_info_var.set("")
                        self.prev_page_btn.configure(state="disabled")
                        self.next_page_btn.configure(state="disabled")

        except Exception as e:
            logger.warning(f"更新队列信息时出错: {e}")

    def _cleanup_task_widgets(self):
        """清理任务组件缓存"""
        try:
            for widget in self.task_widgets_cache.values():
                if widget and widget.winfo_exists():
                    try:
                        widget.destroy()
                    except Exception:
                        pass
            self.task_widgets_cache.clear()
        except Exception as e:
            logger.warning(f"清理任务组件时出错: {e}")

    def _cleanup_file_widgets(self):
        """清理文件组件缓存"""
        try:
            for widget in self.file_widgets_cache.values():
                if widget and widget.winfo_exists():
                    try:
                        widget.destroy()
                    except Exception:
                        pass
            self.file_widgets_cache.clear()
        except Exception as e:
            logger.warning(f"清理文件组件时出错: {e}")

    def _force_cleanup_for_frozen_app(self):
        """打包后程序的强制清理"""
        try:
            # 强制垃圾回收
            import gc
            gc.collect()

            # 清理可能的PyTorch缓存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            except Exception:
                pass

            # 清理可能的OpenCV缓存
            try:
                import cv2
                cv2.destroyAllWindows()
            except Exception:
                pass

            # 清理可能的matplotlib后端
            try:
                import matplotlib
                matplotlib.pyplot.close('all')
            except Exception:
                pass

            # 强制清理所有线程
            import threading
            current_thread = threading.current_thread()
            for thread in threading.enumerate():
                if thread != current_thread and thread.is_alive():
                    try:
                        # 给线程一点时间来自行结束
                        thread.join(timeout=1.0)
                    except Exception:
                        pass

            # 在Windows上，尝试清理可能的进程残留
            if sys.platform == 'win32':
                try:
                    import psutil
                    import os
                    current_pid = os.getpid()
                    current_process = psutil.Process(current_pid)

                    # 清理子进程
                    for child in current_process.children(recursive=True):
                        try:
                            if child.is_running():
                                child.terminate()
                                child.wait(timeout=2)
                        except Exception:
                            try:
                                child.kill()
                            except Exception:
                                pass

                except ImportError:
                    pass  # psutil不可用
                except Exception:
                    pass  # 清理失败，继续

            # 最后一次垃圾回收
            gc.collect()

        except Exception as e:
            logger.warning(f"强制清理时出错: {e}")

    def _check_memory_usage(self):
        """检查内存使用情况"""
        if self._shutdown_event.is_set():
            return

        # 检查是否启用内存监控
        if hasattr(self, 'enable_memory_monitor_var') and not self.enable_memory_monitor_var.get():
            return

        try:
            import psutil
            import os

            current_time = time.time() * 1000  # 转换为毫秒
            if current_time - self._last_memory_check < self._memory_check_interval:
                return

            self._last_memory_check = current_time

            # 获取当前进程内存使用
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)

            # 如果内存使用超过阈值，进行垃圾回收
            if memory_mb > (self._memory_warning_threshold / (1024 * 1024)):
                self.log(f"⚠️ 内存使用较高: {memory_mb:.1f} MB，进行垃圾回收...", switch_to_log=True)
                import gc
                gc.collect()

                # 再次检查内存
                memory_after_gc = process.memory_info().rss / (1024 * 1024)
                self.log(f"   垃圾回收后内存: {memory_after_gc:.1f} MB", switch_to_log=True)

                # 如果内存仍然很高，清理缓存
                if memory_after_gc > (self._memory_warning_threshold / (1024 * 1024) * 0.8):
                    self._cleanup_task_widgets()
                    self.log("   已清理任务组件缓存", switch_to_log=True)

        except ImportError:
            # 如果没有psutil，跳过内存检查
            pass
        except Exception as e:
            logger.warning(f"内存检查时出错: {e}")

    def _auto_cleanup_completed_tasks(self):
        """自动清理已完成的旧任务"""
        if self._shutdown_event.is_set():
            return

        try:
            current_time = time.time() * 1000  # 转换为毫秒
            if current_time - self._last_cleanup_check < self._auto_cleanup_interval:
                return

            self._last_cleanup_check = current_time

            with self.queue_lock:
                # 获取已完成和失败的任务
                completed_tasks = [t for t in self.task_queue if t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]]

                # 使用UI设置的最大保留任务数
                max_completed = self.keep_completed_var.get() if hasattr(self, 'keep_completed_var') else 500

                if len(completed_tasks) > max_completed:
                    # 需要清理的任务数量
                    to_remove_count = len(completed_tasks) - max_completed

                    # 按完成时间排序，保留最新的
                    completed_tasks.sort(key=lambda t: t.end_time or datetime.min, reverse=True)

                    # 获取需要删除的任务
                    tasks_to_remove = completed_tasks[-to_remove_count:]

                    # 在删除前查找任务索引（用于清理组件缓存）
                    task_ids_to_remove = []
                    for task in tasks_to_remove:
                        # 找到任务在原始队列中的索引作为ID
                        for i, t in enumerate(self.task_queue):
                            if t == task:
                                task_ids_to_remove.append(i)
                                break

                    # 从队列中移除这些任务
                    original_length = len(self.task_queue)
                    self.task_queue = [t for t in self.task_queue if t not in tasks_to_remove]

                    removed_count = original_length - len(self.task_queue)

                    if removed_count > 0:
                        self.log(f"🧹 已自动清理 {removed_count} 个旧的已完成任务", switch_to_log=False)

                        # 清理相关的组件缓存
                        for task_id in task_ids_to_remove:
                            self.task_widgets_cache.pop(task_id, None)

                        # 如果当前显示的页面受到影响，调整显示起始位置
                        if self.task_display_start >= len(self.task_queue) and len(self.task_queue) > 0:
                            self.task_display_start = max(0, len(self.task_queue) - self.max_visible_tasks)

                        # 更新显示
                        self._update_queue_info_only()

        except Exception as e:
            logger.warning(f"自动清理任务时出错: {e}")

    def _force_gc_and_cleanup(self):
        """强制垃圾回收和清理"""
        try:
            import gc
            # 强制垃圾回收
            gc.collect()

            # 清理任务缓存
            if len(self.task_widgets_cache) > self.max_visible_tasks:
                # 只保留最近的任务组件
                cache_items = list(self.task_widgets_cache.items())
                # 保留最新的组件
                to_remove = cache_items[:-self.max_visible_tasks]
                for task_id, widget in to_remove:
                    if widget and widget.winfo_exists():
                        try:
                            widget.destroy()
                        except Exception:
                            pass
                    self.task_widgets_cache.pop(task_id, None)

            self.log("已执行内存清理和垃圾回收", switch_to_log=True)
        except Exception as e:
            logger.warning(f"强制清理时出错: {e}")

    def schedule_gui_update(self, callback, *args, **kwargs):
        """线程安全的GUI更新调度"""
        if self._shutdown_event.is_set():
            return

        with self._gui_update_lock:
            self._gui_update_queue.append((callback, args, kwargs))

            # 如果还没有调度更新，则调度一个
            if not self._gui_update_scheduled:
                self._gui_update_scheduled = True
                self.after(50, self._process_gui_updates)  # 50ms后处理

    def _process_gui_updates(self):
        """处理GUI更新队列"""
        if self._shutdown_event.is_set():
            return

        updates_to_process = []
        with self._gui_update_lock:
            updates_to_process = self._gui_update_queue.copy()
            self._gui_update_queue.clear()
            self._gui_update_scheduled = False

        # 在主线程中执行更新
        for callback, args, kwargs in updates_to_process:
            try:
                if callable(callback):
                    callback(*args, **kwargs)
            except Exception as e:
                logger.warning(f"GUI更新时出错: {e}")

        # 如果还有待处理的更新，继续调度
        with self._gui_update_lock:
            if self._gui_update_queue and not self._gui_update_scheduled:
                self._gui_update_scheduled = True
                self.after(50, self._process_gui_updates)

        # 定期检查内存使用情况和队列清理
        self._check_memory_usage()
        self._auto_cleanup_completed_tasks()
    
    def setup_logging(self):
        """配置日志输出到GUI，遵循Python日志最佳实践"""
        # 先添加stderr输出（确保其他模块可以正常工作）
        # 然后再移除默认处理器，避免重复输出
        try:
            # 先添加stderr处理器，确保其他模块（如doclayout_yolo）可以正常工作
            logger.add(
                sys.stderr,
                level="INFO",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
                enqueue=True,
                backtrace=True,
                diagnose=True
            )
            # 移除默认的日志处理器（在添加stderr之后）
            logger.remove(0)  # 移除默认的handler（ID为0）
        except Exception:
            # 如果移除失败，忽略（可能没有默认处理器）
            pass
        
        # 检查log_text是否已初始化
        if not hasattr(self, 'log_text'):
            # 如果log_text还未初始化，只使用stderr输出
            return
        
        # 创建一个自定义sink，将日志输出到GUI
        # 注意：sink函数不能返回None，必须是一个可调用对象
        def gui_log_sink(message):
            """将loguru日志输出到GUI
            
            Args:
                message: loguru的LogRecord对象或已格式化的字符串
            """
            try:
                # 检查log_text是否可用
                if not hasattr(self, 'log_text') or self.log_text is None:
                    # 如果log_text不可用，输出到stderr
                    if isinstance(message, str):
                        sys.stderr.write(f"{message}\n")
                    else:
                        try:
                            record = message.record
                            sys.stderr.write(f"[{record['level'].name}] {record['message']}\n")
                        except Exception:
                            sys.stderr.write(f"{str(message)}\n")
                    sys.stderr.flush()
                    return  # 明确返回None（这是允许的）
                
                # loguru的sink接收的是已格式化的字符串（如果指定了format）
                # 或者LogRecord对象（如果没有指定format）
                if isinstance(message, str):
                    log_message = message
                else:
                    # 如果是LogRecord对象，提取消息
                    try:
                        record = message.record
                        log_message = f"[{record['level'].name}] {record['message']}"
                    except Exception:
                        log_message = str(message)
                
                # 输出到GUI（使用after确保在主线程中执行）
                # 使用lambda捕获当前log_message值，避免闭包问题
                def log_to_gui(msg=log_message):
                    try:
                        if hasattr(self, 'log') and callable(getattr(self, 'log', None)):
                            self.log(msg, switch_to_log=True)
                        else:
                            # 如果log方法不可用，输出到stderr
                            sys.stderr.write(f"{msg}\n")
                            sys.stderr.flush()
                    except Exception:
                        # 如果GUI日志失败，输出到stderr
                        try:
                            sys.stderr.write(f"{msg}\n")
                            sys.stderr.flush()
                        except Exception:
                            pass
                
                # 确保self.after可用
                if hasattr(self, 'after') and callable(getattr(self, 'after', None)):
                    try:
                        self.after(0, log_to_gui)
                    except Exception:
                        # 如果after调用失败，直接调用
                        log_to_gui()
                else:
                    # 如果after不可用，直接调用
                    log_to_gui()
            except Exception:
                # 如果GUI日志失败，至少输出到stderr
                try:
                    error_msg = str(message) if not isinstance(message, str) else message
                    sys.stderr.write(f"日志输出到GUI失败: {error_msg}\n")
                    sys.stderr.flush()
                except Exception:
                    pass  # 如果连stderr都失败，忽略
        
        # 添加GUI日志处理器，只记录INFO及以上级别
        try:
            logger.add(
                gui_log_sink,
                level="INFO",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
                enqueue=True,  # 使用队列确保线程安全
                catch=True  # 捕获异常，避免日志系统本身出错
            )
        except Exception:
            # 如果添加GUI sink失败，至少添加stderr输出
            logger.add(
                sys.stderr,
                level="INFO",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
                enqueue=True
            )
        
        # 对于ERROR及以上级别，同时输出到stderr（用于调试和故障排查）
        try:
            logger.add(
                sys.stderr,
                level="ERROR",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
                enqueue=True
            )
        except Exception:
            pass  # 如果添加失败，忽略（可能已经添加过了）
    
    def create_widgets(self):
        """创建所有界面组件 - 优化布局"""
        # 主容器 - 使用网格布局
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 标题栏
        title_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="MinerU PDF转Markdown",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side="left")
        
        # 关于按钮
        about_btn = ctk.CTkButton(
            title_frame,
            text="ℹ️ 关于",
            command=self.show_about,
            width=80,
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40")
        )
        about_btn.pack(side="right", padx=5)
        
        # 使用TabView进行分组
        self.tabview = ctk.CTkTabview(main_container)
        self.tabview.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tab 1: 基本设置
        self.tab_basic = self.tabview.add("📋 基本设置")
        self.create_basic_tab()
        
        # Tab 2: 任务队列
        self.tab_queue = self.tabview.add("📋 任务队列")
        self.create_queue_tab()
        
        # Tab 3: 高级选项
        self.tab_advanced = self.tabview.add("⚙️ 高级选项")
        self.create_advanced_tab()
        
        # Tab 4: 日志输出
        self.tab_log = self.tabview.add("📝 转换日志")
        self.create_log_tab()
        
        # 底部控制栏（固定在底部）
        self.create_control_bar(main_container)
    
    def create_basic_tab(self):
        """创建基本设置Tab"""
        # 使用滚动框架
        scroll_frame = ctk.CTkScrollableFrame(self.tab_basic)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 文件选择区域
        file_group = ctk.CTkFrame(scroll_frame)
        file_group.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            file_group,
            text="📄 输入文件",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        file_row = ctk.CTkFrame(file_group, fg_color="transparent")
        file_row.pack(fill="x", padx=15, pady=(0, 15))
        
        # 文件选择按钮
        select_file_btn = ctk.CTkButton(
            file_row,
            text="选择单个文件",
            command=self.select_single_file,
            width=120,
            height=35
        )
        select_file_btn.pack(side="left", padx=(0, 10))
        
        select_multiple_btn = ctk.CTkButton(
            file_row,
            text="选择多个文件",
            command=self.select_multiple_files,
            width=120,
            height=35
        )
        select_multiple_btn.pack(side="left", padx=(0, 10))
        
        select_folder_btn = ctk.CTkButton(
            file_row,
            text="选择文件夹",
            command=self.select_folder,
            width=120,
            height=35
        )
        select_folder_btn.pack(side="left")
        
        # 已选文件列表显示
        files_info_frame = ctk.CTkFrame(file_group)
        files_info_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkLabel(
            files_info_frame,
            text="已选择文件:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # 文件统计信息
        self.files_info_var = ctk.StringVar(value="未选择文件")
        files_info_label = ctk.CTkLabel(
            files_info_frame,
            textvariable=self.files_info_var,
            font=ctk.CTkFont(size=11),
            anchor="w",
            text_color=("gray70", "gray50")
        )
        files_info_label.pack(anchor="w", padx=10, pady=(0, 5))

        # 文件列表显示区域（使用滚动框架）
        self.files_scroll_frame = ctk.CTkScrollableFrame(files_info_frame, height=200)
        self.files_scroll_frame.pack(fill="x", padx=10, pady=(0, 10))

        # 分页控制（仅在文件数量超过限制时显示）
        self.files_pagination_frame = ctk.CTkFrame(files_info_frame, fg_color="transparent")
        self.files_pagination_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.files_page_info_var = ctk.StringVar(value="")
        self.files_page_info_label = ctk.CTkLabel(
            self.files_pagination_frame,
            textvariable=self.files_page_info_var,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        self.files_page_info_label.pack(side="left", padx=5)

        self.files_prev_page_btn = ctk.CTkButton(
            self.files_pagination_frame,
            text="◀ 上一页",
            command=self.files_prev_page,
            width=80,
            height=25,
            font=ctk.CTkFont(size=10),
            state="disabled"
        )
        self.files_prev_page_btn.pack(side="left", padx=2)

        self.files_next_page_btn = ctk.CTkButton(
            self.files_pagination_frame,
            text="下一页 ▶",
            command=self.files_next_page,
            width=80,
            height=25,
            font=ctk.CTkFont(size=10),
            state="disabled"
        )
        self.files_next_page_btn.pack(side="left", padx=2)

        # 初始化文件显示
        self.update_files_display()
        
        # 输出目录区域
        output_group = ctk.CTkFrame(scroll_frame)
        output_group.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            output_group,
            text="📁 输出目录",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        output_row = ctk.CTkFrame(output_group, fg_color="transparent")
        output_row.pack(fill="x", padx=15, pady=(0, 15))
        
        self.output_path_var = ctk.StringVar(value=str(Path.cwd() / "output"))
        output_entry = ctk.CTkEntry(
            output_row,
            textvariable=self.output_path_var,
            height=35
        )
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        select_dir_btn = ctk.CTkButton(
            output_row,
            text="选择目录",
            command=self.select_output_dir,
            width=100,
            height=35
        )
        select_dir_btn.pack(side="right")
        
        # 转换配置区域
        config_group = ctk.CTkFrame(scroll_frame)
        config_group.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            config_group,
            text="⚙️ 转换配置",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # 配置选项网格布局
        config_grid = ctk.CTkFrame(config_group, fg_color="transparent")
        config_grid.pack(fill="x", padx=15, pady=(0, 15))
        
        # 第一行：后端
        row1 = ctk.CTkFrame(config_grid, fg_color="transparent")
        row1.pack(fill="x", pady=5)
        
        ctk.CTkLabel(row1, text="后端:", width=100, anchor="w").pack(side="left", padx=5)
        self.backend_var = ctk.StringVar(value="pipeline")
        backend_menu = ctk.CTkOptionMenu(
            row1,
            values=BACKENDS,
            variable=self.backend_var,
            command=self.on_backend_change,
            width=200
        )
        backend_menu.pack(side="left", padx=5)
        
        # 第二行：语言
        row2 = ctk.CTkFrame(config_grid, fg_color="transparent")
        row2.pack(fill="x", pady=5)
        
        ctk.CTkLabel(row2, text="语言:", width=100, anchor="w").pack(side="left", padx=5)
        self.lang_var = ctk.StringVar(value="ch")
        # 使用带说明的显示名称
        lang_display_values = [LANGUAGES_DISPLAY.get(lang, lang) for lang in LANGUAGES]
        lang_menu = ctk.CTkOptionMenu(
            row2,
            values=lang_display_values,
            variable=self.lang_var,
            width=350,
            command=self.on_lang_change
        )
        # 设置初始显示值
        self.lang_var.set(LANGUAGES_DISPLAY.get("ch", "ch"))
        lang_menu.pack(side="left", padx=5)
        
        # 语言说明
        lang_hint = ctk.CTkLabel(
            config_grid,
            text="💡 语言说明: 选择PDF文档的主要语言以提高识别准确率。推荐设置：中文文档选 ch，英文文档选 en，不确定时选 ch（默认）",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50"),
            anchor="w",
            justify="left"
        )
        lang_hint.pack(anchor="w", padx=15, pady=(0, 5))
        
        # 第三行：解析方法
        row3 = ctk.CTkFrame(config_grid, fg_color="transparent")
        row3.pack(fill="x", pady=5)
        
        ctk.CTkLabel(row3, text="解析方法:", width=100, anchor="w").pack(side="left", padx=5)
        self.method_var = ctk.StringVar(value="auto")
        # 使用带说明的显示名称
        method_display_values = [
            'auto (自动选择，推荐)',
            'txt (文本提取，适合可复制文本的PDF)',
            'ocr (OCR识别，适合扫描版PDF)'
        ]
        method_menu = ctk.CTkOptionMenu(
            row3,
            values=method_display_values,
            variable=self.method_var,
            width=450,
            command=self.on_method_change
        )
        # 设置初始显示值
        self.method_var.set('auto (自动选择，推荐)')
        method_menu.pack(side="left", padx=5)
        
        # 解析方法说明
        method_hint_frame = ctk.CTkFrame(config_grid, fg_color="transparent")
        method_hint_frame.pack(anchor="w", padx=15, pady=(0, 10), fill="x")
        
        method_hint_title = ctk.CTkLabel(
            method_hint_frame,
            text="💡 解析方法说明:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray50", "gray50"),
            anchor="w"
        )
        method_hint_title.pack(anchor="w", pady=(0, 2))
        
        method_hint_content = ctk.CTkLabel(
            method_hint_frame,
            text="   • auto (自动，推荐): 程序自动判断PDF类型，选择最佳解析方式\n   • txt (文本提取): 适合可复制文本的PDF，速度快\n   • ocr (OCR识别): 适合扫描版PDF或图片PDF，速度较慢但准确",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50"),
            anchor="w",
            justify="left"
        )
        method_hint_content.pack(anchor="w", padx=(20, 0))
        
        # 功能开关
        switch_frame = ctk.CTkFrame(config_grid, fg_color="transparent")
        switch_frame.pack(fill="x", pady=10)
        
        self.formula_var = ctk.BooleanVar(value=True)
        formula_check = ctk.CTkCheckBox(
            switch_frame,
            text="启用公式识别",
            variable=self.formula_var
        )
        formula_check.pack(side="left", padx=10)
        
        self.table_var = ctk.BooleanVar(value=True)
        table_check = ctk.CTkCheckBox(
            switch_frame,
            text="启用表格识别",
            variable=self.table_var
        )
        table_check.pack(side="left", padx=10)
    
    def create_queue_tab(self):
        """创建任务队列Tab"""
        queue_frame = ctk.CTkFrame(self.tab_queue)
        queue_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 队列控制按钮
        control_frame = ctk.CTkFrame(queue_frame, fg_color="transparent")
        control_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            control_frame,
            text="📋 任务队列",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
        
        button_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        button_frame.pack(side="right")
        
        clear_queue_btn = ctk.CTkButton(
            button_frame,
            text="清空队列",
            command=self.clear_queue,
            width=100,
            height=30
        )
        clear_queue_btn.pack(side="left", padx=5)
        
        # 任务列表（使用滚动框架）
        self.queue_scroll_frame = ctk.CTkScrollableFrame(queue_frame)
        self.queue_scroll_frame.pack(fill="both", expand=True)
        
        # 队列信息标签和分页控制
        info_frame = ctk.CTkFrame(queue_frame, fg_color="transparent")
        info_frame.pack(fill="x", pady=10)
        
        self.queue_info_var = ctk.StringVar(value="队列为空")
        queue_info_label = ctk.CTkLabel(
            info_frame,
            textvariable=self.queue_info_var,
            font=ctk.CTkFont(size=12)
        )
        queue_info_label.pack(side="left", padx=10)
        
        # 分页控制（仅在任务数量超过限制时显示）
        self.pagination_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        self.pagination_frame.pack(side="right", padx=10)
        
        self.page_info_var = ctk.StringVar(value="")
        self.page_info_label = ctk.CTkLabel(
            self.pagination_frame,
            textvariable=self.page_info_var,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        self.page_info_label.pack(side="left", padx=5)
        
        self.prev_page_btn = ctk.CTkButton(
            self.pagination_frame,
            text="◀ 上一页",
            command=self.prev_page,
            width=80,
            height=25,
            font=ctk.CTkFont(size=10),
            state="disabled"
        )
        self.prev_page_btn.pack(side="left", padx=2)
        
        self.next_page_btn = ctk.CTkButton(
            self.pagination_frame,
            text="下一页 ▶",
            command=self.next_page,
            width=80,
            height=25,
            font=ctk.CTkFont(size=10),
            state="disabled"
        )
        self.next_page_btn.pack(side="left", padx=2)
        
        # 初始化队列显示
        self.update_queue_display()
    
    def create_advanced_tab(self):
        """创建高级选项Tab"""
        scroll_frame = ctk.CTkScrollableFrame(self.tab_advanced)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 页码范围
        page_group = ctk.CTkFrame(scroll_frame)
        page_group.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            page_group,
            text="📄 页码范围",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        page_row = ctk.CTkFrame(page_group, fg_color="transparent")
        page_row.pack(fill="x", padx=15, pady=(0, 15))
        
        ctk.CTkLabel(page_row, text="起始页码:", width=100, anchor="w").pack(side="left", padx=5)
        self.start_page_var = ctk.StringVar(value="0")
        start_page_entry = ctk.CTkEntry(
            page_row,
            textvariable=self.start_page_var,
            width=150
        )
        start_page_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(page_row, text="结束页码:", width=100, anchor="w").pack(side="left", padx=5)
        self.end_page_var = ctk.StringVar(value="")
        end_page_entry = ctk.CTkEntry(
            page_row,
            textvariable=self.end_page_var,
            width=150,
            placeholder_text="留空表示到末尾"
        )
        end_page_entry.pack(side="left", padx=5)
        
        # 设备配置
        device_group = ctk.CTkFrame(scroll_frame)
        device_group.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            device_group,
            text="💻 设备配置",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        device_content = ctk.CTkFrame(device_group, fg_color="transparent")
        device_content.pack(fill="x", padx=15, pady=(0, 10))
        
        # 强制使用CPU选项
        self.force_cpu_var = ctk.BooleanVar(value=False)
        force_cpu_check = ctk.CTkCheckBox(
            device_content,
            text="强制使用CPU（纯CPU环境）",
            variable=self.force_cpu_var,
            command=self.on_force_cpu_change
        )
        force_cpu_check.pack(anchor="w", pady=5)
        
        # 设备模式输入
        device_row = ctk.CTkFrame(device_content, fg_color="transparent")
        device_row.pack(fill="x", pady=5)
        
        ctk.CTkLabel(device_row, text="设备模式:", width=100, anchor="w").pack(side="left", padx=5)
        self.device_var = ctk.StringVar(value="")
        self.device_entry = ctk.CTkEntry(
            device_row,
            textvariable=self.device_var,
            placeholder_text="如: cpu, cuda, cuda:0, mps (留空自动检测)",
            state="normal"
        )
        self.device_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        # CPU模式提示
        cpu_hint = ctk.CTkLabel(
            device_content,
            text="💡 提示: MinerU完全支持纯CPU运行，CPU模式下转换速度较慢但功能完整",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50"),
            anchor="w"
        )
        cpu_hint.pack(anchor="w", pady=(5, 15))

        # 性能设置
        perf_group = ctk.CTkFrame(scroll_frame)
        perf_group.pack(fill="x", pady=5)

        ctk.CTkLabel(
            perf_group,
            text="⚡ 性能设置",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        perf_content = ctk.CTkFrame(perf_group, fg_color="transparent")
        perf_content.pack(fill="x", padx=15, pady=(0, 10))

        # 最大队列大小设置
        queue_row = ctk.CTkFrame(perf_content, fg_color="transparent")
        queue_row.pack(fill="x", pady=5)

        ctk.CTkLabel(queue_row, text="最大队列大小:", width=120, anchor="w").pack(side="left", padx=5)
        self.max_queue_size_var = ctk.IntVar(value=2000)
        self.max_queue_entry = ctk.CTkEntry(
            queue_row,
            textvariable=self.max_queue_size_var,
            placeholder_text="2000",
            width=100
        )
        self.max_queue_entry.pack(side="left", padx=5)

        ctk.CTkLabel(queue_row, text="(任务数量上限，建议500-5000)", anchor="w").pack(side="left", padx=5)

        # 自动清理设置
        cleanup_row = ctk.CTkFrame(perf_content, fg_color="transparent")
        cleanup_row.pack(fill="x", pady=5)

        ctk.CTkLabel(cleanup_row, text="保留已完成任务:", width=120, anchor="w").pack(side="left", padx=5)
        self.keep_completed_var = ctk.IntVar(value=500)
        self.keep_completed_entry = ctk.CTkEntry(
            cleanup_row,
            textvariable=self.keep_completed_var,
            placeholder_text="500",
            width=100
        )
        self.keep_completed_entry.pack(side="left", padx=5)

        ctk.CTkLabel(cleanup_row, text="(自动清理旧任务，建议200-1000)", anchor="w").pack(side="left", padx=5)

        # 内存监控设置
        memory_row = ctk.CTkFrame(perf_content, fg_color="transparent")
        memory_row.pack(fill="x", pady=5)

        self.enable_memory_monitor_var = ctk.BooleanVar(value=True)
        memory_monitor_check = ctk.CTkCheckBox(
            memory_row,
            text="启用内存监控",
            variable=self.enable_memory_monitor_var
        )
        memory_monitor_check.pack(side="left", padx=5)

        ctk.CTkLabel(memory_row, text="(自动检测和清理内存泄露)", anchor="w").pack(side="left", padx=5)

        # 性能提示
        perf_hint = ctk.CTkLabel(
            perf_content,
            text="💡 大量文件处理建议: 队列大小2000，保留任务500，启用内存监控\n"
                 "   处理大量文件时会自动进行分页显示和内存清理，避免界面卡顿",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50"),
            anchor="w"
        )
        perf_hint.pack(anchor="w", pady=(10, 15))
        
        # 其他提示
        tips_group = ctk.CTkFrame(scroll_frame)
        tips_group.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            tips_group,
            text="💡 使用提示",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        tips_content = ctk.CTkFrame(tips_group, fg_color="transparent")
        tips_content.pack(fill="x", padx=15, pady=(0, 15))
        
        tips_text = """
• 页码从0开始计数（第一页为0）
• 留空结束页码表示转换到文件末尾
• 设备模式留空会自动检测（优先使用GPU，无GPU时使用CPU）
• 强制使用CPU选项会覆盖设备模式设置
• 推荐使用pipeline后端，功能最全面
        """
        tips_label = ctk.CTkLabel(
            tips_content,
            text=tips_text.strip(),
            font=ctk.CTkFont(size=12),
            text_color=("gray70", "gray70"),
            justify="left",
            anchor="w"
        )
        tips_label.pack(anchor="w", padx=5)
    
    def create_log_tab(self):
        """创建日志输出Tab"""
        log_frame = ctk.CTkFrame(self.tab_log)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            log_frame,
            text="📋 转换日志",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # 日志文本框
        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
    
    def create_control_bar(self, parent):
        """创建底部控制栏"""
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="x", pady=(10, 0))
        
        # 左侧：进度条和状态
        left_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="x", expand=True, padx=15, pady=10)
        
        # 进度条
        self.progress_var = ctk.DoubleVar(value=0.0)
        self.progress_bar = ctk.CTkProgressBar(
            left_frame,
            variable=self.progress_var,
            width=400
        )
        self.progress_bar.pack(side="left", padx=(0, 10))
        
        # 状态标签
        self.status_var = ctk.StringVar(value="就绪")
        status_label = ctk.CTkLabel(
            left_frame,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=12)
        )
        status_label.pack(side="left")
        
        # 右侧：控制按钮
        right_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        right_frame.pack(side="right", padx=15, pady=10)
        
        self.add_to_queue_btn = ctk.CTkButton(
            right_frame,
            text="➕ 添加到队列",
            command=self.add_files_to_queue,
            width=120,
            height=36,
            font=ctk.CTkFont(size=14),
            fg_color=("#10B981", "#059669"),
            hover_color=("#059669", "#047857")
        )
        self.add_to_queue_btn.pack(side="left", padx=5)
        
        self.convert_btn = ctk.CTkButton(
            right_frame,
            text="🚀 开始处理",
            command=self.start_queue_processing,
            width=120,
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#3B82F6", "#2563EB"),
            hover_color=("#2563EB", "#1D4ED8")
        )
        self.convert_btn.pack(side="left", padx=5)
        
        self.cancel_btn = ctk.CTkButton(
            right_frame,
            text="❌ 取消",
            command=self.cancel_conversion,
            width=100,
            height=36,
            font=ctk.CTkFont(size=14),
            fg_color=("#EF4444", "#DC2626"),
            hover_color=("#DC2626", "#B91C1C"),
            state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=5)
    
    def on_backend_change(self, value):
        """后端改变时的回调"""
        pass  # 本地运行，无需特殊处理
    
    def on_lang_change(self, value):
        """语言改变时的回调，将显示名称转换为代码"""
        # 从显示名称中提取语言代码
        for lang_code, display_name in LANGUAGES_DISPLAY.items():
            if value == display_name:
                # 保持显示名称，但实际使用代码
                break
    
    def on_method_change(self, value):
        """解析方法改变时的回调"""
        # 保持显示名称在UI中，实际使用时提取代码
        pass
    
    def on_force_cpu_change(self):
        """强制使用CPU选项改变时的回调"""
        if self.force_cpu_var.get():
            self.device_var.set("cpu")
            self.device_entry.configure(state="disabled")
        else:
            self.device_var.set("")
            self.device_entry.configure(state="normal")
    
    def select_single_file(self):
        """选择单个PDF文件"""
        try:
            file_path = filedialog.askopenfilename(
                title="选择PDF文件",
                filetypes=[
                    ("PDF文件", "*.pdf"),
                    ("图片文件", "*.png *.jpg *.jpeg"),
                    ("所有文件", "*.*")
                ]
            )
            if file_path:
                file_path_obj = Path(file_path)
                
                # 验证文件
                if not file_path_obj.exists():
                    error_msg = MinerUErrorHandler.format_error_message(
                        FileNotFoundError(f"文件不存在: {file_path}"),
                        context="选择文件"
                    )
                    self.log(f"❌ {error_msg}", switch_to_log=True)
                    return
                
                # 检查文件大小
                try:
                    file_size = file_path_obj.stat().st_size
                    if file_size == 0:
                        self.log(f"⚠️ 警告: 文件为空: {file_path}", switch_to_log=False)
                    elif file_size > 500 * 1024 * 1024:  # 500MB
                        self.log(f"⚠️ 警告: 文件较大 ({file_size / 1024 / 1024:.1f}MB)，处理可能需要较长时间", switch_to_log=False)
                except Exception as e:
                    logger.warning(f"检查文件大小时出错: {e}")
                
                self.selected_file_paths = [file_path_obj]
                self.file_display_start = 0  # 重置分页
                self.update_files_display()
                # 选择文件后不切换Tab，保持在当前界面
                self.log(f"✅ 已选择文件: {file_path}", switch_to_log=False)
        except Exception as e:
            error_handler = MinerUErrorHandler()
            formatted_msg = error_handler.format_error_message(e, context="选择文件")
            self.log(f"❌ {formatted_msg}", switch_to_log=True)
            logger.exception("选择文件时出错")
    
    def select_multiple_files(self):
        """选择多个PDF文件"""
        try:
            file_paths = filedialog.askopenfilenames(
                title="选择多个PDF文件",
                filetypes=[
                    ("PDF文件", "*.pdf"),
                    ("图片文件", "*.png *.jpg *.jpeg"),
                    ("所有文件", "*.*")
                ]
            )
            if file_paths:
                valid_paths = []
                invalid_count = 0
                
                for fp in file_paths:
                    try:
                        file_path_obj = Path(fp)
                        if not file_path_obj.exists():
                            invalid_count += 1
                            logger.warning(f"文件不存在: {fp}")
                            continue
                        valid_paths.append(file_path_obj)
                    except Exception as e:
                        invalid_count += 1
                        logger.warning(f"处理文件路径时出错 {fp}: {e}")
                
                if invalid_count > 0:
                    self.log(f"⚠️ 警告: {invalid_count} 个文件无效或不存在，已忽略", switch_to_log=False)
                
                if valid_paths:
                    self.selected_file_paths = valid_paths
                    self.file_display_start = 0  # 重置分页
                    self.update_files_display()
                    # 选择多文件后，提示用户添加到队列，不切换Tab
                    self.log(f"✅ 已选择 {len(valid_paths)} 个有效文件，请点击「添加到队列」按钮", switch_to_log=False)
                    # 自动切换到基本设置Tab，方便用户看到已选文件
                    try:
                        self.tabview.set("📋 基本设置")
                    except Exception:
                        pass  # 如果Tab切换失败，忽略
                else:
                    self.log("❌ 错误: 没有有效的文件被选择", switch_to_log=True)
        except Exception as e:
            error_handler = MinerUErrorHandler()
            formatted_msg = error_handler.format_error_message(e, context="选择多个文件")
            self.log(f"❌ {formatted_msg}", switch_to_log=True)
            logger.exception("选择多个文件时出错")
    
    def select_folder(self):
        """选择文件夹"""
        try:
            dir_path = filedialog.askdirectory(title="选择包含PDF文件的文件夹")
            if dir_path:
                folder_path = Path(dir_path)
                
                # 验证文件夹是否存在
                if not folder_path.exists():
                    error_msg = MinerUErrorHandler.format_error_message(
                        FileNotFoundError(f"文件夹不存在: {dir_path}"),
                        context="选择文件夹"
                    )
                    self.log(f"❌ {error_msg}", switch_to_log=True)
                    return
                
                # 验证是否有读取权限
                if not os.access(folder_path, os.R_OK):
                    error_msg = MinerUErrorHandler.format_error_message(
                        PermissionError(f"没有读取权限: {dir_path}"),
                        context="选择文件夹"
                    )
                    self.log(f"❌ {error_msg}", switch_to_log=True)
                    return
                
                try:
                    pdf_files = list(folder_path.glob("*.pdf"))
                    if pdf_files:
                        self.selected_file_paths = pdf_files
                        self.file_display_start = 0  # 重置分页
                        self.update_files_display()
                        # 选择文件夹后，提示用户添加到队列，不切换Tab
                        self.log(f"✅ 从文件夹选择了 {len(pdf_files)} 个PDF文件，请点击「添加到队列」按钮", switch_to_log=False)
                        # 保持在基本设置Tab
                        try:
                            self.tabview.set("📋 基本设置")
                        except Exception:
                            pass  # 如果Tab切换失败，忽略
                    else:
                        self.log(f"ℹ️ 文件夹中没有找到PDF文件: {dir_path}", switch_to_log=False)
                except Exception as e:
                    error_handler = MinerUErrorHandler()
                    formatted_msg = error_handler.format_error_message(e, context="扫描文件夹")
                    self.log(f"❌ 扫描文件夹时出错: {formatted_msg}", switch_to_log=True)
                    logger.exception(f"扫描文件夹时出错: {dir_path}")
        except Exception as e:
            error_handler = MinerUErrorHandler()
            formatted_msg = error_handler.format_error_message(e, context="选择文件夹")
            self.log(f"❌ {formatted_msg}", switch_to_log=True)
            logger.exception("选择文件夹时出错")
    
    def select_output_dir(self):
        """选择输出目录"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_path_var.set(dir_path)
            # 选择输出目录后不切换Tab
            self.log(f"输出目录: {dir_path}", switch_to_log=False)
    
    def add_files_to_queue(self):
        """将选中的文件添加到队列"""
        try:
            if not self.selected_file_paths:
                self.log("❌ 错误: 请先选择文件", switch_to_log=True)
                return

            # 使用已存储的文件路径列表
            file_paths = self.selected_file_paths

            # 验证文件
            valid_files = []
            invalid_files = []
            
            for file_path in file_paths:
                try:
                    # 检查文件是否存在
                    if not file_path.exists():
                        invalid_files.append((file_path, "文件不存在"))
                        continue
                    
                    # 检查文件扩展名
                    if file_path.suffix.lower() not in ['.pdf', '.png', '.jpg', '.jpeg']:
                        invalid_files.append((file_path, f"不支持的文件类型: {file_path.suffix}"))
                        continue
                    
                    # 检查文件大小（防止添加过大或空文件）
                    try:
                        file_size = file_path.stat().st_size
                        if file_size == 0:
                            invalid_files.append((file_path, "文件为空"))
                            continue
                        # 文件太大也允许，但会警告
                        if file_size > 1000 * 1024 * 1024:  # 1GB
                            logger.warning(f"文件较大 ({file_size / 1024 / 1024:.1f}MB): {file_path}")
                    except Exception as e:
                        logger.warning(f"检查文件大小时出错 {file_path}: {e}")
                    
                    # 检查文件是否可读
                    if not os.access(file_path, os.R_OK):
                        invalid_files.append((file_path, "没有读取权限"))
                        continue
                    
                    valid_files.append(file_path)
                except Exception as e:
                    invalid_files.append((file_path, f"验证失败: {str(e)}"))
                    logger.warning(f"验证文件时出错 {file_path}: {e}")
            
            # 报告无效文件
            if invalid_files:
                invalid_count = len(invalid_files)
                self.log(f"⚠️ 警告: {invalid_count} 个文件无效，已跳过", switch_to_log=False)
                if invalid_count <= 5:  # 只显示前5个无效文件的详情
                    for invalid_file, reason in invalid_files[:5]:
                        self.log(f"   - {invalid_file.name}: {reason}", switch_to_log=False)
                else:
                    for invalid_file, reason in invalid_files[:5]:
                        self.log(f"   - {invalid_file.name}: {reason}", switch_to_log=False)
                    self.log(f"   ... 还有 {invalid_count - 5} 个无效文件", switch_to_log=False)
            
            if not valid_files:
                self.log("❌ 错误: 没有有效的文件可以添加到队列", switch_to_log=True)
                if invalid_files:
                    error_handler = MinerUErrorHandler()
                    sample_error = invalid_files[0][1]
                    self.log(f"   原因: {sample_error}", switch_to_log=True)
                return
            
            # 添加到队列（分批处理，避免一次性创建过多组件）
            added_count = 0
            invalid_count = len(invalid_files) if invalid_files else 0
            
            with self.queue_lock:
                batch_size = 100  # 每批最多添加100个文件

                # 使用UI设置的最大队列大小
                max_queue_size = self.max_queue_size_var.get() if hasattr(self, 'max_queue_size_var') else 2000

                # 检查当前队列大小
                current_queue_size = len(self.task_queue)
                if current_queue_size >= max_queue_size:
                    self.log(f"⚠️ 队列已满（最多{max_queue_size}个任务），无法添加新文件", switch_to_log=False)
                    return

                # 计算可以添加的最大文件数
                available_slots = max_queue_size - current_queue_size
                files_to_add = min(len(valid_files), available_slots)

                if files_to_add < len(valid_files):
                    self.log(f"⚠️ 队列空间不足，只添加前{files_to_add}个文件", switch_to_log=False)

                actual_files = valid_files[:files_to_add]

                for i in range(0, len(actual_files), batch_size):
                    batch = actual_files[i:i + batch_size]
                    for file_path in batch:
                        task = ConversionTask(
                            file_path=file_path,
                            file_name=file_path.stem
                        )
                        self.task_queue.append(task)
                        added_count += 1

                    # 每批处理完后短暂暂停，避免阻塞UI
                    if i + batch_size < len(actual_files):
                        self.after(10)  # 短暂让出控制权

            # 只有在添加的文件数量较少时才立即更新显示
            if len(valid_files) <= 50:
                self.update_queue_display()
            else:
                # 对于大量文件，只更新队列信息，不重新创建组件
                self._update_queue_info_only()

            try:
                self.tabview.set("📋 任务队列")
            except Exception:
                pass  # 如果Tab切换失败，忽略

            # 显示成功消息
            if invalid_count > 0:
                self.log(f"✅ 已添加 {added_count} 个文件到队列（已跳过 {invalid_count} 个无效文件）", switch_to_log=False)
            else:
                self.log(f"✅ 已添加 {added_count} 个文件到队列", switch_to_log=False)
        
        except Exception as e:
            error_handler = MinerUErrorHandler()
            formatted_msg = error_handler.format_error_message(e, context="添加文件到队列")
            self.log(f"❌ {formatted_msg}", switch_to_log=True)
            logger.exception("添加文件到队列时出错")

        # 如果添加了大量文件，给出提示
        if len(valid_files) > 200:
            self.log("💡 已添加大量文件，为避免界面卡顿，仅显示部分任务。请使用分页查看。", switch_to_log=False)
    
    def clear_queue(self):
        """清空任务队列"""
        with self.queue_lock:
            if self.is_converting:
                self.log("⚠️ 警告: 正在处理中，无法清空队列", switch_to_log=False)
                return

            queue_size = len(self.task_queue)

            # 分批清理，避免一次性操作过多任务
            if queue_size > 100:
                self.log(f"正在清理 {queue_size} 个任务...", switch_to_log=False)

            self.task_queue.clear()
            self.current_task_index = -1
            self.task_display_start = 0  # 重置分页

        # 清理相关的组件缓存
        self._cleanup_task_widgets()

        # 强制垃圾回收
        import gc
        gc.collect()

        self.log("✅ 队列已清空", switch_to_log=False)
        self.update_queue_display()
        # 保持在任务队列Tab
    
    def update_queue_display(self):
        """更新队列显示（使用延迟更新避免频繁刷新）"""
        # 如果已有待处理的更新，取消它
        if self.queue_update_id is not None:
            self.after_cancel(self.queue_update_id)
        
        # 延迟更新，避免过于频繁的刷新
        self.queue_update_id = self.after(100, self._do_update_queue_display)
    
    def _do_update_queue_display(self):
        """实际执行队列显示更新（优化版：支持虚拟滚动/分页）"""
        try:
            # 安全地清空现有显示
            try:
                children = list(self.queue_scroll_frame.winfo_children())
                for widget in children:
                    try:
                        if widget.winfo_exists():
                            widget.destroy()
                    except Exception:
                        pass  # 忽略已销毁的组件错误
            except Exception:
                pass  # 忽略清空时的错误
            
            with self.queue_lock:
                queue_size = len(self.task_queue)
                
                if queue_size == 0:
                    self.queue_info_var.set("队列为空")
                    self.page_info_var.set("")
                    self.prev_page_btn.configure(state="disabled")
                    self.next_page_btn.configure(state="disabled")
                    try:
                        empty_label = ctk.CTkLabel(
                            self.queue_scroll_frame,
                            text="队列为空，请先添加文件",
                            font=ctk.CTkFont(size=14),
                            text_color=("gray50", "gray50")
                        )
                        empty_label.pack(pady=20)
                    except Exception:
                        pass
                else:
                    pending, processing, completed, failed = self._calculate_queue_stats()
                    
                    self.queue_info_var.set(
                        f"队列: {queue_size} 个任务 | "
                        f"等待: {pending} | "
                        f"处理中: {processing} | "
                        f"完成: {completed} | "
                        f"失败: {failed}"
                    )
                    
                    # 优化：如果任务数量超过限制，使用分页显示
                    if queue_size > self.max_visible_tasks:
                        # 计算分页信息
                        total_pages = (queue_size + self.max_visible_tasks - 1) // self.max_visible_tasks
                        current_page = (self.task_display_start // self.max_visible_tasks) + 1
                        
                        # 确保起始索引有效
                        if self.task_display_start >= queue_size:
                            self.task_display_start = max(0, queue_size - self.max_visible_tasks)
                        if self.task_display_start < 0:
                            self.task_display_start = 0
                        
                        # 计算显示范围
                        display_end = min(self.task_display_start + self.max_visible_tasks, queue_size)
                        display_tasks = self.task_queue[self.task_display_start:display_end]
                        
                        # 更新分页信息
                        self.page_info_var.set(f"显示 {self.task_display_start + 1}-{display_end} / {queue_size} (第 {current_page}/{total_pages} 页)")
                        self.prev_page_btn.configure(state="normal" if self.task_display_start > 0 else "disabled")
                        self.next_page_btn.configure(state="normal" if display_end < queue_size else "disabled")
                        
                        # 显示提示信息
                        try:
                            hint_label = ctk.CTkLabel(
                                self.queue_scroll_frame,
                                text="💡 任务数量较多，仅显示部分任务。使用分页按钮查看更多。",
                                font=ctk.CTkFont(size=11),
                                text_color=("gray50", "gray50"),
                                anchor="w"
                            )
                            hint_label.pack(fill="x", padx=10, pady=5)
                        except Exception:
                            pass
                        
                        # 显示范围内的任务
                        for local_idx, task in enumerate(display_tasks):
                            global_idx = self.task_display_start + local_idx
                            try:
                                self.create_task_widget(global_idx, task)
                            except Exception:
                                pass  # 忽略单个任务创建错误
                    else:
                        # 任务数量较少，显示所有任务
                        self.page_info_var.set("")
                        self.prev_page_btn.configure(state="disabled")
                        self.next_page_btn.configure(state="disabled")
                        
                        # 显示所有任务
                        for idx, task in enumerate(self.task_queue):
                            try:
                                self.create_task_widget(idx, task)
                            except Exception:
                                pass  # 忽略单个任务创建错误
        except Exception:
            pass  # 忽略所有更新错误，避免崩溃
        finally:
            self.queue_update_id = None
    
    def prev_page(self):
        """显示上一页任务"""
        with self.queue_lock:
            if self.task_display_start > 0:
                self.task_display_start = max(0, self.task_display_start - self.max_visible_tasks)
                self.update_queue_display()
    
    def next_page(self):
        """显示下一页任务"""
        with self.queue_lock:
            queue_size = len(self.task_queue)
            if self.task_display_start + self.max_visible_tasks < queue_size:
                self.task_display_start = min(
                    self.task_display_start + self.max_visible_tasks,
                    queue_size - self.max_visible_tasks
                )
                self.update_queue_display()
    
    def create_task_widget(self, index: int, task: ConversionTask):
        """创建任务显示组件"""
        try:
            task_frame = ctk.CTkFrame(self.queue_scroll_frame)
            task_frame.pack(fill="x", pady=5, padx=5)
            
            # 任务信息行
            info_row = ctk.CTkFrame(task_frame, fg_color="transparent")
            info_row.pack(fill="x", padx=10, pady=5)
            
            # 任务编号和文件名
            task_name_text = f"#{index + 1} {task.file_name}"
            if task.page_count > 0:
                task_name_text += f" ({task.page_count}页)"
            
            task_label = ctk.CTkLabel(
                info_row,
                text=task_name_text,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            task_label.pack(side="left", fill="x", expand=True)
            
            # 状态标签和时间信息
            status_colors = {
                TaskStatus.PENDING: ("gray", "gray"),
                TaskStatus.PROCESSING: ("blue", "blue"),
                TaskStatus.COMPLETED: ("green", "green"),
                TaskStatus.FAILED: ("red", "red"),
                TaskStatus.CANCELLED: ("orange", "orange")
            }
            
            # 状态文本
            status_text = task.status.value
            if task.status == TaskStatus.COMPLETED and task.total_time > 0:
                if task.page_count > 0:
                    status_text += f" | {task.time_per_page:.2f}秒/页"
                else:
                    status_text += f" | {task.total_time:.1f}秒"
            elif task.status == TaskStatus.PROCESSING and task.start_time:
                # 处理中时显示已用时间
                elapsed = (datetime.now() - task.start_time).total_seconds()
                if task.page_count > 0 and task.progress > 0:
                    estimated_total = elapsed / task.progress if task.progress > 0 else 0
                    estimated_per_page = estimated_total / task.page_count if task.page_count > 0 else 0
                    status_text += f" | 预计: {estimated_per_page:.2f}秒/页"
                else:
                    status_text += f" | 已用: {elapsed:.1f}秒"
            
            status_label = ctk.CTkLabel(
                info_row,
                text=status_text,
                font=ctk.CTkFont(size=11),
                text_color=status_colors.get(task.status, ("gray", "gray"))
            )
            status_label.pack(side="right", padx=10)
            
            # 进度条（仅处理中显示）
            if task.status == TaskStatus.PROCESSING:
                progress_frame = ctk.CTkFrame(task_frame, fg_color="transparent")
                progress_frame.pack(fill="x", padx=10, pady=(0, 5))
                
                try:
                    task_progress = ctk.CTkProgressBar(progress_frame)
                    task_progress.set(task.progress)
                    task_progress.pack(fill="x")
                except Exception:
                    pass  # 忽略进度条创建错误
            
            # 错误信息（失败时显示）
            if task.status == TaskStatus.FAILED and task.error_message:
                try:
                    error_label = ctk.CTkLabel(
                        task_frame,
                        text=f"错误: {task.error_message[:100]}",  # 限制长度
                        font=ctk.CTkFont(size=10),
                        text_color=("red", "red"),
                        anchor="w",
                        wraplength=800
                    )
                    error_label.pack(anchor="w", padx=10, pady=(0, 5))
                except Exception:
                    pass  # 忽略错误标签创建错误
            
            # 删除按钮（等待中或失败的任务）
            if task.status in [TaskStatus.PENDING, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                try:
                    delete_btn = ctk.CTkButton(
                        task_frame,
                        text="删除",
                        command=lambda idx=index: self.remove_task(idx),
                        width=60,
                        height=25,
                        font=ctk.CTkFont(size=10),
                        fg_color=("gray70", "gray30")
                    )
                    delete_btn.pack(side="right", padx=10, pady=5)
                except Exception:
                    pass  # 忽略删除按钮创建错误
        except Exception:
            pass  # 忽略整个任务组件创建错误
    
    def remove_task(self, index: int):
        """从队列中删除任务"""
        with self.queue_lock:
            if 0 <= index < len(self.task_queue):
                task = self.task_queue[index]
                if task.status == TaskStatus.PROCESSING:
                    self.log("⚠️ 警告: 无法删除正在处理的任务", switch_to_log=False)
                    return
                self.task_queue.pop(index)
                self.log(f"✅ 已删除任务: {task.file_name}", switch_to_log=False)

        self.update_queue_display()
        # 保持在任务队列Tab

    def update_files_display(self):
        """更新文件显示（使用虚拟翻页）"""
        try:
            # 安全地清空现有显示
            try:
                children = list(self.files_scroll_frame.winfo_children())
                for widget in children:
                    try:
                        if widget.winfo_exists():
                            widget.destroy()
                    except Exception:
                        pass  # 忽略已销毁的组件错误
            except Exception:
                pass  # 忽略清空时的错误

            files_count = len(self.selected_file_paths)

            if files_count == 0:
                self.files_info_var.set("未选择文件")
                self.files_page_info_var.set("")
                self.files_prev_page_btn.configure(state="disabled")
                self.files_next_page_btn.configure(state="disabled")
                try:
                    empty_label = ctk.CTkLabel(
                        self.files_scroll_frame,
                        text="请先选择文件",
                        font=ctk.CTkFont(size=12),
                        text_color=("gray50", "gray50")
                    )
                    empty_label.pack(pady=20)
                except Exception:
                    pass
            else:
                self.files_info_var.set(f"已选择 {files_count} 个文件")

                # 优化：如果文件数量超过限制，使用分页显示
                if files_count > self.max_visible_files:
                    # 计算分页信息
                    total_pages = (files_count + self.max_visible_files - 1) // self.max_visible_files
                    current_page = (self.file_display_start // self.max_visible_files) + 1

                    # 确保起始索引有效
                    if self.file_display_start >= files_count:
                        self.file_display_start = max(0, files_count - self.max_visible_files)
                    if self.file_display_start < 0:
                        self.file_display_start = 0

                    # 计算显示范围
                    display_end = min(self.file_display_start + self.max_visible_files, files_count)
                    display_files = self.selected_file_paths[self.file_display_start:display_end]

                    # 更新分页信息
                    self.files_page_info_var.set(f"显示 {self.file_display_start + 1}-{display_end} / {files_count} (第 {current_page}/{total_pages} 页)")
                    self.files_prev_page_btn.configure(state="normal" if self.file_display_start > 0 else "disabled")
                    self.files_next_page_btn.configure(state="normal" if display_end < files_count else "disabled")

                    # 显示提示信息
                    try:
                        hint_label = ctk.CTkLabel(
                            self.files_scroll_frame,
                            text="💡 文件数量较多，仅显示部分文件。使用分页按钮查看更多。",
                            font=ctk.CTkFont(size=10),
                            text_color=("gray50", "gray50"),
                            anchor="w"
                        )
                        hint_label.pack(fill="x", padx=5, pady=5)
                    except Exception:
                        pass

                    # 显示范围内的文件
                    for local_idx, file_path in enumerate(display_files):
                        global_idx = self.file_display_start + local_idx
                        try:
                            self.create_file_widget(global_idx, file_path)
                        except Exception:
                            pass  # 忽略单个文件创建错误
                else:
                    # 文件数量较少，显示所有文件
                    self.files_page_info_var.set("")
                    self.files_prev_page_btn.configure(state="disabled")
                    self.files_next_page_btn.configure(state="disabled")

                    # 显示所有文件
                    for idx, file_path in enumerate(self.selected_file_paths):
                        try:
                            self.create_file_widget(idx, file_path)
                        except Exception:
                            pass  # 忽略单个文件创建错误
        except Exception:
            pass  # 忽略所有更新错误，避免崩溃

    def create_file_widget(self, index: int, file_path: Path):
        """创建文件显示组件"""
        try:
            file_frame = ctk.CTkFrame(self.files_scroll_frame)
            file_frame.pack(fill="x", pady=2, padx=5)

            # 文件信息行
            info_row = ctk.CTkFrame(file_frame, fg_color="transparent")
            info_row.pack(fill="x", padx=5, pady=3)

            # 文件编号和文件名
            file_name_text = f"#{index + 1} {file_path.name}"

            # 显示文件大小（如果存在）
            try:
                if file_path.exists():
                    size_bytes = file_path.stat().st_size
                    size_mb = size_bytes / (1024 * 1024)
                    file_name_text += f" ({size_mb:.2f} MB)"
            except Exception:
                pass

            file_label = ctk.CTkLabel(
                info_row,
                text=file_name_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w"
            )
            file_label.pack(side="left", fill="x", expand=True)

            # 文件类型图标
            file_type = file_path.suffix.lower()
            type_icon = "📄" if file_type == ".pdf" else "🖼️"
            type_label = ctk.CTkLabel(
                info_row,
                text=type_icon,
                font=ctk.CTkFont(size=12)
            )
            type_label.pack(side="right", padx=5)

            # 删除按钮（如果需要）
            # 可以在这里添加删除单个文件的按钮

        except Exception:
            pass  # 忽略单个文件组件创建错误

    def files_prev_page(self):
        """显示上一页文件"""
        if self.file_display_start > 0:
            self.file_display_start = max(0, self.file_display_start - self.max_visible_files)
            self.update_files_display()

    def files_next_page(self):
        """显示下一页文件"""
        files_count = len(self.selected_file_paths)
        if self.file_display_start + self.max_visible_files < files_count:
            self.file_display_start = min(
                self.file_display_start + self.max_visible_files,
                files_count - self.max_visible_files
            )
            self.update_files_display()
    
    def log(self, message: str, switch_to_log: bool = False):
        """添加日志消息
        
        Args:
            message: 日志消息
            switch_to_log: 是否自动切换到日志Tab（默认False，只在重要消息时切换）
        """
        try:
            # 检查log_text是否已初始化
            if not hasattr(self, 'log_text') or self.log_text is None:
                # 如果log_text未初始化，输出到stderr
                sys.stderr.write(f"{message}\n")
                sys.stderr.flush()
                return
            
            # 检查log_text是否可用（widget可能已被销毁）
            try:
                self.log_text.insert("end", f"{message}\n")
                self.log_text.see("end")
            except Exception:
                # 如果插入失败，输出到stderr
                sys.stderr.write(f"{message}\n")
                sys.stderr.flush()
                return
            
            # 切换到日志Tab（如果需要）
            if switch_to_log:
                try:
                    if hasattr(self, 'tabview') and self.tabview is not None:
                        self.tabview.set("📝 转换日志")
                except Exception:
                    pass  # 如果切换失败，忽略
            
            # 更新界面
            try:
                self.update()
            except Exception:
                pass  # 如果更新失败，忽略
        except Exception:
            # 如果所有操作都失败，至少输出到stderr
            try:
                sys.stderr.write(f"{message}\n")
                sys.stderr.flush()
            except Exception:
                pass  # 如果连stderr都失败，忽略
    
    def log_selected_config(self):
        """输出当前选择的配置模式"""
        self.log("", switch_to_log=True)
        self.log("=" * 60, switch_to_log=True)
        self.log("⚙️  当前选择配置", switch_to_log=True)
        self.log("=" * 60, switch_to_log=True)
        
        # 后端
        backend = self.backend_var.get()
        self.log(f"   - 后端: {backend}", switch_to_log=True)
        
        # 使用统一的配置提取方法
        config = self._get_task_config()
        method = config['method']
        lang = config['lang']
        self.log(f"   - 解析方法: {method}", switch_to_log=True)
        self.log(f"   - 语言: {lang}", switch_to_log=True)
        
        # 功能开关
        formula_enable = self.formula_var.get()
        table_enable = self.table_var.get()
        self.log(f"   - 公式识别: {'启用' if formula_enable else '禁用'}", switch_to_log=True)
        self.log(f"   - 表格识别: {'启用' if table_enable else '禁用'}", switch_to_log=True)
        
        # 设备模式
        force_cpu = self.force_cpu_var.get()
        device_mode = self.device_var.get().strip() or None
        if force_cpu:
            self.log("   - 设备模式: CPU (强制)", switch_to_log=True)
        elif device_mode:
            self.log(f"   - 设备模式: {device_mode} (手动指定)", switch_to_log=True)
        else:
            self.log("   - 设备模式: 自动检测", switch_to_log=True)
        
        # 输出目录
        output_dir = self.output_path_var.get()
        self.log(f"   - 输出目录: {output_dir}", switch_to_log=True)
        
        self.log("=" * 60, switch_to_log=True)
    
    def check_and_log_gpu_status(self):
        """检查并记录GPU加速状态（在开始处理前）"""
        try:
            import torch
            from mineru.utils.config_reader import get_device
            
            self.log("", switch_to_log=True)
            self.log("=" * 60, switch_to_log=True)
            self.log("🎮 GPU 加速状态检查", switch_to_log=True)
            self.log("=" * 60, switch_to_log=True)
            
            # 检查PyTorch CUDA支持
            has_cuda_support = hasattr(torch.version, 'cuda') and torch.version.cuda is not None
            cuda_available = torch.cuda.is_available()
            
            if has_cuda_support:
                cuda_version = torch.version.cuda
                self.log(f"[OK] PyTorch 包含 CUDA 支持 (CUDA版本: {cuda_version})", switch_to_log=True)
                
                if cuda_available:
                    gpu_count = torch.cuda.device_count()
                    self.log(f"[OK] 检测到 {gpu_count} 个 NVIDIA GPU", switch_to_log=True)
                    
                    for i in range(gpu_count):
                        gpu_name = torch.cuda.get_device_name(i)
                        gpu_props = torch.cuda.get_device_properties(i)
                        gpu_memory = gpu_props.total_memory / (1024**3)
                        self.log(f"   - GPU {i}: {gpu_name} ({gpu_memory:.2f} GB)", switch_to_log=True)
                    
                    # 检查实际使用的设备
                    actual_device = get_device()
                    if actual_device.startswith('cuda'):
                        device_id = int(actual_device.split(':')[1]) if ':' in actual_device else 0
                        self.log(f"[OK] 将自动使用 GPU {device_id} 加速", switch_to_log=True)
                    else:
                        self.log(f"[WARN] 检测到GPU但未使用，当前设备: {actual_device}", switch_to_log=True)
                        self.log("   提示: 如果设备模式留空，程序会自动使用GPU", switch_to_log=True)
                else:
                    self.log("[INFO] 当前电脑没有检测到 NVIDIA GPU（这是正常的）", switch_to_log=True)
                    self.log("   打包后的程序仍可在 NVIDIA 电脑上使用 GPU 加速", switch_to_log=True)
                    self.log("   PyTorch 已包含 CUDA 库，在 NVIDIA 电脑上会自动启用 GPU", switch_to_log=True)
            else:
                self.log("[ERROR] PyTorch 不包含 CUDA 支持（当前为 CPU 版本）", switch_to_log=True)
                self.log("   程序将使用 CPU 模式运行（速度较慢）", switch_to_log=True)
                self.log("   如需 GPU 加速，请确保:", switch_to_log=True)
                self.log("   1. 安装了 NVIDIA GPU 驱动", switch_to_log=True)
                self.log("   2. 打包时使用的是 CUDA 版本的 PyTorch", switch_to_log=True)
                self.log("   3. 打包环境有可用的 CUDA 支持", switch_to_log=True)
            
            self.log("=" * 60, switch_to_log=True)
        except Exception as e:
            self.log(f"⚠️  检查 GPU 状态时出错: {str(e)}", switch_to_log=True)
    
    def log_actual_runtime_mode(self):
        """输出实际运行模式"""
        try:
            from mineru.utils.config_reader import get_device
            actual_device = get_device()
            
            self.log("", switch_to_log=True)
            self.log("=" * 60, switch_to_log=True)
            self.log("🚀 实际运行模式", switch_to_log=True)
            self.log("=" * 60, switch_to_log=True)
            self.log(f"   - 实际使用设备: {actual_device}", switch_to_log=True)
            
            # 如果是CUDA，显示GPU信息
            if actual_device.startswith('cuda'):
                try:
                    import torch
                    if torch.cuda.is_available():
                        device_id = int(actual_device.split(':')[1]) if ':' in actual_device else 0
                        gpu_name = torch.cuda.get_device_name(device_id)
                        gpu_memory = torch.cuda.get_device_properties(device_id).total_memory / (1024**3)
                        self.log(f"   - GPU名称: {gpu_name}", switch_to_log=True)
                        self.log(f"   - GPU显存: {gpu_memory:.2f} GB", switch_to_log=True)
                        self.log("   - ✅ GPU 加速已启用", switch_to_log=True)
                except Exception:
                    pass
            
            # 如果是MPS，显示Apple Silicon信息
            elif actual_device == 'mps':
                self.log("   - 使用Apple Silicon GPU加速", switch_to_log=True)
            
            # 如果是CPU
            elif actual_device == 'cpu':
                self.log("   - 使用CPU模式（无GPU加速）", switch_to_log=True)
                self.log("   - 提示: 如需使用GPU，请安装PyTorch ROCm版本（AMD）或CUDA版本（NVIDIA）", switch_to_log=True)
            
            self.log("=" * 60, switch_to_log=True)
        except Exception as e:
            self.log(f"   - 无法检测运行模式: {str(e)}", switch_to_log=True)
    
    def start_queue_processing(self):
        """开始处理队列"""
        if self.is_converting:
            return
        
        with self.queue_lock:
            if not self.task_queue:
                self.log("❌ 错误: 队列为空，请先添加文件")
                return
            
            pending_tasks = [t for t in self.task_queue if t.status == TaskStatus.PENDING]
            if not pending_tasks:
                self.log("ℹ️ 信息: 没有待处理的任务")
                return
        
        # 更新UI状态
        self.is_converting = True
        self.convert_btn.configure(state="disabled")
        self.add_to_queue_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress_var.set(0.0)
        self.status_var.set("处理队列中...")
        self.log_text.delete("1.0", "end")
        # 开始处理时切换到日志Tab
        self.tabview.set("📝 转换日志")
        

        # 在开始处理前进行内存清理
        self.log("🧹 正在准备处理环境...", switch_to_log=True)
        self._force_gc_and_cleanup()

        self.log("", switch_to_log=True)
        self.log("=" * 60, switch_to_log=True)
        self.log(f"开始处理任务队列（{len(pending_tasks)} 个待处理任务）...", switch_to_log=True)
        self.log("=" * 60, switch_to_log=True)
        
        # 在新线程中执行队列处理
        self.conversion_thread = threading.Thread(
            target=self.process_queue,
            daemon=True,
            name="MinerU-Conversion-Thread"
        )
        self.conversion_thread.start()
    
    def process_queue(self):
        """处理任务队列"""
        try:
            while not self._shutdown_event.is_set():
                # 检查是否应该继续处理
                if not self.is_converting:
                    break

                # 获取下一个待处理任务（优化：直接查找索引，避免重复遍历）
                with self.queue_lock:
                    task_index = -1
                    task = None
                    # 查找第一个待处理任务的索引
                    for idx, t in enumerate(self.task_queue):
                        if t.status == TaskStatus.PENDING:
                            task = t
                            task_index = idx
                            break
                    
                    if task is None or task_index < 0:
                        break

                    task.status = TaskStatus.PROCESSING
                    task.start_time = datetime.now()
                    self.current_task_index = task_index

                # 检查关闭事件
                if self._shutdown_event.is_set():
                    break

                # 更新显示（使用线程安全的方法）
                self.schedule_gui_update(self.update_queue_display)

                # 每处理50个任务报告一次进度
                if (task_index + 1) % 50 == 0:
                    total_tasks = len(self.task_queue)
                    self.log(f"\n📊 进度报告: 已开始处理 {task_index + 1}/{total_tasks} 个任务", switch_to_log=True)

                self.log(f"\n开始处理任务 #{task_index + 1}: {task.file_name}", switch_to_log=True)

                # 处理任务
                try:
                    # 获取PDF页数
                    pdf_doc = None
                    try:
                        pdf_bytes = read_fn(task.file_path)
                        pdf_doc = pdfium.PdfDocument(pdf_bytes)
                        task.page_count = len(pdf_doc)
                    except Exception:
                        task.page_count = 0
                    finally:
                        # 确保PDF文档被关闭
                        if pdf_doc:
                            try:
                                pdf_doc.close()
                            except Exception:
                                pass

                    # 检查关闭事件
                    if self._shutdown_event.is_set():
                        task.status = TaskStatus.CANCELLED
                        break

                    # 记录开始时间
                    start_time = time.time()

                    # 处理前检查内存使用情况
                    if (task_index + 1) % 100 == 0:  # 每100个任务检查一次
                        self._check_memory_usage()

                    self.process_single_task(task)

                    # 计算处理时间
                    end_time = time.time()
                    task.total_time = end_time - start_time
                    if task.page_count > 0:
                        task.time_per_page = task.total_time / task.page_count
                    else:
                        task.time_per_page = 0.0

                    task.status = TaskStatus.COMPLETED
                    task.end_time = datetime.now()

                    # 显示完成信息，包含时间统计和重试信息
                    retry_info = ""
                    if task.retry_count > 0:
                        retry_info = f"，重试 {task.retry_count} 次"
                    
                    if task.page_count > 0:
                        time_info = f"（{task.page_count}页，总耗时: {task.total_time:.1f}秒，平均: {task.time_per_page:.2f}秒/页{retry_info}）"
                    else:
                        time_info = f"（总耗时: {task.total_time:.1f}秒{retry_info}）"
                    self.log(f"✅ 任务 #{task_index + 1} 完成: {task.file_name} {time_info}", switch_to_log=True)
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.end_time = datetime.now()
                    
                    # 使用统一的错误处理系统
                    error_handler = MinerUErrorHandler()
                    category, user_msg = error_handler.classify_exception(e)
                    formatted_msg = error_handler.format_error_message(
                        e, 
                        context=f"任务 #{task_index + 1}: {task.file_name}"
                    )
                    
                    # 存储用户友好的错误消息（限制长度），包含重试信息
                    retry_info_msg = ""
                    if task.retry_count > 0:
                        retry_info_msg = f"（已重试 {task.retry_count} 次后失败）"
                    task.error_message = f"{user_msg[:250]}{retry_info_msg}"[:300]
                    
                    # 记录用户友好的错误消息
                    retry_status = ""
                    if task.retry_count >= task.max_retries:
                        retry_status = f"（已重试 {task.max_retries} 次，仍失败）"
                    elif task.retry_count > 0:
                        retry_status = f"（重试 {task.retry_count} 次后失败）"
                    
                    self.log(f"❌ 任务 #{task_index + 1} 失败: {task.file_name}{retry_status}", switch_to_log=True)
                    self.log(f"   错误类别: {category.value}", switch_to_log=True)
                    self.log(f"   错误详情: {user_msg}", switch_to_log=True)
                    
                    # 记录详细信息到日志文件（用于调试）
                    logger.error(f"任务 #{task_index + 1} 处理失败: {task.file_name} (重试次数: {task.retry_count}/{task.max_retries})")
                    logger.exception(f"任务 #{task_index + 1} 处理失败详情")
                    logger.debug(f"错误分类: {category.name}, 原始异常: {type(e).__name__}: {str(e)}")
                    
                    # 如果已达到最大重试次数，给出最终提示并记录错误日志
                    if task.retry_count >= task.max_retries:
                        self.log(f"   ⚠️ 该文件无法成功转换（已重试 {task.max_retries} 次）", switch_to_log=True)
                        self.log("   💡 建议: 请检查文件是否损坏、格式是否正确，或尝试手动处理该文件", switch_to_log=True)
                        
                        # 将错误信息实时保存到导出目录的错误日志文件
                        self._write_error_to_log_file(
                            task=task,
                            error_category=category.value,
                            error_message=user_msg,
                            exception_type=type(e).__name__
                        )
                        self.log("   📝 错误信息已保存到导出目录的「转换错误日志.md」文件中", switch_to_log=True)

                # 更新显示（使用线程安全的方法）
                self.schedule_gui_update(self.update_queue_display)

                # 检查是否取消或关闭
                if not self.is_converting or self._shutdown_event.is_set():
                    if task.status == TaskStatus.PROCESSING:
                        task.status = TaskStatus.CANCELLED
                    break
            
            # 完成
            with self.queue_lock:
                _, _, completed, failed = self._calculate_queue_stats()
                total = len(self.task_queue)
                
                # 计算统计信息
                completed_tasks = [t for t in self.task_queue if t.status == TaskStatus.COMPLETED and t.total_time > 0]
                if completed_tasks:
                    total_pages = sum(t.page_count for t in completed_tasks)
                    total_time = sum(t.total_time for t in completed_tasks)
                    avg_time_per_page = total_time / total_pages if total_pages > 0 else 0
                    
                    stats_info = "\n📊 统计信息:\n"
                    stats_info += f"   - 总页数: {total_pages} 页\n"
                    stats_info += f"   - 总耗时: {total_time:.1f} 秒 ({total_time/60:.1f} 分钟)\n"
                    stats_info += f"   - 平均速度: {avg_time_per_page:.2f} 秒/页\n"
                    if total_pages > 0:
                        pages_per_minute = 60 / avg_time_per_page if avg_time_per_page > 0 else 0
                        stats_info += f"   - 处理速度: {pages_per_minute:.1f} 页/分钟"
                else:
                    stats_info = ""
            
            self.progress_var.set(1.0)
            self.status_var.set(f"队列处理完成 ({completed}/{total} 成功)")
            self.log("", switch_to_log=True)
            self.log("=" * 60, switch_to_log=True)
            self.log(f"✅ 队列处理完成! 成功: {completed}, 失败: {failed}, 总计: {total}", switch_to_log=True)
            if stats_info:
                self.log(stats_info, switch_to_log=True)
            self.log("=" * 60, switch_to_log=True)

            # 执行清理
            self.schedule_gui_update(self._force_gc_and_cleanup)

            # 处理完成后，切换到任务队列Tab查看结果
            self.schedule_gui_update(lambda: self.tabview.set("📋 任务队列"))
            
        except Exception as e:
            # 使用统一的错误处理系统
            error_handler = MinerUErrorHandler()
            formatted_msg = error_handler.format_error_message(e, context="队列处理过程")
            
            self.log("❌ 队列处理出错", switch_to_log=True)
            self.log(f"   {formatted_msg}", switch_to_log=True)
            
            # 使用logger记录详细异常信息（会自动输出到GUI）
            logger.exception("队列处理过程中发生异常")
            logger.debug(f"错误详情: {type(e).__name__}: {str(e)}")
            
            self.status_var.set("队列处理失败")
            
            # 如果是可重试的错误，给出建议
            if error_handler.should_retry(e):
                self.log("   💡 提示: 此错误可能可以重试，请稍后重新开始处理", switch_to_log=True)
        finally:
            # 恢复UI状态
            self.is_converting = False
            self.convert_btn.configure(state="normal")
            self.add_to_queue_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.current_task_index = -1
    
    def _validate_task_config(self, config: dict) -> tuple[bool, Optional[str]]:
        """验证任务配置参数"""
        # 验证输出目录
        output_dir = config.get('output_dir', '').strip()
        if not output_dir:
            return False, "输出目录不能为空"
        
        output_path = Path(output_dir)
        try:
            # 尝试创建输出目录（如果不存在）
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"无法创建输出目录: {str(e)}"
        
        # 验证页码范围
        start_page_id = config.get('start_page_id', 0)
        end_page_id = config.get('end_page_id')
        if start_page_id < 0:
            return False, "起始页码必须 >= 0"
        if end_page_id is not None and end_page_id < start_page_id:
            return False, "结束页码必须 >= 起始页码"
        
        return True, None
    
    def _write_error_to_log_file(self, task: ConversionTask, error_category: str, error_message: str, exception_type: str = ""):
        """将失败的任务信息写入错误日志Markdown文件（实时追加）"""
        try:
            output_dir = self.output_path_var.get().strip()
            if not output_dir:
                logger.warning("输出目录为空，无法写入错误日志")
                return
            
            output_path = Path(output_dir)
            
            # 确保输出目录存在
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"无法创建输出目录 {output_path}: {e}")
                return
            
            # 错误日志文件名
            error_log_file = output_path / "转换错误日志.md"
            
            # 准备Markdown格式的错误记录
            error_entry = []
            error_entry.append("---")
            error_entry.append(f"**失败时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            error_entry.append(f"**文件名称**: `{task.file_name}`")
            error_entry.append(f"**文件路径**: `{task.file_path}`")
            error_entry.append(f"**错误类别**: {error_category}")
            
            if exception_type:
                error_entry.append(f"**异常类型**: `{exception_type}`")
            
            if task.retry_count > 0:
                error_entry.append(f"**重试次数**: {task.retry_count}/{task.max_retries}（已尝试 {task.retry_count + 1} 次）")
            
            if task.start_time and task.end_time:
                duration = (task.end_time - task.start_time).total_seconds()
                error_entry.append(f"**开始时间**: {task.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                error_entry.append(f"**结束时间**: {task.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
                error_entry.append(f"**耗时**: {duration:.2f} 秒")
            elif task.start_time:
                error_entry.append(f"**开始时间**: {task.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if task.page_count > 0:
                error_entry.append(f"**PDF页数**: {task.page_count} 页")
            
            # 文件大小信息
            try:
                if task.file_path.exists():
                    file_size = task.file_path.stat().st_size
                    size_mb = file_size / (1024 * 1024)
                    error_entry.append(f"**文件大小**: {size_mb:.2f} MB")
            except Exception:
                pass
            
            error_entry.append("")
            error_entry.append("### 错误详情")
            error_entry.append("")
            error_entry.append("```")
            # 确保错误消息中的换行被正确处理
            formatted_error = error_message.replace('\n', '\n')
            error_entry.append(formatted_error)
            error_entry.append("```")
            error_entry.append("")
            error_entry.append("")
            
            # 追加写入错误日志文件
            try:
                # 如果是新文件，添加标题和说明
                is_new_file = not error_log_file.exists()
                
                with open(error_log_file, 'a', encoding='utf-8') as f:
                    if is_new_file:
                        # 新文件时添加标题和说明
                        f.write("# MinerU 转换错误日志\n\n")
                        f.write("> 本文档自动记录所有无法成功转换的文件信息\n\n")
                        f.write("---\n\n")
                    
                    # 写入错误记录
                    f.write("\n".join(error_entry))
                    f.flush()  # 立即刷新，确保实时写入
                
                logger.info(f"错误日志已写入: {error_log_file}")
            except Exception as e:
                logger.error(f"写入错误日志文件失败: {e}")
                
        except Exception as e:
            logger.error(f"记录错误日志时发生异常: {e}")
    
    def process_single_task(self, task: ConversionTask):
        """处理单个任务"""
        # 使用统一的配置提取方法
        config = self._get_task_config()
        
        # 验证配置
        is_valid, error_msg = self._validate_task_config(config)
        if not is_valid:
            raise ValueError(f"配置错误: {error_msg}")
        
        output_dir = config['output_dir']
        backend = config['backend']
        method = config['method']
        lang = config['lang']
        formula_enable = config['formula_enable']
        table_enable = config['table_enable']
        start_page_id = config['start_page_id']
        end_page_id = config['end_page_id']
        device_mode = config['device_mode']
        
        # 设置设备模式环境变量
        if device_mode:
            os.environ['MINERU_DEVICE_MODE'] = device_mode

        # 输出实际运行模式（在设备模式设置后）
        self.log_actual_runtime_mode()

        # 读取文件并确保资源管理
        pdf_bytes = None
        
        try:
            # 验证文件是否存在
            if not task.file_path.exists():
                raise FileNotFoundError(f"文件不存在: {task.file_path}")
            
            # 验证文件大小（防止处理过大的文件）
            file_size = task.file_path.stat().st_size
            max_file_size = 500 * 1024 * 1024  # 500MB
            if file_size > max_file_size:
                raise ValueError(f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，超过限制 ({max_file_size / 1024 / 1024:.0f}MB)")
            
            # 读取文件
            try:
                pdf_bytes = read_fn(task.file_path)
                file_name = task.file_name
            except Exception as e:
                error_handler = MinerUErrorHandler()
                formatted_msg = error_handler.format_error_message(
                    e, 
                    context=f"读取文件: {task.file_path}"
                )
                logger.error(formatted_msg)
                raise

            # 检查关闭事件
            if self._shutdown_event.is_set():
                return

            # 更新进度
            task.progress = 0.2
            self.schedule_gui_update(self.update_queue_display)

            # 执行转换（支持重试）
            conversion_success = False
            last_error = None
            
            for attempt in range(task.max_retries + 1):  # 0, 1, 2, 3 (共4次尝试，首次+3次重试)
                try:
                    if attempt > 0:
                        # 重试时等待一小段时间，并记录日志
                        wait_time = min(attempt * 2, 10)  # 最多等待10秒
                        self.log(f"   🔄 第 {attempt} 次重试（等待 {wait_time} 秒后开始）...", switch_to_log=True)
                        time.sleep(wait_time)
                        
                        # 重新读取文件（确保资源是新鲜的）
                        try:
                            if pdf_bytes:
                                try:
                                    if hasattr(pdf_bytes, 'close'):
                                        pdf_bytes.close()
                                except Exception:
                                    pass
                            pdf_bytes = read_fn(task.file_path)
                        except Exception as file_error:
                            # 文件读取错误不应该重试，直接抛出
                            error_handler = MinerUErrorHandler()
                            formatted_msg = error_handler.format_error_message(
                                file_error,
                                context=f"重试时重新读取文件: {task.file_path}"
                            )
                            logger.error(formatted_msg)
                            raise
                    
                    # 执行转换
                    do_parse(
                        output_dir=output_dir,
                        pdf_file_names=[file_name],
                        pdf_bytes_list=[pdf_bytes],
                        p_lang_list=[lang],
                        backend=backend,
                        parse_method=method,
                        formula_enable=formula_enable,
                        table_enable=table_enable,
                        start_page_id=start_page_id,
                        end_page_id=end_page_id,
                    )
                    
                    # 转换成功
                    conversion_success = True
                    task.retry_count = attempt
                    if attempt > 0:
                        self.log("   ✅ 重试成功！", switch_to_log=True)
                    break
                    
                except (FileNotFoundError, ValueError, IOError, OSError) as e:
                    # 文件相关错误不应该重试，直接抛出
                    last_error = e
                    task.retry_count = attempt
                    raise
                except Exception as e:
                    last_error = e
                    task.retry_count = attempt
                    
                    error_handler = MinerUErrorHandler()
                    category, user_msg = error_handler.classify_exception(e)
                    
                    if attempt < task.max_retries:
                        # 还可以重试
                        self.log(f"   ⚠️ 转换失败（第 {attempt + 1} 次尝试）: {category.value}", switch_to_log=True)
                        self.log(f"   错误详情: {user_msg[:100]}...", switch_to_log=True)
                        
                        # 判断是否可以重试
                        if error_handler.should_retry(e):
                            self.log("   💡 此错误可以重试，将自动重试...", switch_to_log=True)
                        else:
                            self.log("   ⚠️ 注意: 此错误类型通常不可重试，但仍将尝试重试", switch_to_log=True)
                    else:
                        # 已达到最大重试次数
                        formatted_msg = error_handler.format_error_message(
                            e,
                            context=f"PDF转换过程: {file_name} (已重试 {task.max_retries} 次)"
                        )
                        logger.error(formatted_msg)
                        self.log(f"   ❌ 转换失败（已重试 {task.max_retries} 次）: {category.value}", switch_to_log=True)
                        self.log(f"   错误详情: {user_msg}", switch_to_log=True)
            
            # 如果所有重试都失败，抛出最后一个错误
            if not conversion_success:
                if last_error:
                    raise last_error
                else:
                    raise RuntimeError(f"转换失败，原因未知（已重试 {task.max_retries} 次）")

            # 完成
            task.progress = 1.0
            self.schedule_gui_update(self.update_queue_display)

        except (FileNotFoundError, ValueError, IOError, OSError):
            # 文件相关错误，直接重新抛出让上层处理
            raise
        except Exception as e:
            # 其他错误，包装后重新抛出
            error_handler = MinerUErrorHandler()
            formatted_msg = error_handler.format_error_message(
                e,
                context=f"处理任务: {task.file_name}"
            )
            logger.error(formatted_msg)
            raise
        finally:
            # 清理资源
            if pdf_bytes:
                try:
                    if hasattr(pdf_bytes, 'close'):
                        pdf_bytes.close()
                except Exception as cleanup_error:
                    logger.warning(f"清理PDF资源时出错: {cleanup_error}")
    
    def cancel_conversion(self):
        """取消转换"""
        if self.is_converting:
            self.log("⚠️ 取消队列处理请求已发送...", switch_to_log=True)
            self.is_converting = False
            self._shutdown_event.set()  # 设置关闭事件
            self.convert_btn.configure(state="normal")
            self.add_to_queue_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.status_var.set("已取消")
            # 取消后切换到任务队列Tab查看状态
            self.schedule_gui_update(lambda: self.tabview.set("📋 任务队列"))
    
    def show_about(self):
        """显示关于对话框"""
        about_window = ctk.CTkToplevel(self)
        about_window.title("关于 MinerU GUI")
        about_window.geometry("500x450")
        about_window.resizable(False, False)
        
        # 使对话框居中
        about_window.transient(self)
        about_window.grab_set()
        
        # 主容器
        main_frame = ctk.CTkFrame(about_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 标题
        title_label = ctk.CTkLabel(
            main_frame,
            text="MinerU GUI",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack(pady=(20, 10))
        
        # 版本信息
        version_label = ctk.CTkLabel(
            main_frame,
            text="PDF转Markdown工具 - GUI版本",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray50")
        )
        version_label.pack(pady=(0, 20))
        
        # 分隔线
        separator = ctk.CTkFrame(main_frame, height=2, fg_color=("gray70", "gray30"))
        separator.pack(fill="x", padx=20, pady=10)
        
        # 项目信息
        info_text = """本项目 Fork 自 opendatalab/MinerU

主要功能：
• 功能完备且美观的GUI界面
• 一键启动，简化使用流程
• 支持任务队列，可批量处理多个PDF文件
• 支持CPU模式运行，无需GPU也能使用
• 自动跟随系统主题切换（浅色/暗色）
• 实时显示处理进度和每页处理时间统计"""
        
        info_label = ctk.CTkLabel(
            main_frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            justify="left",
            anchor="w"
        )
        info_label.pack(pady=10, padx=20, fill="x")
        
        # 分隔线
        separator2 = ctk.CTkFrame(main_frame, height=2, fg_color=("gray70", "gray30"))
        separator2.pack(fill="x", padx=20, pady=10)
        
        # 开发者信息
        dev_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        dev_frame.pack(fill="x", padx=20, pady=10)
        
        dev_title = ctk.CTkLabel(
            dev_frame,
            text="开发者信息",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        dev_title.pack(anchor="w", pady=(0, 5))
        
        dev_info = """开发者: ViVI141
邮箱: 747384120@qq.com
项目地址: https://github.com/ViVi141/MinerU
许可证: AGPL-3.0 license"""
        
        dev_label = ctk.CTkLabel(
            dev_frame,
            text=dev_info,
            font=ctk.CTkFont(size=11),
            justify="left",
            anchor="w"
        )
        dev_label.pack(anchor="w")
        
        # 项目链接按钮
        link_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        link_frame.pack(fill="x", padx=20, pady=10)
        
        def open_github():
            import webbrowser
            webbrowser.open("https://github.com/ViVi141/MinerU")
        
        github_btn = ctk.CTkButton(
            link_frame,
            text="🌐 访问项目主页",
            command=open_github,
            width=200,
            height=35,
            font=ctk.CTkFont(size=12),
            fg_color=("#3B82F6", "#2563EB"),
            hover_color=("#2563EB", "#1D4ED8")
        )
        github_btn.pack(pady=5)
        
        # 关闭按钮
        close_btn = ctk.CTkButton(
            main_frame,
            text="关闭",
            command=about_window.destroy,
            width=150,
            height=35,
            font=ctk.CTkFont(size=12)
        )
        close_btn.pack(pady=(10, 20))


def main():
    """主函数"""
    try:
        app = MinerUGUI()
        app.mainloop()
    except Exception as e:
        # 如果GUI启动失败，提供有用的错误信息
        print(f"GUI启动失败: {e}")
        print("\n可能的原因:")
        print("1. 缺少必要的Python包 (pip install customtkinter)")
        print("2. 图形界面相关问题 (尝试使用命令行模式)")
        print("3. 其他依赖问题")
        print(f"\n详细错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    main()
