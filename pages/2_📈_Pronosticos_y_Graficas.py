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

# NO generar pronósticos aquí - deben estar en session_state desde main.py
# Si no están, mostrar mensaje y no generar para evitar cálculos duplicados
if "pronosticos_generados" not in st.session_state:
    st.warning("⚠️ Los pronósticos no están disponibles. Por favor, primero visita la página principal para que se generen los pronósticos.")
    st.info("💡 Esto asegura que los cálculos solo se hagan una vez y la aplicación sea más rápida.")
    st.stop()

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

# Cargar datos de Banxico - usar session_state para evitar recargas
if "df_banxico" not in st.session_state:
    with st.spinner("📥 Cargando datos de Banxico..."):
        df_banxico = obtener_datos_banxico()
        if df_banxico is not None and not df_banxico.empty:
            st.session_state.df_banxico = df_banxico
        else:
            st.session_state.df_banxico = None
else:
    df_banxico = st.session_state.df_banxico

# Sección principal de contenido
tab1, tab2, tab3 = st.tabs(["📊 Gráficas y Pronósticos", "📉 Estadisticas", "📋 Datos"])

with tab1:
    st.subheader("Gráficas de CETES")
    
    if df_banxico is None or df_banxico.empty:
        st.error("❌ No se pudieron cargar los datos de Banxico. Verifica que la variable de entorno 'BANXICO_API_KEY' o 'BANXICO_API' esté configurada correctamente.")
        st.info("💡 **Instrucciones**: \n"
                "1. Crea un archivo `.env` en la raíz del proyecto\n"
                "2. Agrega tu clave de API: `BANXICO_API_KEY=tu_clave_aqui`\n"
                "3. Obtén tu clave en: https://www.banxico.org.mx/SieAPIRest/service/v1/")
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
        
        # Usar pronósticos pre-generados desde session_state (sin recalcular)
        pronosticos_dict = st.session_state.get('pronosticos_generados', None)
        variable_objetivo = mapeo_plazos[plazo_cetes]
        
        if not pronosticos_dict or variable_objetivo not in pronosticos_dict:
            st.warning("⚠️ Los pronósticos no están disponibles. Por favor, recarga la aplicación desde la página principal.")
            st.stop()
        
        # Usar pronóstico pre-generado (sin cálculos adicionales)
        pronostico_data = pronosticos_dict[variable_objetivo]
        pronostico_series = pronostico_data['pronostico_series']
        fechas_pronostico = pronostico_data['fechas_pronostico']
        limite_inferior_series = pronostico_data.get('limite_inferior_series')
        limite_superior_series = pronostico_data.get('limite_superior_series')
        tiene_intervalo = pronostico_data.get('tiene_intervalo', False)
        
        # Truncar series si el usuario solicita menos semanas (solo visualización)
        if len(pronostico_series) > semanas_pronostico:
            pronostico_series = pronostico_series.iloc[:semanas_pronostico]
            fechas_pronostico = fechas_pronostico[:semanas_pronostico]
            if limite_inferior_series is not None and limite_superior_series is not None:
                limite_inferior_series = limite_inferior_series.iloc[:semanas_pronostico]
                limite_superior_series = limite_superior_series.iloc[:semanas_pronostico]
        
        # Crear gráfica (sin cálculos, solo visualización)
        fig = go.Figure()
        
        # Línea histórica
        fig.add_trace(go.Scatter(
            x=df['Fecha'],
            y=df['Tasa'],
            mode='lines',
            name='Histórico',
            line=dict(color='blue', width=2)
        ))
        
        # Graficar intervalos de confianza PRIMERO si están disponibles (para que el área sombreada funcione)
        if tiene_intervalo and limite_inferior_series is not None and limite_superior_series is not None:
            # Obtener valores como arrays
            try:
                if hasattr(limite_superior_series, 'values'):
                    valores_superior = limite_superior_series.values
                elif isinstance(limite_superior_series, pd.Series):
                    valores_superior = limite_superior_series.to_numpy()
                else:
                    valores_superior = np.array(limite_superior_series)
                
                if hasattr(limite_inferior_series, 'values'):
                    valores_inferior = limite_inferior_series.values
                elif isinstance(limite_inferior_series, pd.Series):
                    valores_inferior = limite_inferior_series.to_numpy()
                else:
                    valores_inferior = np.array(limite_inferior_series)
                
                # Verificar que tenemos datos válidos y que coinciden con las fechas
                if len(valores_superior) > 0 and len(valores_inferior) > 0:
                    # Asegurar que tienen la misma longitud que fechas_pronostico
                    if len(valores_superior) == len(fechas_pronostico) and len(valores_inferior) == len(fechas_pronostico):
                        # Límite superior (sin relleno, se agregará primero)
                        fig.add_trace(go.Scatter(
                            x=fechas_pronostico,
                            y=valores_superior,
                            mode='lines',
                            name='Límite Superior (95%)',
                            line=dict(color='rgba(255,0,0,0.3)', width=1.5, dash='dot'),
                            showlegend=True,
                            legendgroup="intervalo",
                            hovertemplate='Límite Superior: %{y:.2f}%<extra></extra>'
                        ))
                        
                        # Límite inferior CON área sombreada hacia el superior
                        fig.add_trace(go.Scatter(
                            x=fechas_pronostico,
                            y=valores_inferior,
                            mode='lines',
                            name='Límite Inferior (95%)',
                            line=dict(color='rgba(255,0,0,0.3)', width=1.5, dash='dot'),
                            fill='tonexty',  # Rellenar hacia la traza anterior (superior)
                            fillcolor='rgba(255,0,0,0.15)',
                            showlegend=True,
                            legendgroup="intervalo",
                            hovertemplate='Límite Inferior: %{y:.2f}%<extra></extra>'
                        ))
            except Exception as e:
                st.warning(f"⚠️ No se pudieron graficar los intervalos de confianza: {e}")
        
        # Pronóstico (se agrega después para que esté visible sobre el área sombreada)
        fig.add_trace(go.Scatter(
            x=fechas_pronostico,
            y=pronostico_series.values,
            mode='lines',
            name='Pronóstico',
            line=dict(color='red', dash='dash', width=2.5)
        ))
        
        fig.update_layout(
            title=f'Pronóstico de CETES {plazo_cetes} ({semanas_pronostico} semanas)',
            xaxis_title="Fecha",
            yaxis_title="Tasa de Interés (%)",
            hovermode='x unified',
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Métricas del pronóstico (usar datos pre-calculados del diccionario)
        tasa_actual = pronostico_data['tasa_actual']
        tasa_pronostico_inicial = pronostico_data['tasa_pronostico_inicial']
        tasa_pronostico_final = pronostico_data['tasa_pronostico_final']
        cambio_inicial = pronostico_data['cambio_inicial']
        cambio_final = pronostico_data['cambio_final']
        
        # Si se truncó el pronóstico, ajustar la tasa final
        if len(pronostico_series) < len(pronostico_data['pronostico_series']):
            tasa_pronostico_final = pronostico_series.iloc[-1]
            cambio_final = tasa_pronostico_final - tasa_actual
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tasa Actual", f"{tasa_actual:.2f}%")
        with col2:
            st.metric("Primer Pronóstico", f"{tasa_pronostico_inicial:.2f}%", f"{cambio_inicial:+.2f}pp")
        with col3:
            st.metric("Pronóstico Final", f"{tasa_pronostico_final:.2f}%", f"{cambio_final:+.2f}pp")
        
        # Recomendación de inversión (usar datos pre-calculados)
        st.divider()
        st.subheader("💡 Recomendación de Inversión")
        
        CAUTIOUS_THRESHOLD = 0.2  # Umbral para considerar cambios significativos
        
        if cambio_inicial > CAUTIOUS_THRESHOLD:
            recommendation = "🤔 ESPERAR"
            explanation = f"Se predice un alza significativa en la próxima subasta (> {CAUTIOUS_THRESHOLD:.2f}pp). Esperar podría darte un mayor rendimiento."
            st.warning(f"**{recommendation}**\n\n{explanation}")
        elif cambio_inicial < -CAUTIOUS_THRESHOLD:
            recommendation = "✅ ¡INVERTIR AHORA!"
            explanation = f"La tasa actual es atractiva. Nuestro modelo predice que podría bajar pronto (< -{CAUTIOUS_THRESHOLD:.2f}pp), ¡asegura este rendimiento!"
            st.success(f"**{recommendation}**\n\n{explanation}")
        else:
            recommendation = "⚖️ INVERTIR (ESTABLE)"
            explanation = "El cambio previsto es mínimo. Invierte ahora para evitar que tu capital pierda tiempo en efectivo."
            st.info(f"**{recommendation}**\n\n{explanation}")
        
        # Mostrar detalles adicionales
        with st.expander("📊 Detalles del Análisis"):
            st.markdown(f"""
            - **Tasa Actual**: {tasa_actual:.2f}%
            - **Primer Pronóstico** (próxima subasta): {tasa_pronostico_inicial:.2f}%
            - **Cambio Esperado**: {cambio_inicial:+.2f} puntos porcentuales
            - **Umbral de Decisión**: ±{CAUTIOUS_THRESHOLD:.2f} puntos porcentuales
            - **Recomendación**: {recommendation}
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
            st.error("❌ No se pudieron cargar los datos de Banxico. Verifica que la variable de entorno 'BANXICO_API_KEY' o 'BANXICO_API' esté configurada correctamente.")
            st.info("�� **Instrucciones**: \n"
                    "1. Crea un archivo `.env` en la raíz del proyecto\n"
                    "2. Agrega tu clave de API: `BANXICO_API_KEY=tu_clave_aqui`\n"
                    "3. Obtén tu clave en: https://www.banxico.org.mx/SieAPIRest/service/v1/")

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


