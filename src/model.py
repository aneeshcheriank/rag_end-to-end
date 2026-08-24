import os
import logging
from functools import lru_cache

import torch
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
from sentence_transformers import SentenceTransformer
from pydantic import SecretStr

from src.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings():

    if not os.path.exists(settings.embedding_model_path):
        logger.info(
            "downloading %s to %s", settings.embedding_model, settings.embedding_model_path
        )
        model = SentenceTransformer(settings.embedding_model)
        model.save(settings.embedding_model_path)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_kwargs = {"device": device, "local_files_only": True}
    encode_kwargs = {"normalize_embeddings": True}

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model_path,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs,
    )


def get_llm():

    if not settings.deepseek_api_key:
        raise ValueError("DeepSeek api key is missing from environment")

    return ChatDeepSeek(
        model=settings.llm_model,
        temperature=0,
        api_key=SecretStr(settings.deepseek_api_key),
    )
