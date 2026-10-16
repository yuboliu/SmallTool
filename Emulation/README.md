# Emulation — 流量仿真测试工具

由 FWConfigParse 项目的 `lib/cisco_lib.py` 独立拆分并扩展而来，
采用 **B/S 架构**：发送端（sender）回放测试流量，接收端（receiver）
监听并记录到达的流量，用于验证防火墙策略的实际放行情况。

## 标准规则 JSON 格式

本工具**只接受标准 JSON**，与具体防火墙厂商解耦。任何来源
（本仓库的 FW 解析脚本、其他厂商工具、手工编写）只要生成
如下结构即可作为输入：

```json
{
  "metadata": {
    "device_name": "ASA1",
    "vendor": "cisco",
    "export_time": "2025-01-01 00:00:00"
  },
  "rules": [
    {
      "name": "OUTSIDE-IN",
      "action": "permit",
      "protocol": "tcp",
      "src_address": "any",
      "dst_address": "10.1.0.0/24\n10.1.1.5/32",
      "dst_port": "80\n443"
    }
  ]
}
```

规则字段约定：

- `protocol`：`tcp` / `udp` / `icmp` 等（发送端只发送 tcp/udp，其余跳过）
- `src_address` / `dst_address`：CIDR 地址，多个用 `\n` 分隔；`any` 按
  `any_ip_replacement` 替换；兼容华为原始格式 `x.x.x.x mask 32` 和
  范围格式 `a - b`（取起始地址）
- `dst_port`：端口号，多个用 `\n` 分隔，支持范围 `17001-17003`
- 额外字段（如 `source_zone`、`type`）原样保留，不影响处理

本仓库中 `FW.cisco_acl_parse` 和 `FW.huawei_policy_parse` 的 JSON 输出
即为该标准格式（`metadata.vendor` 分别为 `cisco` / `huawei`）。

## 工作流程（B/S 架构）

```
┌─ 发送端 (Client) ──┐          ┌─ 被测设备 ─┐          ┌─ 接收端 (Server) ──┐
│ traffic_emulator   │  TCP/UDP  │  Firewall  │  TCP/UDP  │ traffic_emulator   │
│ send               │ ────────> │  (策略)     │ ────────> │ receive            │
└────────────────────┘           └────────────┘           └────────────────────┘
        ▲                                                          │
        └──────── send_report.yaml ◄── 对比 ── received.jsonl ◄────┘

准备阶段：FW 解析脚本 → 标准 JSON → traffic_emulator plan → traffic_plan.yaml
```

- **plan**（任意平台）：读取标准 JSON，展开生成扁平测试流量计划
  （src_ip / dst_ip / dst_port / protocol）；可选在 Linux 上把地址配置到
  ipvlan 虚拟接口（需 root）
- **send**（发送端）：按计划逐条发送 TCP 连接 / UDP 数据报，可选绑定
  计划中的源地址；结果写入发送报告
- **receive**（接收端）：监听 TCP/UDP 端口，把到达流量记录为 JSON Lines；
  端口可显式配置或从计划文件推导

## 使用

```bash
# 1. 生成标准 JSON（以 Cisco 为例，华为同理）
python -m FW.cisco_acl_parse        # 输出 Output/<设备>.json

# 2. 生成测试流量计划（将 JSON 放入 input.directory 指向的目录）
python -m Emulation.traffic_emulator plan

# 3. 接收端启动监听（在被测设备另一侧的主机上）
python -m Emulation.traffic_emulator receive

# 4. 发送端回放流量
python -m Emulation.traffic_emulator send

# 5. 对比 send_report.yaml 与 logs/received.jsonl，验证策略放行情况
```

无子命令时默认为 `plan`：`python -m Emulation.traffic_emulator -c my.yaml`

## 配置文件（config.yaml）

```yaml
input:
  directory: "ConfigExport"  # 标准规则 JSON 所在目录
  pattern: "*.json"
emulation:
  rules: []                  # 只仿真这些规则名；空 = 全部
  address_field: "dst_address"  # 接口配置用源还是目的地址
  any_ip_replacement:
    src: "192.0.2.1/32"
    dst: "198.51.100.1/32"
  base_interface: "eth0"
  setup_interfaces: false    # true = 配置 ipvlan 接口（仅 Linux，需 root）
output:
  file: "traffic_plan.yaml"
sender:                      # 发送端
  plan_file: "traffic_plan.yaml"
  timeout: 2.0
  bind_source: false         # 绑定计划中的 src_ip（需本机接口已配置该地址）
  report_file: "send_report.yaml"
receiver:                    # 接收端
  host: "0.0.0.0"
  tcp_ports: []              # 与 udp_ports 都为空时从 plan_file 推导
  udp_ports: []
  plan_file: "traffic_plan.yaml"
  log_file: "logs/received.jsonl"
logging:
  console: true
  directory: "logs"
```

## 处理规则

- 多行地址/端口逐一展开，端口范围展开为单端口
- 网段地址取第一个主机地址（如 `10.1.0.0/24` → `10.1.0.1/32`）
- `send` 对协议非 tcp/udp 或端口非数字（如 icmp、端口 0）的条目标记 `skipped`

## 测试

```bash
python -m pytest Emulation/tests -v
```

含 sender/receiver 本机回环端到端用例。

## 重构说明

- 配置来源解耦：只认标准规则 JSON，不再绑定特定工具的导出结构
- 修复原代码 `any_ip_replacement` 字符串/字典混用的接口不一致问题
- 新增 B/S 收发两端（原归档代码只有计划生成库，无收发功能）
- 纯逻辑与系统调用分离，可跨平台测试；`os.system` 改为 `subprocess.run`
