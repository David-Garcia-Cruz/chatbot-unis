from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from sentence_transformers import SentenceTransformer
import PyPDF2
import re
import os
import uvicorn
import logging
import requests
from bs4 import BeautifulSoup
import time
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chatbot UNSIS - Admisión 2026")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN ---
BASE_DIR = "/opt/chatbot_unsis"
DB_PATH = os.path.join(BASE_DIR, "base_conocimiento")
PDF_PATH = os.path.join(BASE_DIR, "ficha_unsis.pdf")

# --- MODELO DE IA ---
logger.info("🔄 Cargando modelo de IA...")
modelo = SentenceTransformer('all-MiniLM-L6-v2')
logger.info("✅ Modelo cargado.")

# --- BASE DE DATOS VECTORIAL ---
cliente = chromadb.PersistentClient(path=DB_PATH)
coleccion = cliente.get_or_create_collection(name="unsis_pdf")

# --- FUNCIONES DEL PDF ---
def extraer_texto_pdf(ruta):
    if not os.path.exists(ruta):
        logger.error(f"❌ PDF no encontrado: {ruta}")
        return ""
    with open(ruta, 'rb') as f:
        lector = PyPDF2.PdfReader(f)
        return "".join(pagina.extract_text() for pagina in lector.pages)

def dividir_chunks(texto, tamano=600):
    texto = re.sub(r'\n+', ' ', texto)
    return [texto[i:i+tamano] for i in range(0, len(texto), tamano)]

# --- INDEXACIÓN (solo primera vez) ---
if coleccion.count() == 0:
    logger.info("📄 Indexando PDF por primera vez...")
    texto_completo = extraer_texto_pdf(PDF_PATH)
    if texto_completo:
        chunks = dividir_chunks(texto_completo)
        embeddings = modelo.encode(chunks).tolist()
        for i, chunk in enumerate(chunks):
            coleccion.add(documents=[chunk], embeddings=[embeddings[i]], ids=[f"chunk_{i}"])
        logger.info(f"✅ Indexación completada. {len(chunks)} fragmentos.")
    else:
        logger.warning("⚠️ No se pudo leer el PDF.")
else:
    logger.info(f"✅ Base de datos lista. {coleccion.count()} fragmentos.")

# --- FUNCIONES DE SCRAPING WEB ---
def extraer_texto_web(url):
    """Obtiene y limpia el texto de una página web."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        texto = ""
        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
            texto += tag.get_text(strip=True) + "\n"
        
        texto = re.sub(r'\n\s*\n', '\n', texto)
        return texto.strip()
    except Exception as e:
        logger.error(f"❌ Error al scrapear {url}: {e}")
        return ""

def buscar_y_scrapear(tema):
    """Busca información en sitios predefinidos de la UNSIS."""
    sitios = {
        "convocatoria": "https://www.unsis.edu.mx/web/",
        "servicios_escolares": "https://www.unsis.edu.mx/web/ensenanza/ingreso_a_la_licenciatura"
    }
    
    tema_lower = tema.lower()
    if "convocatoria" in tema_lower or "admision" in tema_lower:
        url = sitios["convocatoria"]
    elif "guía" in tema_lower or "estudio" in tema_lower or "examen" in tema_lower:
        url = sitios["servicios_escolares"]
    elif "oferta" in tema_lower or "carrera" in tema_lower:
        url = sitios["ensenanza"]
    elif "propedeutico" in tema_lower or "curso" in tema_lower or "fecha" in tema_lower or "calendario" in tema_lower:
        url = sitios["convocatoria"]
    else:
        url = sitios["inicio"]
    
    logger.info(f"🌐 Scrapeando: {url}")
    return extraer_texto_web(url)

def extraer_url(texto):
    patron = r'https?://[^\s]+'
    urls = re.findall(patron, texto)
    return urls[0] if urls else None

# --- MODELO PARA PREGUNTAS ---
class Pregunta(BaseModel):
    mensaje: str

# --- FUNCIONES PARA RESPUESTAS PREDETERMINADAS ---
def obtener_respuesta_saludo(mensaje):
    """Devuelve una respuesta amigable para saludos."""
    mensaje_lower = mensaje.lower()
    
    if any(p in mensaje_lower for p in ["hola", "buenos días", "buen día", "buenas tardes", "buenas noches"]):
        saludos = [
            "👋 ¡Hola! ¿Cómo estás? Soy tu asistente virtual de la UNSIS. ¿En qué puedo ayudarte hoy?",
            "😊 ¡Buen día! Me alegra verte por aquí. ¿Tienes alguna duda sobre el proceso de admisión?",
            "🌟 ¡Hola! Estoy aquí para ayudarte con tu solicitud de ficha. ¿Qué necesitas saber?"
        ]
        return random.choice(saludos)
    
    elif any(p in mensaje_lower for p in ["gracias", "muchas gracias", "gracias por"]):
        agradecimientos = [
            "🙏 ¡De nada! Es un placer ayudarte. ¿Hay algo más en lo que pueda asistirte?",
            "😊 ¡Con gusto! Recuerda que estoy aquí para lo que necesites.",
            "🌟 ¡Gracias a ti por confiar en el asistente de la UNSIS! ¿Alguna otra pregunta?"
        ]
        return random.choice(agradecimientos)
    
    elif any(p in mensaje_lower for p in ["adiós", "chao", "hasta luego", "nos vemos"]):
        despedidas = [
            "👋 ¡Hasta luego! Si tienes más dudas, aquí estoy. ¡Éxito en tu proceso de admisión!",
            "🌟 ¡Nos vemos! No olvides revisar el portal para el estatus de tu solicitud.",
            "😊 ¡Cuídate! Si necesitas ayuda, solo abre el chat y pregúntame."
        ]
        return random.choice(despedidas)
    
    return None

def detectar_intencion(texto):
    """Detecta la intención del usuario."""
    texto = texto.lower()
    
    if any(p in texto for p in ["hola", "buenos días", "buen día", "buenas tardes", "buenas noches", "gracias", "adiós", "chao", "hasta luego"]):
        return "saludo"
    
    if any(p in texto for p in ["documento", "requisito", "necesito", "papel", "acta", "certificado", "curp", "foto"]):
        return "documentos"
    if any(p in texto for p in ["registro", "registrarme", "usuario", "contraseña", "crear cuenta"]):
        return "registro"
    if any(p in texto for p in ["paso", "procedimiento", "cómo hago", "ficha", "solicitar"]):
        return "procedimiento"
    if any(p in texto for p in ["examen", "sede", "fecha", "hora", "aplicación"]):
        return "examen"
    if any(p in texto for p in ["tutor", "padre", "madre", "familiar"]):
        return "tutor"
    if any(p in texto for p in ["estatus", "revisar", "validación", "días"]):
        return "estatus"
    if any(p in texto for p in ["propedeutico", "curso", "calendario", "periodo", "inicia", "inicio"]):
        return "propedeutico"
    
    return "no_detectado"

def formatear_respuesta(intencion, contexto):
    """Construye respuestas formateadas según la intención detectada."""
    
    if not contexto or len(contexto) < 50:
        contexto = "No encontré información específica en el PDF sobre este tema."
    
    respuestas = {
        "documentos": f"""📋 **DOCUMENTOS NECESARIOS PARA TU FICHA**

Estos son los documentos que debes escanear (en PDF, JPG o PNG):

1. 📄 **Acta de nacimiento** (legible, completa)
2. 🎓 **Certificado de bachillerato** o constancia de estudios con materias y calificaciones
3. 🆔 **CURP** (descárgala de [gob.mx](https://www.gob.mx/curp/))
4. 📸 **Fotografía infantil** (blanco y negro, formato JPG o PNG)

⚠️ **Importante:** 
- Cada documento debe ir en un archivo SEPARADO.
- Asegúrate de que sea LEGIBLE y esté COMPLETO.
- Si usas el celular, verifica que no salga borroso.

---
📌 *Contexto del PDF:*  
{contexto[:400]}...
""",
        "registro": f"""🔐 **REGISTRO EN EL SISTEMA**

Para crear tu usuario, sigue estos pasos:

1. 🌐 Ingresa a: `http://inscripciones.unsis.edu.mx/`
2. 👤 Haz clic en **"Registrarse"**
3. ✏️ Captura:
   - **Usuario:** Tu CURP (sin errores ortográficos)
   - **Correo:** Uno personal y activo
   - **Contraseña:** Mínimo 8 caracteres (¡GUÁRDALA!)
4. ✅ Presiona **"Registrar"**

⚠️ Si ves el mensaje *"Un error ocurrió al tratar de guardar usuario"*, revisa que tu CURP esté bien escrita.

---
📌 *Contexto del PDF:*  
{contexto[:400]}...
""",
        "procedimiento": f"""📝 **PROCEDIMIENTO PASO A PASO**

Sigue esta secuencia para obtener tu ficha:

1️⃣ **Reúne documentos** (Acta, Certificado, CURP, Foto)
2️⃣ **Regístrate** en `inscripciones.unsis.edu.mx`
3️⃣ **Llena tus datos** en las pestañas:
   - Datos personales (nombre en MAYÚSCULAS sin acentos)
   - Lengua indígena (selecciona "NINGUNA" si no aplica)
   - Datos académicos (busca tu escuela)
   - Datos médicos
   - Datos de padres/tutores
4️⃣ **Adjunta** los documentos escaneados
5️⃣ **Selecciona** carrera y sede de examen
6️⃣ **Envía** tu solicitud

⏳ Luego espera **2 a 3 días hábiles** para la validación.

---
📌 *Contexto del PDF:*  
{contexto[:400]}...
""",
        "examen": f"""📝 **EXAMEN DE SELECCIÓN**

Información clave:

- 🗓️ **Fecha:** 01 de julio de 2026
- ⏰ **Hora:** 10:00 AM
- 📍 **Sede:** UNSIS Miahuatlán

📌 **Requisitos para el día del examen:**
- Llegar **20 minutos antes**
- Traer este comprobante impreso
- Identificación oficial con foto
- Lápiz, goma, sacapuntas y calculadora

📚 **Guía de estudio:**  
[http://www.unsis.edu.mx/servicios_escolares/index.html](http://www.unsis.edu.mx/servicios_escolares/index.html)

---
📌 *Contexto del PDF:*  
{contexto[:400]}...
""",
        "tutor": f"""👨‍👩‍👧 **DATOS DEL TUTOR**

- Si seleccionaste a tu **padre o madre** como tutor, el sistema copiará automáticamente los datos que ya capturaste.
- Si eliges a **otra persona**, deberás llenar todos sus datos manualmente.

💡 **Tip:** Usa la opción *"Copiar datos de domicilio del Aspirante"* si vives en el mismo lugar.

---
📌 *Contexto del PDF:*  
{contexto[:400]}...
""",
        "estatus": f"""🔍 **REVISAR ESTATUS DE TU SOLICITUD**

Después de enviar tu solicitud:

- ⏳ Espera **2 a 3 días hábiles**.
- 🌐 Ingresa al mismo portal con tu **usuario (CURP)** y **contraseña**.
- ✅ Si todo está correcto: te asignarán un **número de ficha** y podrás descargar tu comprobante.
- ❌ Si hay observaciones: deberás corregir y reenviar los documentos.

📧 ¿Dudas? Escribe a: `admision.unsis@gmail.com`

---
📌 *Contexto del PDF:*  
{contexto[:400]}...
""",
        "propedeutico": f"""📚 **PROPEDÉUTICO Y FECHAS IMPORTANTES**

La información sobre fechas específicas (inicio del propedéutico, cursos, calendario, etc.) suele publicarse en la convocatoria oficial de la UNSIS.

📌 **Recomendaciones:**
1. 🌐 Visita la página oficial: [www.unsis.edu.mx](https://www.unsis.edu.mx)
2. 📧 Contacta a admisión: `admision.unsis@gmail.com`
3. 📱 Sigue las redes sociales de la UNSIS para anuncios importantes

---
📌 *Lo que encontré en el PDF:*  
{contexto[:400]}...
""",
        "no_detectado": f"""🤔 No estoy seguro de haber entendido tu pregunta.

Puedo ayudarte con estos temas específicos:

📋 **Documentos necesarios**  
🔐 **Registro en el sistema**  
📝 **Procedimiento paso a paso**  
📅 **Examen de selección**  
👨‍👩‍👧 **Datos del tutor**  
🔍 **Estatus de tu solicitud**  
📚 **Propedéutico y fechas**  

**Prueba reformulando tu pregunta** o pregúntame sobre alguno de estos temas.

Si necesitas información más actualizada, visita la página oficial: [www.unsis.edu.mx](https://www.unsis.edu.mx)
"""
    }
    
    return respuestas.get(intencion, respuestas["no_detectado"])

# --- ENDPOINT PRINCIPAL ---
@app.post("/chat")
async def chat(pregunta: Pregunta):
    try:
        mensaje = pregunta.mensaje.strip()
        logger.info(f"📨 Pregunta: {mensaje[:50]}...")
        
        intencion = detectar_intencion(mensaje)
        logger.info(f"🎯 Intención detectada: {intencion}")
        
        if intencion == "saludo":
            respuesta = obtener_respuesta_saludo(mensaje)
            return {"respuesta": respuesta}
        
        # Contexto del PDF
        embedding_consulta = modelo.encode(mensaje).tolist()
        resultados = coleccion.query(
            query_embeddings=[embedding_consulta],
            n_results=2
        )
        contexto_pdf = "\n".join(resultados['documents'][0]) if resultados['documents'] else ""
        
        # Scraping web
        contexto_web = ""
        url_usuario = extraer_url(mensaje)
        
        if url_usuario:
            logger.info(f"🔗 URL detectada: {url_usuario}")
            texto_web = extraer_texto_web(url_usuario)
            if texto_web:
                chunks_web = dividir_chunks(texto_web, tamano=500)
                contexto_web = "\n".join(chunks_web[:3])
        elif intencion == "no_detectado" or len(contexto_pdf) < 100:
            logger.info("🌐 Buscando información complementaria en la web...")
            texto_web = buscar_y_scrapear(mensaje)
            if texto_web:
                chunks_web = dividir_chunks(texto_web, tamano=500)
                contexto_web = "\n".join(chunks_web[:3])
        
        # Elegir contexto final
        contexto_final = contexto_web if contexto_web else contexto_pdf
        
        # Generar respuesta
        respuesta = formatear_respuesta(intencion, contexto_final)
        
        if contexto_web:
            respuesta += "\n\n---\n🌐 *Información complementaria obtenida de la página oficial de la UNSIS.*"
        
        return {"respuesta": respuesta}
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT DE SALUD ---
@app.get("/health")
def health():
    return {"status": "ok", "fragmentos": coleccion.count()}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
