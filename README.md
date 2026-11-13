# check

在 Ubuntu 24.04 上用中文查看主机状态的 Bash 命令行工具。普通用户即可运行，终端中自动显示颜色，重定向或管道输出时自动去掉颜色。

## 安装与使用

```bash
sudo bash install.sh
check
check my-server
check --help
```

也可以直接运行 `./check`，无需安装。安装脚本会将同目录的 `check` 复制到 `/usr/local/bin/check`，权限为 `0755`；重复安装会覆盖旧版本。安装脚本可从任意工作目录调用。卸载：

```bash
sudo rm /usr/local/bin/check
```

关闭颜色：

```bash
NO_COLOR=1 check
NO_COLOR=1 check my-server
```

## 显示内容与计算口径

| 内容 | 说明 |
| --- | --- |
| 主机信息 | 主机名、公网 IP、系统版本、开机天数/小时/分钟 |
| CPU | `nproc` 可用核数，以及 1/5/15 分钟负载；各项负载超过核数标红 |
| 内存 | 已用 = `MemTotal - MemAvailable`，避免将可回收缓存全部算作已用 |
| Swap | 已用 = 总量 − 空闲；未启用时显示 0 和提示 |
| 根分区 | 已用/分区总量；百分比按 `df` 的口径，即已用 ÷（已用 + 普通用户可用），保留块不算可用 |
| 本月流量 | 默认出口网卡的 vnStat 月度累计接收 + 发送；无 IPv4 默认路由时使用 vnStat 默认网卡，并显示网卡名和统计月份 |
| tmux | 当前用户、默认 socket 下可访问的会话，包含窗口数和连接状态 |
| 进程 | 按 RSS 从高到低显示前 5 个进程的 PID、用户、RSS MiB、内存百分比和进程名 |

内存、Swap、根分区、流量额度占比**严格超过 80% 标黄，严格超过 90% 标红**，其余标绿；判断使用未四舍五入的值，显示保留一位小数。负载超过 CPU 核数表示可能存在排队，也可能涉及 I/O 等待。

每月额度默认（硅谷）为十进制 **1.5 TB = 1,500,000,000,000 字节**；上海主机 `VM-0-5-ubuntu` 内置 **1 TB 占位额度**，请按实际套餐修改。流量按接收和发送合计计算；容量显示使用二进制 KiB/MiB/GiB/TiB。因此 1.5 TB 额度显示约为 1.36 TiB。多网卡时只统计选中的出口网卡，避免桥接、隧道和物理网卡重复计数。若服务商只计算出站流量，其账单口径可能不同。

## 按主机配置每月额度

额度按被检查机器的 `hostname` 输出精确匹配，区分大小写。优先级为：环境变量 > 配置文件 > 内置主机额度 > 默认 1.5 TB。所有显示、百分比和颜色阈值均使用最终额度。

默认配置文件为 `${XDG_CONFIG_HOME:-$HOME/.config}/check/traffic-quotas.conf`。每行使用 `主机名=额度`，额度单位为十进制 TB，支持小数、空行和 `#` 注释。例如把上海额度改为实际的 2 TB：

```bash
mkdir -p ~/.config/check
cat > ~/.config/check/traffic-quotas.conf <<'EOF'
# 上海：当前内置占位值是 1 TB，在这里替换为实际套餐额度
VM-0-5-ubuntu=2
# 其他主机可继续添加（使用 hostname 的实际输出）
my-silicon-valley-host=1.5
EOF
check
```

也可以通过 `CHECK_CONFIG_FILE=/path/to/traffic-quotas.conf check` 指定配置文件。配置文件只作为数据读取，不执行其中的命令；无需重新安装即可生效。

环境变量 `CHECK_TRAFFIC_QUOTAS` 使用相同格式，多台主机以换行分隔：

```bash
CHECK_TRAFFIC_QUOTAS='VM-0-5-ubuntu=2' check
export CHECK_TRAFFIC_QUOTAS=$'VM-0-5-ubuntu=2\nmy-silicon-valley-host=1.5'
check
```

同一来源重复配置某主机时最后一条生效。额度必须为普通十进制正数（不带 `TB` 后缀，不支持科学计数法），至少 1 字节且不超过 1,000,000 TB；无效的匹配额度会警告并保留较低优先级的额度。未匹配的主机配置不影响当前主机。

`check my-server` 在**远端**读取主机名、配置文件和环境变量。本地配置及 `CHECK_TRAFFIC_QUOTAS` 不会主动传到远端；建议将额度文件放到远端登录用户的上述默认路径。内置的上海占位额度随脚本传输，无需在远端安装新版工具。

## 可选工具与流量统计

脚本使用 Ubuntu 默认具备的 Bash、`/proc`、GNU coreutils、awk、sed 和 ps；不需要 Python、jq 或额外 Bash 库。Python 3 仅用于运行仓库测试。

公网 IP 依次使用 `curl -s -m 3 ifconfig.me`、`curl -s -m 3 ip.sb`、`curl -s -m 3 api.ipify.org` 查询，每次最多等待 3 秒，获取 IP 后立即停止。请求失败或返回内容不是 IP 时尝试下一站；全部失败或缺少 `curl` 时显示“未知”并继续其他检查。返回的是请求的出口公网 IP，可能属于 NAT 或代理。

缺少 `vnstat` 或 `tmux` 时，会显示安装提示，其他检查照常运行。启用月流量统计：

```bash
sudo apt update
sudo apt install -y vnstat
sudo systemctl enable --now vnstat
vnstat --iflist
```

如果出口网卡尚未加入数据库，用实际网卡名替换 `ens3`：

```bash
sudo vnstat --add -i ens3
sudo systemctl restart vnstat
```

vnStat 只能记录开始监控之后的流量，不能补算安装前的历史数据；数据库损坏、服务中断或月度起始日配置都会影响统计。默认按自然月累计，建议保持 vnStat 的 `MonthRotate` 为 `1`；请同时留意输出的统计月份。读取方式使用官方支持的 [`vnstat --oneline b`](https://humdi.net/vnstat/man/2.11/vnstat.html)，直接获取字节数。

## 远程检查

在 `~/.ssh/config` 配置别名，例如：

```sshconfig
Host my-server
    HostName 203.0.113.10
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
```

```bash
check my-server
# 也接受 user@hostname
check ubuntu@example.com
```

本机需要 OpenSSH 客户端，远端需要可用的 SSH 登录、Bash 及 Ubuntu 默认系统命令。工具会把自身脚本通过 SSH 标准输入交给远端 `bash -s` 执行，不写入远端文件，无需预装 `check`，也不会自动安装软件。远端缺少 vnStat 时同样显示安装提示；月度历史流量需要提前启用 vnStat 才能积累。

沿用 SSH 的密钥、端口、跳板和主机密钥校验设置；支持正常的密码或密钥口令提示。连接超时为 10 秒，不分配伪终端，并将 SSH 退出码返回给调用方。远端颜色根据本机终端决定。SSH 本身的错误信息可能是英文。

主机参数只接受常见的别名或 `user@hostname` 字符，不接受 SSH 选项；复杂地址、IPv6 地址及连接选项请放进 SSH 配置中。

## 验证

```bash
bash -n check install.sh
python3 -m unittest discover -s tests -v
```

测试覆盖阈值边界、颜色开关、流量字节解析、按主机额度及覆盖优先级、无效配置、缺少可选工具、异常数据、参数校验、SSH 脚本传输、远端额度及退出码。测试通过替身命令执行，不访问公网或真实远程服务器。
