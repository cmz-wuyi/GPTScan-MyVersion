import os
import json
import csv

# ================= 🔧 配置区域 (Configuration) =================

# 1. 输入目录 (Output Directory)
INPUT_OUTPUT_DIR = r"C:\Coding\CodingTool\PyCharm\PyCharm2025.2.1.1\Project\GPTScan\output"

# 2. 输出 CSV 文件名
RESULT_CSV_PATH = "paper_comprehensive_report.csv"

# 3. 真值配置 (Ground Truth Configuration)
# 定义哪些项目实际上包含漏洞 (Positive Samples)。
# 如果你的测试集全部是无漏洞样本（用于测试误报率），请保持为空集合。
VULNERABLE_PROJECTS = {
    # 示例: "0x4e15361fd6b4bb609fa63c81a2be19d873717870_eth",
}

# 默认标签 (如果项目不在上面的列表中，默认为安全/Negative)
DEFAULT_IS_VULNERABLE = False


# =============================================================

def get_ground_truth(project_name):
    """根据配置判断该项目实际上是否有漏洞"""
    if project_name in VULNERABLE_PROJECTS:
        return True  # Positive (Vulnerable)
    return DEFAULT_IS_VULNERABLE  # Negative (Safe)


def calculate_metrics(tp, fp, tn, fn):
    """计算 Paper 1 所需的分类指标"""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    return precision, recall, f1, accuracy


def generate_report():
    if not os.path.exists(INPUT_OUTPUT_DIR):
        print(f"❌ Error: 找不到目录 {INPUT_OUTPUT_DIR}")
        return

    print(f"📂 正在读取目录: {INPUT_OUTPUT_DIR}")

    try:
        all_files = os.listdir(INPUT_OUTPUT_DIR)
        metadata_files = [f for f in all_files if f.endswith(".metadata.json")]
    except Exception as e:
        print(f"❌ 读取目录失败: {e}")
        return

    print(f"🔍 找到 {len(metadata_files)} 个数据文件，开始全量解析...")

    # --- 统计计数器 ---
    stats = {
        "TP": 0, "FP": 0, "TN": 0, "FN": 0,
        "Total_Time": 0.0,
        "Total_Cost": 0.0,
        "Total_Files": 0,
        "Success_Count": 0,
        "Fail_Count": 0,
        "Total_LOC": 0
    }

    rows = []

    # --- 遍历文件 ---
    for meta_file in metadata_files:
        meta_path = os.path.join(INPUT_OUTPUT_DIR, meta_file)
        main_json_file = meta_file.replace(".metadata.json", "")
        main_json_path = os.path.join(INPUT_OUTPUT_DIR, main_json_file)

        # 提取项目名
        if meta_file.startswith("output_") and meta_file.endswith(".json.metadata.json"):
            project_name = meta_file[7:-19]
        else:
            project_name = meta_file

        # 初始化行数据 (包含两份 CSV 的所有字段)
        row_data = {
            "Project Name": project_name,
            "Success": "Unknown",  # Paper 2: Robustness
            "Real_Label": "",  # Paper 1: Ground Truth
            "Classification": "",  # Paper 1: TP/FP...
            "Final_Reports": 0,  # Paper 2: Detection/Noise
            "Time(s)": 0.0,  # Paper 2: Performance
            "Cost($)": 0.0,  # Paper 1: Economic
            "LOC": 0,  # Paper 2: Scale
            "Files": 0,
            "Contracts": 0,
            "Initial_Warns": 0,  # Process Metric
            "Static_Filtered": 0,  # Process Metric
            "Vuln_Types": "",  # Paper 2: Scope
            "Message": ""  # Error Log
        }

        try:
            # 1. 读取 Metadata (统计数据)
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                row_data["LOC"] = meta.get("loc", 0)
                row_data["Files"] = meta.get("files", 0)
                row_data["Contracts"] = meta.get("contracts", 0)
                row_data["Time(s)"] = meta.get("used_time", 0.0)
                row_data["Cost($)"] = meta.get("estimated_cost", 0.0)

                vul_before = meta.get("vul_before_static", 0)
                vul_after = meta.get("vul_after_static", 0)  # 中间态
                vul_final = meta.get("vul_after_merge", 0)

                row_data["Initial_Warns"] = vul_before
                row_data["Static_Filtered"] = vul_before - vul_after
                row_data["Final_Reports"] = vul_final

                # 累加统计
                stats["Total_Time"] += row_data["Time(s)"]
                stats["Total_Cost"] += row_data["Cost($)"]
                stats["Total_LOC"] += row_data["LOC"]
                stats["Total_Files"] += 1

            # 2. 读取 Main JSON (状态与详情)
            if os.path.exists(main_json_path):
                with open(main_json_path, 'r', encoding='utf-8') as f:
                    main = json.load(f)

                    # 鲁棒性状态
                    success = main.get("success", False)
                    row_data["Success"] = str(success)
                    if success:
                        stats["Success_Count"] += 1
                    else:
                        stats["Fail_Count"] += 1
                        row_data["Message"] = main.get("message", "Unknown Error")

                    # 提取漏洞类型 (Paper 2 Scope)
                    results = main.get("results", [])
                    types = set()
                    for res in results:
                        if isinstance(res, str):
                            types.add(res)
                        elif isinstance(res, dict):
                            # 尝试获取漏洞名称字段，这里假设是 'vulnerability' 或 'name'
                            v_name = res.get("vulnerability", res.get("name", "Unknown"))
                            types.add(v_name)
                    row_data["Vuln_Types"] = "; ".join(types)
            else:
                row_data["Success"] = "False"
                row_data["Message"] = "Main JSON Missing"
                stats["Fail_Count"] += 1

            # 3. 自动分类逻辑 (TP/FP/TN/FN)
            is_really_vulnerable = get_ground_truth(project_name)
            has_ai_warning = row_data["Final_Reports"] > 0

            if is_really_vulnerable:
                row_data["Real_Label"] = "Vulnerable"
                if has_ai_warning:
                    row_data["Classification"] = "TP"
                    stats["TP"] += 1
                else:
                    row_data["Classification"] = "FN"
                    stats["FN"] += 1
            else:
                row_data["Real_Label"] = "Safe"
                if has_ai_warning:
                    row_data["Classification"] = "FP"
                    stats["FP"] += 1
                else:
                    row_data["Classification"] = "TN"
                    stats["TN"] += 1

            rows.append(row_data)

        except Exception as e:
            print(f"⚠️ 解析错误 {project_name}: {e}")

    # --- 计算最终指标 ---
    precision, recall, f1, accuracy = calculate_metrics(
        stats["TP"], stats["FP"], stats["TN"], stats["FN"]
    )
    avg_time = stats["Total_Time"] / stats["Total_Files"] if stats["Total_Files"] > 0 else 0
    success_rate = stats["Success_Count"] / stats["Total_Files"] if stats["Total_Files"] > 0 else 0

    # --- 写入 CSV ---
    # 定义表头 (所有详细列)
    headers = [
        "Project Name", "Success", "Real_Label", "Classification",
        "Final_Reports", "Vuln_Types",
        "Time(s)", "Cost($)",
        "LOC", "Files", "Contracts",
        "Initial_Warns", "Static_Filtered", "Message"
    ]

    try:
        with open(RESULT_CSV_PATH, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)

            # 1. 写入主表头
            writer.writerow(headers)
            # 写入每一行数据
            for r in rows:
                writer.writerow([r[h] for h in headers])

            # 2. 写入分隔空行
            writer.writerow([])
            writer.writerow([])

            # 3. 写入汇总报告 (Metrics Summary)
            writer.writerow(["=== 📊 Final Metrics Summary (汇总报告) ===", "", ""])
            writer.writerow(["Metric (参数)", "Value (数值)", "Detailed Explanation (详细解释)"])

            # Paper 1 Metrics
            writer.writerow(["F1 Score", f"{f1:.2%}",
                             "Paper 1 核心指标。精确率和召回率的调和平均数，综合衡量模型性能。公式: 2*(P*R)/(P+R)。"])
            writer.writerow(
                ["Precision", f"{precision:.2%}", "精确率。所有被报告为有漏洞的合约中，确实有漏洞的比例。衡量抗误报能力。"])
            writer.writerow(
                ["Recall", f"{recall:.2%}", "召回率 (也称 Detection Rate)。所有真实有漏洞的合约中，被成功检测出的比例。"])
            writer.writerow(["Accuracy", f"{accuracy:.2%}", "准确率。模型判断正确(包括TP和TN)的样本占总样本的比例。"])
            writer.writerow(
                ["Total Cost", f"${stats['Total_Cost']:.4f}", "经济成本。调用 LLM API (如 GPT-4) 所消耗的总费用。"])

            # Paper 2 Metrics
            writer.writerow(["Avg Time", f"{avg_time:.2f}s",
                             "Paper 2 核心指标 (效率)。平均每个项目的分析耗时。对比标准: Slither(~5s), Mythril(~84s)。"])
            writer.writerow(
                ["Success Rate", f"{success_rate:.2%}", "Paper 2 核心指标 (鲁棒性)。工具成功完成分析未崩溃的比例。"])
            writer.writerow(["Total LOC", stats["Total_LOC"], "代码规模。测试集中包含的 Solidity 代码总行数。"])

            # Raw Counts
            writer.writerow(["True Positives (TP)", stats["TP"], "正确检测。实际上有漏洞且工具成功报出。"])
            writer.writerow(["False Positives (FP)", stats["FP"], "误报 (噪音)。实际上安全但工具报出有漏洞。"])
            writer.writerow(["True Negatives (TN)", stats["TN"], "正确忽略。实际上安全且工具未报漏洞。"])
            writer.writerow(["False Negatives (FN)", stats["FN"], "漏报。实际上有漏洞但工具未能检出。"])

            # 4. 写入数据字典 (Data Dictionary / Glossary)
            writer.writerow([])
            writer.writerow(["=== 📖 Column Glossary (参数详细解释字典) ===", "", ""])
            writer.writerow(["Column Name (列名)", "-", "Detailed Explanation (参数解释)"])

            glossary = [
                ("Project Name", "被测试的智能合约项目名称或哈希值。"),
                ("Success", "鲁棒性状态。True 表示工具完整运行结束，False 表示运行中途崩溃或超时。"),
                ("Real_Label", "Ground Truth (真值)。根据配置预设的标签，'Vulnerable' 表示真实有毒，'Safe' 表示真实安全。"),
                ("Classification", "分类结果。TP(真阳性), FP(误报), TN(真阴性), FN(漏报)。用于计算 F1 分数。"),
                ("Final_Reports",
                 "最终报告数量。经过静态分析过滤后，AI 最终认定的漏洞数量。在安全样本测试中，此值大于0即为误报。"),
                ("Vuln_Types",
                 "漏洞类型。工具检测出的具体漏洞类别 (如 Reentrancy, Arithmetic)，用于评估 Paper 2 的检测范围 (Scope)。"),
                ("Time(s)", "执行时间。从启动分析到生成报告的总耗时 (秒)。"),
                ("Cost($)", "预估成本。基于 Token 消耗计算的 API 费用。"),
                ("LOC", "Lines of Code。合约的代码行数，衡量项目复杂度和规模。"),
                ("Files / Contracts", "文件数 / 合约数。项目的结构复杂度指标。"),
                ("Initial_Warns", "初始警报。LLM 在第一阶段（未结合静态分析前）产生的原始怀疑数量。"),
                ("Static_Filtered", "过滤数量。被静态分析引擎（如 Slither 验证）排除掉的 AI 误报数量。"),
                ("Message", "错误日志。如果 Success 为 False，此处记录崩溃原因。")
            ]

            for item in glossary:
                writer.writerow([item[0], "-", item[1]])

        print(f"\n✅ 终极报告已生成: {os.path.abspath(RESULT_CSV_PATH)}")
        print(f"📊 F1 Score: {f1:.2%}")
        print(f"🚀 Avg Time: {avg_time:.2f}s")

    except Exception as e:
        print(f"❌ 写入 CSV 失败: {e}")


if __name__ == "__main__":
    generate_report()