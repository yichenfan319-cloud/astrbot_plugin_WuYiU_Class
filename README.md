# 🎓 武夷学院课表查询插件

适用于 [AstrBot](https://github.com/Soulter/AstrBot) 的武夷学院教务系统自动查课表插件。

如果有课表查询失败请向qq3450541935@outlook.com发送邮件

## ⚠️ 安全警告（必读）

**本插件需要存储您的教务系统账号密码，请注意以下安全事项：**

1. **密码存储方式**：密码以**明文形式**存储在 AstrBot 的配置文件中（`data/config/wuyi-kebiao.json`），这是 AstrBot 插件架构的限制，无法加密存储。
2. **服务器安全**：请确保您的 AstrBot 部署环境（服务器或本地电脑）是安全的，避免他人获取配置文件。
3. **权限管理**：建议限制配置文件的访问权限（Linux: `chmod 600`）。
4. **风险提示**：**请勿将包含真实密码的配置文件提交到 GitHub 等公共仓库！**
5. **账号安全**：本插件仅用于查询课表，不会上传您的账号信息到除武夷学院教务系统外的任何第三方服务器。

## 功能特性

-  自动登录，无需手动抓取 Cookie
-  智能缓存，本周课表只需获取一次
-  跨周判断，自动处理明天/后天是否处于下周
-  多维度查询：今天、明天、后天、本周、下周、指定周
-  可视化输出，按天/时段分组展示

## 安装方法

### 方式一：通过 AstrBot 插件市场安装（推荐）

在 AstrBot WebUI 中进入「插件管理」→「安装插件」，输入： 武夷学院课表查询  安装即可


### 方式二：手动安装

1. 克隆仓库到 AstrBot 的插件目录（通常是 `data/plugins/`）
https://github.com/yichenfan319/astrbot_plugin_WuYiU_Class
2. 重启 AstrBot

## 配置说明

安装后，进入 AstrBot WebUI →「插件配置」→「武夷课表」，填写：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| username | 学号 | 123456789 |
| password | 教务系统密码 | 你的密码 |
| browser_path | Chromium 浏览器路径 | 见下方平台说明 |

### 各平台 Chromium 安装说明

#### 🐧 Linux 服务器（原生部署）

如果您是**直接**在 Linux 服务器上安装 AstrBot（非 Docker），执行：

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install chromium-browser chromium-chromedriver

# CentOS/RHEL
sudo yum install chromium chromium-driver

配置 browser_path 为：/usr/bin/chromium 或 /usr/bin/chromium-browser


🐳 Docker 部署（⚠️ 特别注意）
如果您使用 Docker 运行 AstrBot（这是最常见的部署方式），必须在容器内部安装 Chromium！
因为 Docker 容器与宿主机环境隔离，宿主机的 Chrome 对容器内的插件不可见。
操作步骤：

1.进入 AstrBot 容器：
# 查看容器名称（通常是 astrbot 或 astrbot-main）
docker ps

# 进入容器
docker exec -it astrbot /bin/bash

2.在容器内安装 Chromium：
apt update
apt install -y chromium chromium-driver

3.配置插件:
browser_path 为：/usr/bin/chromium


#### Heading level 4
Windows 本地部署
Windows 环境下无需配置 browser_path，留空即可。插件会自动检测以下位置的 Chrome/Edge：
C:\Program Files\Google\Chrome\Application\chrome.exe
C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
用户目录下的 Chrome

# Heading level 1
故障排查
提示"未配置学号或密码"
进入 AstrBot WebUI → 插件配置 → 武夷课表，填写账号密码后重启 AstrBot。
提示"浏览器未找到"（Linux）
确认 Chromium 已安装：which chromium
Docker 用户确认是在容器内安装的 Chromium，而非宿主机
检查 browser_path 配置是否正确
登录失败
确认账号密码正确（注意大小写）
确认账号可以正常登录 教务系统
检查网络连接（服务器需能访问武夷学院内网/VPN）
获取不到课表数据
确认当前时间处于学期内（非假期）
尝试发送 更新课表 刷新缓存
查看 AstrBot 日志获取详细错误信息
技术说明
基于 DrissionPage 实现无头浏览器自动化
使用 BeautifulSoup4 解析 HTML
缓存文件存储在 data/wuyi-kebiao/courses.json
免责声明
本插件仅供学习交流使用，使用者需自行承担因使用本插件可能带来的账号安全风险。开发者不对因密码泄露、账号异常等情况造成的损失负责。
