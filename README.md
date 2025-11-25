# Mi Asesor CETES

Chatbot experto en CETES y productos de inversión en México, desarrollado con Gradio y OpenAI.

## Características

- 💬 **Asesor experto con IA**: Chatbot inteligente que responde preguntas sobre CETES y productos de inversión
- 🔮 **Pronósticos avanzados**: Modelos SARIMAX con variables exógenas para pronosticar tasas de CETES (hasta 13 semanas)
- 📊 **Análisis de datos históricos**: Extracción y análisis de datos de Banxico desde 2006
- 📈 **Visualización interactiva**: Gráficas dinámicas con Plotly para comparar diferentes plazos de CETES
- 🔊 **Audio integrado**: Respuestas en texto y audio usando OpenAI TTS

## Instalación

1. Clona el repositorio:
```bash
git clone https://github.com/Vazqmi02/Proyecto-MiAsesorCETES.git
cd Proyecto-MiAsesorCETES
```

2. Crea un entorno virtual:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt
```

4. Configura tus API keys:
```bash
cp .env.example .env
```
Edita el archivo `.env` y agrega:
- `OPENAI_API_KEY`: Tu API key de OpenAI (obligatorio)
- `BANXICO_API_KEY`: Tu token de API de Banxico (obligatorio). Obtén tu token en: https://www.banxico.org.mx/SieAPIRest/service/v1/token

## Uso

Ejecuta la aplicación:
```bash
python app.py
```

La aplicación se abrirá en tu navegador en `http://127.0.0.1:7860`

## Estructura del Proyecto

- `app.py`: Aplicación principal con interfaz Gradio
- `banxico_data.py`: Módulo para extraer datos de Banxico y generar pronósticos SARIMAX
- `prompts.py`: Prompts del sistema para el chatbot
- `tooling.py`: Funciones de herramientas para el chatbot
- `requirements.txt`: Dependencias del proyecto

## Tecnologías Utilizadas

- **Gradio**: Interfaz web interactiva
- **OpenAI API**: Chatbot y generación de audio
- **Statsmodels**: Modelos SARIMAX para pronósticos
- **Plotly**: Gráficas interactivas
- **Pandas**: Manipulación de datos
- **Banxico API**: Datos históricos de CETES

## Autor

Vazqmi02

