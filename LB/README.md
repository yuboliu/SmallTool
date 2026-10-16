# LB — 负载均衡配置工具

负载均衡设备配置文件的解析与报表工具集。

## 工具列表

| 工具 | 输入 | 输出 |
|---|---|---|
| `f5_conf_to_csv` | F5 BIG-IP LTM `bigip.conf` | 每类对象一个 CSV + 汇总 Excel |
| `adp_conf_to_excel` | 弘积 ADP `startup-config` | 一个 Excel 工作簿 |

两个工具都基于 `common/blockparser.py` 的通用大括号块解析器，
Excel 输出共用 `common/excel.py`。

## f5_conf_to_csv

解析 `bigip.conf`，提取以下对象：

- `f5-nodes` — 节点（名称、地址）
- `f5-pools` — 池（成员、监视器、负载均衡算法）
- `f5-virtualaddresses` — 虚拟地址
- `f5-virtualservers` — 虚拟服务器（含 profiles、rules、persist、SNAT）
- `f5-monitors` — 健康监视器
- `f5-profiles` — 配置文件
- `f5-persistence` — 会话保持
- `f5-rules` — iRule 原文
- `f5-overview` — 虚拟服务器 ↔ 池 ↔ 成员关联总览

配置文件 `config.yaml`：

```yaml
input:
  directory: "."        # 扫描配置文件的目录（相对路径基于运行目录）
  pattern: "*.conf"     # 输入文件匹配模式
  encoding: "utf-8"
output:
  directory: "Output"   # 输出根目录，每个输入文件生成一个子目录
  formats:              # 输出格式，可选: csv, excel
    - csv
    - excel
```

输出结构：`Output/<文件名>/f5-*.csv` 和 `Output/<文件名>/<文件名>.xlsx`。

## adp_conf_to_excel

解析弘积 ADP `startup-config`，生成包含以下工作表的 Excel：

- `ip_nat_pool` — NAT 地址池
- `health_check` — 健康检查（含头部参数 interval/retry/timeout/up-check-cnt）
- `slb_pool` — SLB 池（成员以换行合并在 member 列）
- `slb_profile` — SLB 配置文件（不含 node/persist 类）
- `slb_profile_persist` — 会话保持配置文件
- `slb_virtual-address` — 虚拟地址（每个 port 一行，`%uXXXX` 编码自动解码为中文）

配置文件 `config.yaml`：

```yaml
input:
  file: "startup-config"  # ADP 设备导出的启动配置文件
  encoding: "utf-8"
output:
  file: "output.xlsx"     # 输出的 Excel 工作簿
```

## 测试

```bash
python -m pytest LB/tests -v
```

`tests/samples/` 目录下的 `bigip.conf` 与 `startup-config` 为测试样例，
也可用于手动验证工具输出。
