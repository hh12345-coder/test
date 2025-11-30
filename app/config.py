import os
import logging
from dotenv import load_dotenv

# 配置基本日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()
logger.info("环境变量已加载")

# 读取API密钥
BAIDU_MAPS_API_KEY = os.getenv("BAIDU_MAPS_API_KEY")
# 只打印密钥的前5个字符和后5个字符，保护隐私
if BAIDU_MAPS_API_KEY:
    logger.info(f"百度地图API密钥已加载: {BAIDU_MAPS_API_KEY[:5]}...{BAIDU_MAPS_API_KEY[-5:]}")
else:
    logger.warning("百度地图API密钥未找到")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")