import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import generate_with_citation


load_dotenv()

st.set_page_config(
    page_title="RAG Chatbot",
    page_icon="R",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("RAG Chatbot")
    top_k = st.slider("Số chunks", 3, 10, 5)

st.title("RAG Chatbot")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            sources = message.get("sources", [])
            if sources:
                with st.expander(f"Nguồn ({len(sources)})"):
                    st.caption(f"Retrieval: {message.get('retrieval_source', 'unknown')}")
                    for index, source in enumerate(sources, 1):
                        metadata = source["metadata"]
                        url = metadata.get("url")
                        source_label = (
                            f"[{index}] [{metadata['title']}]({url})"
                            if url
                            else f"[{index}] {metadata['title']}"
                        )
                        st.markdown(
                            f"{source_label}  \n"
                            f"`{metadata['source']}` | method=`{source['retrieval_method']}` | "
                            f"score=`{source['score']:.4f}`"
                        )

query = st.chat_input("Nhập câu hỏi...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        generation = generate_with_citation(query, top_k)
        answer = generation["answer"]
        st.markdown(answer)
        sources = generation["sources"]
        if sources:
            with st.expander(f"Nguồn ({len(sources)})"):
                st.caption(f"Retrieval: {generation['retrieval_source']}")
                for index, source in enumerate(sources, 1):
                    metadata = source["metadata"]
                    url = metadata.get("url")
                    source_label = (
                        f"[{index}] [{metadata['title']}]({url})"
                        if url
                        else f"[{index}] {metadata['title']}"
                    )
                    st.markdown(
                        f"{source_label}  \n"
                        f"`{metadata['source']}` | method=`{source['retrieval_method']}` | "
                        f"score=`{source['score']:.4f}`"
                    )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "retrieval_source": generation["retrieval_source"],
        }
    )
