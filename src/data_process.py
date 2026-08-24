from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import logging

logger = logging.getLogger(__name__)


def load_pdf(pdf_path):
    loader = PyPDFLoader(pdf_path)
    doc = loader.load()
    logger.info("Loaded the doc from path: %s", pdf_path)
    return doc


def get_splitter():
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=50)

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
    )

    return child_splitter, parent_splitter