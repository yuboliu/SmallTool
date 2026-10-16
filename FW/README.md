# FW — 防火墙配置解析工具

防火墙设备配置文件的解析与报表工具集，由 FWConfigParse 项目重构而来。

## 工具列表

| 工具 | 设备 | 输入 | 输出 |
|---|---|---|---|
| `cisco_acl_parse` | Cisco ASA | `Config/*.txt` | Excel（地址组/服务组/ACL规则）+ JSON |
| `huawei_policy_parse` | 华为 USG | `Config/*` | Excel（地址集/服务集/安全策略） |

## cisco_acl_parse

解析 Cisco ASA 配置（测试过 ASA 7.2(4) 风格配置）：

- `object-group network` → 地址组（IP/掩码自动转换为 CIDR）
- `object-group service` → 服务组（服务名自动映射端口号，如 www→80）
- `access-list` → ACL 规则（源/目的地址、目的端口、object-group 引用）
- `replace_object_group: true` 时 ACL 中的 object-group 引用展开为实际内容

配置文件 `config.yaml`：

```yaml
input:
  directory: "Config"   # 存放设备配置文件的目录
  pattern: "*.txt"
  encoding: "utf-8"
output:
  directory: "Output"   # 每个设备生成 <设备名>.xlsx / <设备名>.json
  formats: [excel, json]
parse:
  replace_object_group: true
```

运行：`python -m FW.cisco_acl_parse [-c config.yaml]`

## huawei_policy_parse

解析华为 USG 配置（`display current-configuration` 输出）：

- `ip address-set` → 地址集（支持 mask / range 格式，IPv4/IPv6）
- `ip service-set` → 服务集
- `security-policy` → 安全策略
- 「安全策略-关联」工作表：策略中的地址集/服务集引用展开为实际内容

配置文件 `config.yaml`：

```yaml
input:
  directory: "Config"
  pattern: "*"
  encoding: "utf-8"
output:
  directory: "Output"   # 每个设备生成 <设备名>.xlsx
```

运行：`python -m FW.huawei_policy_parse [-c config.yaml]`

## 测试

```bash
python -m pytest FW/tests -v
```

## 重构说明

- 配置由缺失的 `config.py` 模块改为 YAML 文件
- 华为工具移除了 pandas 依赖，直接使用 openpyxl 写 Excel
- 提取函数改为接收配置文本而非文件路径，便于测试
- 修复了服务集在遇到 `#` 分节符时不闭合、导致策略内 service 行误入服务集的问题
- 原项目中的 `lib/cisco_lib.py`（Linux 测试流量仿真库，需 root 配置 veth 接口）
  与配置解析无关，未纳入本仓库
