gis # Mi Asesor CETES

Aplicación web inteligente desarrollada con Streamlit para realizar pronósticos y análisis de los Certificados de la Tesorería de la Federación (CETES).

## ✨ Características

- 📊 Pronósticos de tasas CETES usando modelos SARIMAX
- 🤖 Asesor Experto con IA (OpenAI GPT)
- 🎤 Entrada por voz (transcripción y síntesis)
- 📈 Gráficas interactivas con Plotly
- 📉 Análisis estadístico de datos históricos

## 🚀 Despliegue en Streamlit Cloud

1. Sube tu código a GitHub
2. Conecta tu repositorio en [Streamlit Cloud](https://share.streamlit.io/)
3. Configura los secrets:
   - `OPENAI_API_KEY`: Tu clave de OpenAI
   - `BANXICO_API_KEY`: Tu clave de Banxico
4. Especifica el archivo principal: `main.py`
5. ¡Despliega!

## ⚙️ Desarrollo Local

### Instalación

```bash
pip install -r requirements.txt
```

### Ejecución

```bash
streamlit run main.py --server.headless=false
```

### Variables de Entorno

Crea un archivo `.env` con:
```
OPENAI_API_KEY=tu_clave
BANXICO_API_KEY=tu_clave
```

## 📝 Licencia

Ver el archivo `LICENSE` para más detalles.
