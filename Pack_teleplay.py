import os
import re
import subprocess
import sys
import random
import glob
import shutil
import configparser

def get_7z_executable():
    if shutil.which('7z'):
        return '7z'
    
    fallback_path = r"C:\Program Files\7-Zip\7z.exe"
    if os.path.exists(fallback_path):
        return fallback_path
        
    return None

def auto_pack_interactive():
    print("=== 自动分卷加密打包程序 ===")
    
    ARCHIVER_CMD = get_7z_executable()
    if not ARCHIVER_CMD:
        print("错误: 系统找不到 '7z' 命令，且默认路径 C:\\Program Files\\7-Zip\\7z.exe 不存在。")
        print("请确认已安装 7-Zip。")
        return

    # --- 读取配置文件 ---
    config = configparser.ConfigParser()
    config_file = 'config.ini'
    
    conf_password = ""
    conf_output_dir = ""
    conf_auto_overwrite = False
    conf_auto_name_fallback = "" 
    
    if os.path.exists(config_file):
        config.read(config_file, encoding='utf-8')
        if 'Settings' in config:
            conf_password = config['Settings'].get('password', '').strip()
            conf_output_dir = config['Settings'].get('output_dir', '').strip()
            conf_auto_overwrite = config['Settings'].getboolean('auto_overwrite', fallback=False)
            conf_auto_name_fallback = config['Settings'].get('auto_name_fallback', fallback='').strip().lower()
            print(f"[+] 检测到 {config_file}，已加载静默配置。")

    # --- 变量初始化（优先使用配置，否则回退到交互） ---
    password = conf_password
    if not password:
        password = input("请输入加密密码: ").strip()
        if not password:
            print("错误: 密码不能为空")
            return

    output_dir = conf_output_dir
    if not output_dir:
        output_dir = input("请输入输出目录路径 (例如 D:\\Backup): ").strip()
        
    output_dir = output_dir.strip('"').strip("'")
    if not output_dir:
        print("错误: 输出目录不能为空")
        return

    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"无法创建目录: {e}")
        return

    VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.ts', '.webm', '.iso')
    SIZE_THRESHOLD = 1.8 * 1024 * 1024 * 1024 

    files = [f for f in os.listdir('.') if os.path.isfile(f) and f.lower().endswith(VIDEO_EXTS)]
    
    if not files:
        print("当前目录下未找到视频文件。")
        return

    print(f"扫描到 {len(files)} 个视频文件，准备处理...")

    try:
        abs_out_dir = os.path.abspath(output_dir)
        if sys.platform == 'win32':
            os.startfile(abs_out_dir)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', abs_out_dir])
        else:
            subprocess.Popen(['xdg-open', abs_out_dir])
    except Exception as e:
        print(f"自动打开目录失败: {e}")

    for filename in files:
        print(f"\n--------------------------------------------------")
        print(f"[-] 正在分析: {filename}")
        
        file_path = os.path.abspath(filename)
        file_size = os.path.getsize(file_path)
        base_name = os.path.splitext(filename)[0]
        
        ep_number = None
        
        # 优先进行强特征匹配
        match_ep = re.search(r'(?i)e(?:p)?\s*0*(\d{1,4})', base_name)
        match_ch = re.search(r'第\s*0*(\d+)\s*[集话]', base_name)
        
        if match_ep:
            ep_number = match_ep.group(1)
        elif match_ch:
            ep_number = match_ch.group(1)
        else:
            clean_name = base_name
            
            noise_patterns = [
                r'(?i)1080[pi]?|720[pi]?|2160[pi]?|480[pi]?|4k|8k',  
                r'(?i)x264|h264|x265|h265|hevc|av1|avc',             
                r'(?i)aac|ac3|flac|mp3|dts',                         
                r'(?i)10bit|8bit|hdr|web-dl|bdrip|bluray',           
                r'\b(?:19|20)\d{2}\b'                                
            ]
            
            for pattern in noise_patterns:
                clean_name = re.sub(pattern, ' ', clean_name)
            
            match_num_list = re.findall(r'(?<![a-zA-Z\d])(\d{1,4})(?![a-zA-Z\d])', clean_name)
            
            if match_num_list:
                ep_number = match_num_list[0]

        final_name = ""
        should_pack = True

        if ep_number:
            print(f"    > 识别到集数: {ep_number}")
            final_name = f"{ep_number}.7z"
        else:
            print("    ! 警告: 未能自动识别集数特征")
            
            if conf_auto_name_fallback == 'y':
                final_name = f"{base_name}.7z"
                print(f"    > 根据配置，自动使用原文件名: {final_name}")
            elif conf_auto_name_fallback == 'n':
                should_pack = False
                print("    > 根据配置，自动跳过该文件")
            else:
                choice = input(f"    ? 是否使用原文件名 '{base_name}' 打包? (y/n/输入新名称): ").strip()
                if choice.lower() == 'y':
                    final_name = f"{base_name}.7z"
                elif choice.lower() == 'n':
                    should_pack = False
                    print("    > 已跳过")
                else:
                    custom_name = choice
                    if not custom_name.endswith('.7z'):
                        custom_name += '.7z'
                    final_name = custom_name

        if should_pack:
            output_file_path = os.path.join(output_dir, final_name)
            is_split = file_size > SIZE_THRESHOLD
            
            check_paths = [output_file_path, output_file_path + ".001"]
            if any(os.path.exists(p) for p in check_paths):
                print(f"    ! 警告: 目标目录已存在同名压缩包 ({final_name})")
                
                if conf_auto_overwrite:
                    overwrite = 'y'
                    print("    > 根据配置，自动执行覆盖")
                else:
                    overwrite = input("    ? 是否覆盖原有文件? (y/n，按 y 覆盖，其他键跳过): ").strip().lower()
                
                if overwrite == 'y':
                    old_files = glob.glob(output_file_path + "*")
                    for old_f in old_files:
                        try:
                            os.remove(old_f)
                        except OSError:
                            pass
                    print("    > 已清理旧文件，准备重新打包...")
                else:
                    print("    > 已跳过该文件")
                    continue
            
            # 初始化基础命令
            cmd = [
                ARCHIVER_CMD, 'a',
                '-t7z', 
                '-mx=0',            
                f'-p{password}',    
                '-mhe=on',          
                output_file_path,
                file_path
            ]
            
            if is_split:
                # 估算所需的最大分卷数量
                # 以 1GB (1024^3) 作为估算底线，再加 5 个作为冗余，确保生成的参数足够用
                estimated_vols = int(file_size / (1024 ** 3)) + 5
                
                split_args = []
                # 循环生成多个大小不一的 -v 参数
                for _ in range(estimated_vols):
                    # 目前设定在 1.65 GB 到 1.8 GB 之间随机
                    split_gib = random.triangular(1.65, 1.8, 1.8)
                    split_mb = int(split_gib * 1024)
                    split_args.append(f'-v{split_mb}m')
                
                print(f"    > 文件大小 {(file_size / (1024**3)):.2f} GB，启用不规则随机分卷")
                
                # 将所有生成的 -v 参数插入到 cmd 列表中
                cmd = cmd[:-2] + split_args + cmd[-2:]
            else:
                print(f"    > 目标路径: {output_file_path}")
            
            try:
                subprocess.run(cmd, check=True)
                print(f"    [√] 打包成功")
            except subprocess.CalledProcessError as e:
                print(f"    [X] 7z 运行出错: {e}")
            except Exception as e:
                print(f"    [X] 未知错误: {e}")

if __name__ == '__main__':
    try:
        auto_pack_interactive()
    except KeyboardInterrupt:
        print("\n\n[!] 用户强制中断")
    input("\n按回车键退出...")