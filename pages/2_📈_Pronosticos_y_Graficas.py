import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
from utils.common import obtener_datos_banxico, generar_todos_los_pronosticos

# Configuración de la página
st.set_page_config(
    page_title="Pronósticos y Gráficas - Mi Asesor CETES",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.header("📈 Pronósticos y Gráficas de CETES")
st.markdown("Visualiza pronósticos y análisis de tendencias de CETES.")
st.divider()

# Verificar y generar pronósticos si no existen (por si se accede directamente a esta página)
if "pronosticos_generados" not in st.session_state:
    if "cargando_datos" not in st.session_state:
        st.session_state.cargando_datos = True
        try:
            with st.spinner("⏳ Cargando datos de Banxico..."):
                df_banxico = obtener_datos_banxico()
                if df_banxico is not None and not df_banxico.empty:
                    st.session_state.df_banxico = df_banxico
                    with st.spinner("⏳ Generando pronósticos (esto puede tardar unos minutos)..."):
                        try:
                            # Reducir periodos iniciales para acelerar
                            pronosticos = generar_todos_los_pronosticos(df_banxico, periodos_pronostico=4)
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

# Sidebar para configuraciones
with st.sidebar:
    st.subheader("⚙️ Configuración")
    
    # Opciones de visualización
    tipo_visualizacion = st.selectbox(
        "Tipo de visualización",
        ["Tendencia Histórica", "Pronóstico", "Comparativa"]
    )
    
    plazo_cetes = st.selectbox(
        "Plazo de CETES",
        ["28 días", "91 días", "182 días", "364 días"],
        index=2
    )
    
    semanas_pronostico = st.slider(
        "Semanas de pronóstico",
        min_value=1,
        max_value=13,
        value=4,
        step=1
    )

# Mapeo de plazos a columnas
mapeo_plazos = {
    "28 días": "CETE_28D",
    "91 días": "CETE_91D",
    "182 días": "CETE_182D",
    "364 días": "CETE_364D"
}

# Cargar datos de Banxico desde session_state o generar si no existen
def cargar_datos_banxico():
    """Carga datos de Banxico desde session_state o los obtiene si no existen"""
    if 'df_banxico' in st.session_state and st.session_state.df_banxico is not None:
        return st.session_state.df_banxico
    else:
        df = obtener_datos_banxico()
        if df is not None and not df.empty:
            st.session_state.df_banxico = df
        return df

# Cargar datos
with st.spinner("📥 Descargando datos de Banxico..."):
    df_banxico = cargar_datos_banxico()

# Sección principal de contenido
tab1, tab2, tab3 = st.tabs(["📊 Gráficas y Pronósticos", "📉 Estadisticas", "📋 Datos"])

with tab1:
    st.subheader("Gráficas de CETES")
    
    if df_banxico is None or df_banxico.empty:
        st.error("❌ No se pudieron cargar los datos de Banxico. Verifica que la API key esté configurada correctamente.")
        st.info("💡 **Instrucciones para Streamlit Cloud**: \n"
                "1. Ve a la configuración de tu app en Streamlit Cloud\n"
                "2. Agrega un secret: `BANXICO_API_KEY` = `tu_clave_aqui`\n"
                "3. Obtén tu clave en: https://www.banxico.org.mx/SieAPIRest/service/v1/\n\n"
                "💡 **Para desarrollo local**: \n"
                "1. Crea un archivo `.env` en la raíz del proyecto\n"
                "2. Agrega: `BANXICO_API_KEY=tu_clave_aqui`")
        st.stop()
    
    st.success("✅ Datos de Banxico cargados correctamente.")
    # Preparar DataFrame para visualización
    columna_tasa = mapeo_plazos[plazo_cetes]
    
    if columna_tasa not in df_banxico.columns:
        st.error(f"❌ La columna {columna_tasa} no está disponible en los datos de Banxico.")
        st.stop()
    
    # Crear DataFrame con fecha y tasa
    df = df_banxico[[columna_tasa]].copy()
    df = df.dropna(subset=[columna_tasa])
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'Fecha', columna_tasa: 'Tasa'}, inplace=True)
    
    if df.empty:
        st.warning("⚠️ No hay datos disponibles para mostrar.")
        st.stop()
    
    if tipo_visualizacion == "Tendencia Histórica":
        fig = px.line(
            df, 
            x='Fecha', 
            y='Tasa',
            title=f'Tendencia Histórica de CETES {plazo_cetes}',
            labels={'Tasa': 'Tasa de Interés (%)', 'Fecha': 'Fecha'}
        )
        fig.update_layout(
            xaxis_title="Fecha",
            yaxis_title="Tasa de Interés (%)",
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    elif tipo_visualizacion == "Pronóstico":
        if df.empty:
            st.warning("⚠️ No hay datos suficientes para generar un pronóstico.")
            st.stop()
        
        try:
            # Preparar datos para SARIMAX
            df_completo = df_banxico.copy()
            
            # Definir variables exógenas
            exog_cols = [c for c in df_completo.columns if 'CETE' not in c]
            
            # Variable objetivo según el plazo seleccionado
            variable_objetivo = mapeo_plazos[plazo_cetes]
            
            if variable_objetivo not in df_completo.columns:
                st.error(f"⚠️ La variable {variable_objetivo} no está disponible en los datos.")
            else:
                # Usar pronósticos pre-generados desde session_state
                pronosticos_dict = st.session_state.get('pronosticos_generados', None)
                
                if pronosticos_dict and variable_objetivo in pronosticos_dict:
                    # Usar pronóstico pre-generado
                    pronostico_data = pronosticos_dict[variable_objetivo]
                    pronostico_series = pronostico_data['pronostico_series']
                    fechas_pronostico = pronostico_data['fechas_pronostico']
                    modelo_ajustado = pronostico_data['modelo_ajustado']
                    
                    # Si el usuario solicita menos semanas que las generadas, truncar
                    if len(pronostico_series) > semanas_pronostico:
                        pronostico_series = pronostico_series.iloc[:semanas_pronostico]
                        fechas_pronostico = fechas_pronostico[:semanas_pronostico]
                else:
                    st.warning("⚠️ Los pronósticos no están disponibles. Por favor, recarga la aplicación desde la página principal.")
                    pronostico_series = None
                    fechas_pronostico = None
                    modelo_ajustado = None
                
                if pronostico_series is None:
                    st.error("❌ No se pudo cargar el pronóstico. Verifica que haya suficientes datos históricos.")
                else:
                    # Datos históricos
                    fig = go.Figure()
                    
                    # Línea histórica
                    fig.add_trace(go.Scatter(
                        x=df['Fecha'],
                        y=df['Tasa'],
                        mode='lines',
                        name='Histórico',
                        line=dict(color='blue', width=2)
                    ))
                    
                    # Pronóstico con intervalo de confianza (si está disponible)
                    fig.add_trace(go.Scatter(
                        x=fechas_pronostico,
                        y=pronostico_series.values,
                        mode='lines',
                        name='Pronóstico',
                        line=dict(color='red', dash='dash', width=2)
                    ))
                    
                    # Agregar intervalo de confianza si está disponible en los pronósticos pre-generados
                    if pronosticos_dict and variable_objetivo in pronosticos_dict:
                        pronostico_data = pronosticos_dict[variable_objetivo]
                        if pronostico_data.get('tiene_intervalo', False):
                            # Usar intervalos pre-calculados
                            limite_inferior = pronostico_data['limite_inferior']
                            limite_superior = pronostico_data['limite_superior']
                        
                        # Crear series para los intervalos 
                        try:
                            # Intentar obtener intervalos del modelo si están disponibles
                            exog_cols_forecast = [c for c in df_completo.columns if 'CETE' not in c]
                            
                            if exog_cols_forecast:
                                exog_forecast_df = pd.DataFrame(
                                    index=fechas_pronostico,
                                    columns=exog_cols_forecast
                                )
                                for col in exog_cols_forecast:
                                    if col in df_completo.columns:
                                        exog_forecast_df[col] = df_completo[col].ffill().iloc[-1]
                                
                                forecast_obj = modelo_ajustado.get_forecast(
                                    steps=semanas_pronostico, 
                                    exog=exog_forecast_df
                                )
                            else:
                                forecast_obj = modelo_ajustado.get_forecast(steps=semanas_pronostico)
                            
                            pronostico_ci = forecast_obj.conf_int()
                            
                            # Intervalo superior
                            fig.add_trace(go.Scatter(
                                x=fechas_pronostico,
                                y=pronostico_ci.iloc[:, 1],
                                mode='lines',
                                name='Límite Superior (95%)',
                                line=dict(color='rgba(255,0,0,0.3)', width=1),
                                showlegend=True
                            ))
                            
                            # Intervalo inferior
                            fig.add_trace(go.Scatter(
                                x=fechas_pronostico,
                                y=pronostico_ci.iloc[:, 0],
                                mode='lines',
                                name='Límite Inferior (95%)',
                                line=dict(color='rgba(255,0,0,0.3)', width=1),
                                fill='tonexty',
                                fillcolor='rgba(255,0,0,0.1)',
                                showlegend=True
                            ))
                        except Exception:
                            # Si no se pueden obtener intervalos, continuar sin ellos
                            pass
                    
                    fig.update_layout(
                        title=f'Pronóstico de CETES {plazo_cetes} ({semanas_pronostico} semanas)',
                        xaxis_title="Fecha",
                        yaxis_title="Tasa de Interés (%)",
                        hovermode='x unified',
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Métricas del pronóstico
                    tasa_actual = df['Tasa'].iloc[-1]
                    tasa_pronosticada = pronostico_series.iloc[-1]
                    tasa_pronostico_inicial = pronostico_series.iloc[0]  # Primer pronóstico
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Tasa Actual", f"{tasa_actual:.2f}%")
                    with col2:
                        st.metric("Tasa Pronosticada", f"{tasa_pronosticada:.2f}%")
                    with col3:
                        cambio = tasa_pronosticada - tasa_actual
                        st.metric("Cambio Esperado", f"{cambio:+.2f}%")
                    
                    # --- LÓGICA DE RECOMENDACIÓN (Cautelosa) ---
                    st.divider()
                    st.subheader("💡 Recomendación de Inversión")
                    
                    # Umbral para considerar cambios significativos (en puntos porcentuales)
                    CAUTIOUS_THRESHOLD = 0.2  # 0.2 puntos porcentuales
                    
                    # Cambio esperado en la próxima subasta (primer pronóstico vs tasa actual)
                    change = tasa_pronostico_inicial - tasa_actual
                    
                    if change > CAUTIOUS_THRESHOLD:
                        # Predicción: Alza significativa -> ESPERAR para comprar a mejor tasa
                        recommendation = "🤔 ESPERAR"
                        explanation = f"Se predice un alza significativa en la próxima subasta (> {CAUTIOUS_THRESHOLD:.2f}pp). Esperar podría darte un mayor rendimiento."
                        st.warning(f"**{recommendation}**\n\n{explanation}")
                    elif change < -CAUTIOUS_THRESHOLD:
                        # Predicción: Baja significativa -> INVERTIR AHORA para asegurar la tasa actual
                        recommendation = "✅ ¡INVERTIR AHORA!"
                        explanation = f"La tasa actual es atractiva. Nuestro modelo predice que podría bajar pronto (< -{CAUTIOUS_THRESHOLD:.2f}pp), ¡asegura este rendimiento!"
                        st.success(f"**{recommendation}**\n\n{explanation}")
                    else:
                        # Predicción: Estable o cambio menor -> INVERTIR por defecto
                        recommendation = "⚖️ INVERTIR (ESTABLE)"
                        explanation = "El cambio previsto es mínimo. Invierte ahora para evitar que tu capital pierda tiempo en efectivo."
                        st.info(f"**{recommendation}**\n\n{explanation}")
                    
                    # Mostrar detalles adicionales
                    with st.expander("📊 Detalles del Análisis"):
                        st.markdown(f"""
                        - **Tasa Actual**: {tasa_actual:.2f}%
                        - **Primer Pronóstico** (próxima subasta): {tasa_pronostico_inicial:.2f}%
                        - **Cambio Esperado**: {change:+.2f} puntos porcentuales
                        - **Umbral de Decisión**: ±{CAUTIOUS_THRESHOLD:.2f} puntos porcentuales
                        - **Recomendación**: {recommendation}
                        """)
                
                    
        except Exception as e:
            st.error(f"❌ Error al generar pronóstico: {str(e)}")
            st.info("💡 Intentando con método de respaldo...")
            
            # Método de respaldo simple
            fecha_fin_historico = df['Fecha'].max()
            # Crear fechas semanales para el pronóstico
            fechas_pronostico = pd.date_range(
                start=fecha_fin_historico + timedelta(weeks=1),
                periods=semanas_pronostico,
                freq='W-THU'
            )
            tasa_actual = df['Tasa'].iloc[-1]
            
            if len(df) > 10:
                tendencia = (df['Tasa'].iloc[-1] - df['Tasa'].iloc[-10]) / 10
                pronostico = [tasa_actual + tendencia * (i + 1) for i in range(semanas_pronostico)]
            else:
                pronostico = [tasa_actual] * semanas_pronostico
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df['Fecha'],
                y=df['Tasa'],
                mode='lines',
                name='Histórico',
                line=dict(color='blue')
            ))
            fig.add_trace(go.Scatter(
                x=fechas_pronostico,
                y=pronostico,
                mode='lines',
                name='Pronóstico (Respaldo)',
                line=dict(color='red', dash='dash')
            ))
            fig.update_layout(
                title=f'Pronóstico de CETES {plazo_cetes} ({semanas_pronostico} semanas)',
                xaxis_title="Fecha",
                yaxis_title="Tasa de Interés (%)",
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Métricas y recomendaciones del método de respaldo
            tasa_pronosticada_respaldo = pronostico[-1]
            tasa_pronostico_inicial_respaldo = pronostico[0]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Tasa Actual", f"{tasa_actual:.2f}%")
            with col2:
                st.metric("Tasa Pronosticada", f"{tasa_pronosticada_respaldo:.2f}%")
            with col3:
                cambio_respaldo = tasa_pronosticada_respaldo - tasa_actual
                st.metric("Cambio Esperado", f"{cambio_respaldo:+.2f}%")
            
            # --- LÓGICA DE RECOMENDACIÓN (Cautelosa) - Método de Respaldo ---
            st.divider()
            st.subheader("💡 Recomendación de Inversión")
            
            # Umbral para considerar cambios significativos (en puntos porcentuales)
            CAUTIOUS_THRESHOLD = 0.2  # 0.2 puntos porcentuales
            
            # Cambio esperado en la próxima subasta (primer pronóstico vs tasa actual)
            change_respaldo = tasa_pronostico_inicial_respaldo - tasa_actual
            
            if change_respaldo > CAUTIOUS_THRESHOLD:
                # Predicción: Alza significativa -> ESPERAR para comprar a mejor tasa
                recommendation = "🤔 ESPERAR"
                explanation = f"Se predice un alza significativa en la próxima subasta (> {CAUTIOUS_THRESHOLD:.2f}pp). Esperar podría darte un mayor rendimiento."
                st.warning(f"**{recommendation}**\n\n{explanation}")
            elif change_respaldo < -CAUTIOUS_THRESHOLD:
                # Predicción: Baja significativa -> INVERTIR AHORA para asegurar la tasa actual
                recommendation = "✅ ¡INVERTIR AHORA!"
                explanation = f"La tasa actual es atractiva. Nuestro modelo predice que podría bajar pronto (< -{CAUTIOUS_THRESHOLD:.2f}pp), ¡asegura este rendimiento!"
                st.success(f"**{recommendation}**\n\n{explanation}")
            else:
                # Predicción: Estable o cambio menor -> INVERTIR por defecto
                recommendation = "⚖️ INVERTIR (ESTABLE)"
                explanation = "El cambio previsto es mínimo. Invierte ahora para evitar que tu capital pierda tiempo en efectivo."
                st.info(f"**{recommendation}**\n\n{explanation}")
            
            # Mostrar detalles adicionales
            with st.expander("📊 Detalles del Análisis"):
                st.markdown(f"""
                - **Tasa Actual**: {tasa_actual:.2f}%
                - **Primer Pronóstico** (próxima subasta): {tasa_pronostico_inicial_respaldo:.2f}%
                - **Cambio Esperado**: {change_respaldo:+.2f} puntos porcentuales
                - **Umbral de Decisión**: ±{CAUTIOUS_THRESHOLD:.2f} puntos porcentuales
                - **Recomendación**: {recommendation}
                - **Nota**: Usando método de pronóstico de respaldo basado en tendencia histórica.
                """)
    
    elif tipo_visualizacion == "Comparativa":
        # Comparativa entre diferentes plazos - Tendencias históricas
        if df_banxico is not None and not df_banxico.empty:
            # Crear gráfica de líneas con todas las tendencias históricas
            fig = go.Figure()
            
            plazos = ["28 días", "91 días", "182 días", "364 días"]
            colores = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # Colores diferentes para cada plazo
            
            plazos_con_datos = []
            
            for idx, plazo in enumerate(plazos):
                col = mapeo_plazos[plazo]
                if col in df_banxico.columns:
                    datos_plazo = df_banxico[col].dropna()
                    if not datos_plazo.empty:
                        fig.add_trace(go.Scatter(
                            x=datos_plazo.index,
                            y=datos_plazo.values,
                            mode='lines',
                            name=plazo,
                            line=dict(color=colores[idx % len(colores)], width=2)
                        ))
                        plazos_con_datos.append(plazo)
            
            if plazos_con_datos:
                fig.update_layout(
                    title='Tendencia Histórica Comparativa de Todos los Plazos de CETES',
                    xaxis_title="Fecha",
                    yaxis_title="Tasa de Interés (%)",
                    hovermode='x unified',
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                    height=600
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Mostrar estadísticas comparativas
                st.subheader("📊 Resumen Estadístico por Plazo")
                
                # Crear DataFrame con estadísticas
                estadisticas_data = []
                for plazo in plazos_con_datos:
                    col = mapeo_plazos[plazo]
                    datos_plazo = df_banxico[col].dropna()
                    if not datos_plazo.empty:
                        estadisticas_data.append({
                            'Plazo': plazo,
                            'Tasa Actual': f"{datos_plazo.iloc[-1]:.2f}%",
                            'Promedio': f"{datos_plazo.mean():.2f}%",
                            'Máximo': f"{datos_plazo.max():.2f}%",
                            'Mínimo': f"{datos_plazo.min():.2f}%",
                            'Volatilidad': f"{datos_plazo.std():.2f}pp"
                        })
                
                if estadisticas_data:
                    df_estadisticas = pd.DataFrame(estadisticas_data)
                    st.dataframe(df_estadisticas, use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ No hay datos suficientes para mostrar la comparativa de tendencias.")
        else:
            st.error("❌ No se pudieron cargar los datos de Banxico. Verifica que la API key esté configurada en Streamlit Cloud secrets o variables de entorno.")


with tab2:
    st.subheader("Análisis de Pronósticos")
    
    # Verificar si hay datos disponibles para análisis
    if df_banxico is not None and not df_banxico.empty:
        columna_tasa_analisis = mapeo_plazos[plazo_cetes]
        
        if columna_tasa_analisis in df_banxico.columns:
            # Obtener datos históricos del plazo seleccionado
            datos_historicos = df_banxico[columna_tasa_analisis].dropna()
            
            if not datos_historicos.empty:
                # === ESTADÍSTICAS HISTÓRICAS ===
                st.markdown("### 📊 Estadísticas Históricas")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    tasa_actual_display = datos_historicos.iloc[-1]
                    st.metric("Tasa Actual", f"{tasa_actual_display:.2f}%")
                with col2:
                    tasa_maxima = datos_historicos.max()
                    st.metric("Máximo Histórico", f"{tasa_maxima:.2f}%")
                with col3:
                    tasa_minima = datos_historicos.min()
                    st.metric("Mínimo Histórico", f"{tasa_minima:.2f}%")
                with col4:
                    tasa_promedio = datos_historicos.mean()
                    st.metric("Promedio Histórico", f"{tasa_promedio:.2f}%")
                
                # === ANÁLISIS DE TENDENCIA ===
                st.divider()
                st.markdown("### 📈 Análisis de Tendencia")
                
                # Calcular tendencia reciente (últimos 3 meses vs últimos 6 meses)
                ultimos_3_meses = datos_historicos.tail(12)  # Aproximadamente 3 meses
                ultimos_6_meses = datos_historicos.tail(24)  # Aproximadamente 6 meses
                
                if len(ultimos_3_meses) >= 4 and len(ultimos_6_meses) >= 8:
                    promedio_3m = ultimos_3_meses.mean()
                    promedio_6m = ultimos_6_meses.mean()
                    cambio_tendencia = promedio_3m - promedio_6m
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "Promedio Últimos 3 Meses",
                            f"{promedio_3m:.2f}%",
                            delta=f"{cambio_tendencia:+.2f}pp vs 6 meses"
                        )
                    
                    with col2:
                        # Calcular volatilidad (desviación estándar)
                        volatilidad = datos_historicos.tail(52).std()  # Último año
                        st.metric(
                            "Volatilidad (último año)",
                            f"{volatilidad:.2f}pp",
                            help="Desviación estándar de las tasas en el último año"
                        )
                
                # === COMPARACIÓN CON VALORES HISTÓRICOS ===
                st.divider()
                st.markdown("### 🔍 Posición Relativa de la Tasa Actual")
                
                # Calcular percentiles
                percentil_25 = datos_historicos.quantile(0.25)
                percentil_50 = datos_historicos.quantile(0.50)  # Mediana
                percentil_75 = datos_historicos.quantile(0.75)
                
                # Determinar en qué cuartil está la tasa actual
                if tasa_actual_display <= percentil_25:
                    posicion = "Bajo (Primer Cuartil)"
                    color_posicion = "success"
                    icono_posicion = "🟢"
                    interpretacion = "La tasa actual está en el 25% más bajo de la historia. Es una oportunidad atractiva para invertir."
                elif tasa_actual_display <= percentil_50:
                    posicion = "Medio-Bajo (Segundo Cuartil)"
                    color_posicion = "info"
                    icono_posicion = "🔵"
                    interpretacion = "La tasa actual está entre el 25% y 50% más bajo. Puede ser un buen momento para invertir."
                elif tasa_actual_display <= percentil_75:
                    posicion = "Medio-Alto (Tercer Cuartil)"
                    color_posicion = "warning"
                    icono_posicion = "🟡"
                    interpretacion = "La tasa actual está en el rango medio-alto. Considera esperar si buscas mejores condiciones."
                else:
                    posicion = "Alto (Cuarto Cuartil)"
                    color_posicion = "error"
                    icono_posicion = "🔴"
                    interpretacion = "La tasa actual está en el 25% más alto de la historia. Puede ser conveniente esperar."
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"""
                    **Posición:** {icono_posicion} {posicion}
                    
                    - **Percentil 25:** {percentil_25:.2f}%
                    - **Mediana (50):** {percentil_50:.2f}%
                    - **Percentil 75:** {percentil_75:.2f}%
                    """)
                
                with col2:
                    if color_posicion == "success":
                        st.success(f"**Interpretación:** {interpretacion}")
                    elif color_posicion == "info":
                        st.info(f"**Interpretación:** {interpretacion}")
                    elif color_posicion == "warning":
                        st.warning(f"**Interpretación:** {interpretacion}")
                    else:
                        st.error(f"**Interpretación:** {interpretacion}")
                
                # === RANGO DE DATOS DISPONIBLES ===
                st.divider()
                st.markdown("### 📅 Período de Datos Analizados")
                
                fecha_inicio = datos_historicos.index.min()
                fecha_fin = datos_historicos.index.max()
                total_semanas = len(datos_historicos)
                total_años = total_semanas / 52
                
                # Formatear fechas de manera segura
                try:
                    fecha_inicio_str = fecha_inicio.strftime('%d/%m/%Y') if isinstance(fecha_inicio, pd.Timestamp) else str(fecha_inicio)
                    fecha_fin_str = fecha_fin.strftime('%d/%m/%Y') if isinstance(fecha_fin, pd.Timestamp) else str(fecha_fin)
                except:
                    fecha_inicio_str = str(fecha_inicio)
                    fecha_fin_str = str(fecha_fin)
                
                st.info(f"""
                - **Fecha Inicio:** {fecha_inicio_str}
                - **Fecha Fin:** {fecha_fin_str}
                - **Total de Observaciones:** {total_semanas:,} semanas
                - **Período:** ~{total_años:.1f} años
                """)
        
        # === CONTEXTO ECONÓMICO ===
        st.divider()
        st.markdown("### 🌍 Contexto Económico (Últimos Valores Disponibles)")
        
        # Mostrar variables exógenas más recientes
        variables_exogenas = {
            'Tasa_Objetivo': '🏛️ Tasa Objetivo Banxico',
            'Tasa_FED': '🇺🇸 Tasa de Referencia FED',
            'Tipo_Cambio_Fix': '💱 Tipo de Cambio Fix',
            'INPC': '📊 INPC (Inflación)'
        }
        
        cols_contexto = st.columns(min(4, len([v for v in variables_exogenas.keys() if v in df_banxico.columns])))
        idx_contexto = 0
        
        for var, nombre in variables_exogenas.items():
            if var in df_banxico.columns:
                valor_actual = df_banxico[var].dropna().iloc[-1]
                if idx_contexto < len(cols_contexto):
                    with cols_contexto[idx_contexto]:
                        if var == 'Tipo_Cambio_Fix':
                            st.metric(nombre, f"${valor_actual:.2f}")
                        elif var == 'INPC':
                            st.metric(nombre, f"{valor_actual:.2f}")
                        else:
                            st.metric(nombre, f"{valor_actual:.2f}%")
                    idx_contexto += 1
    
    else:
        # Si no hay datos, mostrar solo la información del modelo
        st.markdown("""
        ### Modelo de Pronóstico
        
        Este módulo utiliza técnicas de análisis de series de tiempo para generar 
        pronósticos de las tasas de CETES.
        
        **Metodología:**
        - Análisis de tendencias históricas
        - Indicadores económicos relevantes
        - Análisis de volatilidad
        
        **Limitaciones:**
        - Los pronósticos son estimaciones basadas en datos históricos
        - No garantizan resultados futuros
        - Deben usarse solo como referencia educativa
        
        **Nota:** Para ver análisis detallados, asegúrate de tener datos de Banxico cargados.
        """)

with tab3:
    st.subheader("Datos de CETES")
    
    if df_banxico is not None and not df_banxico.empty:
        # Mostrar datos específicos del plazo seleccionado
        if not df.empty:
            st.markdown(f"### Datos de CETES {plazo_cetes}")
            st.dataframe(
                df.tail(50),
                use_container_width=True,
                height=300
            )
            
            # Opción de descarga del plazo específico
            csv_plazo = df.to_csv(index=False)
            st.download_button(
                label=f"📥 Descargar datos de {plazo_cetes} como CSV",
                data=csv_plazo,
                file_name=f"cetes_{plazo_cetes.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    else:
        st.warning("⚠️ No hay datos disponibles para mostrar.")
        if not df.empty:
            st.dataframe(
                df.tail(50),
                use_container_width=True,
                height=400
            )
            
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar datos como CSV",
                data=csv,
                file_name=f"cetes_{plazo_cetes.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )