import requests
import streamlit as st
import os

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000/v1")
TIMEOUT_QUERY = 30
TIMEOUT_INGEST = 6000

st.set_page_config(page_title="Multi-Agent RAG")

st.title("Multi-Agent RAG")


st.header("Ingest")

if st.button("Rodar Ingest"):
    try:
        response = requests.post(
            f"{BASE_URL}/ingest",
            json={}, 
            timeout=TIMEOUT_INGEST,
        )

        if response.ok:
            data = response.json()
            st.success("Ingest concluído.")

            c1, c2, c3 = st.columns(3)
            c1.metric("total_requested", data.get("total_requested", "-"))
            c2.metric("total_downloaded", data.get("total_downloaded", "-"))
            c3.metric("total_failed", data.get("total_failed", "-"))

        else:
            st.error(f"Erro HTTP {response.status_code}")

    except requests.Timeout:
        st.error("Timeout no ingest.")
    except requests.ConnectionError:
        st.error("Erro de conexão com a API.")

st.header("Query")

question = st.text_input("Pergunta")

if st.button("Perguntar"):

    if not question.strip():
        st.error("Digite uma pergunta.")
    else:
        try:
            response = requests.post(
                f"{BASE_URL}/query",
                json={"query": question},
                timeout=TIMEOUT_QUERY,
            )

            if response.ok:
                data = response.json()

                st.subheader("Resposta")
                st.write(data.get("final_answer", "Sem resposta."))

                confidence = data.get("confidence")
                if confidence is not None:
                    st.caption(f"confidence: {confidence}")

                if data.get("trace"):
                    with st.expander("Trace"):
                        st.json(data["trace"])

            else:
                st.error(f"Erro HTTP {response.status_code}")

        except requests.Timeout:
            st.error("Timeout da API.")
        except requests.ConnectionError:
            st.error("Erro de conexão com a API.")
