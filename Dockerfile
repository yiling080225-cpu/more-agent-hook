FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 从 .env.example 创建默认 .env (如果用户未提供)
RUN if [ ! -f .env ]; then cp .env.example .env; fi

# 创建数据目录
RUN mkdir -p data

# 启动
EXPOSE 8000 8001 8002 8003
CMD ["python", "run.py"]
