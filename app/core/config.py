from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "FastAPI LangGraph Demo"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "app.db"
    modelscope_api_base: str = "https://api-inference.modelscope.cn/v1"
    modelscope_api_key: str = ""
    model_deepseek_r1: str = "deepseek-ai/deepseek-r1"
    model_deepseek_v3_2: str = "deepseek-ai/DeepSeek-V3.2"
    model_default: str = "deepseek-ai/DeepSeek-V3.2"
    model_temperature_default: float = 0.3
    model_top_p_default: float = 0.95
    model_presence_penalty_default: float = 0.0
    model_frequency_penalty_default: float = 0.0
    model_max_tokens_default: int | None = None
    model_stream_default: bool = False
    ragflow_api_base: str = ""
    ragflow_api_key: str = ""
    ragflow_top_k_default: int = 4
    ragflow_kb_id: str | None = None
    # 可选：RAGFlow /v1/retrieval 的 dataset_ids，逗号分隔
    ragflow_dataset_ids: str = ""
    # 可选：RAGFlow rerank_id
    ragflow_rerank_id: str | None = None
    school_api_base: str = ""
    school_api_timeout: float = 30.0
    redis_url: str = "redis://117.72.149.125:6379/0"
    redis_ttl_minutes: int = 30

    class Config:
        env_file = ".env"
        env_prefix = "APP_"
        case_sensitive = False
        protected_namespaces = ("settings_",)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
