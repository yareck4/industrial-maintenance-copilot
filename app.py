import time
import streamlit as st
import chromadb
from sentence_transformers import SentenceTransformer
from google import genai

# Configuración de página
st.set_page_config(page_title="Copiloto de Mantenimiento", page_icon="⚙️")
st.title("⚙️ Copiloto de Mantenimiento Industrial (RAG)")

# Sidebar para la API Key
api_key = st.sidebar.text_input("Tu Gemini API Key:", type="password")
st.sidebar.markdown("Consíguela gratis en [Google AI Studio](https://google.com)")

# Cargar base de datos y modelo de embeddings en caché
@st.cache_resource
def cargar_recursos():
    client_db = chromadb.PersistentClient(path="./chroma_db")
    collection = client_db.get_collection(name="manuales_industriales")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return collection, embedder

try:
    collection, embedder = cargar_recursos()
except Exception:
    st.error("⚠️ No se encontró la base de datos. Ejecuta primero `python ingestor.py`.")
    st.stop()

def consultar_con_resiliencia(client_ai, prompt, documentos, metadatos):
    """Intenta múltiples modelos con reintentos progresivos; si la nube falla, entrega contingencia local."""
    modelos = [
        
        "gemini-3.5-flash-lite",  # El más rápido y con menor saturación en capa gratuita
        "gemini-3.6-flash",       # Excelente disponibilidad para razonamiento técnico
        "gemini-3.8-flash",       # Modelo principal
        "gemini-4-hydrogen"       # Respaldo de nueva generación
        
        ]
    
    for modelo in modelos:
        for intento in range(2):  # Hasta 2 intentos por modelo
            try:
                respuesta = client_ai.models.generate_content(
                    model=modelo,
                    contents=prompt
                )
                return respuesta.text, f"Nube ({modelo})"
            except Exception as e:
                error_str = str(e)
                # Si el modelo no existe (404), saltamos directo al siguiente modelo
                if "404" in error_str or "NOT_FOUND" in error_str:
                    break
                # Si está saturado (503) o límite de cuota (429), esperamos y reintentamos
                if "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str:
                    time.sleep(2 ** intento)  # Espera 1s, luego 2s
                    continue
                raise e

    # MODO CONTINGENCIA OFFLINE: Si todos los servidores están saturados, nunca dejamos al técnico sin dato
    resumen_local = "⚠️ **Los servidores de IA están saturados temporalmente, pero encontré estas secciones exactas en tus manuales:**\n\n"
    for doc, meta in zip(documentos, metadatos):
        resumen_local += f"📄 **Archivo:** `{meta['fuente']}` | **Página:** {meta['pagina']}\n> {doc.strip()}\n\n---\n"
    
    return resumen_local, "Modo Contingencia Local (Sin LLM)"

# Caja de pregunta
pregunta = st.text_input("¿Qué falla, código de error o procedimiento necesitas consultar?")

if st.button("Consultar Manual") and pregunta:
    if not api_key:
        st.warning("Por favor ingresa tu API Key de Gemini en la barra lateral.")
        st.stop()

    with st.spinner("Buscando en los manuales técnicos y generando diagnóstico..."):
        # 1. Buscar los 4 fragmentos más relevantes en ChromaDB (100% local)
        query_embedding = embedder.encode(pregunta).tolist()
        resultados = collection.query(
            query_embeddings=[query_embedding],
            n_results=4
        )

        documentos = resultados["documents"][0]
        metadatos = resultados["metadatas"][0]

        # Armar el contexto con citas
        contexto = ""
        for doc, meta in zip(documentos, metadatos):
            contexto += f"\n--- Fuente: {meta['fuente']} (Pág. {meta['pagina']}) ---\n{doc}\n"

        # 2. Consultar a Gemini con tolerancia a fallos
        client_ai = genai.Client(api_key=api_key)
        prompt = f"""Eres un ingeniero experto en mantenimiento industrial. 
Responde a la consulta del técnico basándote ÚNICAMENTE en los siguientes fragmentos de manuales.
Cita siempre el nombre del archivo y el número de página de donde sacaste el dato.
Si la respuesta no está en el contexto, di claramente que no aparece en los manuales cargados.

CONTEXTO DE MANUALES:
{contexto}

CONSULTA DEL TÉCNICO:
{pregunta}
"""
        texto_final, motor_usado = consultar_con_resiliencia(client_ai, prompt, documentos, metadatos)

        st.subheader("📋 Diagnóstico / Procedimiento:")
        st.caption(f"Motor de respuesta: {motor_usado}")
        st.markdown(texto_final)

        with st.expander("🔍 Ver fragmentos exactos recuperados del PDF"):
            st.text(contexto)
