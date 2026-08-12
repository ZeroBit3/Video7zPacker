<div align="center">

📦

# Video7zPacker

自动化、动态不规则分卷的加密打包工具集<br>
基于 Python 构建，驱动 7-Zip 核心进行物理级防和谐处理

[反馈问题](https://github.com/zerobit3/Video7zPacker/issues) · [更新日志](https://github.com/zerobit3/Video7zPacker/releases)

[![Version](https://img.shields.io/github/v/release/zerobit3/Video7zPacker)](https://github.com/zerobit3/Video7zPacker/releases/latest)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Stars](https://img.shields.io/github/stars/zerobit3/Video7zPacker?color=ffcb47&labelColor=black)<br>
![Python 3.10](https://img.shields.io/badge/Python-3.10-blue?logo=python)
![7-Zip](https://img.shields.io/badge/Core-7--Zip-%2324C8D8)
![GitHub Actions](https://img.shields.io/badge/Build-Actions-%23000000?logo=github-actions)

</div>

---

这是一个基于 Python 的自动化分卷加密打包工具集。通过调用系统底层的 7-Zip 命令，提供自动化打包方案。核心特色在于支持动态、不规则的分卷大小，以应对网盘限制并增加文件特征差异。

> **⚠️ 重要更新提示**：剧集处理功能现已全面整合进 `Pack_7z_general.py`。今后日常使用强烈建议只运行 `general` 版本，它已成为支持电影、剧集、资料及外挂字幕混合处理的终极通用工具，原 `Pack_teleplay.py` 已基本废弃。

## ✨ 功能特性

### 🎬 【通用综合版】（核心主力：Pack_7z_general.py）

- **文件与文件夹混合打包**：支持扫描当前目录，将文件夹和独立的视频文件混合列出，并视作独立任务处理。
- **同集数智能编组（新）**：自动检测当前目录下的字幕文件（如 SRT、ASS、VTT 等）。当存在字幕时，可自动提取集数特征，将**同一集数的视频文件与所有关联字幕合并打包**成同一个压缩卷。
- **灵活的文件命名方式**：支持在打包前选择：
  1. **纯数字保密命名**：自动递增为 `1.7z`, `2.7z` 等纯数字序列，完美隐藏原始特征。
  2. **保留原名称命名**：直接使用原始文件或文件夹名称，内置自动防冲突防覆盖机制。
  3. **智能集数提取命名（新）**：智能识别并提取文件名中的集数（如 `E01`, `第1集` 等）命名为 `01.7z`。若识别失败则自动触发回退机制，安全回退至原名称命名。
- **交互式任务菜单**：运行后自动列出当前目录下的有效项目，可输入序号选择打包特定文件/文件夹，或一键打包全部。
- **智能过滤机制**：自动排除 Python 脚本自身、配置文件（`.ini`）以及系统隐藏文件，避免无效打包。

### ⚙️ 【共有核心特性】

- **动态不规则分卷**：当目标超过设定阈值（默认 1.8GB）时自动触发。程序会为**每一个分卷**生成随机的大小（在 1.65GiB 到 1.8GiB 之间动态浮动）。
- **安全加密与存储**：使用 7z 格式存储（`-mx=0` 仅存储，无损且速度极快），并开启强制文件名加密（`-mhe=on`）。
- **交互与静默配置**：首次运行无配置时支持交互式引导，并自动生成 `config_movie.ini`，后续运行自动读取实现无人值守。

## 🛠️ 环境要求

1. **Python 3.x**：脚本仅依赖 Python 内置模块，无需安装第三方包。
2. **7-Zip**：系统必须已安装 7-Zip。程序会自动寻找默认路径 (`C:\Program Files\7-Zip\7z.exe`) 或环境变量中的执行文件（配置环境变量，即将你的 7z 安装目录添加到系统 Path 中）。

## 🚀 使用方法

将对应的脚本放置在需要打包的资源同级目录下，在终端运行：

- **启动通用综合打包程序（推荐）**：

  ```bash
  python Pack_7z_general.py
  ```

## 注意事项

- 确保输出目录有足够的写入权限。
