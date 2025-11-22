import streamlit as st
from utils.common import obtener_datos_banxico, generar_todos_los_pronosticos

# Configuración de la página
st.set_page_config(
    page_title="Mi Asesor CETES",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Generar pronósticos al inicio de la aplicación (carga diferida para evitar timeout)
if "pronosticos_generados" not in st.session_state:
    # Marcar que estamos cargando para evitar múltiples intentos simultáneos
    if "cargando_datos" not in st.session_state:
        st.session_state.cargando_datos = True
        try:
            # Primero cargar solo los datos de Banxico (más rápido)
            with st.spinner("⏳ Cargando datos de Banxico..."):
                df_banxico = obtener_datos_banxico()
                if df_banxico is not None and not df_banxico.empty:
                    st.session_state.df_banxico = df_banxico
                    # Generar pronósticos en segundo plano (puede tardar más)
                    with st.spinner("⏳ Generando pronósticos (esto puede tardar unos minutos)..."):
                        try:
                            # Reducir periodos iniciales para acelerar la primera carga
                            pronosticos = generar_todos_los_pronosticos(df_banxico, periodos_pronostico=4)  # Empezar con 4 semanas
                            st.session_state.pronosticos_generados = pronosticos
                            st.session_state.pronosticos_listos = True
                        except Exception as pronostico_error:
                            # Si falla la generación de pronósticos, continuar sin ellos
                            st.session_state.pronosticos_generados = None
                            st.session_state.pronosticos_listos = False
                else:
                    st.session_state.pronosticos_generados = None
                    st.session_state.df_banxico = None
                    st.session_state.pronosticos_listos = False
        except Exception as e:
            # Manejo de error general
            st.session_state.pronosticos_generados = None
            st.session_state.df_banxico = None
            st.session_state.pronosticos_listos = False
        finally:
            st.session_state.cargando_datos = False

# Sección de bienvenida
st.header("🏡 Bienvenido")
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