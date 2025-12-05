<div align="center" xmlns="http://www.w3.org/1999/html">

## 📌 Project Description

**This project is Forked from [opendatalab/MinerU](https://github.com/opendatalab/MinerU)**

The main goals of this project are:
- 🎨 **Develop a fully-featured and beautiful GUI interface**
- 🚀 **One-click startup to simplify usage**
- 📋 **Task queue support for batch processing multiple PDF files**
- ⚡ **CPU mode support, no GPU required**
- 🌓 **Automatic theme switching (light/dark)**
- 📊 **Real-time progress display and per-page processing time statistics**

**GUI Launch Method:**
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

# MinerU - PDF to Markdown Tool

## Project Introduction

MinerU is a tool that converts PDF documents into machine-readable formats (such as Markdown, JSON), allowing easy extraction into any format.

This project is a simplified version for end users, providing a beautiful and easy-to-use graphical interface that allows you to use it easily without command-line knowledge.

---

## ✨ Key Features

- ✅ **Intelligent Layout Analysis** - Automatically recognizes document structure, preserving headings, paragraphs, lists, etc.
- ✅ **Content Extraction** - Extracts text, images, tables, formulas, and more
- ✅ **OCR Recognition** - Supports scanned PDFs with automatic OCR activation
- ✅ **Formula Recognition** - Automatically recognizes mathematical formulas and converts them to LaTeX format
- ✅ **Table Recognition** - Automatically recognizes tables and converts them to HTML format
- ✅ **Multi-language Support** - OCR supports 109 languages
- ✅ **Reading Order** - Outputs text in human-readable order
- ✅ **Batch Processing** - Supports task queue for batch processing multiple files
- ✅ **Real-time Progress** - Displays processing progress and statistics

---

## 🚀 Quick Start

### System Requirements

- **Operating System**: Windows / Linux / macOS
- **Python**: 3.10 - 3.13
- **Memory**: Minimum 16GB, recommended 32GB
- **Disk Space**: 20GB or more (including model files)
- **GPU**: Optional, CPU mode is supported

### Installation Steps

#### 1. Clone the Project

```bash
git clone https://github.com/opendatalab/MinerU.git
cd MinerU
```

#### 2. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install project (including core features)
pip install -e .[core]
```

#### 3. Download Models (First-time Use)

```bash
mineru-models-download
```

### Usage

#### Method 1: GUI Application (Recommended) ⭐

This is the easiest way to use:

```bash
python mineru_gui.py
```

**GUI Features:**
- 🎨 Beautiful graphical interface
- 📋 Task queue for batch processing
- 📊 Real-time progress display
- 🌓 Automatic theme following
- ⚡ CPU mode support

#### Method 2: Command Line

```bash
# Basic usage
mineru -p input.pdf -o output/

# Specify language
mineru -p input.pdf -o output/ --lang ch

# Batch process directory
mineru -p input_dir/ -o output/
```

#### Method 3: Package as Executable (Optional)

If you want to package it as a standalone executable:

```bash
python build_exe.py
```

After packaging, the executable file will be in the `dist/MinerU_GUI/` directory.

---

## 📖 Usage Examples

### GUI Usage Steps

1. **Launch GUI**
   ```bash
   python mineru_gui.py
   ```

2. **Add Files**
   - Click "Add Files" button
   - Select PDF files to process (multiple selection supported)
   - Or drag and drop files directly into the window

3. **Set Output Directory**
   - Click "Select Output Directory" button
   - Choose where to save results

4. **Start Processing**
   - Click "Start Processing" button
   - Wait for processing to complete
   - View real-time progress and statistics

5. **View Results**
   - After processing, result files are saved in the output directory
   - Includes Markdown and JSON files

### Command Line Examples

```bash
# Process single PDF file
mineru -p document.pdf -o output/

# Process entire directory
mineru -p pdf_folder/ -o output/

# Specify language (Chinese)
mineru -p document.pdf -o output/ --lang ch

# CPU only
mineru -p document.pdf -o output/ --device cpu
```

---

## 📁 Output File Description

After processing, the following files will be generated in the output directory:

- `*.md` - Document content in Markdown format
- `*_content_list.json` - JSON format sorted by reading order
- `*_middle.json` - Intermediate format with rich information
- `*_layout.pdf` - Layout visualization result
- `*_span.pdf` - Span visualization result
- `images/` - Extracted image files

---

## ⚙️ Configuration

### Backend Information

This GUI version uses the **Pipeline Backend**:
- ✅ Fast speed
- ✅ CPU mode supported
- ✅ Accuracy 82+
- ✅ Fully functional, suitable for daily use

### Language Settings

Supports the following language options:
- `ch` - Chinese (default)
- `en` - English
- `auto` - Auto-detect

For more language support, please refer to the OCR language list.

---

## ❓ FAQ

### Q: What if processing is slow?

A: You can try:
- Use GPU acceleration (if you have an NVIDIA GPU)
- Disable unnecessary features (such as formula recognition, table recognition)
- Process smaller files

### Q: What file formats are supported?

A: Mainly supports PDF files, also supports image formats (PNG, JPG, etc.).

### Q: Do I need internet connection?

A: 
- First-time use requires downloading model files
- Can be used offline after downloading

### Q: How to download models?

A: Run the following command:
```bash
mineru-models-download
```

### Q: What if the results are not ideal?

A: 
- Try different language settings
- Check PDF file quality
- If PDF is scanned, ensure images are clear
- Refer to "Known Issues" below

---

## ⚠️ Known Issues

- Reading order may be partially out of order in extremely complex layouts
- Limited support for vertical text
- Complex tables may have row/column recognition errors
- Special document types like comic books and art albums may not parse well
- Some formulas may not render correctly in Markdown

---

## 🔗 Related Resources

- **Original Project**: https://github.com/opendatalab/MinerU
- **Online Experience**: https://mineru.net/
- **Issue Reports**: https://github.com/opendatalab/MinerU/issues

---

## 📄 License

This project is licensed under [AGPL-3.0](LICENSE.md).

---

## 🙏 Acknowledgments

This project is based on [opendatalab/MinerU](https://github.com/opendatalab/MinerU). Thanks to all contributors of the original project.

---

**Enjoy using MinerU!** 🎉
