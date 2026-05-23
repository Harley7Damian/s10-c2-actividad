import hashlib
import html
import io
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader

load_dotenv()

from cache import get_cached_response, set_cached_response
from db import clear_history, get_history, get_sources, init_db, save_message, save_source


init_db()


APP_TITLE = "Chatbot con Gemini"
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_SOURCE_CHARS = 28000
SUPPORTED_TYPES = ["txt", "md", "csv", "json", "pdf"]


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
        .stApp {
            background: #f7f8fb;
        }
        [data-testid="stSidebar"] {
            background: #111827;
            color: #f9fafb;
        }
        [data-testid="stSidebar"] * {
            color: #f9fafb;
        }
        .main .block-container {
            max-width: 1040px;
            padding-top: 2rem;
            padding-bottom: 5rem;
        }
        .chat-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1.25rem;
        }
        .chat-title {
            margin: 0;
            font-size: 2rem;
            line-height: 1.1;
            color: #101828;
        }
        .chat-subtitle {
            margin: .35rem 0 0;
            color: #667085;
            font-size: 1rem;
        }
        .status-pill {
            border: 1px solid #d0d5dd;
            background: #ffffff;
            color: #344054;
            border-radius: 999px;
            padding: .5rem .8rem;
            font-size: .85rem;
            white-space: nowrap;
        }
        .source-box {
            border: 1px solid #eaecf0;
            background: #ffffff;
            border-radius: 8px;
            padding: .8rem;
            margin: .5rem 0;
            color: #344054;
        }
        .source-name {
            font-weight: 700;
            color: #101828;
            margin-bottom: .25rem;
        }
        .source-meta {
            color: #667085;
            font-size: .85rem;
        }
        div[data-testid="stChatInput"] {
            background: #ffffff;
            border-top: 1px solid #eaecf0;
        }
        section[data-testid="stSidebar"] button {
            border-radius: 8px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("Falta configurar GEMINI_API_KEY en las variables de entorno.")
        st.stop()
    return genai.Client(api_key=api_key)


def file_hash(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()


def extract_text(uploaded_file):
    file_bytes = uploaded_file.getvalue()
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    if extension in {"txt", "md", "json"}:
        return file_bytes.decode("utf-8", errors="ignore")

    if extension == "csv":
        dataframe = pd.read_csv(io.BytesIO(file_bytes))
        return dataframe.to_csv(index=False)

    if extension == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"Pagina {index}\n{page_text}")
        return "\n\n".join(pages)

    raise ValueError("Formato no soportado")


def normalize_source_text(text):
    clean_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return clean_text[:MAX_SOURCE_CHARS]


def build_sources_context(sources):
    if not sources:
        return ""

    blocks = []
    for source in sources:
        name = source["name"]
        content = source["content"]
        blocks.append(f"Fuente: {name}\nContenido:\n{content}")

    return "\n\n---\n\n".join(blocks)


def build_prompt(user_prompt, sources_context):
    if not sources_context:
        return user_prompt

    return f"""
Responde usando principalmente las fuentes entregadas por el usuario.
Si la respuesta no aparece en las fuentes, dilo claramente y complementa solo si es util.
Cita el nombre del archivo cuando uses informacion de una fuente.

FUENTES:
{sources_context}

PREGUNTA DEL USUARIO:
{user_prompt}
""".strip()


def get_source_cache_key(prompt, sources):
    source_fingerprints = "|".join(source["hash"] for source in sources)
    return f"{prompt}::sources::{source_fingerprints}"


if "active_sources" not in st.session_state:
    st.session_state.active_sources = []


client = get_client()

with st.sidebar:
    st.markdown("## Fuentes")
    st.caption("Sube archivos para que Gemini los use como contexto en sus respuestas.")

    uploaded_files = st.file_uploader(
        "Agregar fuentes",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            uploaded_bytes = uploaded_file.getvalue()
            uploaded_hash = file_hash(uploaded_bytes)
            already_loaded = any(source["hash"] == uploaded_hash for source in st.session_state.active_sources)

            if already_loaded:
                continue

            try:
                extracted = normalize_source_text(extract_text(uploaded_file))
            except Exception as exc:
                st.warning(f"No se pudo leer {uploaded_file.name}: {exc}")
                continue

            if not extracted:
                st.warning(f"{uploaded_file.name} no tiene texto legible.")
                continue

            source = {
                "name": uploaded_file.name,
                "content": extracted,
                "hash": uploaded_hash,
                "size": len(uploaded_bytes),
            }
            st.session_state.active_sources.append(source)
            save_source(uploaded_file.name, uploaded_hash, extracted)

    if st.session_state.active_sources:
        st.success(f"{len(st.session_state.active_sources)} fuente(s) activa(s)")

        for source in st.session_state.active_sources:
            source_name = html.escape(source["name"])
            st.markdown(
                f"""
                <div class="source-box">
                    <div class="source-name">{source_name}</div>
                    <div class="source-meta">{len(source["content"]):,} caracteres listos para consultar</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button("Quitar fuentes activas", use_container_width=True):
            st.session_state.active_sources = []
            st.rerun()
    else:
        st.info("Aun no hay fuentes activas.")

    with st.expander("Fuentes guardadas"):
        saved_sources = get_sources()
        if saved_sources:
            for saved in saved_sources:
                col_info, col_action = st.columns([3, 1])
                with col_info:
                    st.caption(f"{saved.name} - {saved.created_at:%d/%m/%Y %H:%M}")
                with col_action:
                    if st.button("Usar", key=f"use-{saved.file_hash}"):
                        already_loaded = any(
                            source["hash"] == saved.file_hash for source in st.session_state.active_sources
                        )
                        if not already_loaded:
                            st.session_state.active_sources.append(
                                {
                                    "name": saved.name,
                                    "content": saved.content,
                                    "hash": saved.file_hash,
                                    "size": len(saved.content.encode("utf-8")),
                                }
                            )
                        st.rerun()
        else:
            st.caption("No hay fuentes guardadas todavia.")

    st.markdown("---")
    if st.button("Limpiar historial", use_container_width=True):
        clear_history()
        st.rerun()

    st.caption(f"Modelo: {MODEL_NAME}")


sources_context = build_sources_context(st.session_state.active_sources)

st.markdown(
    f"""
    <div class="chat-header">
        <div>
            <h1 class="chat-title">🤖 Chatbot Gemini</h1>
            <p class="chat-subtitle">Pregunta normalmente o adjunta fuentes para respuestas con contexto.</p>
        </div>
        <div class="status-pill">{len(st.session_state.active_sources)} fuente(s) activa(s)</div>
    </div>
    """,
    unsafe_allow_html=True,
)

history = get_history()

if not history:
    with st.chat_message("assistant"):
        st.markdown(
            "Hola. Puedes hacerme una pregunta directa o usar el panel de la izquierda para subir PDFs, CSV, TXT, MD o JSON como fuentes."
        )

for role, message in history:
    with st.chat_message(role):
        st.markdown(message)

prompt = st.chat_input("Escribe un mensaje o pregunta sobre tus fuentes...")

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)

    save_message("user", prompt)

    cache_key = get_source_cache_key(prompt, st.session_state.active_sources)
    cached = get_cached_response(cache_key)

    if cached:
        response_text = cached
    else:
        full_prompt = build_prompt(prompt, sources_context)

        with st.spinner("Pensando con Gemini..."):
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=full_prompt,
            )
            response_text = response.text or "No pude generar una respuesta."
            set_cached_response(cache_key, response_text)

    with st.chat_message("assistant"):
        st.markdown(response_text)

    save_message("assistant", response_text)
