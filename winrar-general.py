import os
import subprocess
import random
import glob
import shutil
import configparser
import sys
import re
import math


def get_rar_executable():
    """查找 WinRAR 命令行程序 (优先 rar.exe，其次 WinRAR.exe)"""
    for cmd in ['rar', 'WinRAR']:
        if shutil.which(cmd):
            return cmd

    fallback_paths = [
        r"C:\Program Files\WinRAR\Rar.exe",
        r"C:\Program Files\WinRAR\WinRAR.exe",
        r"C:\Program Files (x86)\WinRAR\Rar.exe",
        r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
    ]
    for path in fallback_paths:
        if os.path.exists(path):
            return path

    return None


def get_dir_size(folder_path):
    """递归计算文件夹总大小（字节）"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size


def extract_episode_number(filename):
    """提取文件或文件夹的集数（强特征匹配 + 特征降噪兜底）"""
    base_name, _ = os.path.splitext(filename)

    # === 第一步：强特征匹配 ===
    match_en = re.search(r'(?i)e(?:p)?\s*0*(\d{1,4})', base_name)
    if match_en:
        return match_en.group(1).zfill(2)

    match_zh = re.search(r'第\s*0*(\d+)\s*[集话]', base_name)
    if match_zh:
        return match_zh.group(1).zfill(2)

    # === 第二步：特征降噪与弱匹配 ===
    noise_patterns = [
        r'(?i)(1080p|2160p|4k|720p)',
        r'(?i)(x264|x265|h264|h265|hevc|av1)',
        r'(?i)(aac|flac|ac3|dts|mp3|ogg)',
        r'(?i)(10bit|8bit|web-dl|bluray|bdrip|tvrip)',
        r'(19\d{2}|20\d{2})'
    ]

    cleaned_name = base_name
    for pattern in noise_patterns:
        cleaned_name = re.sub(pattern, ' ', cleaned_name)

    match_weak = re.search(r'(?<![a-zA-Z\d])(\d{1,4})(?![a-zA-Z\d])', cleaned_name)
    if match_weak:
        return match_weak.group(1).zfill(2)

    return None


def get_conflict_pattern(output_dir_abs, base_name):
    """生成用于检测命名冲突的通配符列表（兼容单文件、partN分卷及rev恢复卷）"""
    return [
        os.path.join(output_dir_abs, f"{base_name}.rar"),
        os.path.join(output_dir_abs, f"{base_name}.part*.rar"),
        os.path.join(output_dir_abs, f"{base_name}.part*.rev"),
        os.path.join(output_dir_abs, f"{base_name}.rev")
    ]


def has_naming_conflict(output_dir_abs, base_name):
    for pattern in get_conflict_pattern(output_dir_abs, base_name):
        if glob.glob(pattern):
            return True
    return False


def calculate_small_file_volumes(total_size):
    """
    针对小于阈值（1.8GB）的文件计算合理的分卷大小（单位：KB）：
    - 对于极小文件（如几 KB 的文本/配置文件），允许低至 1KB 每卷，确保能够切出多卷并成功生成恢复卷。
    """
    total_kb = max(1, math.ceil(total_size / 1024))

    # 如果文件极小（小于 4 KB），直接设为 1 KB 一卷，强制分卷以支持恢复卷
    if total_kb < 4:
        vol_kb = 1
        actual_vols = total_kb
    else:
        if total_size < 100 * 1024 * 1024:          # < 100 MB -> 分 3 卷
            target_vols = 3
        elif total_size < 800 * 1024 * 1024:        # 100 MB ~ 800 MB -> 分 4 卷
            target_vols = 4
        else:                                       # 800 MB ~ 1.8 GB -> 分 5 卷
            target_vols = 5

        vol_kb = max(1, math.ceil(total_kb / target_vols))
        actual_vols = math.ceil(total_kb / vol_kb)

    return vol_kb, actual_vols


def generate_random_volume_sizes_mb(total_size):
    """
    为超过阈值的项目生成随机单卷大小列表（单位：MB），
    分布范围与 Pack_7z_general.py 一致：random.triangular(1.65, 1.8, 1.8)。
    额外多生成几个分卷尺寸作为余量，避免估算卷数偏少。
    """
    min_vol_bytes = 1.65 * 1024 * 1024 * 1024
    estimated_vols = math.ceil(total_size / min_vol_bytes) + 5
    vol_sizes_mb = []
    for _ in range(estimated_vols):
        split_gib = random.triangular(1.65, 1.8, 1.8)
        split_mb = max(1, int(split_gib * 1024))
        vol_sizes_mb.append(split_mb)
    return vol_sizes_mb


def auto_pack_items():
    print("=== 自动分卷加密打包程序 (WinRAR 随机分卷 + 极小文件强制分卷抗损版) ===")

    ARCHIVER_CMD = get_rar_executable()
    if not ARCHIVER_CMD:
        print("错误: 系统找不到 'rar' 或 'WinRAR' 命令，且默认安装路径不存在。")
        print("请确认已安装 WinRAR 并将其目录添加到系统环境变量 Path 中。")
        return

    config_file = 'config_movie.ini'
    config = configparser.ConfigParser()

    password = ""
    output_dir = ""

    if os.path.exists(config_file):
        config.read(config_file, encoding='utf-8')
        if 'Settings' in config:
            password = config['Settings'].get('password', '').strip()
            output_dir = config['Settings'].get('output_dir', '').strip()
            print(f"[+] 检测到 {config_file}，已加载配置。")
    else:
        print(f"[-] 未检测到 {config_file}，请进行初始设置。")

        password = input("请输入加密密码: ").strip()
        while not password:
            print("错误: 密码不能为空")
            password = input("请输入加密密码: ").strip()

        output_dir = input("请输入输出目录路径 (例如 D:\\Backup): ").strip().strip('"').strip("'")
        while not output_dir:
            print("错误: 输出目录不能为空")
            output_dir = input("请输入输出目录路径 (例如 D:\\Backup): ").strip().strip('"').strip("'")

        config['Settings'] = {
            'password': password,
            'output_dir': output_dir,
            'auto_overwrite': 'False'
        }
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                config.write(f)
            print(f"[+] 配置文件 {config_file} 已在当前目录自动生成。后续运行将直接读取该文件。")
        except Exception as e:
            print(f"警告: 无法生成配置文件 {e}，将仅在本次运行生效。")

    output_dir_abs = os.path.abspath(output_dir)
    try:
        os.makedirs(output_dir_abs, exist_ok=True)
    except Exception as e:
        print(f"无法创建输出目录: {e}")
        return

    SIZE_THRESHOLD = 1.8 * 1024 * 1024 * 1024

    all_items = os.listdir('.')
    valid_targets = []

    script_name = os.path.basename(__file__) if '__file__' in globals() else sys.argv[0]
    script_name = os.path.basename(script_name)

    for f in all_items:
        f_abs = os.path.abspath(f)
        if f_abs == output_dir_abs or f.startswith('.'):
            continue
        if f in [script_name, config_file, 'config.ini'] or f.endswith('.py'):
            continue
        valid_targets.append(f)

    if not valid_targets:
        print("当前目录下未找到可打包的项目 (文件或文件夹)。")
        return

    print(f"\n=== 检测到以下 {len(valid_targets)} 个待处理项目 ===")
    print("  [0] 打包以下全部项目")
    for i, f_name in enumerate(valid_targets, 1):
        item_type = "文件夹" if os.path.isdir(f_name) else "文件  "
        print(f"  [{i}] [{item_type}] {f_name}")
    print("--------------------------------------------------")

    selected_targets = []
    while True:
        choice = input(f"请输入对应的数字进行选择 (0-{len(valid_targets)}，输入 q 退出): ").strip()
        if choice.lower() == 'q':
            print("退出程序。")
            return

        if choice.isdigit():
            idx = int(choice)
            if idx == 0:
                selected_targets = valid_targets
                print("\n[+] 已选择：打包全部项目。")
                break
            elif 1 <= idx <= len(valid_targets):
                selected_targets = [valid_targets[idx - 1]]
                print(f"\n[+] 已选择：仅打包 [{valid_targets[idx - 1]}]。")
                break

        print("输入无效，请重新输入。")

    # --- 字幕文件检测与编组选项 ---
    subtitle_exts = {'.srt', '.ass', '.ssa', '.vtt', '.sub'}
    has_subtitles = False
    for target in selected_targets:
        if os.path.isfile(target):
            _, ext = os.path.splitext(target)
            if ext.lower() in subtitle_exts:
                has_subtitles = True
                break

    group_choice = '2'  # 默认关闭编组
    if has_subtitles:
        print("\n=== 检测到字幕文件，是否开启【同集数智能编组】功能？ ===")
        print("开启后，将自动提取集数，把相同集数的视频和字幕（如 01.mp4 与 01.ass）合并打包。")
        print("  [1] 开启 (自动编组，推荐)")
        print("  [2] 关闭 (每个文件/文件夹独立打包)")
        while True:
            group_choice = input("请输入选择 (1 或 2，默认 1): ").strip()
            if not group_choice:
                group_choice = '1'
                break
            if group_choice in ['1', '2']:
                break
            print("输入无效，请重新输入。")

    # --- 命名方式选择 ---
    print("\n=== 请选择分卷文件的命名方式 ===")
    print("  [1] 纯数字命名 (例如 1.part1.rar, 2.part1.rar... 隐匿原名，增强保密性)")
    print("  [2] 原名称命名 (直接使用原文件或文件夹的名字命名)")
    print("  [3] 智能集数提取命名 (例如 01.part1.rar, 识别失败自动回退至原名称命名)")
    naming_choice = ""
    while True:
        naming_choice = input("请输入对应的数字进行选择 (1, 2 或 3): ").strip()
        if naming_choice in ['1', '2', '3']:
            break
        print("输入无效，请重新输入。")

    # --- 任务编组处理 ---
    task_groups = []
    if group_choice == '1':
        ep_dict = {}
        ungrouped = []
        for target in selected_targets:
            ep_num = extract_episode_number(target)
            if ep_num:
                if ep_num not in ep_dict:
                    ep_dict[ep_num] = []
                ep_dict[ep_num].append(target)
            else:
                ungrouped.append(target)

        for ep_num in sorted(ep_dict.keys()):
            task_groups.append({'key': ep_num, 'items': ep_dict[ep_num], 'is_grouped': True})

        for item in ungrouped:
            task_groups.append({'key': item, 'items': [item], 'is_grouped': False})
    else:
        for item in selected_targets:
            task_groups.append({'key': item, 'items': [item], 'is_grouped': False})

    # --- 开始打包逻辑 ---
    print("\n准备开始处理...")

    for task in task_groups:
        items = task['items']
        is_grouped = task['is_grouped']
        group_key = task['key']

        total_size = 0
        main_item = items[0]
        max_size = -1

        for item in items:
            item_path = os.path.abspath(item)
            if os.path.isdir(item_path):
                size = get_dir_size(item_path)
            else:
                size = os.path.getsize(item_path)

            total_size += size
            if size > max_size:
                max_size = size
                main_item = item

        type_label = "文件组" if len(items) > 1 else ("文件夹" if os.path.isdir(items[0]) else "文件")
        print(f"\n--------------------------------------------------")
        if len(items) > 1:
            print(f"[-] 正在分析{type_label}: 包含 {len(items)} 个项目 (归集识别码: {group_key})")
            for it in items:
                print(f"    - {it}")
        else:
            print(f"[-] 正在分析{type_label}: {items[0]}")

        if naming_choice == '1':
            base_num = 1
            while True:
                candidate_base = str(base_num)
                if has_naming_conflict(output_dir_abs, candidate_base):
                    base_num += 1
                else:
                    final_base = candidate_base
                    break
        else:
            base_name = ""

            if naming_choice == '3':
                if is_grouped:
                    base_name = group_key
                    print(f"    [!] 成功提取集数：{group_key}")
                else:
                    ep_num = extract_episode_number(main_item)
                    if ep_num:
                        base_name = ep_num
                        print(f"    [!] 成功提取集数：{ep_num}")
                    else:
                        print(f"    [!] 集数识别失败，触发回退机制（使用主文件名）。")

            if not base_name:
                if os.path.isdir(main_item):
                    base_name = main_item
                else:
                    base_name = os.path.splitext(main_item)[0]

            final_base = base_name
            conflict_num = 1
            while has_naming_conflict(output_dir_abs, final_base):
                final_base = f"{base_name}_{conflict_num}"
                conflict_num += 1

        final_name = f"{final_base}.rar"
        output_file_path = os.path.join(output_dir_abs, final_name)

        cmd = [
            ARCHIVER_CMD, 'a',
            '-m0',
            f'-hp{password}',
            '-ep1',
            '-r',
            '-rv2'
        ]

        is_large = total_size > SIZE_THRESHOLD
        if is_large:
            vol_sizes_mb = generate_random_volume_sizes_mb(total_size)
            for split_mb in vol_sizes_mb:
                cmd.append(f'-v{split_mb}m')

            preview_vols = vol_sizes_mb[:6]
            preview_str = ", ".join(f"{m}MB" for m in preview_vols)
            if len(vol_sizes_mb) > 6:
                preview_str += f", ... (共生成 {len(vol_sizes_mb)} 个随机卷规则)"

            print(f"    > {type_label}总大小 {(total_size / (1024**3)):.2f} GB（超阈值），启用不规则随机分卷")
            print(f"    > 随机分卷序列: {preview_str} (+ 2 个恢复卷)")
        else:
            vol_kb, actual_vols = calculate_small_file_volumes(total_size)
            cmd.append(f'-v{vol_kb}k')
            if total_size < 4 * 1024:
                print(f"    > {type_label}为极小文件（{total_size} 字节），强制切分为 {actual_vols} 个数据卷（单卷 {vol_kb} KB）+ 2 个恢复卷")
            else:
                size_mb = total_size / (1024 * 1024)
                print(f"    > {type_label}总大小 {size_mb:.2f} MB（低于阈值），智能切分为 {actual_vols} 个数据卷（单卷 {vol_kb} KB）+ 2 个恢复卷")

        print(f"    > 输出路径: {os.path.join(output_dir_abs, final_base)}.part*.rar (+ 2 个 .rev)")

        cmd.append(output_file_path)
        for it in items:
            cmd.append(os.path.abspath(it))

        try:
            subprocess.run(cmd, check=True)
            print(f"    [√] [{final_base}] 打包及恢复卷生成成功！")
        except subprocess.CalledProcessError as e:
            print(f"    [X] WinRAR 运行出错 (退出码 {e.returncode}): {e}")
        except Exception as e:
            print(f"    [X] 未知错误: {e}")


if __name__ == '__main__':
    try:
        auto_pack_items()
    except KeyboardInterrupt:
        print("\n\n[!] 用户强制中断")
    input("\n按回车键退出...")