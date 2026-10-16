# SmallTool

网络运维小工具合集。本项目由以下项目合并重构而来：

- f5-conf-to-csv（已合并至此仓库）
- Horizon-ADP_Conf-To-Excel（已合并至此仓库）
- FWConfigParse（已合并至此仓库）
- Subnet Segment Generation（已合并至此仓库）

## 目录结构

```
SmallTool/
├── LB/                          # 负载均衡配置工具
│   ├── common/                  # 公共库：配置块解析器、Excel 输出
│   ├── f5_conf_to_csv/          # F5 BIG-IP LTM 配置 → CSV + Excel
│   ├── adp_conf_to_excel/       # 弘积 ADP 配置 → Excel
│   └── tests/
├── FW/                          # 防火墙配置解析工具
│   ├── cisco_acl_parse/         # Cisco ASA 配置 → Excel + JSON
│   ├── huawei_policy_parse/     # 华为 USG 配置 → Excel
│   └── tests/
├── Subnet/                      # 子网段生成工具
│   ├── subnet_generator/        # IPv4/IPv6 子网生成 + 地址分配
│   └── tests/
├── Emulation/                   # 流量仿真测试工具（B/S 架构）
│   ├── traffic_emulator/        # plan 计划生成 / send 发送端 / receive 接收端
│   └── tests/
├── requirements.txt
└── README.md
```

每个工具的详细说明见各自目录下的 README：[LB](LB/README.md) ｜
[FW](FW/README.md) ｜ [Subnet](Subnet/README.md) ｜ [Emulation](Emulation/README.md)

## 环境要求

- Python 3.10+
- 依赖见 `requirements.txt`：`pip install -r requirements.txt`
- 测试依赖：`pip install pytest`

## 快速开始

所有命令均在仓库根目录下执行，每个工具由各自的 `config.yaml` 控制
（`-c` 可指定其他配置文件）。

```bash
# F5 BIG-IP 配置 → CSV + Excel（扫描当前目录 *.conf）
python -m LB.f5_conf_to_csv

# 弘积 ADP startup-config → Excel
python -m LB.adp_conf_to_excel

# Cisco ASA 配置（Config/*.txt）→ Excel + JSON
python -m FW.cisco_acl_parse

# 华为 USG 配置（Config/*）→ Excel
python -m FW.huawei_policy_parse

# 子网段生成（命令行参数或 YAML 配置文件）
python -m Subnet.subnet_generator --ipv4-base 10.8.242.0/24 --ipv4-prefix 29 --count 24

# 流量仿真（B/S 架构）：标准规则 JSON → 计划 → 发送 / 接收
# FW 解析脚本的 JSON 输出即为 Emulation 的标准输入格式
python -m Emulation.traffic_emulator plan      # 生成测试流量计划
python -m Emulation.traffic_emulator receive   # 接收端：监听并记录到达流量
python -m Emulation.traffic_emulator send      # 发送端：按计划回放流量
```

## 运行测试

```bash
python -m pytest LB/tests FW/tests Subnet/tests Emulation/tests -v
```

## 重构说明

相比原项目的改进：

- 统一使用 Python 3，配置全部改为 YAML 文件
- 移除了 pandas、sqlite3、xlsxwriter 依赖，仅使用标准库 csv + openpyxl
- 两个 LB 工具共用同一个大括号配置块解析器（`LB/common/blockparser.py`）
- 修复了原实现中的多处解析 bug（`str.lstrip()` 误用、名称字段错位、
  `cache-uri-include` 字段丢失、华为服务集遇 `#` 不闭合等）
- 补充了 pytest 测试与样例配置文件
