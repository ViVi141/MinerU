<div align="center" xmlns="http://www.w3.org/1999/html">

## 📌 项目说明

**本项目 Fork 自 [opendatalab/MinerU](https://github.com/opendatalab/MinerU)**

本项目的主要目标是：
- 🎨 **开发一个功能完备且美观的GUI界面**
- 🚀 **实现一键启动，简化使用流程**
- 📋 **支持任务队列功能，可批量处理多个PDF文件**
- ⚡ **支持CPU模式运行，无需GPU也能使用**
- 🌓 **自动跟随系统主题切换（浅色/暗色）**
- 📊 **实时显示处理进度和每页处理时间统计**

**GUI启动方式：**
```bash
python mineru_gui.py
```

---

<!-- logo -->
<p align="center">
  <img src="https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/docs/images/MinerU-logo.png" width="300px" style="vertical-align:middle;">
</p>

<!-- icon -->

[![stars](https://img.shields.io/github/stars/opendatalab/MinerU.svg)](https://github.com/opendatalab/MinerU)
[![PyPI version](https://img.shields.io/pypi/v/mineru)](https://pypi.org/project/mineru/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mineru)](https://pypi.org/project/mineru/)

<!-- language -->

[English](README.md) | [简体中文](README_zh-CN.md)

</div>

# MinerU - PDF 转 Markdown 工具

## 项目简介

MinerU 是一款将 PDF 文档转换为机器可读格式的工具（如 Markdown、JSON），可以很方便地抽取为任意格式。

本项目是面向普通用户的简化版本，提供美观易用的图形界面，让您无需命令行知识即可轻松使用。

---

## ✨ 主要功能

- ✅ **智能布局分析** - 自动识别文档结构，保留标题、段落、列表等
- ✅ **内容提取** - 提取文本、图像、表格、公式等内容
- ✅ **OCR 识别** - 支持扫描版 PDF，自动启用 OCR 功能
- ✅ **公式识别** - 自动识别数学公式并转换为 LaTeX 格式
- ✅ **表格识别** - 自动识别表格并转换为 HTML 格式
- ✅ **多语言支持** - OCR 支持 109 种语言
- ✅ **阅读顺序** - 输出符合人类阅读顺序的文本
- ✅ **批量处理** - 支持任务队列，可批量处理多个文件
- ✅ **实时进度** - 显示处理进度和统计信息

---

## 🚀 快速开始

### 系统要求

- **操作系统**: Windows / Linux / macOS
- **Python**: 3.10 - 3.13
- **内存**: 最低 16GB，推荐 32GB
- **磁盘空间**: 20GB 以上（包含模型文件）
- **GPU**: 可选，支持 CPU 模式运行

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/opendatalab/MinerU.git
cd MinerU
```

#### 2. 安装依赖

```bash
# 升级 pip
pip install --upgrade pip

# 安装项目（包含核心功能）
pip install -e .[core]
```

#### 3. 下载模型（首次使用）

```bash
mineru-models-download
```

### 使用方式

#### 方式 1: GUI 应用程序（推荐）⭐

这是最简单易用的方式：

```bash
python mineru_gui.py
```

**GUI 功能特点：**
- 🎨 美观的图形界面
- 📋 任务队列，支持批量处理
- 📊 实时进度显示
- 🌓 自动跟随系统主题
- ⚡ 支持 CPU 模式

#### 方式 2: 命令行

```bash
# 基本用法
mineru -p input.pdf -o output/

# 指定语言
mineru -p input.pdf -o output/ --lang ch

# 批量处理目录
mineru -p input_dir/ -o output/
```

#### 方式 3: 打包为可执行文件（可选）

如果您想打包为独立的可执行文件：

```bash
python build_exe.py
```

打包完成后，可执行文件位于 `dist/MinerU_GUI/` 目录。

---

## 📖 使用示例

### GUI 使用步骤

1. **启动 GUI**
   ```bash
   python mineru_gui.py
   ```

2. **添加文件**
   - 点击"添加文件"按钮
   - 选择要处理的 PDF 文件（支持多选）
   - 或直接将文件拖拽到窗口中

3. **设置输出目录**
   - 点击"选择输出目录"按钮
   - 选择结果保存位置

4. **开始处理**
   - 点击"开始处理"按钮
   - 等待处理完成
   - 查看实时进度和统计信息

5. **查看结果**
   - 处理完成后，结果文件保存在输出目录
   - 包含 Markdown 文件和 JSON 文件

### 命令行使用示例

```bash
# 处理单个 PDF 文件
mineru -p document.pdf -o output/

# 处理整个目录
mineru -p pdf_folder/ -o output/

# 指定语言（中文）
mineru -p document.pdf -o output/ --lang ch

# 仅使用 CPU
mineru -p document.pdf -o output/ --device cpu
```

---

## 📁 输出文件说明

处理完成后，会在输出目录生成以下文件：

- `*.md` - Markdown 格式的文档内容
- `*_content_list.json` - 按阅读顺序排序的 JSON 格式
- `*_middle.json` - 包含丰富信息的中间格式
- `*_layout.pdf` - 布局可视化结果
- `*_span.pdf` - Span 可视化结果
- `images/` - 提取的图片文件

---

## ⚙️ 配置说明

### 后端说明

本 GUI 版本使用 **Pipeline 后端**：
- ✅ 速度快
- ✅ 支持 CPU 模式
- ✅ 精度 82+
- ✅ 功能完整，适合日常使用

### 语言设置

支持以下语言选项：
- `ch` - 中文（默认）
- `en` - 英文
- `auto` - 自动检测

更多语言支持请参考 OCR 语言列表。

---

## ❓ 常见问题

### Q: 处理速度慢怎么办？

A: 可以尝试：
- 使用 GPU 加速（如果有 NVIDIA GPU）
- 关闭不需要的功能（如公式识别、表格识别）
- 处理较小的文件

### Q: 支持哪些文件格式？

A: 主要支持 PDF 文件，也支持图片格式（PNG、JPG 等）。

### Q: 需要联网吗？

A: 
- 首次使用需要下载模型文件
- 下载完成后可以离线使用

### Q: 如何下载模型？

A: 运行以下命令：
```bash
mineru-models-download
```

### Q: 处理结果不理想怎么办？

A: 
- 尝试使用不同的语言设置
- 检查 PDF 文件质量
- 如果 PDF 是扫描版，确保图片清晰
- 参考下方的"已知限制"

---

## ⚠️ 已知限制

- 阅读顺序在极端复杂排版下可能部分乱序
- 竖排文字支持较为有限
- 复杂表格可能出现行/列识别错误
- 漫画书、艺术图册等特殊类型文档解析效果不佳
- 部分公式可能无法在 Markdown 中正确渲染

---

## 🔗 相关资源

- **原项目**: https://github.com/opendatalab/MinerU
- **在线体验**: https://mineru.net/
- **问题反馈**: https://github.com/opendatalab/MinerU/issues

---

## 📄 许可证

本项目采用 [AGPL-3.0](LICENSE.md) 许可证。

---

## 🙏 致谢

本项目基于 [opendatalab/MinerU](https://github.com/opendatalab/MinerU) 开发，感谢原项目的贡献者。

---

**享受使用 MinerU！** 🎉
