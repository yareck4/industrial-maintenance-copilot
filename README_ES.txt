README_ES

# ⚙️ Industrial Maintenance Copilot (RAG)

Asistente técnico basado en **Retrieval-Augmented Generation (RAG)** diseñado para consultar manuales de maquinaria industrial, brazos robóticos y PLCs en lenguaje natural. El sistema extrae información técnica real y entrega diagnósticos estructurados paso a paso citando el archivo y número de página exactos para evitar alucinaciones operativas.

---

## 🏗️ Arquitectura del Sistema

1. **Ingesta y Segmentación (`ingestor.py`):** Lee documentos PDF desde `manuales_pdf/`, divide el texto en bloques (*chunks*) con solapamiento y preserva los metadatos de origen (nombre de archivo y página).
2. **Vectorización Local:** Utiliza `sentence-transformers` (`all-MiniLM-L6-v2`) para generar *embeddings* sin costo de API y almacenarlos de forma persistente en `ChromaDB`.
3. **Recuperación y Alta Disponibilidad (`app.py`):** Ante una consulta del técnico, recupera los fragmentos más relevantes por similitud semántica y consulta la API de Google Gemini (`google-genai`). Incorpora una arquitectura tolerante a fallos con **reintentos progresivos (*exponential backoff*)**, **cascada de modelos (*model fallback*)** y **modo de contingencia local** si los servidores en la nube están saturados.

---

## 📂 Estructura del Proyecto

```text
industrial-maintenance-copilot/
├── manuales_pdf/       # Carpeta donde se depositan los manuales técnicos (.pdf)
├── chroma_db/          # Base de datos vectorial generada localmente (ignorada en Git)
├── ingestor.py         # Script de procesamiento, chunking y carga a ChromaDB
├── app.py              # Aplicación web en Streamlit con lógica RAG y resiliencia
├── requirements.txt    # Dependencias del proyecto
├── .gitignore          # Exclusión de entorno virtual, caché y bases locales
└── README.md           # Documentación técnica y guía de troubleshooting
```

---

## 🚀 Instalación y Ejecución

### 1. Preparar el entorno virtual
Abre una terminal dentro de la carpeta raíz del proyecto (`industrial-maintenance-copilot/`) y ejecuta:

```bash
python -m venv venv
venv\Scripts\activate
pip install --default-timeout=1000 -r requirements.txt
```

### 2. Cargar los manuales técnicos
Coloca uno o más manuales en formato `.pdf` dentro de la carpeta `manuales_pdf/` y ejecuta el script de ingesta:

```bash
python ingestor.py
```
*Verifica en consola que se imprima el conteo real de fragmentos guardados antes de continuar.*

### 3. Iniciar el Copiloto
Obtén una API Key gratuita en [Google AI Studio](https://google.com) y arranca la interfaz web:

```bash
streamlit run app.py
```
Ingresa tu API Key en la barra lateral izquierda y realiza tu consulta técnica.

---

## 🛠️ Solución de Problemas y Lecciones Aprendidas (Troubleshooting)

Durante el desarrollo y despliegue en entorno local (Windows 11 + VS Code), se identificaron y resolvieron los siguientes problemas técnicos habituales en proyectos RAG:

### 1. Error: `Python was not found` o bloqueo de instalador `.msix` en Windows 11
* **Causa:** Windows 11 puede bloquear paquetes de instalación modernos (*App Installer / Sideloading policy*) o no registrar Python en las variables de entorno (`PATH`).
* **Solución:** Instalar Python directamente desde la **Microsoft Store** oficial o descargar el instalador tradicional **`Windows installer (64-bit) .exe`** marcando obligatoriamente la casilla **`Add python.exe to PATH`**. Reiniciar VS Code por completo tras la instalación.

### 2. Cortes de red (`ReadTimeoutError` / `SSLError`) al instalar librerías pesadas
* **Causa:** `sentence-transformers` descarga dependencias pesadas (como PyTorch > 2 GB). Cualquier microcorte de red aborta `pip`.
* **Solución:** Aumentar el tiempo de espera con `--default-timeout=1000` e instalar los paquetes críticos por separado (`pip install --default-timeout=1000 sentence-transformers`). Si se interrumpe, repetir el comando aprovecha la caché local de `pip`.

### 3. Advertencias de importación amarilla en VS Code (`Import "chromadb" could not be resolved`)
* **Causa:** VS Code apunta al intérprete global de Python o al `.venv` de una carpeta padre en lugar del entorno virtual del proyecto.
* **Solución:** Presionar `Ctrl + Shift + P` -> `Python: Select Interpreter` -> `Enter Interpreter Path...` y seleccionar manualmente `.\industrial-maintenance-copilot\venv\Scripts\python.exe`.

### 4. Base de datos vacía (`0 fragmentos`) o creación de carpetas duplicadas
* **Causa:** Tanto `ingestor.py` como `app.py` utilizan rutas relativas (`./chroma_db` y `manuales_pdf`). Si la terminal está ubicada en una carpeta padre (ej. `git/` en lugar de `git/industrial-maintenance-copilot/`), Python creará una base de datos vacía en el directorio equivocado.
* **Solución:** Asegurarse siempre de hacer `cd industrial-maintenance-copilot` antes de ejecutar cualquier script. Si se generó una base vacía por error, eliminarla en PowerShell con `Remove-Item -Recurse -Force chroma_db` y volver a correr `python ingestor.py`.

### 5. Error `503 UNAVAILABLE` (Saturación de servidores) o `404 NOT_FOUND` en la API
* **Causa:** Los modelos en capa gratuita sufren picos de demanda (`503`) o cambian de versión/nomenclatura (`404`).
* **Solución:** Se implementó una función de resiliencia en `app.py` que:
  1. Reintenta automáticamente con espera exponencial (`time.sleep(2 ** intento)`).
  2. Salta automáticamente a una lista de modelos alternativos (`gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.8-flash`).
  3. Activa un **Modo de Contingencia Local** que entrega los extractos exactos recuperados de `ChromaDB` con su archivo y página si todos los modelos en nube fallan.

### 6. Rendimiento y calidad del Prompt en consultas técnicas
* **Causa:** Prompts excesivamente largos aumentan el consumo de tokens, elevan la latencia y provocan mayor tasa de rechazo en servidores saturados.
* **Solución:** Mantener un *System Prompt* conciso, directo y con restricción estricta al contexto (`ÚNICAMENTE los fragmentos del manual`), priorizando la velocidad de respuesta y la precisión operativa sobre el estilo conversacional.

## 💡 Consejos técnicos rápidos y consideraciones de arquitectura

* **Segmentación y solapamiento (`tamano=800, solapamiento=150`):** Dividir el texto con un solapamiento de 150 caracteres garantiza que las especificaciones críticas o los códigos de error —que podrían quedar justo en el punto de corte— no se fragmenten, preservando así el contexto completo entre los distintos segmentos.
* **¿Por qué usar *embeddings* locales (`all-MiniLM-L6-v2`)?** Ejecutar el modelo de *embeddings* de forma local permite indexar cientos de páginas de manuales sin incurrir en costes de tokens de API (**$0**), además de mantener la confidencialidad de los documentos técnicos sensibles durante el proceso de vectorización.
* **Búsqueda semántica frente a búsqueda por palabras clave:** A diferencia de la función `Ctrl + F`, ChromaDB compara el significado semántico de los vectores. Por ejemplo, una búsqueda como *"el brazo no se mueve"* permitirá recuperar secciones tituladas *"Fallo en el servocontrolador"* o *"Eje bloqueado"*.
* **Almacenamiento en caché con Streamlit (`@st.cache_resource`):** El modelo de *embeddings* (~80 MB) y la conexión con ChromaDB se almacenan en la memoria caché, cargándose una sola vez al iniciar la aplicación; esto evita que la interfaz de usuario se congele cada vez que se realiza una nueva consulta.
* **Instrucción de fundamentación estricta (*Grounding*):** Obligar al LLM a responder *únicamente* basándose en los fragmentos recuperados evita peligrosas "alucinaciones" en un entorno industrial (como la invención de valores de par o tolerancias de voltaje).
* **Actualización segura de manuales:** Si añades o sustituyes archivos PDF en el directorio `manuales_pdf/`, elimina la carpeta `chroma_db/` antes de volver a ejecutar `ingestor.py`. Esto evita que los vectores antiguos o duplicados se mezclen con los nuevos.
* **Seguridad de la clave API:** Nunca incluyas tu clave API de Gemini directamente en el código (`app.py`) ni la subas a GitHub. Utiliza una entrada en la interfaz de usuario durante la ejecución o cárgala mediante variables de entorno (`.env`).

### 7. Subida accidental de entornos virtuales o bases locales a GitHub
* **Causa:** Crear el repositorio sin `.gitignore` provoca que Git intente rastrear miles de archivos de `venv/` y binarios de `chroma_db/`.
* **Solución:** Incluir un `.gitignore` excluyendo `venv/`, `.venv/`, `chroma_db/`, `__pycache__/` y `.env`. Si ya se habían agregado al *staging*, limpiar la caché con `git rm -r --cached .` antes de hacer `git commit`.
