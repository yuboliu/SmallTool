# Emulation — 流量仿真测试工具

由 FWConfigParse 项目的 `lib/cisco_lib.py` 独立拆分而来。

读取 [FW/cisco_acl_parse](../FW/README.md) 导出的结构化 JSON（`ConfigExport/*.json`），
将 ACL 规则展开为扁平的测试流量计划（src_ip / dst_ip / dst_port / protocol），
导出为 YAML/JSON 供流量发生器使用；在 Linux 上还可以自动把目的地址
配置到 ipvlan 虚拟接口上（需 root），使测试流量可达。

## 工作流程

```
FW.cisco_acl_parse ──> ConfigExport/<设备>.json ──> traffic_emulator ──> traffic_plan.yaml
                                                              │
                                              (可选, Linux+root) ipvlan 接口配置
```

## 处理规则

- 多行地址/端口（`\n` 分隔）逐一展开，端口范围（如 `17001-17003`）展开为单端口
- 网段地址取该网段的第一个主机地址（如 `10.1.0.0/24` → `10.1.0.1/32`）
- ACL 中的 `any` 按 `any_ip_replacement` 替换为测试地址
- `emulation.rules` 非空时只仿真列出的 ACL 规则名

## 配置文件（config.yaml）

```yaml
input:
  directory: "ConfigExport"  # cisco_acl_parse 导出的 JSON 所在目录
  pattern: "*.json"
emulation:
  rules: []                  # 只仿真这些规则名；空 = 全部
  address_field: "dst_address"
  any_ip_replacement:
    src: "192.0.2.1/32"
    dst: "198.51.100.1/32"
  base_interface: "eth0"
  setup_interfaces: false    # true = 配置 ipvlan 接口（仅 Linux，需 root）
output:
  file: "traffic_plan.yaml"  # .json 后缀则输出 JSON
logging:
  console: true
  directory: "logs"
```

## 运行

```bash
python -m Emulation.traffic_emulator [-c config.yaml]
```

`setup_interfaces: false` 时可在任意平台运行（只导出流量计划）；
设为 `true` 必须在 Linux 上以 root 运行，会对每个目的地址执行
`ip link add link <base> veth<N> type ipvlan mode l2` 等命令。

## 测试

```bash
python -m pytest Emulation/tests -v
```

## 重构说明

- 配置由缺失的 config 模块改为 YAML 文件
- 修复原代码 `any_ip_replacement` 一处按字符串、一处按字典使用的接口不一致问题
- 流量计划生成等纯逻辑与 Linux 系统调用分离，纯逻辑可跨平台测试
- `os.system` 改为 `subprocess.run(check=True)`，失败会记录日志
