import streamlit as st
from utils.common import get_image_path, obtener_datos_banxico, generar_todos_los_pronosticos

# Configuración de la página
st.set_page_config(
    page_title="Mi Asesor CETES",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Generar pronósticos al inicio de la aplicación
if "pronosticos_generados" not in st.session_state:
    with st.spinner("⏳ Actualizando base de datos..."):
        df_banxico = obtener_datos_banxico()
        if df_banxico is not None and not df_banxico.empty:
            pronosticos = generar_todos_los_pronosticos(df_banxico, periodos_pronostico=13)  # Máximo de semanas
            st.session_state.pronosticos_generados = pronosticos
            st.session_state.df_banxico = df_banxico
            st.session_state.pronosticos_listos = True
        else:
            st.session_state.pronosticos_generados = None
            st.session_state.df_banxico = None
            st.session_state.pronosticos_listos = False

# Sección de bienvenida con imagen
st.header("🏡 Bienvenido")
col1, col2 = st.columns([2, 1])

with col1:
    st.write("""
    **Mi Asesor CETES** es tu herramienta inteligente para realizar pronósticos y análisis 
    de los Certificados de la Tesorería de la Federación (CETES). 
    
    Con esta aplicación podrás:
    - 📊 Analizar tendencias históricas de CETES
    - 📈 Realizar pronósticos de tasas de interés
    - 💡 Tomar decisiones de inversión informadas
    - 📉 Visualizar gráficos interactivos
    - 🤖 Consultar con un Asesor Experto en CETES
    """)

with col2:
    logo_path = get_image_path("Logo.png")
    if logo_path:
        st.image(logo_path, width=250)