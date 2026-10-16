# SmallTool

网络运维小工具合集。本项目由以下两个仓库合并重构而来：

- f5-conf-to-csv（已合并至此仓库）
- Horizon-ADP_Conf-To-Excel（已合并至此仓库）

## 目录结构

```
SmallTool/
├── LB/                          # 负载均衡相关工具
│   ├── common/                  # 公共库：配置块解析器、Excel 输出
│   ├── f5_conf_to_csv/          # F5 BIG-IP LTM 配置 → CSV + Excel
│   │   ├── config.yaml
│   │   └── converter.py
│   ├── adp_conf_to_excel/       # 弘积 ADP 配置 → Excel
│   │   ├── config.yaml
│   │   └── converter.py
│   └── tests/                   # pytest 测试与样例配置
├── requirements.txt
└── README.md
```

## 环境要求

- Python 3.10+
- 依赖见 `requirements.txt`：`pip install -r requirements.txt`
- 测试依赖：`pip install pytest`

## 快速开始

所有命令均在仓库根目录下执行。

**F5 BIG-IP 配置转换**（将 `bigip.conf` 放到当前目录）：

```bash
python -m LB.f5_conf_to_csv                    # 使用默认配置
python -m LB.f5_conf_to_csv -c my-config.yaml  # 指定配置文件
```

**弘积 ADP 配置转换**（将 `startup-config` 放到当前目录）：

```bash
python -m LB.adp_conf_to_excel
python -m LB.adp_conf_to_excel -c my-config.yaml
```

每个工具的行为由 YAML 配置文件控制，详见 [LB/README.md](LB/README.md)。

## 运行测试

```bash
python -m pytest LB/tests -v
```

## 重构说明

相比原仓库的改进：

- 统一使用 Python 3，配置由命令行参数/硬编码改为 YAML 文件
- F5 工具移除了 pandas、sqlite3、xlsxwriter 依赖，仅使用标准库 csv + openpyxl
- 两个工具共用同一个大括号配置块解析器（`LB/common/blockparser.py`）
- 修复了原实现中 `str.lstrip()` 误用导致的字段解析错误、monitor/profile/persistence
  名称错位、`cache-uri-include` 字段丢失等问题
- 补充了 pytest 测试与样例配置文件
