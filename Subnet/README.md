# Subnet — 子网段生成工具

由 Subnet Segment Generation 项目重构而来：生成 IPv4/IPv6 子网，
并自动为每个子网分配交换机和防火墙地址（默认交换机奇数、防火墙偶数，可互换）。

## 使用

在仓库根目录下运行：

```bash
# 命令行参数方式
python -m Subnet.subnet_generator --ipv4-base 10.8.242.0/24 --ipv4-prefix 29 --count 24

# 同时生成 IPv4 + IPv6
python -m Subnet.subnet_generator \
  --ipv4-base 10.8.242.0/24 --ipv4-prefix 29 \
  --ipv6-base FC00:0:8:242::/120 --ipv6-prefix 125 \
  --count 24 --output subnets.csv

# YAML 配置文件方式（注意：--config 会忽略其他命令行参数）
python -m Subnet.subnet_generator --config config.yaml

# 无任何参数时使用工具自带的 config.yaml
python -m Subnet.subnet_generator
```

## 命令行参数

| 参数 | 说明 | 示例 |
|---|---|---|
| `--ipv4-base` | IPv4 基础网段 | `10.8.242.0/24` |
| `--ipv4-prefix` | IPv4 目标前缀长度 | `29` |
| `--ipv6-base` | IPv6 基础网段 | `FC00:0:8:242::/120` |
| `--ipv6-prefix` | IPv6 目标前缀长度 | `125` |
| `--count` | 生成子网数量 | `24` |
| `--switch-odd` | 交换机使用奇数地址（默认） | - |
| `--firewall-odd` | 防火墙使用奇数地址 | - |
| `--output` | 输出文件路径（默认终端） | `subnets.csv` |
| `--format` | 输出格式：`csv`/`json`/`text` | `csv` |
| `--config` | 从 YAML 配置文件加载 | `config.yaml` |

## 配置文件格式（YAML）

```yaml
ipv4_base: "10.8.242.0/24"
ipv4_prefix: 29
ipv6_base: "FC00:0:8:242::/120"
ipv6_prefix: 125
count: 24
switch_is_odd: true
output_file: "subnets.csv"
output_format: "csv"
```

## 地址分配规则

- 自动跳过网段地址（主机位全 0）和广播地址（主机位全 1）
- 默认交换机取子网内第一个奇数地址，防火墙取第一个偶数地址
- 以 /29（IPv4）或 /125（IPv6）为例：8 个地址中 6 个可用

## 测试

```bash
python -m pytest Subnet/tests -v
```

## 重构说明

- 配置文件格式由 JSON 改为 YAML
- 无第三方依赖（仅用标准库 `ipaddress`；仅配置文件需要 PyYAML）
