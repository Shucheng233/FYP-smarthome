FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝服务代码
COPY . .

# 默认服务端口（你也可以后面改成 8001）
EXPOSE 8000

# 启动 FastAPI：假设入口文件是 app.py，FastAPI 实例名为 app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
