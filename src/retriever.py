from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_community.storage import SQLStore
from langchain_postgres import PGVector

from src.config import settings
from src.model import get_embeddings
from src.data_process import get_splitter

import logging

logger = logging.getLogger(__name__)


def generate_retriever(k=4):

    embedding_model = get_embeddings()
    connection_string = settings.database_url
    child_splitter, parent_splitter = get_splitter()

    child_retriever = PGVector(
        embeddings=embedding_model,
        collection_name="child_chunks",
        connection=connection_string,
        use_jsonb=True,
    )

    parent_retriever = SQLStore(
        namespace="postgres_parent_store",
        db_url=connection_string,
    )

    retriever = ParentDocumentRetriever(
        vectorstore=child_retriever,
        byte_store=parent_retriever,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
        search_kwargs={"k": k},
    )

    logger.info("Retriever has been created")

    return retriever
