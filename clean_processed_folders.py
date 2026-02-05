import os
import shutil

# ================= 配置区域 (请务必确认路径) =================

# 1. 存放输出结果的文件夹 (参考也就是你的 output 目录)
OUTPUT_DIR_PATH = r"C:\Coding\CodingTool\PyCharm\PyCharm2025.2.1.1\Project\GPTScan\output"

# 2. 存放原始合约的文件夹 (也就是你要删除其中文件夹的地方)
SOURCE_DIR_PATH = r"C:\Coding\CodingTool\PyCharm\PyCharm2025.2.1.1\Project\GPTScan\GPTScan-Top200-dev"


# ===========================================================

def clean_processed_projects():
    # 1. 检查路径是否存在
    if not os.path.exists(OUTPUT_DIR_PATH) or not os.path.exists(SOURCE_DIR_PATH):
        print("❌ 错误：配置的路径不存在，请检查 OUTPUT_DIR_PATH 和 SOURCE_DIR_PATH")
        return

    print(f"📂 正在扫描输出目录: {OUTPUT_DIR_PATH}")
    print(f"🗑️  目标删除目录: {SOURCE_DIR_PATH}")
    print("-" * 60)

    deleted_count = 0
    skipped_count = 0

    # 2. 获取输出目录下的所有文件
    try:
        output_files = os.listdir(OUTPUT_DIR_PATH)
    except Exception as e:
        print(f"❌ 读取输出目录失败: {e}")
        return

    # 3. 遍历每一个 json 文件
    for filename in output_files:
        # 过滤条件：必须是以 output_ 开头，以 .json 结尾
        if filename.startswith("output_") and filename.endswith(".json"):

            # 4. 提取文件夹名称
            # 逻辑：去除前缀 "output_" (7个字符) 和后缀 ".json" (5个字符)
            # 例如: output_0x123..._poly.json  ->  0x123..._poly
            target_folder_name = filename[7:-5]

            # 5. 构建要删除的目标文件夹完整路径
            target_folder_path = os.path.join(SOURCE_DIR_PATH, target_folder_name)

            # 6. 检查目标文件夹是否存在
            if os.path.exists(target_folder_path) and os.path.isdir(target_folder_path):
                try:
                    # 7. 执行删除 (shutil.rmtree 可以删除包含文件的文件夹)
                    shutil.rmtree(target_folder_path)
                    print(f"✅ 已删除: {target_folder_name}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ 删除失败: {target_folder_name} (原因: {e})")
            else:
                # 文件夹不存在 (可能已经被删了，或者本身就没有)
                # print(f"ℹ️  跳过: {target_folder_name} (源目录中不存在)")
                skipped_count += 1

    print("-" * 60)
    print(f"🎉 清理完成！")
    print(f"共删除了 {deleted_count} 个文件夹。")
    print(f"跳过了 {skipped_count} 个 (未找到或已删除)。")


if __name__ == "__main__":
    # 为了防止误删，增加一个简单的确认步骤
    confirm = input(f"⚠️ 警告：这将永久删除 {SOURCE_DIR_PATH} 下已完成处理的文件夹。\n确认要继续吗？(输入 y 继续): ")
    if confirm.lower() == 'y':
        clean_processed_projects()
    else:
        print("已取消操作。")