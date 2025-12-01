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

            # 清理队列更新定时器
            if self.queue_update_id:
                try:
                    self.after_cancel(self.queue_update_id)
                    self.queue_update_id = None
                except Exception:
                    pass

            # 停止GUI更新处理器
            self._shutdown_event.set()

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
                    pending = sum(1 for t in self.task_queue if t.status == TaskStatus.PENDING)
                    processing = sum(1 for t in self.task_queue if t.status == TaskStatus.PROCESSING)
                    completed = sum(1 for t in self.task_queue if t.status == TaskStatus.COMPLETED)
                    failed = sum(1 for t in self.task_queue if t.status == TaskStatus.FAILED)

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
                    to_remove_count = len(completed_tasks) - self._max_completed_tasks

                    # 按完成时间排序，保留最新的
                    completed_tasks.sort(key=lambda t: t.end_time or datetime.min, reverse=True)

                    # 获取需要删除的任务
                    tasks_to_remove = completed_tasks[-to_remove_count:]

                    # 从队列中移除这些任务
                    original_length = len(self.task_queue)
                    self.task_queue = [t for t in self.task_queue if t not in tasks_to_remove]

                    removed_count = original_length - len(self.task_queue)

                    if removed_count > 0:
                        self.log(f"🧹 已自动清理 {removed_count} 个旧的已完成任务", switch_to_log=False)

                        # 清理相关的组件缓存
                        task_ids_to_remove = []
                        for task in tasks_to_remove:
                            # 找到任务在原始队列中的索引作为ID
                            for i, t in enumerate(self.task_queue):
                                if t == task:
                                    task_ids_to_remove.append(i)
                                    break

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
        
        self.selected_files_var = ctk.StringVar(value="未选择文件")
        files_label = ctk.CTkLabel(
            files_info_frame,
            textvariable=self.selected_files_var,
            font=ctk.CTkFont(size=11),
            anchor="w",
            justify="left",
            wraplength=800
        )
        files_label.pack(anchor="w", padx=10, pady=(0, 10))
        
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
        file_path = filedialog.askopenfilename(
            title="选择PDF文件",
            filetypes=[
                ("PDF文件", "*.pdf"),
                ("图片文件", "*.png *.jpg *.jpeg"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.selected_files_var.set(file_path)
            # 选择文件后不切换Tab，保持在当前界面
            self.log(f"已选择文件: {file_path}", switch_to_log=False)
    
    def select_multiple_files(self):
        """选择多个PDF文件"""
        file_paths = filedialog.askopenfilenames(
            title="选择多个PDF文件",
            filetypes=[
                ("PDF文件", "*.pdf"),
                ("图片文件", "*.png *.jpg *.jpeg"),
                ("所有文件", "*.*")
            ]
        )
        if file_paths:
            files_str = "\n".join(file_paths)
            self.selected_files_var.set(files_str)
            # 选择多文件后，提示用户添加到队列，不切换Tab
            self.log(f"已选择 {len(file_paths)} 个文件，请点击「添加到队列」按钮", switch_to_log=False)
            # 自动切换到基本设置Tab，方便用户看到已选文件
            self.tabview.set("📋 基本设置")
    
    def select_folder(self):
        """选择文件夹"""
        dir_path = filedialog.askdirectory(title="选择包含PDF文件的文件夹")
        if dir_path:
            folder_path = Path(dir_path)
            pdf_files = list(folder_path.glob("*.pdf"))
            if pdf_files:
                files_str = "\n".join(str(f) for f in pdf_files)
                self.selected_files_var.set(files_str)
                # 选择文件夹后，提示用户添加到队列，不切换Tab
                self.log(f"从文件夹选择了 {len(pdf_files)} 个PDF文件，请点击「添加到队列」按钮", switch_to_log=False)
                # 保持在基本设置Tab
                self.tabview.set("📋 基本设置")
            else:
                self.log(f"文件夹中没有找到PDF文件: {dir_path}", switch_to_log=False)
    
    def select_output_dir(self):
        """选择输出目录"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_path_var.set(dir_path)
            # 选择输出目录后不切换Tab
            self.log(f"输出目录: {dir_path}", switch_to_log=False)
    
    def add_files_to_queue(self):
        """将选中的文件添加到队列"""
        files_str = self.selected_files_var.get()
        if not files_str or files_str == "未选择文件":
            self.log("❌ 错误: 请先选择文件", switch_to_log=True)
            return
        
        # 解析文件路径
        file_paths = [Path(f.strip()) for f in files_str.split("\n") if f.strip()]
        
        # 验证文件
        valid_files = []
        invalid_count = 0
        for file_path in file_paths:
            if not file_path.exists():
                invalid_count += 1
                continue
            if file_path.suffix.lower() not in ['.pdf', '.png', '.jpg', '.jpeg']:
                invalid_count += 1
                continue
            valid_files.append(file_path)
        
        if not valid_files:
            self.log("❌ 错误: 没有有效的文件可以添加到队列", switch_to_log=True)
            return
        
        # 添加到队列（分批处理，避免一次性创建过多组件）
        added_count = 0
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

        self.tabview.set("📋 任务队列")

        # 显示成功消息
        if invalid_count > 0:
            self.log(f"✅ 已添加 {added_count} 个文件到队列（已跳过 {invalid_count} 个无效文件）", switch_to_log=False)
        else:
            self.log(f"✅ 已添加 {added_count} 个文件到队列", switch_to_log=False)

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
                    pending = sum(1 for t in self.task_queue if t.status == TaskStatus.PENDING)
                    processing = sum(1 for t in self.task_queue if t.status == TaskStatus.PROCESSING)
                    completed = sum(1 for t in self.task_queue if t.status == TaskStatus.COMPLETED)
                    failed = sum(1 for t in self.task_queue if t.status == TaskStatus.FAILED)
                    
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
    
    def get_system_info(self) -> dict:
        """获取系统硬件和软件配置信息（增强版）"""
        info = {
            'platform': {},
            'cpu': {},
            'memory': {},
            'disk': {},
            'python': {},
            'dependencies': {},
            'pytorch': {},
            'gpu': {},
            'mineru_config': {}
        }
        
        # 平台信息
        import platform
        info['platform'] = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'platform_string': platform.platform()
        }
        
        # CPU信息（增强，获取详细型号）
        try:
            import psutil
            cpu_count_physical = psutil.cpu_count(logical=False) or psutil.cpu_count()
            cpu_count_logical = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # 尝试获取更详细的CPU型号信息
            cpu_model = platform.processor()
            cpu_brand = None
            
            # Windows系统使用WMI获取详细CPU信息
            if platform.system() == 'Windows':
                try:
                    import wmi
                    c = wmi.WMI()
                    for processor in c.Win32_Processor():
                        cpu_brand = processor.Name.strip()
                        cpu_model = cpu_brand if cpu_brand else cpu_model
                        break
                except ImportError:
                    # 如果没有wmi库，尝试使用其他方法
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['wmic', 'cpu', 'get', 'name'],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            if len(lines) > 1:
                                cpu_brand = lines[1].strip()
                                cpu_model = cpu_brand if cpu_brand else cpu_model
                    except Exception:
                        pass
                except Exception:
                    pass
            
            # Linux系统使用/proc/cpuinfo
            elif platform.system() == 'Linux':
                try:
                    with open('/proc/cpuinfo', 'r', encoding='utf-8') as f:
                        for line in f:
                            if 'model name' in line.lower():
                                cpu_brand = line.split(':')[1].strip()
                                cpu_model = cpu_brand if cpu_brand else cpu_model
                                break
                except Exception:
                    pass
            
            info['cpu'] = {
                'model': cpu_model,
                'brand': cpu_brand if cpu_brand else cpu_model,
                'physical_cores': cpu_count_physical,
                'logical_cores': cpu_count_logical,
                'current_freq_mhz': round(cpu_freq.current, 2) if cpu_freq else None,
                'min_freq_mhz': round(cpu_freq.min, 2) if cpu_freq else None,
                'max_freq_mhz': round(cpu_freq.max, 2) if cpu_freq else None,
                'usage_percent': round(cpu_percent, 2),
                'architecture': platform.machine()
            }
        except Exception as e:
            info['cpu'] = {'error': f'无法获取CPU信息: {str(e)}'}
        
        # 内存信息
        try:
            import psutil
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            info['memory'] = {
                'total_gb': round(mem.total / (1024**3), 2),
                'available_gb': round(mem.available / (1024**3), 2),
                'used_gb': round(mem.used / (1024**3), 2),
                'usage_percent': round(mem.percent, 2),
                'swap_total_gb': round(swap.total / (1024**3), 2),
                'swap_used_gb': round(swap.used / (1024**3), 2),
                'swap_usage_percent': round(swap.percent, 2) if swap.total > 0 else 0
            }
        except Exception as e:
            info['memory'] = {'error': f'无法获取内存信息: {str(e)}'}
        
        # 磁盘信息
        try:
            import shutil
            import psutil
            disk_usage = shutil.disk_usage('.')
            disk_io = psutil.disk_io_counters()
            
            info['disk'] = {
                'total_gb': round(disk_usage.total / (1024**3), 2),
                'used_gb': round(disk_usage.used / (1024**3), 2),
                'free_gb': round(disk_usage.free / (1024**3), 2),
                'usage_percent': round((disk_usage.used / disk_usage.total) * 100, 2),
                'read_mb': round(disk_io.read_bytes / (1024**2), 2) if disk_io else None,
                'write_mb': round(disk_io.write_bytes / (1024**2), 2) if disk_io else None
            }
        except Exception as e:
            info['disk'] = {'error': f'无法获取磁盘信息: {str(e)}'}
        
        # Python信息
        info['python'] = {
            'version': sys.version.split()[0],
            'version_full': sys.version,
            'executable': sys.executable,
            'implementation': platform.python_implementation(),
            'compiler': platform.python_compiler()
        }
        
        # 依赖库版本信息
        dependencies = {}
        dep_list = [
            'numpy', 'PIL', 'pypdfium2', 'loguru', 'customtkinter',
            'magika', 'opencv-python', 'ultralytics', 'onnxruntime'
        ]
        for dep in dep_list:
            try:
                if dep == 'PIL':
                    import PIL
                    dependencies['PIL (Pillow)'] = PIL.__version__
                elif dep == 'opencv-python':
                    import cv2
                    dependencies['OpenCV'] = cv2.__version__
                elif dep == 'pypdfium2':
                    # pdfium是通过pypdfium2包提供的
                    import pypdfium2
                    dependencies['pdfium (pypdfium2)'] = pypdfium2.__version__ if hasattr(pypdfium2, '__version__') else '已安装'
                else:
                    mod = __import__(dep.replace('-', '_'))
                    if hasattr(mod, '__version__'):
                        dependencies[dep] = mod.__version__
            except ImportError:
                # 显示友好的名称
                display_name = 'pdfium (pypdfium2)' if dep == 'pypdfium2' else dep
                dependencies[display_name] = '未安装'
            except Exception:
                display_name = 'pdfium (pypdfium2)' if dep == 'pypdfium2' else dep
                dependencies[display_name] = '未知'
        info['dependencies'] = dependencies
        
        # PyTorch信息
        try:
            import torch
            info['pytorch'] = {
                'version': torch.__version__,
                'cuda_available': torch.cuda.is_available(),
                'cuda_version': torch.version.cuda if hasattr(torch.version, 'cuda') and torch.version.cuda else None,
                'hip_version': torch.version.hip if hasattr(torch.version, 'hip') and torch.version.hip else None,
                'mps_available': torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
                'xpu_available': hasattr(torch, 'xpu') and torch.xpu.is_available() if hasattr(torch, 'xpu') else False
            }
            
            # GPU信息（增强 - 检测所有GPU，包括不支持的）
            all_gpus = []
            supported_gpus = []
            unsupported_gpus = []
            
            # 检测PyTorch支持的GPU
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                for i in range(gpu_count):
                    props = torch.cuda.get_device_properties(i)
                    # 获取当前GPU使用情况
                    try:
                        mem_allocated = torch.cuda.memory_allocated(i) / (1024**3)
                        mem_reserved = torch.cuda.memory_reserved(i) / (1024**3)
                    except Exception:
                        mem_allocated = None
                        mem_reserved = None
                    
                    gpu_info = {
                        'index': i,
                        'name': props.name,
                        'model': props.name,  # 完整型号名称
                        'memory_total_gb': round(props.total_memory / (1024**3), 2),
                        'memory_allocated_gb': round(mem_allocated, 2) if mem_allocated else None,
                        'memory_reserved_gb': round(mem_reserved, 2) if mem_reserved else None,
                        'compute_capability': f"{props.major}.{props.minor}" if hasattr(props, 'major') else 'N/A',
                        'multiprocessor_count': props.multi_processor_count if hasattr(props, 'multi_processor_count') else None,
                        'supported': True,
                        'support_type': 'CUDA'
                    }
                    supported_gpus.append(gpu_info)
                    all_gpus.append(gpu_info)
            
            # 检测Apple Silicon GPU
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                gpu_info = {
                    'index': 0,
                    'name': 'Apple Silicon GPU',
                    'model': 'Apple Silicon (MPS)',
                    'supported': True,
                    'support_type': 'MPS'
                }
                supported_gpus.append(gpu_info)
                all_gpus.append(gpu_info)
            
            # 检测Intel XPU
            if hasattr(torch, 'xpu') and torch.xpu.is_available():
                try:
                    xpu_count = torch.xpu.device_count()
                    for i in range(xpu_count):
                        gpu_info = {
                            'index': i,
                            'name': f'Intel GPU {i}',
                            'model': f'Intel XPU {i}',
                            'supported': True,
                            'support_type': 'XPU'
                        }
                        supported_gpus.append(gpu_info)
                        all_gpus.append(gpu_info)
                except Exception:
                    pass
            
            # 检测系统中所有GPU（包括不支持的）
            # Windows系统使用WMI
            if platform.system() == 'Windows':
                try:
                    import wmi
                    c = wmi.WMI()
                    wmi_gpus = []
                    for gpu in c.Win32_VideoController():
                        gpu_name = gpu.Name.strip() if gpu.Name else 'Unknown GPU'
                        # 检查是否已经在支持的GPU列表中
                        is_supported = any(g['name'] == gpu_name or gpu_name in g.get('model', '') for g in supported_gpus)
                        if not is_supported:
                            wmi_gpus.append({
                                'name': gpu_name,
                                'model': gpu_name,
                                'adapter_ram_mb': round(gpu.AdapterRAM / (1024**2), 2) if gpu.AdapterRAM else None,
                                'driver_version': gpu.DriverVersion if gpu.DriverVersion else None,
                                'supported': False,
                                'support_type': '不支持（未安装CUDA/ROCm驱动或PyTorch不支持）'
                            })
                    
                    # 去重并添加到列表
                    for wmi_gpu in wmi_gpus:
                        # 检查是否已存在
                        if not any(g['name'] == wmi_gpu['name'] for g in all_gpus):
                            unsupported_gpus.append(wmi_gpu)
                            all_gpus.append(wmi_gpu)
                except ImportError:
                    # 如果没有wmi库，尝试使用其他方法
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            for line in lines[1:]:  # 跳过标题行
                                gpu_name = line.strip()
                                if gpu_name and gpu_name != 'Name':
                                    # 检查是否已经在支持的GPU列表中
                                    is_supported = any(g['name'] == gpu_name or gpu_name in g.get('model', '') for g in supported_gpus)
                                    if not is_supported:
                                        gpu_info = {
                                            'name': gpu_name,
                                            'model': gpu_name,
                                            'supported': False,
                                            'support_type': '不支持（未安装CUDA/ROCm驱动或PyTorch不支持）'
                                        }
                                        if not any(g['name'] == gpu_name for g in all_gpus):
                                            unsupported_gpus.append(gpu_info)
                                            all_gpus.append(gpu_info)
                    except Exception:
                        pass
                except Exception:
                    pass
            
            # Linux系统使用lspci
            elif platform.system() == 'Linux':
                try:
                    import subprocess
                    result = subprocess.run(
                        ['lspci'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'VGA' in line or '3D' in line or 'Display' in line:
                                gpu_name = line.split(':')[2].strip() if ':' in line else line.strip()
                                # 检查是否已经在支持的GPU列表中
                                is_supported = any(g['name'] == gpu_name or gpu_name in g.get('model', '') for g in supported_gpus)
                                if not is_supported and gpu_name:
                                    gpu_info = {
                                        'name': gpu_name,
                                        'model': gpu_name,
                                        'supported': False,
                                        'support_type': '不支持（未安装CUDA/ROCm驱动或PyTorch不支持）'
                                    }
                                    if not any(g['name'] == gpu_name for g in all_gpus):
                                        unsupported_gpus.append(gpu_info)
                                        all_gpus.append(gpu_info)
                except Exception:
                    pass
            
            # 构建GPU信息
            if all_gpus:
                info['gpu'] = {
                    'available': len(supported_gpus) > 0,
                    'total_count': len(all_gpus),
                    'supported_count': len(supported_gpus),
                    'unsupported_count': len(unsupported_gpus),
                    'devices': all_gpus,
                    'supported_devices': supported_gpus,
                    'unsupported_devices': unsupported_gpus
                }
            else:
                info['gpu'] = {
                    'available': False,
                    'total_count': 0,
                    'supported_count': 0,
                    'unsupported_count': 0,
                    'devices': [],
                    'supported_devices': [],
                    'unsupported_devices': []
                }
        except ImportError:
            info['pytorch'] = {'error': 'PyTorch未安装'}
            info['gpu'] = {'available': False}
        
        # MinerU配置
        try:
            from mineru.utils.config_reader import get_device
            detected_device = get_device()
            info['mineru_config'] = {
                'detected_device': detected_device,
                'model_source': os.environ.get('MINERU_MODEL_SOURCE', '未设置'),
                'config_file': os.environ.get('MINERU_TOOLS_CONFIG_JSON', '未设置')
            }
        except Exception as e:
            info['mineru_config'] = {'error': str(e)}
        
        return info
    
    def log_system_info(self):
        """输出系统配置信息到日志（增强版）"""
        self.log("", switch_to_log=True)
        self.log("=" * 80, switch_to_log=True)
        self.log("📋 系统配置信息（完整报告）", switch_to_log=True)
        self.log("=" * 80, switch_to_log=True)
        
        info = self.get_system_info()
        
        # 平台信息
        self.log("\n🖥️  平台信息:", switch_to_log=True)
        self.log(f"   - 操作系统: {info['platform']['system']} {info['platform']['release']}", switch_to_log=True)
        if 'platform_string' in info['platform']:
            platform_str = info['platform']['platform_string']
            if len(platform_str) > 100:
                platform_str = platform_str[:100] + "..."
            self.log(f"   - 系统版本: {platform_str}", switch_to_log=True)
        self.log(f"   - 架构: {info['platform']['machine']}", switch_to_log=True)
        self.log(f"   - 处理器: {info['platform']['processor']}", switch_to_log=True)
        
        # CPU信息
        self.log("\n⚙️  CPU信息:", switch_to_log=True)
        if 'error' in info['cpu']:
            self.log(f"   - {info['cpu']['error']}", switch_to_log=True)
        else:
            # 显示CPU型号（优先显示brand，如果没有则显示model）
            cpu_model_display = info['cpu'].get('brand') or info['cpu'].get('model') or info['cpu'].get('processor_name', '未知')
            self.log(f"   - CPU型号: {cpu_model_display}", switch_to_log=True)
            self.log(f"   - 物理核心数: {info['cpu']['physical_cores']}", switch_to_log=True)
            self.log(f"   - 逻辑核心数: {info['cpu']['logical_cores']}", switch_to_log=True)
            if info['cpu']['current_freq_mhz']:
                self.log(f"   - 当前频率: {info['cpu']['current_freq_mhz']} MHz", switch_to_log=True)
            if info['cpu']['max_freq_mhz']:
                self.log(f"   - 最大频率: {info['cpu']['max_freq_mhz']} MHz", switch_to_log=True)
            self.log(f"   - CPU使用率: {info['cpu']['usage_percent']}%", switch_to_log=True)
            self.log(f"   - 架构: {info['cpu']['architecture']}", switch_to_log=True)
        
        # 内存信息
        self.log("\n💾 内存信息:", switch_to_log=True)
        if 'error' in info['memory']:
            self.log(f"   - {info['memory']['error']}", switch_to_log=True)
        else:
            self.log(f"   - 总内存: {info['memory']['total_gb']} GB", switch_to_log=True)
            self.log(f"   - 可用内存: {info['memory']['available_gb']} GB", switch_to_log=True)
            self.log(f"   - 已用内存: {info['memory']['used_gb']} GB ({info['memory']['usage_percent']}%)", switch_to_log=True)
            if info['memory']['swap_total_gb'] > 0:
                self.log(f"   - 虚拟内存: {info['memory']['swap_total_gb']} GB (已用: {info['memory']['swap_used_gb']} GB, {info['memory']['swap_usage_percent']}%)", switch_to_log=True)
        
        # 磁盘信息
        self.log("\n💿 磁盘信息:", switch_to_log=True)
        if 'error' in info['disk']:
            self.log(f"   - {info['disk']['error']}", switch_to_log=True)
        else:
            self.log(f"   - 总容量: {info['disk']['total_gb']} GB", switch_to_log=True)
            self.log(f"   - 已用空间: {info['disk']['used_gb']} GB ({info['disk']['usage_percent']}%)", switch_to_log=True)
            self.log(f"   - 可用空间: {info['disk']['free_gb']} GB", switch_to_log=True)
            if info['disk']['read_mb']:
                self.log(f"   - 累计读取: {info['disk']['read_mb']} MB", switch_to_log=True)
            if info['disk']['write_mb']:
                self.log(f"   - 累计写入: {info['disk']['write_mb']} MB", switch_to_log=True)
        
        # Python信息
        self.log("\n🐍 Python信息:", switch_to_log=True)
        self.log(f"   - 版本: {info['python']['version']}", switch_to_log=True)
        self.log(f"   - 实现: {info['python']['implementation']}", switch_to_log=True)
        self.log(f"   - 编译器: {info['python']['compiler']}", switch_to_log=True)
        self.log(f"   - 可执行文件: {info['python']['executable']}", switch_to_log=True)
        
        # 依赖库版本
        self.log("\n📦 依赖库版本:", switch_to_log=True)
        for dep_name, dep_version in info['dependencies'].items():
            status = "✅" if dep_version != "未安装" and dep_version != "未知" else "❌"
            self.log(f"   - {status} {dep_name}: {dep_version}", switch_to_log=True)
        
        # PyTorch信息
        self.log("\n🔥 PyTorch信息:", switch_to_log=True)
        if 'error' in info['pytorch']:
            self.log(f"   - {info['pytorch']['error']}", switch_to_log=True)
        else:
            self.log(f"   - 版本: {info['pytorch']['version']}", switch_to_log=True)
            self.log(f"   - CUDA/HIP可用: {'是' if info['pytorch']['cuda_available'] else '否'}", switch_to_log=True)
            if info['pytorch']['cuda_version']:
                self.log(f"   - CUDA版本: {info['pytorch']['cuda_version']}", switch_to_log=True)
            if info['pytorch']['hip_version']:
                self.log(f"   - HIP版本: {info['pytorch']['hip_version']} (AMD ROCm)", switch_to_log=True)
            if info['pytorch']['mps_available']:
                self.log("   - MPS可用: 是 (Apple Silicon)", switch_to_log=True)
            if info['pytorch']['xpu_available']:
                self.log("   - XPU可用: 是 (Intel GPU)", switch_to_log=True)
        
        # GPU信息（增强 - 显示所有GPU，包括不支持的）
        self.log("\n🎮 GPU信息:", switch_to_log=True)
        self.log(f"   - 检测到GPU总数: {info['gpu'].get('total_count', 0)}", switch_to_log=True)
        self.log(f"   - 支持的GPU: {info['gpu'].get('supported_count', 0)}", switch_to_log=True)
        self.log(f"   - 不支持的GPU: {info['gpu'].get('unsupported_count', 0)}", switch_to_log=True)
        
        # 显示支持的GPU
        if info['gpu'].get('supported_devices'):
            self.log("\n   ✅ 支持的GPU:", switch_to_log=True)
            for gpu in info['gpu']['supported_devices']:
                gpu_index = gpu.get('index', '?')
                gpu_model = gpu.get('model') or gpu.get('name', '未知')
                support_type = gpu.get('support_type', '未知')
                self.log(f"\n   📱 GPU {gpu_index} ({support_type}):", switch_to_log=True)
                self.log(f"      - 型号: {gpu_model}", switch_to_log=True)
                if 'memory_total_gb' in gpu:
                    self.log(f"      - 总显存: {gpu['memory_total_gb']} GB", switch_to_log=True)
                if gpu.get('memory_allocated_gb') is not None:
                    self.log(f"      - 已分配显存: {gpu['memory_allocated_gb']} GB", switch_to_log=True)
                if gpu.get('memory_reserved_gb') is not None:
                    self.log(f"      - 已保留显存: {gpu['memory_reserved_gb']} GB", switch_to_log=True)
                if 'compute_capability' in gpu and gpu['compute_capability'] != 'N/A':
                    self.log(f"      - 计算能力: {gpu['compute_capability']}", switch_to_log=True)
                if gpu.get('multiprocessor_count'):
                    self.log(f"      - 多处理器数量: {gpu['multiprocessor_count']}", switch_to_log=True)
        
        # 显示不支持的GPU
        if info['gpu'].get('unsupported_devices'):
            self.log("\n   ❌ 不支持的GPU:", switch_to_log=True)
            for gpu in info['gpu']['unsupported_devices']:
                gpu_model = gpu.get('model') or gpu.get('name', '未知')
                support_type = gpu.get('support_type', '不支持')
                self.log(f"\n   📱 {gpu_model}:", switch_to_log=True)
                self.log(f"      - 状态: {support_type}", switch_to_log=True)
                if 'adapter_ram_mb' in gpu and gpu['adapter_ram_mb']:
                    self.log(f"      - 显存: {gpu['adapter_ram_mb']} MB", switch_to_log=True)
                if 'driver_version' in gpu and gpu['driver_version']:
                    self.log(f"      - 驱动版本: {gpu['driver_version']}", switch_to_log=True)
        
        if not info['gpu'].get('available'):
            if info['gpu'].get('total_count', 0) == 0:
                self.log("\n   - 未检测到GPU设备", switch_to_log=True)
            else:
                self.log("\n   - 警告: 检测到GPU但PyTorch不支持，将使用CPU模式", switch_to_log=True)
            self.log("   - 提示: 如需使用GPU，请安装PyTorch ROCm版本（AMD）或CUDA版本（NVIDIA）", switch_to_log=True)
        
        # MinerU配置
        self.log("\n⚙️  MinerU配置:", switch_to_log=True)
        if 'error' in info['mineru_config']:
            self.log(f"   - {info['mineru_config']['error']}", switch_to_log=True)
        else:
            self.log(f"   - 自动检测设备: {info['mineru_config']['detected_device']}", switch_to_log=True)
            self.log(f"   - 模型来源: {info['mineru_config']['model_source']}", switch_to_log=True)
            if info['mineru_config']['config_file'] != '未设置':
                self.log(f"   - 配置文件: {info['mineru_config']['config_file']}", switch_to_log=True)
        
        self.log("", switch_to_log=True)
        self.log("=" * 80, switch_to_log=True)
    
    def log_selected_config(self):
        """输出当前选择的配置模式"""
        self.log("", switch_to_log=True)
        self.log("=" * 60, switch_to_log=True)
        self.log("⚙️  当前选择配置", switch_to_log=True)
        self.log("=" * 60, switch_to_log=True)
        
        # 后端
        backend = self.backend_var.get()
        self.log(f"   - 后端: {backend}", switch_to_log=True)
        
        # 解析方法（从显示名称中提取实际代码）
        method_display = self.method_var.get()
        if 'auto' in method_display:
            method = 'auto'
        elif 'txt' in method_display:
            method = 'txt'
        elif 'ocr' in method_display:
            method = 'ocr'
        else:
            method = method_display
        self.log(f"   - 解析方法: {method}", switch_to_log=True)
        
        # 语言（从显示名称中提取实际代码）
        lang_display = self.lang_var.get()
        lang = lang_display.split()[0] if ' ' in lang_display else lang_display  # 提取代码部分
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
        
        # 输出系统配置信息
        self.log_system_info()
        
        # 输出当前选择配置
        self.log_selected_config()

        # 在开始处理前进行内存清理
        self.log("🧹 正在准备处理环境...", switch_to_log=True)
        self._force_gc_and_cleanup()

        # 检查并提示GPU加速状态
        self.check_and_log_gpu_status()

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

                # 获取下一个待处理任务
                with self.queue_lock:
                    pending_tasks = [t for t in self.task_queue if t.status == TaskStatus.PENDING]
                    if not pending_tasks:
                        break

                    task = pending_tasks[0]
                    task.status = TaskStatus.PROCESSING
                    task.start_time = datetime.now()
                    task_index = self.task_queue.index(task)
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
                    import time
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

                    # 显示完成信息，包含时间统计
                    if task.page_count > 0:
                        time_info = f"（{task.page_count}页，总耗时: {task.total_time:.1f}秒，平均: {task.time_per_page:.2f}秒/页）"
                    else:
                        time_info = f"（总耗时: {task.total_time:.1f}秒）"
                    self.log(f"✅ 任务 #{task_index + 1} 完成: {task.file_name} {time_info}", switch_to_log=True)
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)[:200]  # 限制错误信息长度
                    task.end_time = datetime.now()
                    self.log(f"❌ 任务 #{task_index + 1} 失败: {task.file_name}", switch_to_log=True)
                    self.log(f"   错误: {str(e)}", switch_to_log=True)
                    # 使用logger记录详细异常信息（会自动输出到GUI）
                    logger.exception(f"任务 #{task_index + 1} 处理失败: {task.file_name}")

                # 更新显示（使用线程安全的方法）
                self.schedule_gui_update(self.update_queue_display)

                # 检查是否取消或关闭
                if not self.is_converting or self._shutdown_event.is_set():
                    if task.status == TaskStatus.PROCESSING:
                        task.status = TaskStatus.CANCELLED
                    break
            
            # 完成
            with self.queue_lock:
                completed = sum(1 for t in self.task_queue if t.status == TaskStatus.COMPLETED)
                failed = sum(1 for t in self.task_queue if t.status == TaskStatus.FAILED)
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
            self.log(f"❌ 队列处理出错: {str(e)}", switch_to_log=True)
            # 使用logger记录详细异常信息（会自动输出到GUI）
            logger.exception("队列处理过程中发生异常")
            self.status_var.set("队列处理失败")
        finally:
            # 恢复UI状态
            self.is_converting = False
            self.convert_btn.configure(state="normal")
            self.add_to_queue_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.current_task_index = -1
    
    def process_single_task(self, task: ConversionTask):
        """处理单个任务"""
        # 获取配置参数
        output_dir = self.output_path_var.get()
        backend = self.backend_var.get()

        # 从显示名称中提取实际的方法代码
        method_display = self.method_var.get()
        if 'auto' in method_display:
            method = 'auto'
        elif 'txt' in method_display:
            method = 'txt'
        elif 'ocr' in method_display:
            method = 'ocr'
        else:
            method = method_display

        # 从显示名称中提取实际的语言代码
        lang_display = self.lang_var.get()
        lang = lang_display.split()[0] if ' ' in lang_display else lang_display  # 提取代码部分
        formula_enable = self.formula_var.get()
        table_enable = self.table_var.get()

        # 页码范围
        try:
            start_page_id = int(self.start_page_var.get()) if self.start_page_var.get() else 0
        except ValueError:
            start_page_id = 0

        try:
            end_page_id = int(self.end_page_var.get()) if self.end_page_var.get() else None
        except ValueError:
            end_page_id = None

        # 设备模式
        device_mode = self.device_var.get().strip() or None
        if device_mode:
            os.environ['MINERU_DEVICE_MODE'] = device_mode

        # 输出实际运行模式（在设备模式设置后）
        self.log_actual_runtime_mode()

        # 读取文件并确保资源管理
        pdf_bytes = None
        try:
            pdf_bytes = read_fn(task.file_path)
            file_name = task.file_name

            # 检查关闭事件
            if self._shutdown_event.is_set():
                return

            # 更新进度
            task.progress = 0.2
            self.schedule_gui_update(self.update_queue_display)

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

            # 完成
            task.progress = 1.0
            self.schedule_gui_update(self.update_queue_display)

        except Exception as e:
            # 重新抛出异常，让上层处理
            raise e
        finally:
            # 清理资源
            if pdf_bytes:
                # 如果pdf_bytes有close方法，调用它
                try:
                    if hasattr(pdf_bytes, 'close'):
                        pdf_bytes.close()
                except Exception:
                    pass
    
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
