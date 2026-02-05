import os
import subprocess
import time
import shlex
import sys
import re  # 用于正则提取版本号

# ================= 配置区域 =================

# 1. GPTScan main.py 所在的目录 (工作目录)
GPTSCAN_SRC_DIR = r"C:\Coding\CodingTool\PyCharm\PyCharm2025.2.1.1\Project\GPTScan\src"

# 2. 待测试的总文件夹 (父目录)
INPUT_ROOT_DIR = r"C:\Coding\CodingTool\PyCharm\PyCharm2025.2.1.1\Project\GPTScan\GPTScan-Top200-dev"

# 3. 结果输出保存的文件夹
OUTPUT_ROOT_DIR = r"C:\Coding\CodingTool\PyCharm\PyCharm2025.2.1.1\Project\GPTScan\output"

# 4. 你的 API Key
API_KEY = "sk-746vT8RFtvagefSpucPpl6i5pfitNXRBjugRADHYY0QfPqRz"

# 5. 触发熔断的敏感词列表
STOP_KEYWORDS = ["API限制每日200次请求"]

# 6. Python 命令
PYTHON_CMD = sys.executable


# ===========================================================

def detect_solc_version(folder_path):
    """
    根据文件夹内容智能嗅探 Solidity 版本
    """
    try:
        items = os.listdir(folder_path)
    except Exception as e:
        print(f"⚠️ 无法读取目录: {e}")
        return "0.8.0"  # 默认回退

    # --- 情况 3: 检查是否包含子文件夹 ---
    has_subdirectories = any(os.path.isdir(os.path.join(folder_path, i)) for i in items)
    if has_subdirectories:
        print("   -> 检测到嵌套文件夹 (Case 3)，默认使用 0.8.0")
        return "0.8.0"

    # --- 情况 1 & 2: 提取 .sol 文件 ---
    sol_files = [f for f in items if f.endswith(".sol")]

    if not sol_files:
        print("   -> 未找到 .sol 文件，默认使用 0.8.0")
        return "0.8.0"

    # 读取第一个 sol 文件
    target_file = os.path.join(folder_path, sol_files[0])
    try:
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

            # 使用正则提取 pragma solidity ^0.x.x; 中的版本号
            # 匹配模式：pragma solidity [空格] [^,><=]* (数字.数字.数字)
            match = re.search(r'pragma\s+solidity\s+[\^~><=]*\s*(\d+\.\d+\.\d+)', content)

            if match:
                version = match.group(1)
                print(f"   -> 从文件 {sol_files[0]} 中检测到版本: {version}")
                return version
            else:
                print(f"   -> 文件 {sol_files[0]} 中未发现明确版本号，默认使用 0.8.0")
                return "0.8.0"
    except Exception as e:
        print(f"⚠️ 读取文件出错: {e}")
        return "0.8.0"


def switch_solc_version(version):
    """
    调用 solc-select 切换版本
    """
    print(f"🔧 正在切换编译器版本至: {version} ...")
    try:
        # 1. 安装 (如果已安装会跳过)
        subprocess.run(f"solc-select install {version}", shell=True, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        # 2. 使用
        subprocess.run(f"solc-select use {version}", shell=True, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        print(f"✅ 编译器已切换: {version}")
    except subprocess.CalledProcessError:
        print(f"❌ 切换版本失败 (可能是 solc-select 未配置好或网络问题)，将尝试继续运行...")


def run_batch_scan():
    if not os.path.exists(OUTPUT_ROOT_DIR):
        os.makedirs(OUTPUT_ROOT_DIR)

    try:
        items = os.listdir(INPUT_ROOT_DIR)
    except FileNotFoundError:
        print(f"Error: 找不到输入目录 {INPUT_ROOT_DIR}")
        return

    sub_folders = [f for f in items if os.path.isdir(os.path.join(INPUT_ROOT_DIR, f))]

    print(f"Target Directory: {INPUT_ROOT_DIR}")
    print(f"Total Projects: {len(sub_folders)}")
    print("-" * 60)

    emergency_stop = False
    failed_folder = ""

    for index, folder_name in enumerate(sub_folders):
        print(f"\n[{index + 1}/{len(sub_folders)}] Processing Project: {folder_name}")

        source_path = os.path.join(INPUT_ROOT_DIR, folder_name)
        output_filename = f"output_{folder_name}.json"
        output_path = os.path.join(OUTPUT_ROOT_DIR, output_filename)

        # === 步骤 A: 智能版本切换 ===
        target_version = detect_solc_version(source_path)
        switch_solc_version(target_version)
        # ==========================

        command = [
            PYTHON_CMD,
            "main.py",
            "-s", source_path,
            "-o", output_path,
            "-k", API_KEY
        ]

        if hasattr(shlex, 'join'):
            full_command_str = shlex.join(command)
        else:
            full_command_str = " ".join([f'"{c}"' if " " in c else c for c in command])
        print(f"📋 Command: {full_command_str}")

        start_time = time.time()

        try:
            # 使用 Popen 进行流式监控
            process = subprocess.Popen(
                command,
                cwd=GPTSCAN_SRC_DIR,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    print(line, end='')
                    for keyword in STOP_KEYWORDS:
                        if keyword in line:
                            print(f"\n\n{'!' * 40}")
                            print(f"🚨 触发熔断保护！检测到关键词: '{keyword}'")
                            print(f"🚨 问题出现在文件夹: {folder_name}")
                            print(f"{'!' * 40}\n")

                            emergency_stop = True
                            failed_folder = folder_name
                            process.terminate()
                            break

                if emergency_stop:
                    break

            if not emergency_stop:
                process.wait()

            elapsed = time.time() - start_time

            if emergency_stop:
                break

            if process.returncode == 0:
                print(f"✅ Success: {folder_name} (Time: {elapsed:.2f}s)")
            else:
                print(f"❌ Failed: {folder_name} (Return Code: {process.returncode})")

        except Exception as e:
            print(f"❌ Exception: {e}")

        print("-" * 60)

    if emergency_stop:
        print("\n" + "=" * 40)
        print("⛔ 自动化测试已强制终止 ⛔")
        print(f"原因: API 使用次数/额度达到上限")
        print(f"终止位置: {failed_folder}")
        print("=" * 40 + "\n")
    else:
        print("\n🎉 所有任务已全部完成！")


if __name__ == "__main__":
    run_batch_scan()