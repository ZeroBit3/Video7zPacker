import os
import subprocess
import random
import glob
import shutil
import configparser
import sys

def get_7z_executable():
    if shutil.which('7z'):
        return '7z'
    
    fallback_path = r"C:\Program Files\7-Zip\7z.exe"
    if os.path.exists(fallback_path):
        return fallback_path
        
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

def auto_pack_items():
    print("=== 自动分卷加密打包程序 (文件/文件夹混合保密版) ===")
    
    ARCHIVER_CMD = get_7z_executable()
    if not ARCHIVER_CMD:
        print("错误: 系统找不到 '7z' 命令，且默认路径 C:\\Program Files\\7-Zip\\7z.exe 不存在。")
        print("请确认已安装 7-Zip。")
        return

    # --- 读取或生成配置文件 ---
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

        # 自动生成配置文件
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

    SIZE_THRESHOLD = 1.8 * 1024 * 1024 * 1024  # 1.8 GB 阈值

    # --- 扫描与筛选目录和文件 ---
    all_items = os.listdir('.')
    valid_targets = []
    
    # 获取脚本自身文件名，防止自我打包
    script_name = os.path.basename(__file__) if '__file__' in globals() else sys.argv[0]
    script_name = os.path.basename(script_name)

    for f in all_items:
        f_abs = os.path.abspath(f)
        
        # 过滤规则：
        # 1. 跳过输出目录本身（防止死循环）
        # 2. 跳过隐藏文件/文件夹
        # 3. 跳过当前运行的脚本本身
        # 4. 跳过配置文件
        if f_abs == output_dir_abs or f.startswith('.'):
            continue
        if f in [script_name, config_file, 'config.ini'] or f.endswith('.py'):
            continue
            
        valid_targets.append(f)

    if not valid_targets:
        print("当前目录下未找到可打包的项目 (文件或文件夹)。")
        return

    # --- 任务确认与选择 ---
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

    # --- 开始打包逻辑 ---
    print("\n准备开始处理...")
    
    for target_name in selected_targets:
        print(f"\n--------------------------------------------------")
        target_path = os.path.abspath(target_name)
        
        # 判断是文件还是文件夹，分别计算大小
        if os.path.isdir(target_path):
            target_size = get_dir_size(target_path)
            type_label = "文件夹"
        else:
            target_size = os.path.getsize(target_path)
            type_label = "文件"
            
        print(f"[-] 正在分析{type_label}: {target_name}")
        
        # --- 自动寻找可用的数字命名 (1.7z, 2.7z, ...) ---
        base_num = 1
        while True:
            final_name = f"{base_num}.7z"
            output_file_path = os.path.join(output_dir_abs, final_name)
            
            # 使用 glob 检查该前缀的文件是否存在 (如 1.7z, 1.7z.001 等)
            existing_files = glob.glob(output_file_path + "*")
            if existing_files:
                base_num += 1  # 如果被占用了，数字+1继续找
            else:
                break
        
        is_split = target_size > SIZE_THRESHOLD
        
        # 初始化基础命令 (自动适配文件或文件夹输入)
        cmd = [
            ARCHIVER_CMD, 'a',
            '-t7z', 
            '-mx=0',            # 仅存储
            f'-p{password}',    # 加密密码
            '-mhe=on',          # 加密文件名
            output_file_path,
            target_path
        ]
        
        if is_split:
            estimated_vols = int(target_size / (1024 ** 3)) + 5
            
            split_args = []
            for _ in range(estimated_vols):
                split_gib = random.triangular(1.65, 1.8, 1.8)
                split_mb = int(split_gib * 1024)
                split_args.append(f'-v{split_mb}m')
            
            print(f"    > {type_label}总大小 {(target_size / (1024**3)):.2f} GB，启用不规则随机分卷")
            print(f"    > 输出保密路径: {output_file_path} (分卷)")
            
            cmd = cmd[:-2] + split_args + cmd[-2:]
        else:
            print(f"    > 输出保密路径: {output_file_path}")
        
        try:
            subprocess.run(cmd, check=True)
            print(f"    [√] [{target_name}] 打包成功，已保密命名为 -> {final_name}")
        except subprocess.CalledProcessError as e:
            print(f"    [X] 7z 运行出错: {e}")
        except Exception as e:
            print(f"    [X] 未知错误: {e}")

if __name__ == '__main__':
    try:
        auto_pack_items()
    except KeyboardInterrupt:
        print("\n\n[!] 用户强制中断")
    input("\n按回车键退出...")