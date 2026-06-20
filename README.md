# Service Health Check

定时监控网站状态，异常时自动告警。

## 使用

```bash
# 检查所有服务
python healthcheck.py

# 每 60 秒自动检查
python healthcheck.py --interval 60

# 查看历史记录
python healthcheck.py --status

# 开启飞书告警
python healthcheck.py --webhook https://your-webhook-url
Docker
docker run ghcr.io/kkivc/service-healthcheck:latest
CI/CD
Git push 后 GitHub Actions 自动构建 Docker 镜像并推送至 ghcr.io。