from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

rag_prompt = ChatPromptTemplate(
    [
        (
            "system",
            "You are an assistant for question-answering tasks.\n"
            "Use the following pieces of retrieved context to answer the question.\n"
            "If you do not know the answer, say that you don't know.\n\n"
            "Context:\n{context}",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
    ]
)