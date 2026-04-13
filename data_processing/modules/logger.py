import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),  # 记录到文件
        logging.StreamHandler()  # 打印到控制台
    ]
)

logger = logging.getLogger()
