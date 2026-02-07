import os
import re
import subprocess
import sys

def auto_pack_interactive():
    # --- 1. 获取用户配置 ---
    print("=== 自动分卷加密打包程序 ===")
    
    password = input("请输入加密密码: ").strip()
    if not password:
        print("错误: 密码不能为空")
        return

    output_dir = input("请输入输出目录路径 (例如 D:\\Backup): ").strip()
    # 去除可能存在的引号（针对直接拖入文件夹路径的情况）
    output_dir = output_dir.strip('"').strip("'")
    
    if not output_dir:
        print("错误: 输出目录不能为空")
        return

    # 尝试创建输出目录
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"无法创建目录: {e}")
        return

    # --- 2. 核心参数配置 ---
    # 7z 命令 (需确保 7z 在环境变量 PATH 中，或者修改此处为绝对路径)
    ARCHIVER_CMD = '7z' 
    
    # 支持的视频格式扩展名
    VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.ts', '.webm', '.iso')
    
    # 触发分卷的阈值: 2GB (字节)
    SIZE_THRESHOLD = 2 * 1024 * 1024 * 1024 
    
    # 分卷参数: 1955MB
    SPLIT_ARG = '-v1955m'

    # --- 3. 扫描与处理 ---
    # 获取当前目录下所有匹配的视频文件
    files = [f for f in os.listdir('.') if os.path.isfile(f) and f.lower().endswith(VIDEO_EXTS)]
    
    if not files:
        print("当前目录下未找到视频文件。")
        return

    print(f"扫描到 {len(files)} 个视频文件，准备处理...")

    for filename in files:
        print(f"\n--------------------------------------------------")
        print(f"[-] 正在分析: {filename}")
        
        file_path = os.path.abspath(filename)
        file_size = os.path.getsize(file_path)
        base_name = os.path.splitext(filename)[0]
        
        # --- 智能集数识别逻辑 ---
        ep_number = None
        
        # 策略A: 匹配 "E01", "EP01" (忽略大小写)
        match_ep = re.search(r'(?i)e(?:p)?(\d{1,4})', base_name)
        
        # 策略B: 匹配 "第xx集", "第xx话"
        match_ch = re.search(r'第(\d+)[集话]', base_name)
        
        # 策略C: 匹配被符号包裹或独立的数字 (如 [01], - 01 -, (01))
        # 排除 19xx/20xx 这种年份数字
        match_num_list = re.findall(r'(?:^|\D)(\d{1,4})(?:$|\D)', base_name)
        
        valid_nums = []
        if match_num_list:
            for num in match_num_list:
                # 过滤掉常见的年份 (1980-2030) 和分辨率 (1080, 720, 2160)
                if len(num) == 4 and (num.startswith('19') or num.startswith('20')):
                    continue
                if num in ['1080', '720', '2160', '480']:
                    continue
                valid_nums.append(num)

        # 判定优先级
        if match_ep:
            ep_number = match_ep.group(1)
        elif match_ch:
            ep_number = match_ch.group(1)
        elif valid_nums:
            # 取第一个看起来像集数的数字
            ep_number = valid_nums[0]

        # --- 交互确认 ---
        final_name = ""
        should_pack = True

        if ep_number:
            print(f"    > 识别到集数: {ep_number}")
            final_name = f"{ep_number}.7z"
        else:
            print("    ! 警告: 未能自动识别集数特征")
            choice = input(f"    ? 是否使用原文件名 '{base_name}' 打包? (y/n/输入新名称): ").strip()
            
            if choice.lower() == 'y':
                final_name = f"{base_name}.7z"
            elif choice.lower() == 'n':
                should_pack = False
                print("    > 已跳过")
            else:
                # 用户输入了自定义名称
                custom_name = choice
                if not custom_name.endswith('.7z'):
                    custom_name += '.7z'
                final_name = custom_name

        # --- 执行打包命令 ---
        if should_pack:
            output_file_path = os.path.join(output_dir, final_name)
            
            cmd = [
                ARCHIVER_CMD, 'a',
                '-t7z', 
                '-mx=0',           # 存储模式 (不压缩)
                f'-p{password}',   # 密码
                '-mhe=on',         # 加密文件名
                output_file_path,
                file_path
            ]
            
            # 检测大小是否需要分卷
            if file_size > SIZE_THRESHOLD:
                print(f"    > 文件大小 {(file_size / (1024**3)):.2f} GB，启用分卷 ({SPLIT_ARG})")
                cmd.append(SPLIT_ARG)
            
            print(f"    > 目标路径: {output_file_path}")
            
            try:
                # 调用 7z，直接显示输出以便查看进度
                subprocess.run(cmd, check=True)
                print(f"    [√] 打包成功")
            except FileNotFoundError:
                print("    [X] 错误: 系统找不到 '7z' 命令，请确认已安装并添加到环境变量 PATH 中。")
                break
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