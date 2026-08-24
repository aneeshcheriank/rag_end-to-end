from langchain_core.output_parsers import StrOutputParser
from typing import Sequence
from langchain_core.messages import BaseMessage

from src.retriever import generate_retriever
from src.model import get_llm
from src.prompts import rag_prompt


def format_docs(docs):
    """
    combined retrieved docuemnts into a single text
    """
    return "\n\n".join(doc.page_content for doc in docs)


def rag(question: str, chat_history: Sequence[BaseMessage] | None = None, k=8):

    # Guard against mutable default parameter issue
    chat_history = list(chat_history) if chat_history is not None else []

    llm = get_llm()
    vectorstore = generate_retriever(k=k)
    prompt = rag_prompt

    chain = prompt | llm | StrOutputParser()
    context = vectorstore.invoke(question)
    formated_context = format_docs(context)

    response = chain.invoke(
        {
            "question": question,
            "chat_history": chat_history,
            "context": formated_context,
        }
    )

    return {
        "response": response,
        "context": context,
    }