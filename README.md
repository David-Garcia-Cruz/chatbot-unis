# Chatbot UNSIS - Admisión 2026

Asistente virtual para el proceso de obtención de ficha de admisión en la Universidad de la Sierra Sur (UNSIS).

Este chatbot responde preguntas frecuentes sobre el procedimiento de inscripción, documentos necesarios, fechas de examen, y más. Utiliza un motor de búsqueda semántica sobre un PDF institucional y puede complementar la información con scraping web del sitio oficial.

---

## Características principales

- Respuestas automáticas a preguntas frecuentes (documentos, registro, examen, estatus, etc.)
- Búsqueda semántica en el PDF oficial del procedimiento (con SentenceTransformers + ChromaDB)
- Scraping web complementario para obtener información actualizada del sitio de la UNSIS
- Interfaz amigable con colores institucionales (guinda y blanco)
- Saludos y despedidas con respuestas personalizadas
- Servicio systemd para ejecución permanente en Ubuntu

---

## Tecnologías utilizadas

Backend: Python 3.14, FastAPI, Uvicorn
IA / NLP: SentenceTransformers (all-MiniLM-L6-v2), ChromaDB (vector database)
Scraping: Requests + BeautifulSoup4 + lxml
Servidor web: Apache2 (proxy inverso)
Frontend: HTML5, CSS3, JavaScript (vanilla)
Despliegue: Ubuntu 24.04 LTS, systemd

---

## Requisitos previos

- Ubuntu 22.04 o superior (o cualquier sistema con systemd)
- Python 3.10 o superior
- Apache2 con módulos proxy y proxy_http habilitados
- Git (para clonar el repositorio)

---

## Instalación y configuración

1. Clonar el repositorio:
   git clone https://github.com/David-Garcia-Cruz/chatbot-unis.git
   cd chatbot-unis

2. Crear entorno virtual e instalar dependencias:
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

3. Colocar el PDF con el procedimiento:
   Copia el archivo "Procedimiento para obtener tu ficha en linea 2026.pdf" en la carpeta del proyecto y renómbralo a "ficha_unsis.pdf":
   cp /ruta/del/pdf.pdf ficha_unsis.pdf

4. Configurar el servicio systemd:
   sudo cp config/chatbot-unsis.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable chatbot-unsis.service
   sudo systemctl start chatbot-unsis.service

5. Configurar Apache como proxy inverso:
   sudo cp config/apache.conf /etc/apache2/sites-available/000-default.conf
   sudo a2enmod proxy proxy_http
   sudo systemctl restart apache2

6. Copiar el frontend al directorio web:
   sudo mkdir -p /var/www/unsis_chat
   sudo cp frontend/index.html /var/www/unsis_chat/
   sudo chown -R www-data:www-data /var/www/unsis_chat

7. Verificar el estado:
   sudo systemctl status chatbot-unsis.service
   sudo journalctl -u chatbot-unsis.service -f

---

## Uso

Una vez instalado, abre tu navegador y ve a la IP de tu servidor (o http://localhost). Aparecerá la página de la UNSIS con el chatbot flotante abajo a la derecha.

Haz clic en el botón 💬 y prueba preguntar:
- "Hola" (responderá con un saludo)
- "¿Qué documentos necesito?"
- "¿Cómo me registro?"
- "¿Cuándo es el examen?"
- "¿Cuál es el estatus de mi solicitud?"
- "¿Qué carreras ofrece la UNSIS?" (scrapea la web)

---

## Estructura del proyecto

/chatbot-unis/
├── main.py                  # Backend FastAPI
├── frontend/
│   └── index.html           # Interfaz del chatbot (HTML, CSS, JS)
├── config/
│   ├── chatbot-unsis.service # Archivo de servicio systemd
│   └── apache.conf          # Configuración de Apache (proxy inverso)
├── requirements.txt         # Dependencias de Python
├── .gitignore               # Archivos ignorados por Git
├── ficha_unsis.pdf          # PDF del procedimiento (debe estar presente)
└── README.md                # Este archivo

---

## Créditos / Autores

- Desarrollador: David García Cruz
- Tecnologías de IA y scraping: SentenceTransformers, ChromaDB, BeautifulSoup
- Link del video: https://drive.google.com/file/d/1kUw9QEK3D3i6QUUEcMCXoubquPax_hbC/view?usp=drive_link

---



Para dudas o sugerencias, escribe a: admision.unsis@gmail.com o abre un issue en este repositorio.

---

¡Gracias por visitar este proyecto! 🎓🚀
