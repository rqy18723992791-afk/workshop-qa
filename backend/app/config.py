"""集中管理环境变量与路径。

约定：
- 配置来源只有 backend/.env（不入库），代码里不出现任何密钥；
- 相对路径一律以仓库根目录为基准，避免"从哪个目录启动"影响结果。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> parents[2] 即仓库根目录
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / "backend" / ".env")


def _resolve(env_name: str, default: str) -> Path:
    """读取路径类配置；相对路径按仓库根目录解析。"""
    path = Path(os.getenv(env_name, default))
    return path if path.is_absolute() else BASE_DIR / path


# ===== Ollama 本地模型 =====
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct-q4_K_M")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "4096"))

# ===== 存储路径 =====
CHROMA_DIR = _resolve("CHROMA_DIR", "data/chroma")
DOCS_DIR = _resolve("DOCS_DIR", "data/docs")
REGISTRY_PATH = _resolve("REGISTRY_PATH", "data/kb_registry.json")

# ===== 检索参数 =====
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "4"))
# 余弦相似度低于该阈值视为"知识库无相关内容"，用于拒答与端云路由。
# 30 条问句校准（backend/scripts/calibrate.py）：15 条可回答问题最低 0.675，
# 8 条无关问题最高 0.522，中间存在 0.522～0.675 的安全间隔；取中点 0.6，
# 两侧各留约 0.075 余量。领域相关但知识库无答案的"灰色问题"（0.436～0.617）
# 会通过或落到生成层/云端判断，详见 docs/calibration.md。
RETRIEVAL_MIN_SIM = float(os.getenv("RETRIEVAL_MIN_SIM", "0.6"))

# ===== 切分与向量化 =====
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))      # 单块目标字符数
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))  # 相邻块重叠字符数
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "16"))      # 单次请求向量化的文本条数

# ===== 端云协同路由 =====
# auto：检索不命中或本地模型拒答时自动升级 DeepSeek；
# kb_only：只用知识库，不调用云端（严格拒答模式）。
ROUTE_MODE = os.getenv("ROUTE_MODE", "auto").strip().lower()
CLOUD_TIMEOUT = int(os.getenv("CLOUD_TIMEOUT", "60"))

# ===== DeepSeek 云端兜底 =====
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
