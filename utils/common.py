import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import base64
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
warnings.filterwarnings('ignore')

# Carga de variables de entorno
load_dotenv(override=True)  # Para desarrollo local

# Claves API - Priorizar secrets de Streamlit Cloud, luego variables de entorno
def get_secret_or_env(key: str) -> str | None:
    """Obtiene un secret de Streamlit Cloud o variable de entorno como fallback"""
    try:
        import streamlit as st
        # Intentar acceder a st.secrets (disponible en Streamlit Cloud)
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except (AttributeError, FileNotFoundError, TypeError, KeyError):
        pass
    # Fallback a variable de entorno
    return os.getenv(key)

OPENAI_API_KEY = get_secret_or_env("OPENAI_API_KEY")
DEEPSEEK_API_KEY = get_secret_or_env("DEEPSEEK_API_KEY")
BANXICO_API_KEY = get_secret_or_env("BANXICO_API_KEY")

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
# BANXICO_API se eliminó porque no se usa

# Inicializar clientes
client_openai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
client_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL) if DEEPSEEK_API_KEY else None
# client_banxico se eliminó porque no se usa


model_deepseek = "deepseek-chat"

def get_image_path(filename):
    """Obtiene la ruta de una imagen local"""
    image_dir = Path("images")
    if image_dir.exists():
        image_path = image_dir / filename
        if image_path.exists():
            return str(image_path)
    return None

def audio_player_with_speed(audio_bytes, playback_speed=1.25):
    """Crea un reproductor de audio con velocidad de reproducción personalizada"""
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    audio_html = f"""
    <audio controls id="audioPlayer" style="width: 100%;">
        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
    </audio>
    <script>
        var audio = document.getElementById('audioPlayer');
        audio.playbackRate = {playback_speed};
        audio.addEventListener('loadedmetadata', function() {{
            audio.playbackRate = {playback_speed};
        }});
    </script>
    """
    return audio_html

def descarga_bmx_series(series_dict, fechainicio, fechafin):
    """
    Descarga series de datos económicos del API de Banxico.
    Args:
        series_dict (dict): Diccionario con el ID de la serie como clave 
                            y el nombre deseado de la columna como valor.
        fechainicio (str): Fecha de inicio de la descarga (YYYY-MM-DD).
        fechafin (str): Fecha de fin de la descarga (YYYY-MM-DD).
    Returns:
        pd.DataFrame or None: DataFrame con todas las series concatenadas,
                              o None si no se descargaron datos.
    """
    # Usar BANXICO_API_KEY
    token = BANXICO_API_KEY
    
    if not token:
        print("Error: La variable de entorno 'BANXICO_API_KEY' no está configurada.")
        return None
        
    headers = {'Bmx-Token': token}
    all_data = []
    for serie, nombre in series_dict.items():
        # Construye la URL para la consulta API
        url = f'https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos/{fechainicio}/{fechafin}/'
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f'Error en la consulta para la serie **{nombre}** ({serie}), código **{response.status_code}**')
                continue
            raw_data = response.json()
            # Verifica la estructura del JSON y si contiene datos
            if 'bmx' in raw_data and 'series' in raw_data['bmx'] and len(raw_data['bmx']['series']) > 0:
                serie_data = raw_data['bmx']['series'][0]
                if 'datos' in serie_data and len(serie_data['datos']) > 0:
                    data = serie_data['datos']
                    df = pd.DataFrame(data)
                    
                    # Procesa y limpia los datos
                    df['dato'] = df['dato'].replace('N/E', np.nan).astype(float)
                    # La fecha de Banxico a menudo tiene formato 'DD/MM/YYYY'
                    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce') 
                    
                    # Elimina filas con fecha no válida antes de establecer el índice
                    df.dropna(subset=['fecha'], inplace=True)
                    
                    df.set_index('fecha', inplace=True)
                    df.rename(columns={'dato': nombre}, inplace=True)
                    
                    # Solo mantiene la columna con el nombre de la serie
                    all_data.append(df[[nombre]]) 
                else:
                    print(f"No se encontraron datos en el campo 'datos' para la serie **{nombre}** ({serie})")
            else:
                print(f"Estructura inesperada o datos faltantes para la serie **{nombre}** ({serie})")
                
        except requests.exceptions.RequestException as e:
            print(f"Error de conexión o petición para la serie **{nombre}** ({serie}): {e}")
            continue
    # Concatena todos los DataFrames
    if all_data:
        # Usa join='outer' para asegurar que todas las fechas estén presentes
        df_final = pd.concat(all_data, axis=1, join='outer') 
        return df_final
    else:
        print("No se descargaron datos.")
        return None

def obtener_datos_banxico(fechainicio='2006-01-01', fechafin=None):
    """
    Obtiene y procesa datos de Banxico para CETES y otras series económicas.
    Args:
        fechainicio (str): Fecha de inicio (YYYY-MM-DD). Por defecto '2006-01-01'.
        fechafin (str): Fecha de fin (YYYY-MM-DD). Si es None, usa la fecha actual.
    Returns:
        pd.DataFrame or None: DataFrame procesado con datos semanales, o None si hay error.
    """
    if fechafin is None:
        fechafin = datetime.now().strftime('%Y-%m-%d')
    
    # Definición de las series de Banxico a descargar
    series = {
        'SF43936': 'CETE_28D',
        'SF43939': 'CETE_91D',
        'SF43942': 'CETE_182D',
        'SF43945': 'CETE_364D',
        'SF61745': 'Tasa_Objetivo',
        'SI237': 'Tasa_FED',
        'SF43718': 'Tipo_Cambio_Fix',
        'SP1': 'INPC'
    }
    
    df_final = descarga_bmx_series(series, fechainicio, fechafin)
    
    if df_final is None:
        return None
    
    # Ordena el índice por fecha
    df_final.sort_index(inplace=True)
    
    # Relleno de Datos Faltantes (ffill)
    columns_to_ffill = ['CETE_28D','CETE_91D','CETE_182D','CETE_364D', 'Tasa_Objetivo', 'INPC', 'Tasa_FED', 'Tipo_Cambio_Fix']
    for col in columns_to_ffill:
        if col in df_final.columns:
            df_final[col] = df_final[col].ffill()
    
    # Creación del DataFrame Maestro con Frecuencia Semanal
    if 'CETE_28D' in df_final.columns:
        cetes_28d_series = df_final['CETE_28D'].dropna()
        
        if not cetes_28d_series.empty:
            # Crea un índice semanal (jueves) desde la primera hasta la última fecha de CETE_28D
            idx = pd.date_range(start=cetes_28d_series.index.min(), 
                                end=cetes_28d_series.index.max(), 
                                freq='W-THU')
            
            df_master = pd.DataFrame(index=idx)
            
            # Combina el índice semanal con los datos descargados
            df = pd.merge(df_master, df_final, left_index=True, right_index=True, how='left')
            
            # Asegura que las columnas rellenadas anteriormente se mantengan rellenadas
            for col in columns_to_ffill:
                if col in df.columns:
                    df[col] = df[col].ffill()
            
            return df
        else:
            print("No hay datos válidos en la serie 'CETE_28D' para crear el índice semanal.")
            return None
    else:
        print("La serie 'CETE_28D' no se descargó correctamente para crear el índice semanal.")
        return None

def pronostico_sarimax(df, variable_objetivo, exog_cols, periodos_pronostico=30, 
                       order=(1, 1, 1), seasonal_order=(1, 1, 1, 52)):
    """
    Genera pronósticos usando el modelo SARIMAX con variables exógenas.
    
    Args:
        df (pd.DataFrame): DataFrame con datos históricos (índice debe ser fecha)
        variable_objetivo (str): Nombre de la columna a predecir (debe estar en cetes_cols)
        exog_cols (list): Lista de columnas exógenas (variables predictoras)
        periodos_pronostico (int): Número de períodos a pronosticar
        order (tuple): Parámetros (p, d, q) del modelo ARIMA. Default: (1, 1, 1)
        seasonal_order (tuple): Parámetros estacionales (P, D, Q, s). Default: (1, 1, 1, 52) para datos semanales
    
    Returns:
        tuple: (pronostico, fechas_pronostico, modelo_ajustado)
            - pronostico: Serie con los valores pronosticados
            - fechas_pronostico: Índice de fechas para el pronóstico
            - modelo_ajustado: Modelo SARIMAX ajustado
    """
    try:
        # Preparar datos
        df_work = df.copy()
        
        # Verificar que la variable objetivo existe
        if variable_objetivo not in df_work.columns:
            raise ValueError(f"La variable objetivo '{variable_objetivo}' no existe en el DataFrame")
        
        # Filtrar datos válidos (sin NaN en la variable objetivo)
        df_work = df_work.dropna(subset=[variable_objetivo])
        
        if len(df_work) < 52:  # Necesitamos al menos un año de datos semanales
            raise ValueError(f"Se necesitan al menos 52 observaciones. Solo hay {len(df_work)}")
        
        # Separar variable endógena y exógenas
        y = df_work[variable_objetivo]
        
        # Preparar variables exógenas (solo las que existen y tienen datos)
        exog_train = None
        exog_cols_validas = []
        
        for col in exog_cols:
            if col in df_work.columns and col != variable_objetivo:
                # Rellenar NaN con forward fill
                exog_series = df_work[col].ffill().bfill()
                if not exog_series.isna().all():
                    exog_cols_validas.append(col)
        
        # Crear DataFrame de exógenas si hay variables disponibles
        if exog_cols_validas:
            exog_train = df_work[exog_cols_validas].copy()
            # Asegurar que tenga el mismo índice que y y rellenar NaN
            exog_train = exog_train.reindex(y.index)
            exog_train = exog_train.ffill().bfill()
        
        # Ajustar modelo SARIMAX
        if exog_train is not None and not exog_train.empty:
            modelo = SARIMAX(
                y,
                exog=exog_train,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False
            )
        else:
            # Si no hay exógenas, usar SARIMA simple
            modelo = SARIMAX(
                y,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False
            )
        
        modelo_ajustado = modelo.fit(disp=False, maxiter=50)
        
        # Generar pronóstico
        fecha_fin = y.index[-1]
        
        # Crear fechas futuras (asumiendo frecuencia semanal)
        if isinstance(y.index, pd.DatetimeIndex):
            freq = pd.infer_freq(y.index)
            if freq is None:
                # Si no se puede inferir, usar frecuencia semanal por defecto
                freq = 'W-THU'
        else:
            freq = 'W-THU'
        
        fechas_pronostico = pd.date_range(
            start=fecha_fin + timedelta(weeks=1),
            periods=periodos_pronostico,
            freq=freq
        )
        
        # Preparar exógenas para el pronóstico
        # Para el pronóstico, usamos el último valor conocido de cada variable exógena
        # En producción, podrías usar pronósticos de las variables exógenas también
        if exog_train is not None and not exog_train.empty:
            # Usar el último valor de cada variable exógena para todo el horizonte de pronóstico
            exog_forecast = pd.DataFrame(
                index=fechas_pronostico,
                columns=exog_train.columns
            )
            for col in exog_train.columns:
                # Usar el último valor conocido
                exog_forecast[col] = exog_train[col].iloc[-1]
            
            pronostico = modelo_ajustado.forecast(steps=periodos_pronostico, exog=exog_forecast)
        else:
            pronostico = modelo_ajustado.forecast(steps=periodos_pronostico)
        
        # Crear serie con índice de fechas
        pronostico_series = pd.Series(pronostico, index=fechas_pronostico)
        
        return pronostico_series, fechas_pronostico, modelo_ajustado
        
    except Exception as e:
        raise Exception(f"Error al generar pronóstico SARIMAX: {str(e)}")

def obtener_pronostico_cached(df, variable_objetivo, exog_cols, periodos_pronostico=4):
    """
    Genera un pronóstico SARIMAX con cache para evitar recalcular el modelo.
    Esta función está diseñada para ser usada con @st.cache_data en Streamlit.
    
    Args:
        df (pd.DataFrame): DataFrame con datos históricos de Banxico
        variable_objetivo (str): Nombre de la columna a predecir (ej: 'CETE_91D')
        exog_cols (list): Lista de columnas exógenas
        periodos_pronostico (int): Número de períodos a pronosticar
    
    Returns:
        tuple: (pronostico_series, fechas_pronostico, modelo_ajustado) o None si hay error
    """
    try:
        if df is None or df.empty:
            return None
        
        if variable_objetivo not in df.columns:
            return None
        
        datos_historicos = df[variable_objetivo].dropna()
        if len(datos_historicos) < 52:
            return None
        
        # Generar pronóstico
        pronostico_series, fechas_pronostico, modelo_ajustado = pronostico_sarimax(
            df=df,
            variable_objetivo=variable_objetivo,
            exog_cols=exog_cols,
            periodos_pronostico=periodos_pronostico
        )
        
        return pronostico_series, fechas_pronostico, modelo_ajustado
    except Exception as e:
        return None

def generar_todos_los_pronosticos(df, periodos_pronostico=4):
    """
    Genera pronósticos para todos los plazos de CETES y retorna un diccionario estructurado.
    
    Args:
        df (pd.DataFrame): DataFrame con datos históricos de Banxico
        periodos_pronostico (int): Número de semanas a pronosticar. Default: 4
    
    Returns:
        dict: Diccionario con pronósticos para cada plazo, o None si hay error
        Estructura: {
            'CETE_28D': {
                'pronostico_series': pd.Series,
                'fechas_pronostico': pd.DatetimeIndex,
                'modelo_ajustado': modelo,
                'tasa_actual': float,
                'tasa_pronostico_inicial': float,
                'tasa_pronostico_final': float,
                'cambio_inicial': float,
                'cambio_final': float,
                'limite_inferior': float,
                'limite_superior': float,
                'tiene_intervalo': bool
            },
            ...
        }
    """
    if df is None or df.empty:
        return None
    
    try:
        # Definir plazos y sus columnas
        plazos_info = {
            "28 días": "CETE_28D",
            "91 días": "CETE_91D",
            "182 días": "CETE_182D",
            "364 días": "CETE_364D"
        }
        
        # Variables exógenas
        exog_cols = [c for c in df.columns if 'CETE' not in c]
        
        pronosticos_dict = {}
        
        for plazo_nombre, columna in plazos_info.items():
            if columna not in df.columns:
                continue
            
            try:
                # Obtener datos históricos del plazo
                datos_historicos = df[columna].dropna()
                if len(datos_historicos) < 52:
                    continue
                
                # Generar pronóstico
                pronostico_series, fechas_pronostico, modelo_ajustado = pronostico_sarimax(
                    df=df,
                    variable_objetivo=columna,
                    exog_cols=exog_cols,
                    periodos_pronostico=periodos_pronostico
                )
                
                # Calcular métricas
                tasa_actual = datos_historicos.iloc[-1]
                tasa_pronostico_inicial = pronostico_series.iloc[0]
                tasa_pronostico_final = pronostico_series.iloc[-1]
                cambio_inicial = tasa_pronostico_inicial - tasa_actual
                cambio_final = tasa_pronostico_final - tasa_actual
                
                # Obtener intervalo de confianza si es posible
                try:
                    if exog_cols:
                        exog_forecast_df = pd.DataFrame(
                            index=fechas_pronostico,
                            columns=exog_cols
                        )
                        for col in exog_cols:
                            if col in df.columns:
                                exog_forecast_df[col] = df[col].ffill().iloc[-1]
                        forecast_obj = modelo_ajustado.get_forecast(
                            steps=periodos_pronostico,
                            exog=exog_forecast_df
                        )
                    else:
                        forecast_obj = modelo_ajustado.get_forecast(steps=periodos_pronostico)
                    
                    pronostico_ci = forecast_obj.conf_int()
                    limite_inferior = pronostico_ci.iloc[0, 0]
                    limite_superior = pronostico_ci.iloc[0, 1]
                    tiene_intervalo = True
                except:
                    tiene_intervalo = False
                    limite_inferior = None
                    limite_superior = None
                
                # Guardar en diccionario
                pronosticos_dict[columna] = {
                    'plazo_nombre': plazo_nombre,
                    'pronostico_series': pronostico_series,
                    'fechas_pronostico': fechas_pronostico,
                    'modelo_ajustado': modelo_ajustado,
                    'tasa_actual': tasa_actual,
                    'tasa_pronostico_inicial': tasa_pronostico_inicial,
                    'tasa_pronostico_final': tasa_pronostico_final,
                    'cambio_inicial': cambio_inicial,
                    'cambio_final': cambio_final,
                    'limite_inferior': limite_inferior,
                    'limite_superior': limite_superior,
                    'tiene_intervalo': tiene_intervalo,
                    'datos_historicos': datos_historicos
                }
                
            except Exception as e:
                # Si falla un plazo, continuar con los demás
                continue
        
        return pronosticos_dict if pronosticos_dict else None
        
    except Exception as e:
        return None

def obtener_resumen_pronosticos_sarimax(df=None, periodos_pronostico=4, pronosticos_dict=None):
    """
    Genera un resumen formateado de los pronósticos SARIMAX.
    Puede usar un diccionario de pronósticos pre-generados o generar nuevos desde un DataFrame.
    
    Args:
        df (pd.DataFrame, optional): DataFrame con datos históricos de Banxico
        periodos_pronostico (int): Número de semanas a pronosticar. Default: 4
        pronosticos_dict (dict, optional): Diccionario de pronósticos pre-generados
    
    Returns:
        str: Resumen formateado de los pronósticos para todos los plazos, o None si hay error
    """
    # Si se proporciona un diccionario de pronósticos, usarlo directamente
    if pronosticos_dict is not None:
        pronosticos_data = pronosticos_dict
    elif df is not None and not df.empty:
        # Generar pronósticos si no se proporcionan
        pronosticos_data = generar_todos_los_pronosticos(df, periodos_pronostico)
        if pronosticos_data is None:
            return None
    else:
        return None
    
    try:
        resumen_lineas = []
        resumen_lineas.append("=" * 60)
        resumen_lineas.append("📊 PRONÓSTICOS SARIMAX - DATOS ACTUALIZADOS")
        resumen_lineas.append("=" * 60)
        resumen_lineas.append("")
        
        pronosticos_para_comparacion = {}
        
        for columna, datos in pronosticos_data.items():
            plazo_nombre = datos['plazo_nombre']
            tasa_actual = datos['tasa_actual']
            tasa_pronostico_inicial = datos['tasa_pronostico_inicial']
            tasa_pronostico_final = datos['tasa_pronostico_final']
            cambio_inicial = datos['cambio_inicial']
            cambio_final = datos['cambio_final']
            tiene_intervalo = datos['tiene_intervalo']
            limite_inferior = datos['limite_inferior']
            limite_superior = datos['limite_superior']
            
            # Determinar el número real de semanas disponibles en el pronóstico
            semanas_reales = periodos_pronostico
            if 'pronostico_series' in datos:
                semanas_reales = len(datos['pronostico_series'])
            
            # Formatear información del plazo
            resumen_lineas.append(f"📈 CETES {plazo_nombre.upper()}:")
            resumen_lineas.append(f"   • Tasa Actual: {tasa_actual:.2f}%")
            resumen_lineas.append(f"   • Pronóstico Próxima Subasta: {tasa_pronostico_inicial:.2f}% (cambio: {cambio_inicial:+.2f}pp)")
            resumen_lineas.append(f"   • Pronóstico Final ({semanas_reales} semanas): {tasa_pronostico_final:.2f}% (cambio: {cambio_final:+.2f}pp)")
            
            # Agregar información de pronósticos intermedios si hay más de 4 semanas
            if semanas_reales > 4 and 'pronostico_series' in datos:
                # Mostrar pronóstico a la mitad del período
                mitad_semanas = semanas_reales // 2
                if mitad_semanas > 0 and mitad_semanas < len(datos['pronostico_series']):
                    tasa_mitad = datos['pronostico_series'].iloc[mitad_semanas - 1]
                    cambio_mitad = tasa_mitad - tasa_actual
                    resumen_lineas.append(f"   • Pronóstico Intermedio ({mitad_semanas} semanas): {tasa_mitad:.2f}% (cambio: {cambio_mitad:+.2f}pp)")
            
            if tiene_intervalo:
                resumen_lineas.append(f"   • Intervalo de Confianza 95%: [{limite_inferior:.2f}%, {limite_superior:.2f}%]")
            
            # Recomendación básica
            if cambio_inicial > 0.2:
                recomendacion = "ESPERAR (se predice alza)"
            elif cambio_inicial < -0.2:
                recomendacion = "INVERTIR AHORA (se predice baja)"
            else:
                recomendacion = "INVERTIR (estable)"
            
            resumen_lineas.append(f"   • Recomendación: {recomendacion}")
            resumen_lineas.append("")
            
            # Guardar para comparación
            pronosticos_para_comparacion[plazo_nombre] = {
                'cambio_inicial': cambio_inicial
            }
        
        # Agregar resumen comparativo
        if pronosticos_para_comparacion:
            resumen_lineas.append("-" * 60)
            resumen_lineas.append("📊 RESUMEN COMPARATIVO:")
            resumen_lineas.append("")
            
            # Encontrar mejor y peor pronóstico
            mejor_cambio = max(pronosticos_para_comparacion.items(), key=lambda x: x[1]['cambio_inicial'])
            peor_cambio = min(pronosticos_para_comparacion.items(), key=lambda x: x[1]['cambio_inicial'])
            
            resumen_lineas.append(f"   • Mejor Pronóstico (mayor alza esperada): CETES {mejor_cambio[0]} (+{mejor_cambio[1]['cambio_inicial']:.2f}pp)")
            resumen_lineas.append(f"   • Peor Pronóstico (mayor baja esperada): CETES {peor_cambio[0]} ({peor_cambio[1]['cambio_inicial']:+.2f}pp)")
            resumen_lineas.append("")
            
            # Fecha de última actualización
            fecha_actualizacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            resumen_lineas.append(f"📅 Última actualización: {fecha_actualizacion}")
            resumen_lineas.append("=" * 60)
        
        return "\n".join(resumen_lineas) if resumen_lineas else None
        
    except Exception as e:
        return f"Error al generar resumen de pronósticos: {str(e)}"