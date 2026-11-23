import os
import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# 1. Inicializar base de datos local y modelo de embeddings
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="manuales_industriales")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

def dividir_texto(texto, tamano=800, solapamiento=150):
    chunks = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + tamano
        chunks.append(texto[inicio:fin])
        inicio += tamano - solapamiento
    return chunks

def procesar_manuales(carpeta="manuales_pdf"):
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)
        print(f"Crea la carpeta '{carpeta}', mete un PDF ahí y vuelve a correr este script.")
        return

    archivos = [f for f in os.listdir(carpeta) if f.endswith(".pdf")]
    if not archivos:
        print(f"No hay PDFs en '{carpeta}'. Agrega al menos uno.")
        return

    id_contador = 0
    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        print(f"Procesando: {archivo}...")
        reader = PdfReader(ruta)
        
        for num_pag, pagina in enumerate(reader.pages):
            texto = pagina.extract_text()
            if not texto:
                continue
                
            chunks = dividir_texto(texto)
            for chunk in chunks:
                embedding = embedder.encode(chunk).tolist()
                collection.add(
                    ids=[f"doc_{id_contador}"],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[{"fuente": archivo, "pagina": num_pag + 1}]
                )
                id_contador += 1

    print(f"¡Listo! Se guardaron {id_contador} fragmentos en la base de datos.")

if __name__ == "__main__":
    procesar_manuales()
