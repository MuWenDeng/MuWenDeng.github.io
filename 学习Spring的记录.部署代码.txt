很多小公司或传统企业确实没有用 Docker，直接部署到 Linux 服务器上是最常见的做法。我直接给你一套**从零开始的完整部署流程**，每一步都有命令和说明。

---

## 一、整体流程图

```
本地开发电脑                      Linux 服务器（生产环境）
     │                                    │
     │  1. git push 代码                   │
     │───────────────────────────────────>│  2. git pull 拉取代码
     │                                    │
     │  3. mvn clean package              │  4. 生成 jar 包
     │                                    │
     │  5. scp 上传 jar 包                │  6. 停止旧服务
     │───────────────────────────────────>│  7. 启动新服务
     │                                    │  8. 验证接口
```

---

## 第一步：在本地编译打包

### 1.1 确认代码已经提交

```bash
# 查看是否有未提交的修改
git status

# 如果有，先提交
git add .
git commit -m "发布 v1.0.0"
git push origin main
```

### 1.2 在本地执行 Maven 打包

```bash
# 进入项目根目录（有 pom.xml 的地方）
cd /path/to/your-project

# 清理 + 打包（跳过单元测试，加快速度）
mvn clean package -DskipTests

# 打包成功后，jar 包在 target/ 目录下
ls -lh target/*.jar
# 输出示例：-rw-r--r-- 1 user user  52M Jun 30 15:30 my-api-1.0.0.jar
```

**如果你的项目有多个微服务**，依次对每个服务执行打包：

```bash
# user-service
cd /path/to/user-service
mvn clean package -DskipTests

# order-service
cd /path/to/order-service
mvn clean package -DskipTests

# gateway-service
cd /path/to/gateway-service
mvn clean package -DskipTests
```

---

## 第二步：上传到服务器

### 2.1 确认服务器信息

```bash
# 你需要知道：
# - 服务器 IP：例如 192.168.1.100
# - 登录用户名：root 或 appuser
# - 密码或 SSH 密钥
```

### 2.2 上传 jar 包（三种方式）

**方式一：scp 命令（最常用）**

```bash
# 单文件上传
scp target/my-api-1.0.0.jar root@192.168.1.100:/app/

# 上传到指定目录
scp target/my-api-1.0.0.jar root@192.168.1.100:/home/app/deploy/

# 如果指定了端口（如 22）
scp -P 22 target/my-api-1.0.0.jar root@192.168.1.100:/app/
```

**方式二：rsync（支持断点续传，适合大文件）**

```bash
rsync -avz target/my-api-1.0.0.jar root@192.168.1.100:/app/
```

**方式三：使用 FTP/SFTP 工具（推荐 FileZilla / WinSCP）**

- 打开 WinSCP / FileZilla
- 输入服务器 IP、用户名、密码
- 本地目录找到 `target/*.jar`
- 远程目录定位到 `/app/`
- 拖拽上传

---

## 第三步：在服务器上部署

### 3.1 登录服务器

```bash
ssh root@192.168.1.100
# 输入密码
```

### 3.2 准备部署目录

```bash
# 创建应用目录
mkdir -p /app
cd /app

# 查看已上传的 jar 包
ls -lh
```

### 3.3 备份当前版本（重要！）

```bash
# 如果已经有运行的版本，先备份
cp /app/my-api-1.0.0.jar /app/backup/my-api-1.0.0.backup.$(date +%Y%m%d_%H%M%S).jar
```

### 3.4 停止旧服务

```bash
# 查找正在运行的 Java 进程
ps -ef | grep java | grep my-api

# 或者用 jps 命令（更清晰）
jps -l

# 输出示例：
# 12345 /app/my-api-1.0.0.jar
# 67890 sun.tools.jps.Jps

# 停止旧服务（优雅停止）
kill <pid>          # 例如：kill 12345

# 如果 kill 无法停止，强制杀死
kill -9 <pid>
```

### 3.5 启动新服务

```bash
# 基础启动（前台运行，用于测试）
java -jar my-api-1.0.0.jar

# ⭐ 生产环境标准启动（后台运行 + 日志输出）
nohup java -jar my-api-1.0.0.jar > /app/logs/app.log 2>&1 &

# 指定 JVM 参数启动（推荐）
nohup java -Xms512m -Xmx1024m \
  -XX:+UseG1GC \
  -Dfile.encoding=UTF-8 \
  -Duser.timezone=Asia/Shanghai \
  -jar my-api-1.0.0.jar \
  --spring.profiles.active=prod \
  > /app/logs/app.log 2>&1 &

# 查看启动日志
tail -f /app/logs/app.log

# 看到类似输出即成功：
# Started DemoApplication in 5.234 seconds (JVM running for 5.789)
```

---

## 第四步：验证服务是否正常

### 4.1 检查进程

```bash
# 查看 Java 进程是否在运行
ps -ef | grep java | grep my-api

# 或使用 jps
jps -l

# 检查端口是否监听（假设端口是 8080）
netstat -tlnp | grep 8080
# 输出示例：tcp6 0 0 :::8080 :::* LISTEN 12345/java
```

### 4.2 测试接口

```bash
# 本地测试（在服务器上执行）
curl -X GET http://localhost:8080/actuator/health

# 或测试业务接口
curl -X GET http://localhost:8080/api/users

# 使用 Postman 测试（在本地电脑上）
# GET http://192.168.1.100:8080/api/users
```

### 4.3 查看日志确认无异常

```bash
# 查看最近 50 行日志
tail -50 /app/logs/app.log

# 搜索错误
grep ERROR /app/logs/app.log

# 实时监控日志
tail -f /app/logs/app.log
```

---

## 第五步：配置开机自启动（生产环境必备）

### 5.1 使用 systemd（CentOS 7+ / Ubuntu 16+）

创建 systemd 服务文件：

```bash
vi /etc/systemd/system/my-api.service
```

写入以下内容：

```ini
[Unit]
Description=My API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/app
ExecStart=/usr/bin/java -Xms512m -Xmx1024m -XX:+UseG1GC -Dfile.encoding=UTF-8 -Duser.timezone=Asia/Shanghai -jar /app/my-api-1.0.0.jar --spring.profiles.active=prod
ExecStop=/bin/kill -15 $MAINPID
Restart=on-failure
RestartSec=30
SuccessExitStatus=143
StandardOutput=append:/app/logs/app.log
StandardError=append:/app/logs/app-error.log

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
# 重新加载 systemd
systemctl daemon-reload

# 启动服务
systemctl start my-api

# 设置开机自启动
systemctl enable my-api

# 查看状态
systemctl status my-api

# 查看日志
journalctl -u my-api -f
```

### 5.2 使用 Supervisor（更轻量）

```bash
# 安装 Supervisor
apt-get install supervisor -y   # Ubuntu
yum install supervisor -y        # CentOS

# 创建配置文件
vi /etc/supervisor/conf.d/my-api.conf
```

```ini
[program:my-api]
command=/usr/bin/java -Xms512m -Xmx1024m -jar /app/my-api-1.0.0.jar --spring.profiles.active=prod
directory=/app
user=root
autostart=true
autorestart=true
startsecs=30
stderr_logfile=/app/logs/error.log
stdout_logfile=/app/logs/app.log
```

```bash
# 重新加载
supervisorctl reload

# 启动
supervisorctl start my-api

# 查看状态
supervisorctl status
```

---

## 第六步：编写发布脚本（简化操作）

创建一个 `deploy.sh` 脚本，把所有步骤串起来：

```bash
#!/bin/bash

# deploy.sh - 一键发布脚本
# 用法：./deploy.sh <项目名> <版本号>

PROJECT_NAME=$1
VERSION=$2
SERVER_IP="192.168.1.100"
DEPLOY_PATH="/app"

echo "========== 开始部署 $PROJECT_NAME v$VERSION =========="

# 1. 本地打包
echo "Step 1: Maven 打包..."
cd /path/to/$PROJECT_NAME
mvn clean package -DskipTests

# 2. 上传到服务器
echo "Step 2: 上传 jar 包到服务器..."
scp target/$PROJECT_NAME-$VERSION.jar root@$SERVER_IP:$DEPLOY_PATH/

# 3. 服务器远程执行部署命令
echo "Step 3: 远程部署..."
ssh root@$SERVER_IP << EOF
  cd $DEPLOY_PATH
  
  # 备份旧版本
  if [ -f $PROJECT_NAME-current.jar ]; then
    mv $PROJECT_NAME-current.jar backup/$PROJECT_NAME-$(date +%Y%m%d_%H%M%S).jar
  fi
  
  # 新版本标记为 current
  mv $PROJECT_NAME-$VERSION.jar $PROJECT_NAME-current.jar
  
  # 停止服务
  systemctl stop $PROJECT_NAME
  
  # 启动服务
  systemctl start $PROJECT_NAME
  
  # 等待启动完成
  sleep 10
  
  # 检查状态
  systemctl status $PROJECT_NAME
EOF

echo "========== 部署完成 =========="
```

使用方式：

```bash
chmod +x deploy.sh
./deploy.sh my-api 1.0.0
```

---

## 第七步：回滚方案（出事能救命）

```bash
# 1. 查看历史备份
ls -lh /app/backup/

# 2. 停止当前服务
systemctl stop my-api

# 3. 恢复到指定版本
cp /app/backup/my-api-20250630_153000.jar /app/my-api-current.jar

# 4. 重启服务
systemctl start my-api

# 5. 验证
curl http://localhost:8080/actuator/health
```

---

## 完整操作速查表

| 操作 | 命令 |
|------|------|
| 打包 | `mvn clean package -DskipTests` |
| 上传 | `scp target/*.jar root@192.168.1.100:/app/` |
| 登录服务器 | `ssh root@192.168.1.100` |
| 查看进程 | `ps -ef \| grep java` 或 `jps -l` |
| 停止服务 | `kill <pid>` 或 `systemctl stop my-api` |
| 启动服务 | `systemctl start my-api` 或 `nohup java -jar ... &` |
| 查看日志 | `tail -f /app/logs/app.log` |
| 重启服务 | `systemctl restart my-api` |
| 查看状态 | `systemctl status my-api` |
| 开机自启 | `systemctl enable my-api` |

---

现在你已经有了一套完整的非 Docker 部署方案。你是想先本地试一遍，还是想深入了解 **Nginx 反向代理配置** 或 **日志切割（logrotate）** 的配置？😊
