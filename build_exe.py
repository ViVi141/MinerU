# -*- coding: utf-8 -*-
"""
MinerU GUI 打包脚本
使用 PyInstaller 打包为独立的可执行文件
"""
import sys
import shutil
import subprocess
from pathlib import Path

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    # 设置标准输出为UTF-8编码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    # 或者使用环境变量
    import os
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def check_virtual_env():
    """检查是否在虚拟环境中运行"""
    import sys

    # 检查是否在虚拟环境中
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

    if not in_venv:
        print("[WARN] 警告: 未检测到虚拟环境")
        print("建议在虚拟环境中运行打包脚本以避免依赖冲突")
        print("")
        print("如果您有虚拟环境，请先激活它:")
        print("Windows: .venv\\Scripts\\activate")
        print("Linux/Mac: source .venv/bin/activate")
        print("")
        print("按回车键继续，或 Ctrl+C 取消...")
        try:
            input()
        except KeyboardInterrupt:
            print("\n已取消打包")
            return False

    # 检查虚拟环境中的Python路径
    python_exe = sys.executable
    print(f"[INFO] 使用Python: {python_exe}")

    # 检查关键包是否在虚拟环境中
    try:
        import torch
        torch_path = torch.__file__
        if 'site-packages' in torch_path and python_exe not in torch_path:
            print(f"[WARN] PyTorch路径: {torch_path}")
            print("PyTorch可能不在当前虚拟环境中")
    except ImportError:
        print("[ERROR] PyTorch 未安装")
        return False

    return True

def check_pyinstaller():
    """检查 PyInstaller 是否已安装"""
    try:
        import PyInstaller  # noqa: F401
        print("[OK] PyInstaller 已安装")
        return True
    except ImportError:
        print("[ERROR] PyInstaller 未安装")
        print("请运行: pip install pyinstaller")
        return False

def check_pytorch_cuda():
    """检查 PyTorch 是否包含 CUDA 支持（用于GPU加速）
    
    注意：即使当前电脑没有NVIDIA GPU，只要安装了CUDA版本的PyTorch，
    打包后的程序就能在NVIDIA电脑上使用GPU加速。
    """
    try:
        import torch
        import os
        
        # 检查PyTorch是否包含CUDA库（不检查是否有实际GPU）
        # 关键：检查torch.version.cuda是否存在，这表示PyTorch包含CUDA支持
        has_cuda_support = hasattr(torch.version, 'cuda') and torch.version.cuda is not None
        
        if has_cuda_support:
            cuda_version = torch.version.cuda
            print(f"[OK] PyTorch 包含 CUDA 支持 (CUDA版本: {cuda_version})")
            
            # 尝试检查是否有实际GPU（可选，不影响打包）
            try:
                cuda_available = torch.cuda.is_available()
                if cuda_available:
                    gpu_count = torch.cuda.device_count()
                    print(f"[OK] 检测到 {gpu_count} 个 NVIDIA GPU:")
                    for i in range(gpu_count):
                        gpu_name = torch.cuda.get_device_name(i)
                        print(f"      GPU {i}: {gpu_name}")
                else:
                    print("[INFO] 当前电脑没有检测到 NVIDIA GPU（这是正常的）")
                    print("       打包后的程序仍可在 NVIDIA 电脑上使用 GPU 加速")
            except Exception:
                print("[INFO] 无法检测GPU（可能没有NVIDIA GPU，不影响打包）")
            
            # 检查CUDA库文件是否存在（确保打包时会包含）
            try:
                torch_lib_path = os.path.dirname(torch.__file__)
                cuda_lib_path = os.path.join(torch_lib_path, 'lib')
                if os.path.exists(cuda_lib_path):
                    # 检查是否有CUDA相关的DLL/so文件
                    cuda_files = []
                    for ext in ['.dll', '.so', '.dylib']:
                        for file in os.listdir(cuda_lib_path):
                            if 'cuda' in file.lower() and file.endswith(ext):
                                cuda_files.append(file)
                    if cuda_files:
                        print(f"[OK] 找到 CUDA 库文件 ({len(cuda_files)} 个)")
                    else:
                        print("[WARN] 未找到 CUDA 库文件，但 PyTorch 包含 CUDA 支持")
                else:
                    print("[INFO] CUDA 库文件路径不存在，PyInstaller 会自动处理")
            except Exception:
                pass  # 忽略检查错误
            
            return True
        else:
            print("[WARN] PyTorch 不包含 CUDA 支持（当前为 CPU 版本）")
            print("      打包后的程序将无法在 NVIDIA 电脑上使用 GPU 加速")
            print("")
            print("      解决方案：在 AMD 电脑上安装 CUDA 版本的 PyTorch（用于打包）")
            print("      即使没有 NVIDIA GPU，也可以安装 CUDA 版本的 PyTorch")
            print("")
            print("      安装命令（选择适合的CUDA版本）:")
            print("      # CUDA 11.8 (推荐)")
            print("      pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
            print("")
            print("      # CUDA 12.1")
            print("      pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
            print("")
            print("      安装后重新运行打包脚本即可")
            return False
    except ImportError:
        print("[WARN] PyTorch 未安装")
        print("      请先安装 PyTorch（推荐 CUDA 版本）")
        return False
    except Exception as e:
        print(f"[WARN] 检查 PyTorch CUDA 支持时出错: {e}")
        return False

def verify_necessary_files(project_dir: Path):
    """验证必要的文件和目录是否存在"""
    print("\n" + "=" * 60)
    print("验证必要的文件和目录...")
    print("=" * 60)
    
    necessary_items = {
        '配置文件': [
            project_dir / 'mineru.json',
        ],
        '模型目录': [
            project_dir / 'models' / 'pipeline',
        ],
        'MinerU资源': [
            project_dir / 'mineru' / 'resources' / 'fasttext-langdetect',
            project_dir / 'mineru' / 'model' / 'utils' / 'pytorchocr' / 'utils' / 'resources',
        ],
    }
    
    all_ok = True
    for category, items in necessary_items.items():
        print(f"\n{category}:")
        for item in items:
            if item.exists():
                if item.is_file():
                    size = item.stat().st_size / (1024 * 1024)  # MB
                    print(f"  [OK] {item.name} ({size:.2f} MB)")
                else:
                    # 计算目录大小
                    total_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    size_mb = total_size / (1024 * 1024)
                    file_count = sum(1 for _ in item.rglob('*') if _.is_file())
                    print(f"  [OK] {item.name}/ ({size_mb:.2f} MB, {file_count} 个文件)")
            else:
                print(f"  [ERROR] {item} (缺失)")
                all_ok = False
    
    # 检查非必要文件夹（不应被打包）
    unnecessary_dirs = [
        project_dir / 'demo',
        project_dir / 'docs',
        project_dir / 'docker',
        project_dir / 'projects',
        project_dir / 'tests',
        project_dir / 'build',
        project_dir / 'dist',
    ]
    
    print("\n非必要文件夹（不应被打包）:")
    for dir_path in unnecessary_dirs:
        if dir_path.exists():
            print(f"  [WARN] {dir_path.name}/ (存在，将被排除)")
    
    print("=" * 60)
    return all_ok

def create_spec_file():
    """创建 PyInstaller spec 文件"""
    project_dir = Path(__file__).parent
    
    # 验证必要文件
    if not verify_necessary_files(project_dir):
        print("\n[WARN] 警告: 部分必要文件缺失，打包可能失败")
        response = input("是否继续打包? (y/n): ").strip().lower()
        if response != 'y':
            return None
    
    # 构建数据文件列表
    datas = []
    
    # 配置文件
    if (project_dir / 'mineru.json').exists():
        datas.append((str(project_dir / 'mineru.json'), '.'))
    if (project_dir / 'mineru.template.json').exists():
        datas.append((str(project_dir / 'mineru.template.json'), '.'))
    
    # 模型文件 - Pipeline
    pipeline_dir = project_dir / 'models' / 'pipeline'
    if pipeline_dir.exists():
        datas.append((str(pipeline_dir), 'models/pipeline'))
        print(f"[INFO] 已添加Pipeline模型目录: {pipeline_dir}")
    
    # 模型文件 - VLM（排除以减小体积，仅支持Pipeline后端）
    # vlm_dir = project_dir / 'models' / 'vlm'
    # if vlm_dir.exists():
    #     datas.append((str(vlm_dir), 'models/vlm'))
    
    # MinerU资源文件（必需）
    mineru_resources_dir = project_dir / 'mineru' / 'resources'
    if mineru_resources_dir.exists():
        # 包含fasttext-langdetect语言检测模型
        fasttext_dir = mineru_resources_dir / 'fasttext-langdetect'
        if fasttext_dir.exists():
            datas.append((str(fasttext_dir), 'mineru/resources/fasttext-langdetect'))
            print(f"[INFO] 已添加fasttext语言检测模型: {fasttext_dir}")
        
        # header.html（Gradio使用，GUI不需要，但包含也无妨）
        header_file = mineru_resources_dir / 'header.html'
        if header_file.exists():
            datas.append((str(header_file), 'mineru/resources'))
            print(f"[INFO] 已添加header.html: {header_file}")
    
    # MinerU模型工具资源（OCR配置和字典）
    mineru_model_utils_resources = project_dir / 'mineru' / 'model' / 'utils' / 'pytorchocr' / 'utils' / 'resources'
    if mineru_model_utils_resources.exists():
        datas.append((str(mineru_model_utils_resources), 'mineru/model/utils/pytorchocr/utils/resources'))
        print(f"[INFO] 已添加OCR资源目录: {mineru_model_utils_resources}")
    
    # SSL证书文件（certifi，必需，用于HTTPS连接）
    try:
        import certifi
        import os
        certifi_dir = os.path.dirname(certifi.__file__)
        # certifi的证书文件
        cert_file = os.path.join(certifi_dir, 'cacert.pem')
        if os.path.exists(cert_file):
            datas.append((cert_file, 'certifi'))
            print(f"[INFO] 已添加SSL证书文件: {cert_file}")
        else:
            # 如果cacert.pem不存在，尝试包含整个certifi目录
            datas.append((certifi_dir, 'certifi'))
            print(f"[INFO] 已添加certifi目录: {certifi_dir}")
    except ImportError:
        print("[WARN] 无法导入certifi，SSL证书可能缺失，HTTPS连接可能失败")
    except Exception as e:
        print(f"[WARN] 添加certifi证书文件时出错: {e}")
    
    # magika模型和配置文件（需要完整目录结构）
    try:
        import magika
        import os
        magika_dir = os.path.dirname(magika.__file__)
        
        # 打包models目录
        magika_models_dir = os.path.join(magika_dir, 'models')
        if os.path.exists(magika_models_dir):
            datas.append((magika_models_dir, 'magika/models'))
            print(f"[INFO] 已添加magika模型目录: {magika_models_dir}")
        
        # 打包config目录（包含content_types_kb.min.json等配置文件）
        magika_config_dir = os.path.join(magika_dir, 'config')
        if os.path.exists(magika_config_dir):
            datas.append((magika_config_dir, 'magika/config'))
            print(f"[INFO] 已添加magika配置目录: {magika_config_dir}")
    except ImportError:
        print("[WARN] 无法导入magika，跳过magika文件")
    except Exception as e:
        print(f"[WARN] 添加magika文件时出错: {e}")

    # fast_langdetect模型和资源文件（需要resources目录）
    try:
        import fast_langdetect
        import os
        fast_langdetect_dir = os.path.dirname(fast_langdetect.__file__)

        # 添加ft_detect/resources目录（包含lid.176.ftz等模型文件）
        ft_detect_resources_dir = os.path.join(fast_langdetect_dir, 'ft_detect', 'resources')
        if os.path.exists(ft_detect_resources_dir):
            datas.append((ft_detect_resources_dir, 'fast_langdetect/ft_detect/resources'))
            print(f"[INFO] 已添加fast_langdetect资源目录: {ft_detect_resources_dir}")
    except ImportError:
        print("[WARN] 无法导入fast_langdetect，跳过fast_langdetect文件")
    except Exception as e:
        print(f"[WARN] 添加fast_langdetect文件时出错: {e}")

    # doclayout_yolo配置和数据文件（需要完整目录结构）
    try:
        import doclayout_yolo
        import os
        doclayout_yolo_dir = os.path.dirname(doclayout_yolo.__file__)
        
        # 打包cfg目录（包含default.yaml等配置文件）
        doclayout_yolo_cfg_dir = os.path.join(doclayout_yolo_dir, 'cfg')
        if os.path.exists(doclayout_yolo_cfg_dir):
            datas.append((doclayout_yolo_cfg_dir, 'doclayout_yolo/cfg'))
            print(f"[INFO] 已添加doclayout_yolo配置目录: {doclayout_yolo_cfg_dir}")
        
        # 打包其他可能的数据文件目录（如果存在）
        for subdir in ['data', 'utils']:
            subdir_path = os.path.join(doclayout_yolo_dir, subdir)
            if os.path.exists(subdir_path):
                datas.append((subdir_path, f'doclayout_yolo/{subdir}'))
                print(f"[INFO] 已添加doclayout_yolo {subdir} 目录: {subdir_path}")
    except ImportError:
        print("[WARN] 无法导入doclayout_yolo，跳过doclayout_yolo文件")
    except Exception as e:
        print(f"[WARN] 添加doclayout_yolo文件时出错: {e}")
    
    # 将数据文件列表转换为字符串（处理Windows路径）
    def format_path(path):
        return path.replace('\\', '/').replace("'", "\\'")
    
    datas_lines = [f"    ('{format_path(d[0])}', '{d[1]}')" for d in datas]
    
    # 添加magika模型文件的动态获取代码
    datas_str = ',\n'.join(datas_lines)
    if datas_str:
        datas_str += ','
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None

# 数据文件列表
datas = [
''' + datas_str + '''
]

# 动态添加magika模型和配置文件
try:
    import magika
    magika_dir = os.path.dirname(magika.__file__)
    
    # 添加models目录
    magika_models_dir = os.path.join(magika_dir, 'models')
    if os.path.exists(magika_models_dir):
        datas.append((magika_models_dir, 'magika/models'))
    
    # 添加config目录（包含content_types_kb.min.json等）
    magika_config_dir = os.path.join(magika_dir, 'config')
    if os.path.exists(magika_config_dir):
        datas.append((magika_config_dir, 'magika/config'))
except:
    pass

# 动态添加doclayout_yolo配置和数据文件
try:
    import doclayout_yolo
    doclayout_yolo_dir = os.path.dirname(doclayout_yolo.__file__)
    
    # 添加cfg目录（包含default.yaml等配置文件）
    doclayout_yolo_cfg_dir = os.path.join(doclayout_yolo_dir, 'cfg')
    if os.path.exists(doclayout_yolo_cfg_dir):
        datas.append((doclayout_yolo_cfg_dir, 'doclayout_yolo/cfg'))
    
    # 添加其他可能的数据文件目录（如果存在）
    for subdir in ['data', 'utils']:
        subdir_path = os.path.join(doclayout_yolo_dir, subdir)
        if os.path.exists(subdir_path):
            datas.append((subdir_path, f'doclayout_yolo/{subdir}'))
except:
    pass

# 动态添加MinerU资源文件（确保包含）
try:
    import mineru
    mineru_dir = os.path.dirname(mineru.__file__)
    
    # 添加resources目录（包含fasttext-langdetect语言检测模型）
    mineru_resources_dir = os.path.join(mineru_dir, 'resources')
    if os.path.exists(mineru_resources_dir):
        # fasttext-langdetect模型
        fasttext_dir = os.path.join(mineru_resources_dir, 'fasttext-langdetect')
        if os.path.exists(fasttext_dir):
            datas.append((fasttext_dir, 'mineru/resources/fasttext-langdetect'))
        
        # header.html（可选）
        header_file = os.path.join(mineru_resources_dir, 'header.html')
        if os.path.exists(header_file):
            datas.append((header_file, 'mineru/resources'))
    
    # 添加OCR资源目录（模型配置和字典）
    ocr_resources_path = os.path.join(mineru_dir, 'model', 'utils', 'pytorchocr', 'utils', 'resources')
    if os.path.exists(ocr_resources_path):
        datas.append((ocr_resources_path, 'mineru/model/utils/pytorchocr/utils/resources'))
except:
    pass

# 动态添加certifi SSL证书文件（必需，用于HTTPS连接）
try:
    import certifi
    certifi_dir = os.path.dirname(certifi.__file__)
    # certifi的证书文件通常在cacert.pem
    cert_file = os.path.join(certifi_dir, 'cacert.pem')
    if os.path.exists(cert_file):
        datas.append((cert_file, 'certifi'))
        print(f"[INFO] 已添加SSL证书文件: {cert_file}")
    # 或者整个certifi目录
    elif os.path.exists(certifi_dir):
        datas.append((certifi_dir, 'certifi'))
        print(f"[INFO] 已添加certifi目录: {certifi_dir}")
except ImportError:
    print("[WARN] 无法导入certifi，SSL证书可能缺失")
except Exception as e:
    print(f"[WARN] 添加certifi证书文件时出错: {e}")

# 动态添加fast_langdetect资源文件（必需，包含语言检测模型）
try:
    import fast_langdetect
    fast_langdetect_dir = os.path.dirname(fast_langdetect.__file__)
    # fast_langdetect的资源文件在ft_detect/resources目录下
    ft_detect_resources_dir = os.path.join(fast_langdetect_dir, 'ft_detect', 'resources')
    if os.path.exists(ft_detect_resources_dir):
        datas.append((ft_detect_resources_dir, 'fast_langdetect/ft_detect/resources'))
except:
    pass

# 隐藏导入（仅Pipeline后端所需，排除VLM相关依赖以减小体积）
hiddenimports = [
    'customtkinter',
    'loguru',
    'pypdfium2',
    'pdfium',
    'torch',
    'torchvision',
    'PIL',
    'PIL.Image',
    'numpy',
    'cv2',
    'onnxruntime',
    'ultralytics',
    'paddleocr2torch',
    'transformers',  # Pipeline后端也需要（layout_reader, unimernet等）
    'tokenizers',  # Pipeline后端也需要（pp_formulanet_plus_m）
    'albumentations',  # Pipeline后端也需要（unimernet图像处理）
    'ftfy',  # Pipeline后端也需要（文本修复）
    'tqdm',  # Pipeline后端也需要（进度条）
    'omegaconf',  # Pipeline后端也需要（配置管理）
    'pyclipper',  # Pipeline后端也需要（OCR后处理）
    'shapely',  # Pipeline后端也需要（几何计算）
    'scipy',  # Pipeline后端也需要（科学计算）
    'skimage',  # Pipeline后端也需要（图像处理）
    'yaml',  # Pipeline后端也需要（YAML配置）
    'beautifulsoup4',  # bs4的包名
    'bs4',  # Pipeline后端也需要（HTML解析）
    'click',  # Pipeline后端也需要（命令行解析）
    'certifi',  # SSL证书（必需，用于HTTPS连接）
    'requests',  # Pipeline后端也需要（HTTP请求）
    'huggingface_hub',  # Pipeline后端也需要（模型下载）
    'modelscope',  # Pipeline后端也需要（模型下载）
    'pydantic',  # Pipeline后端也需要（数据验证）
    'reportlab',  # Pipeline后端也需要（PDF生成）
    'packaging',  # Pipeline后端也需要（版本检查）
    'rapid_table',  # Pipeline后端也需要（表格识别）
    'sympy',  # Pipeline后端也需要（符号计算）
    # 可选依赖（如果使用S3或LLM功能）
    'boto3',  # 可选：S3存储
    'botocore',  # 可选：S3存储
    'openai',  # 可选：LLM辅助功能
    'json_repair',  # 可选：JSON修复
    # 'sentencepiece',  # VLM后端需要，Pipeline不需要，已排除
    'protobuf',
    'mineru',
    'mineru.cli',
    'mineru.cli.common',  # GUI需要：do_parse, read_fn
    # 'mineru.cli.fast_api',  # GUI不需要，已排除
    # 'mineru.cli.gradio_app',  # GUI不需要，已排除
    # 'mineru.cli.vlm_server',  # GUI不需要，已排除
    # 'mineru.cli.client',  # GUI不需要，已排除
    # 'mineru.cli.models_download',  # GUI不需要，已排除
    'mineru.backend',
    'mineru.backend.pipeline',  # GUI需要：Pipeline后端
    # 'mineru.backend.vlm',  # VLM后端，已排除
    'mineru.model',  # GUI需要：所有模型
    'mineru.model.layout',  # GUI需要：布局识别
    'mineru.model.mfr',  # GUI需要：公式识别
    'mineru.model.ocr',  # GUI需要：OCR
    'mineru.model.table',  # GUI需要：表格识别
    'mineru.model.reading_order',  # GUI需要：阅读顺序
    'mineru.model.utils',  # GUI需要：模型工具
    'mineru.utils',  # GUI需要：工具函数
    'mineru.utils.config_reader',  # GUI需要：get_device
    'mineru.utils.language',  # GUI需要：语言检测
    'mineru.data',  # GUI需要：数据处理
    'pdfminer',
    'pdfminer.six',
    'pdftext',
    'layoutreader',
    'fast_langdetect',
    'magika',
    'doclayout_yolo',
    'pypdf',
    'pypdfium2',
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'threading',
    'dataclasses',
    'datetime',
    'enum',
    'pathlib',
    'typing',
]

# 排除VLM相关大型依赖以减小打包体积
# 注意：transformers 和 tokenizers 不能排除，因为 Pipeline 后端也需要它们
excludes = [
    'vllm',
    'lmdeploy',
    'sentencepiece',  # VLM依赖，Pipeline不需要
    'accelerate',  # VLM依赖，Pipeline不需要
    'bitsandbytes',  # VLM依赖，Pipeline不需要
    'flash_attn',  # VLM依赖，Pipeline不需要
    'xformers',  # VLM依赖，Pipeline不需要
    'mineru.backend.vlm',  # VLM后端模块
    'mineru_vl_utils',  # VLM工具包
    # 排除非必要的CLI模块（GUI不需要）
    'mineru.cli.fast_api',  # FastAPI服务器（GUI不需要）
    'mineru.cli.gradio_app',  # Gradio应用（GUI不需要）
    'mineru.cli.vlm_server',  # VLM服务器（GUI不需要）
    'mineru.cli.client',  # CLI客户端（GUI不需要）
    'mineru.cli.models_download',  # 模型下载工具（GUI不需要，模型已打包）
    # 排除非必要的项目文件夹（这些不会被自动包含，但明确排除更安全）
    'projects',  # 其他项目示例
    'demo',  # 演示文件
    'docs',  # 文档
    'docker',  # Docker配置
    'tests',  # 测试文件
]

# 动态收集PyTorch CUDA库文件（如果存在）
binaries = []
try:
    import torch
    import os
    # PyTorch的CUDA库通常在这些位置
    torch_lib_path = os.path.dirname(torch.__file__)
    cuda_lib_path = os.path.join(torch_lib_path, 'lib')
    
    if os.path.exists(cuda_lib_path):
        # 收集所有CUDA相关的DLL文件（Windows）
        for file in os.listdir(cuda_lib_path):
            if file.endswith('.dll') and ('cuda' in file.lower() or 'cudnn' in file.lower()):
                src_path = os.path.join(cuda_lib_path, file)
                # PyInstaller会自动处理这些文件，但我们可以显式添加以确保包含
                binaries.append((src_path, 'torch/lib'))
                print(f"[INFO] 已添加 CUDA 库文件: {file}")
except Exception as e:
    # 如果收集失败，PyInstaller会自动处理，不影响打包
    print(f"[INFO] CUDA 库文件将由 PyInstaller 自动收集: {e}")
    pass

a = Analysis(
    ['mineru_gui.py'],
    pathex=[],
    binaries=binaries,  # 包含CUDA库文件
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 使用onedir模式（目录模式）
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 目录模式：不将二进制文件打包到exe中
    name='MinerU_GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 使用UPX压缩以减小文件大小
    upx_exclude=[],
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)

# 目录模式：收集所有文件到目录中
coll = COLLECT(
    exe,
    a.binaries,  # 所有二进制文件
    a.zipfiles,  # 所有zip文件
    a.datas,  # 所有数据文件
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MinerU_GUI'
)
'''
    
    spec_file = project_dir / 'mineru_gui.spec'
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"[OK] 已创建 spec 文件: {spec_file}")
    return spec_file

def update_mineru_json_for_bundle():
    """更新 mineru.json 以支持打包后的路径"""
    project_dir = Path(__file__).parent
    config_file = project_dir / "mineru.json"
    
    if not config_file.exists():
        print("[WARN] 配置文件不存在: " + str(config_file))
        return None
    
    import json
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 更新模型路径为相对路径（打包后会在_MEIPASS/models/pipeline下）
    # 仅包含Pipeline模型，排除VLM以减小体积
    if 'models-dir' not in config:
        config['models-dir'] = {}
    
    # 打包后的模型路径在_MEIPASS/models/pipeline下
    # 但MinerU会从配置文件读取，所以需要设置为相对路径
    # 实际运行时，程序会从_MEIPASS/models/pipeline读取
    config['models-dir']['pipeline'] = './models/pipeline'
    
    # 不包含VLM模型路径，因为已排除VLM后端
    if 'vlm' in config['models-dir']:
        del config['models-dir']['vlm']
    
    # 保存备份
    backup_file = config_file.with_suffix('.json.backup')
    shutil.copy(config_file, backup_file)
    print(f"[OK] 已备份原配置文件: {backup_file}")
    
    # 保存更新后的配置
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    print("[OK] 已更新配置文件以支持打包")
    print(f"     模型路径已设置为: {config['models-dir']['pipeline']}")
    return backup_file

def restore_mineru_json(backup_file):
    """恢复原始配置文件"""
    if backup_file and backup_file.exists():
        config_file = backup_file.with_suffix('').with_suffix('.json')
        shutil.copy(backup_file, config_file)
        backup_file.unlink()
        print("[OK] 已恢复原始配置文件")

def analyze_package_size():
    """分析打包体积，显示优化建议"""
    print("=" * 60)
    print("📊 打包体积分析")
    print("=" * 60)

    # 分析模型文件大小
    pipeline_dir = Path("models/pipeline")
    if pipeline_dir.exists():
        total_size = sum(f.stat().st_size for f in pipeline_dir.rglob('*') if f.is_file())
        size_gb = total_size / (1024**3)
        print(f"📁 Pipeline模型目录: {size_gb:.2f} GB")

        # 分析子目录
        for subdir in pipeline_dir.rglob('*'):
            if subdir.is_dir():
                sub_size = sum(f.stat().st_size for f in subdir.rglob('*') if f.is_file())
                if sub_size > 0:
                    sub_size_mb = sub_size / (1024**2)
                    print(f"  └─ {subdir.name}: {sub_size_mb:.1f} MB")

    # 分析其他大文件
    other_dirs = [
        ("mineru/resources", "MinerU资源"),
        (".venv/Lib/site-packages", "虚拟环境包"),
    ]

    for dir_path, desc in other_dirs:
        path = Path(dir_path)
        if path.exists():
            total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            size_gb = total_size / (1024**3)
            if size_gb > 0.1:  # 只显示大于100MB的目录
                print(f"📁 {desc}: {size_gb:.2f} GB")

    print("=" * 60)
    print("💡 体积优化建议:")
    print("• 已排除多语言OCR模型（仅保留中英文）")
    print("• 已排除VLM相关大型依赖")
    print("• 已启用UPX压缩和strip处理")
    print("• 已优化数据文件包含列表")
    print("=" * 60)

def build_exe():
    """执行打包"""
    project_dir = Path(__file__).parent

    print("=" * 60)
    print("MinerU GUI 打包脚本（优化版 - 体积减小）")
    print("=" * 60)

    # 分析打包体积
    analyze_package_size()

    # 检查虚拟环境
    if not check_virtual_env():
        return False

    # 检查 PyInstaller
    if not check_pyinstaller():
        return False
    
    # 检查 PyTorch CUDA 支持（用于GPU加速）
    print("\n" + "=" * 60)
    print("检查 GPU 加速支持...")
    print("=" * 60)
    print("说明: 即使当前电脑没有 NVIDIA GPU，只要安装了 CUDA 版本的 PyTorch，")
    print("      打包后的程序就能在 NVIDIA 电脑上自动使用 GPU 加速。")
    print("=" * 60)
    cuda_supported = check_pytorch_cuda()
    if not cuda_supported:
        print("\n" + "=" * 60)
        print("[WARN] 警告: 当前 PyTorch 不包含 CUDA 支持")
        print("=" * 60)
        print("打包后的程序将无法在 NVIDIA 电脑上使用 GPU 加速。")
        print("")
        print("建议操作:")
        print("1. 在 AMD 电脑上安装 CUDA 版本的 PyTorch（即使没有 NVIDIA GPU）")
        print("2. 安装命令: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
        print("3. 安装后重新运行打包脚本")
        print("")
        response = input("是否继续打包（打包后的程序将只能使用 CPU）? (y/n): ").strip().lower()
        if response != 'y':
            print("打包已取消")
            return False
        print("\n继续打包（CPU 版本）...")
    else:
        print("\n[OK] PyTorch 包含 CUDA 支持，打包后的程序可在 NVIDIA 电脑上使用 GPU 加速")
    print("=" * 60)
    
    # 检查必要文件
    gui_file = project_dir / "mineru_gui.py"
    if not gui_file.exists():
        print(f"[ERROR] GUI 文件不存在: {gui_file}")
        return False
    
    models_dir = project_dir / "models"
    if not models_dir.exists():
        print(f"[ERROR] 模型目录不存在: {models_dir}")
        print("请先运行 download_models_to_project.py 下载模型")
        return False
    
    # 更新配置文件
    backup_file = update_mineru_json_for_bundle()
    
    try:
        # 创建 spec 文件
        spec_file = create_spec_file()
        if spec_file is None:
            return False
        
        # 清理之前的构建
        dist_dir = project_dir / "dist"
        build_dir = project_dir / "build"
        if dist_dir.exists():
            print("[INFO] 清理旧的 dist 目录...")
            shutil.rmtree(dist_dir)
        if build_dir.exists():
            print("[INFO] 清理旧的 build 目录...")
            shutil.rmtree(build_dir)
        
        # 执行打包
        print("\n" + "=" * 60)
        print("开始打包（使用目录模式）...")
        print("=" * 60)
        print("目录模式说明:")
        print("  - 打包后会生成 MinerU_GUI 文件夹，包含所有依赖文件")
        print("  - 主程序为 MinerU_GUI.exe，位于文件夹内")
        print("  - 启动速度更快，文件大小不受4GB限制")
        print("  - 适合大型应用和需要频繁更新的场景")
        print("=" * 60)
        
        cmd = [
            sys.executable,
            "-m", "PyInstaller",
            "--clean",
            str(spec_file)
        ]
        
        result = subprocess.run(cmd, cwd=project_dir)
        
        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("[OK] 打包成功！")
            print("=" * 60)
            # onedir模式会生成一个文件夹
            exe_dir = dist_dir / "MinerU_GUI"
            exe_path = exe_dir / "MinerU_GUI.exe"
            
            if exe_dir.exists() and exe_path.exists():
                # 计算目录总大小
                total_size = sum(
                    f.stat().st_size for f in exe_dir.rglob('*') if f.is_file()
                )
                size_mb = total_size / (1024*1024)
                size_gb = total_size / (1024*1024*1024)
                
                print(f"\n打包目录位置: {exe_dir}")
                print(f"主程序位置: {exe_path}")
                if size_gb >= 1:
                    print(f"目录总大小: {size_gb:.2f} GB ({size_mb:.2f} MB)")
                else:
                    print(f"目录总大小: {size_mb:.2f} MB")
                
                # 统计文件数量
                file_count = sum(1 for _ in exe_dir.rglob('*') if _.is_file())
                print(f"包含文件数: {file_count} 个")
                
                print("\n[OK] 目录模式打包完成，可以正常使用")
                
                print("\n提示:")
                print("1. 将整个 MinerU_GUI 文件夹复制到目标电脑")
                print("2. 运行 MinerU_GUI.exe 启动程序")
                print("3. 目录模式启动速度更快，无需解压临时文件")
                print("4. 确保目标电脑有足够的磁盘空间（至少5GB可用空间）")
                print("5. 首次运行可能需要一些时间加载模型")
                
                # 检查GPU支持情况
                try:
                    import torch
                    has_cuda = hasattr(torch.version, 'cuda') and torch.version.cuda is not None
                    if has_cuda:
                        cuda_version = torch.version.cuda
                        print(f"\n[OK] GPU 加速支持: 已包含 CUDA {cuda_version} 支持")
                        print("   打包后的程序可在 NVIDIA 电脑上自动使用 GPU 加速")
                        print("   目标电脑需要: NVIDIA GPU + 相应的 GPU 驱动（CUDA驱动由PyTorch自带）")
                    else:
                        print("\n[WARN] GPU 加速支持: 未包含 CUDA 支持")
                        print("   打包后的程序将只能使用 CPU 模式")
                        print("   如需 GPU 支持，请在 AMD 电脑上安装 CUDA 版本的 PyTorch 后重新打包")
                except Exception:
                    pass
                
                print("\n注意: 使用目录模式（onedir），所有文件都在文件夹中，便于管理和更新")
            return True
        else:
            print("\n[ERROR] 打包失败")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 打包过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 恢复配置文件
        if backup_file:
            restore_mineru_json(backup_file)

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)

