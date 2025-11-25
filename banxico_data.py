import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
warnings.filterwarnings('ignore')
from dotenv import load_dotenv

load_dotenv()

def descarga_bmx_series(series_dict, fechainicio, fechafin, token):
    headers = {'Bmx-Token': token} if token else {}
    all_data = []
    
    for serie, nombre in series_dict.items():
        url = f'https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos/{fechainicio}/{fechafin}/'
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                continue
            
            if not response.text or response.text.strip() == '':
                continue
            
            try:
                raw_data = response.json()
            except (ValueError, json.JSONDecodeError):
                continue
            
            if 'bmx' in raw_data and 'series' in raw_data['bmx'] and len(raw_data['bmx']['series']) > 0:
                serie_data = raw_data['bmx']['series'][0]
                if 'datos' in serie_data and len(serie_data['datos']) > 0:
                    data = serie_data['datos']
                    df = pd.DataFrame(data)
                    
                    # Procesa y limpia los datos
                    df['dato'] = df['dato'].replace('N/E', np.nan).astype(float)
                    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
                    df.dropna(subset=['fecha'], inplace=True)
                    df.set_index('fecha', inplace=True)
                    df.rename(columns={'dato': nombre}, inplace=True)
                    all_data.append(df[[nombre]])
        except requests.exceptions.RequestException:
            continue
    
    if all_data:
        return pd.concat(all_data, axis=1, join='outer')
    return None


def obtener_datos_banxico(fecha_inicio=None, fecha_fin=None, incluir_exogenas=True):
    token_banxico = os.getenv('BANXICO_API_KEY', '')
    if not token_banxico or token_banxico.strip() == '':
        raise ValueError("BANXICO_API_KEY no está configurada. Configura tu token en el archivo .env")
    
    try:
        if fecha_fin is None:
            fecha_fin = datetime.now().strftime('%Y-%m-%d')
        if fecha_inicio is None:
            fecha_inicio = '2006-01-01'
        
        series_banxico_dict = {
            'SF43936': 'CETE_28D',
            'SF43939': 'CETE_91D',
            'SF43942': 'CETE_182D',
            'SF43945': 'CETE_364D',
        }
        
        if incluir_exogenas:
            series_banxico_dict.update({
                'SF61745': 'Tasa_Objetivo',
                'SI237': 'Tasa_FED',
                'SF43718': 'Tipo_Cambio_Fix',
                'SP1': 'INPC'
            })
        
        df_final_raw = descarga_bmx_series(series_banxico_dict, fecha_inicio, fecha_fin, token_banxico)
        
        if df_final_raw is None or len(df_final_raw) == 0:
            raise ValueError("No se pudieron descargar datos de Banxico. Verifica tu token y conexión")
        
        columns_to_ffill = list(series_banxico_dict.values())
        df_final_raw.sort_index(inplace=True)
        for col in columns_to_ffill:
            if col in df_final_raw.columns:
                df_final_raw[col] = df_final_raw[col].ffill()
        
        cetes_28d_series = df_final_raw['CETE_28D'].dropna()
        if len(cetes_28d_series) == 0:
            raise ValueError("No se encontraron datos de CETE_28D")
        
        idx_weekly = pd.date_range(
            start=cetes_28d_series.index.min(),
            end=cetes_28d_series.index.max(),
            freq='W-THU'
        )
        
        df_master_weekly = pd.DataFrame(index=idx_weekly)
        temp_df_processed = pd.merge(
            df_master_weekly, 
            df_final_raw, 
            left_index=True, 
            right_index=True, 
            how='left'
        )
        
        for col in columns_to_ffill:
            if col in temp_df_processed.columns:
                temp_df_processed[col] = temp_df_processed[col].ffill()
        
        df_banxico_processed = temp_df_processed.dropna()
        
        if len(df_banxico_processed) == 0:
            raise ValueError("No hay datos válidos después del procesamiento")
        
        return df_banxico_processed
            
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Error al obtener datos de Banxico: {str(e)}")

def generar_datos_ejemplo():
    """
    Genera datos de ejemplo (DEPRECADO - No se usa automáticamente)
    
    NOTA: Esta función ya no se llama automáticamente. La API de Banxico es obligatoria.
    Se mantiene solo para referencia o pruebas manuales.
    """
    fecha_inicio = datetime.now() - timedelta(days=730)
    fechas = pd.date_range(start=fecha_inicio, end=datetime.now(), freq='W-THU')
    
    # Simular datos de CETES con tendencia y estacionalidad
    np.random.seed(42)
    base_tasa = 11.0
    tendencia = np.linspace(0, 0.5, len(fechas))
    estacionalidad = 0.3 * np.sin(2 * np.pi * np.arange(len(fechas)) / 52)
    ruido = np.random.normal(0, 0.1, len(fechas))
    
    valores = base_tasa + tendencia + estacionalidad + ruido
    
    df = pd.DataFrame({
        "CETE_28D": valores,
        "CETE_91D": valores * 1.15,
        "CETE_182D": valores * 1.25,
        "CETE_364D": valores * 1.35,
        "Tasa_Objetivo": valores * 0.95,
        "Tasa_FED": valores * 0.8,
        "Tipo_Cambio_Fix": 17.0 + np.random.normal(0, 0.5, len(fechas)),
        "INPC": 100 + np.cumsum(np.random.normal(0.1, 0.05, len(fechas)))
    }, index=fechas)
    
    return df

def generar_pronostico_sarimax(df, serie_pronosticar='CETE_28D', semanas_pronostico=4, 
                                orden=(1, 1, 1), orden_estacional=(1, 1, 1, 52),
                                usar_exogenas=True):
    """
    Genera pronóstico usando modelo SARIMAX con variables exógenas
    
    Args:
        df: DataFrame con datos históricos (debe incluir CETES y variables exógenas)
        serie_pronosticar: Nombre de la serie a pronosticar ('CETE_28D', 'CETE_91D', etc.)
        semanas_pronostico: Número de semanas a pronosticar
        orden: Orden del modelo ARIMA (p, d, q)
        orden_estacional: Orden estacional (P, D, Q, s) - s=52 para datos semanales
        usar_exogenas: Si True, usa variables exógenas en el modelo
    
    Returns:
        DataFrame con pronósticos, diccionario con estadísticas del modelo, modelo ajustado
    """
    try:
        if df is None or len(df) == 0:
            return None, None, None
        
        if serie_pronosticar not in df.columns:
            return None, None, None
        
        y = df[serie_pronosticar].dropna()
        exog = None
        exog_future = None
        exog_vars = []
        
        if usar_exogenas:
            variables_exogenas = ['Tasa_Objetivo', 'INPC', 'Tasa_FED', 'Tipo_Cambio_Fix']
            exog_vars = [var for var in variables_exogenas if var in df.columns]
            
            if exog_vars:
                exog = df[exog_vars].loc[y.index].ffill().bfill()
                ultimos_valores = df[exog_vars].iloc[-1:]
                exog_future = pd.concat([ultimos_valores] * semanas_pronostico, ignore_index=False)
                fecha_inicio_pronostico = df.index[-1] + pd.Timedelta(weeks=1)
                fechas_pronostico = pd.date_range(
                    start=fecha_inicio_pronostico,
                    periods=semanas_pronostico,
                    freq='W-THU'
                )
                exog_future.index = fechas_pronostico
        modelo = SARIMAX(
            y,
            exog=exog,
            order=orden,
            seasonal_order=orden_estacional,
            enforce_stationarity=False,
            enforce_invertibility=False
        )
        
        modelo_ajustado = modelo.fit(disp=False, maxiter=200)
        
        if exog_future is not None:
            pronostico = modelo_ajustado.forecast(steps=semanas_pronostico, exog=exog_future)
            intervalo_confianza = modelo_ajustado.get_forecast(steps=semanas_pronostico, exog=exog_future).conf_int()
            fechas_pronostico = exog_future.index
        else:
            pronostico = modelo_ajustado.forecast(steps=semanas_pronostico)
            intervalo_confianza = modelo_ajustado.get_forecast(steps=semanas_pronostico).conf_int()
            fecha_inicio_pronostico = df.index[-1] + pd.Timedelta(weeks=1)
            fechas_pronostico = pd.date_range(start=fecha_inicio_pronostico, periods=semanas_pronostico, freq='W-THU')
        
        df_pronostico = pd.DataFrame({
            "pronostico": pronostico.values,
            "limite_inferior": intervalo_confianza.iloc[:, 0].values,
            "limite_superior": intervalo_confianza.iloc[:, 1].values
        }, index=fechas_pronostico)
        
        estadisticas = {
            "aic": modelo_ajustado.aic,
            "bic": modelo_ajustado.bic,
            "rmse": np.sqrt(modelo_ajustado.mse) if hasattr(modelo_ajustado, 'mse') else None,
            "r2": modelo_ajustado.rsquared if hasattr(modelo_ajustado, 'rsquared') else None,
            "serie_pronosticada": serie_pronosticar,
            "variables_exogenas_usadas": exog_vars if exog is not None else []
        }
        
        return df_pronostico, estadisticas, modelo_ajustado
        
    except Exception as e:
        return None, None, None

