from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_community.storage import SQLStore
from langchain_postgres import PGVector

import logging
from sqlalchemy import create_engine, text

from src.model import get_embeddings
from src.data_process import get_splitter, load_pdf
from src.config import settings

logger = logging.getLogger(__name__)

def load_docs(docs, clear_existing=True):

    logger.info("Started loading doc to dbs")
    embedding_model = get_embeddings()
    child_splitter, parent_splitter = get_splitter()

    connection_string = settings.database_url

    # 1. Clear Parent DB Table if clear_existing is True
    if clear_existing:
        logger.info("Clearing existing parent store...")
        engine = create_engine(connection_string)
        with engine.begin() as conn:
            # Drop the SQLStore table so it recreates cleanly.
            # SQLStore stores all namespaces in the single table
            # `langchain_key_value_stores` (namespace is a column, not a table).
            conn.execute(text(
                "DROP TABLE IF EXISTS langchain_key_value_stores CASCADE;"
                ))

    vectorstore = PGVector(
        embeddings = embedding_model,
        collection_name="child_chunks",
        connection=connection_string,
        use_jsonb=True,
        pre_delete_collection=clear_existing #Drop existing child vector collection
    )

    parent_store = SQLStore(
        namespace="postgres_parent_store",
        db_url = connection_string
    )

    # Create DB tables for the paret store if they dont exist
    parent_store.create_schema()

    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        byte_store=parent_store,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter
    )

    retriever.add_documents(docs)
    logger.info("Documents has been added to the parent and child dbs")

    return retriever

def load_data_to_db(file_path, clear_flag=False):
    docs = load_pdf(file_path)
    return load_docs(docs, clear_existing=clear_flag)
