import os
import json
import gradio as gr
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv
from prompts import stronger_prompt
from tooling import handle_tool_calls, tools
import tempfile

load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client_openai = OpenAI(api_key=OPENAI_API_KEY)

model_openai = "gpt-5.1"
model_transcribe = "whisper-1"
model_tts = "gpt-4o-mini-tts"

def process_message(message, audio_input, chat_history, datos_df=None, pronosticos_df=None):
    """Procesa el mensaje del usuario (texto o audio) y genera la respuesta"""
    
    # Asegurar que chat_history es una lista
    if chat_history is None:
        chat_history = []
    
    user_prompt = None
    user_display_content = None
    
    # Procesar entrada de texto
    if message and message.strip():
        user_prompt = message.strip()
        user_display_content = user_prompt
    
    # Procesar entrada de audio
    elif audio_input is not None:
        try:
            # audio_input es el path del archivo cuando type="filepath"
            audio_path = audio_input if isinstance(audio_input, str) else None
            
            if audio_path and os.path.exists(audio_path):
                with open(audio_path, "rb") as audio_file:
                    transcription = client_openai.audio.transcriptions.create(
                        model=model_transcribe,
                        file=audio_file,
                    )
                user_prompt = transcription.text.strip()
                user_display_content = f"(Audio) {user_prompt}" if user_prompt else None
            else:
                return chat_history, "", None, "Error: No se pudo procesar el archivo de audio"
        except Exception as e:
            return chat_history, "", None, f"Error al transcribir audio: {str(e)}"
    
    if not user_prompt:
        return chat_history, "", None, None
    
    # Agregar mensaje del usuario al historial (asegurar que sea string)
    user_msg_str = str(user_display_content or user_prompt)
    chat_history.append((user_msg_str, None))
    
    # Construir prompt del sistema con información de pronósticos si está disponible
    system_prompt = str(stronger_prompt)
    
    # Agregar información de pronósticos al prompt si está disponible
    if pronosticos_df is not None and len(pronosticos_df) > 0:
        pronostico_info = f"""
        
INFORMACIÓN DE PRONÓSTICOS DISPONIBLE:
- Pronóstico para la próxima semana: {pronosticos_df['pronostico'].iloc[0]:.2f}%
- Pronóstico promedio ({len(pronosticos_df)} semanas): {pronosticos_df['pronostico'].mean():.2f}%
- Pronóstico máximo: {pronosticos_df['pronostico'].max():.2f}%
- Pronóstico mínimo: {pronosticos_df['pronostico'].min():.2f}%
- Intervalo de confianza (próxima semana): {pronosticos_df['limite_inferior'].iloc[0]:.2f}% - {pronosticos_df['limite_superior'].iloc[0]:.2f}%
"""
        system_prompt += pronostico_info
    
    # Agregar información de datos históricos si está disponible
    if datos_df is not None and len(datos_df) > 0:
        datos_info_lines = ["\nINFORMACIÓN DE DATOS HISTÓRICOS DISPONIBLE:"]
        
        # Información de CETES disponibles
        cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
        for serie in cetes_series:
            if serie in datos_df.columns:
                serie_clean = serie.replace('CETE_', '').replace('D', ' días')
                ultima_tasa = datos_df[serie].iloc[-1]
                promedio = datos_df[serie].mean()
                datos_info_lines.append(f"- {serie_clean}: Última tasa {ultima_tasa:.2f}%, Promedio {promedio:.2f}%")
        
        # Información de variables exógenas
        if any(col in datos_df.columns for col in ['Tasa_Objetivo', 'Tasa_FED', 'Tipo_Cambio_Fix', 'INPC']):
            datos_info_lines.append("\nVariables económicas:")
            if 'Tasa_Objetivo' in datos_df.columns:
                datos_info_lines.append(f"- Tasa Objetivo: {datos_df['Tasa_Objetivo'].iloc[-1]:.2f}%")
            if 'Tasa_FED' in datos_df.columns:
                datos_info_lines.append(f"- Tasa FED: {datos_df['Tasa_FED'].iloc[-1]:.2f}%")
            if 'Tipo_Cambio_Fix' in datos_df.columns:
                datos_info_lines.append(f"- Tipo de Cambio: ${datos_df['Tipo_Cambio_Fix'].iloc[-1]:.2f}")
            if 'INPC' in datos_df.columns:
                datos_info_lines.append(f"- INPC: {datos_df['INPC'].iloc[-1]:.2f}")
        
        datos_info = "\n".join(datos_info_lines)
        system_prompt += datos_info
    
    # Construir conversación con el prompt del sistema
    conversation = [{"role": "system", "content": system_prompt}]
    
    # Procesar el historial, asegurando que cada entrada sea una tupla válida
    for entry in chat_history:
        if isinstance(entry, tuple) and len(entry) >= 2:
            user_msg, bot_msg = entry[0], entry[1]
            
            # Agregar mensaje del usuario si existe y es válido
            if user_msg is not None:
                user_content = str(user_msg).strip()
                if user_content:
                    conversation.append({"role": "user", "content": user_content})
            
            # Agregar mensaje del asistente si existe y es válido
            if bot_msg is not None:
                bot_content = str(bot_msg).strip()
                if bot_content:
                    conversation.append({"role": "assistant", "content": bot_content})
    
    # Procesar respuesta con manejo de tool calls y streaming
    done = False
    response = ""
    audio_bytes = None
    
    while not done:
        try:
            # Limpiar y validar formato de mensajes antes de enviar
            cleaned_conversation = []
            for msg in conversation:
                if not isinstance(msg, dict):
                    continue
                
                cleaned_msg = {"role": str(msg.get("role", ""))}
                
                # Agregar content si existe
                if "content" in msg and msg["content"] is not None:
                    cleaned_msg["content"] = str(msg["content"])
                elif "content" in msg and msg["content"] is None:
                    # Permitir content None solo si hay tool_calls
                    if "tool_calls" in msg:
                        cleaned_msg["content"] = None
                
                # Agregar tool_calls si existe
                if "tool_calls" in msg:
                    cleaned_msg["tool_calls"] = msg["tool_calls"]
                
                # Agregar tool_call_id si es un mensaje de tool
                if "tool_call_id" in msg:
                    cleaned_msg["tool_call_id"] = str(msg["tool_call_id"])
                
                # Solo agregar si tiene role válido y al menos content o tool_calls
                if cleaned_msg["role"] and ("content" in cleaned_msg or "tool_calls" in cleaned_msg):
                    cleaned_conversation.append(cleaned_msg)
            
            # Usar streaming para mostrar la respuesta mientras se genera
            stream = client_openai.chat.completions.create(
                model=model_openai,
                messages=cleaned_conversation,
                tools=tools,
                stream=True,
            )
            
            # Acumular la respuesta mientras se recibe
            full_response = ""
            message_role = None
            finish_reason = None
            tool_calls = None
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    full_response += chunk.choices[0].delta.content
                if chunk.choices[0].delta.role:
                    message_role = chunk.choices[0].delta.role
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
                if chunk.choices[0].delta.tool_calls:
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.extend(chunk.choices[0].delta.tool_calls)
            
            # Crear el objeto message simulado para compatibilidad
            class SimulatedMessage:
                def __init__(self, role, content, tool_calls=None):
                    self.role = role
                    self.content = content
                    self.tool_calls = tool_calls
            
            message = SimulatedMessage(message_role or "assistant", full_response, tool_calls)
            
            # Si hay tool calls, procesarlos
            if finish_reason == "tool_calls" and tool_calls:
                # Procesar tool calls (código existente)
                tool_calls_serialized = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                        "type": tc.type,
                    }
                    for tc in tool_calls if hasattr(tc, 'id')
                ]
                
                results = handle_tool_calls(tool_calls)
                safe_content = full_response or ""
                
                assistant_msg = {
                    "role": message_role or "assistant",
                    "tool_calls": tool_calls_serialized,
                }
                if safe_content:
                    assistant_msg["content"] = str(safe_content)
                else:
                    assistant_msg["content"] = None
                
                conversation.append(assistant_msg)
                conversation.extend(results)
                continue
            
            done = True
            response = full_response
            
        except Exception as e:
            response = f"Error: {str(e)}"
            done = True
    
    # Actualizar historial con la respuesta
    # Asegurar que response sea un string
    response_str = str(response) if response else ""
    
    if chat_history and len(chat_history) > 0:
        # Asegurar que ambos elementos de la tupla sean strings
        user_msg = str(chat_history[-1][0]) if chat_history[-1][0] else ""
        chat_history[-1] = (user_msg, response_str)
    
    # Generar audio de la respuesta automáticamente
    audio_output = None
    if response_str and response_str.strip():
        try:
            speech = client_openai.audio.speech.create(
                model=model_tts,
                voice="shimmer",
                input=response_str
            )
            audio_bytes = speech.read()
            # Guardar en archivo temporal para Gradio
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_file.write(audio_bytes)
                audio_output = tmp_file.name
        except Exception as e:
            pass
    
    return chat_history, "", audio_output, None

def clear_chat():
    """Limpia el historial del chat"""
    return [], None

with gr.Blocks(title="Mi Asesor CETES") as demo:
    gr.Markdown("# Mi Asesor CETES")
    
    # Variable global para almacenar pronósticos
    pronosticos_globales = gr.State(value=None)
    datos_historicos = gr.State(value=None)
    
    with gr.Tabs() as tabs:
        # SEGMENTO 1: INICIO
        with gr.Tab("🏠 Inicio"):
            gr.Markdown("## Bienvenido a Mi Asesor CETES")
            gr.Markdown("""
            Esta aplicación te ayuda a tomar decisiones informadas sobre inversiones en CETES.
            
            **Funcionalidades:**
            - 💬 Asesor experto con IA
            - 🔮 Pronósticos generados con modelos avanzados
            - 📊 Análisis de datos históricos de Banxico
            - 📈 Visualización de gráficas comparativas
            
            **Instrucciones:**
            1. Haz clic en "Actualizar Datos" para cargar información actualizada de Banxico y generar pronósticos
            2. Navega a las otras pestañas para usar el asesor o ver gráficas
            """)
            
            actualizar_datos_btn = gr.Button("🔄 Actualizar Datos", variant="primary", size="lg")
            
            status_text = gr.Textbox(label="Estado", value="Listo para actualizar datos", interactive=False)
            
            datos_info = gr.Markdown("### Información de Datos", visible=False)
            pronostico_info = gr.Markdown("### Información de Pronósticos", visible=False)
            
            def actualizar_datos():
                try:
                    from banxico_data import obtener_datos_banxico, generar_pronostico_sarimax
                    
                    # Paso 1: Cargar datos
                    df = obtener_datos_banxico()
                    
                    if df is None or len(df) == 0:
                        return "", "❌ Error al cargar datos", None, None, ""
                    
                    # Paso 2: Generar pronósticos
                    serie_pronosticar = 'CETE_28D'
                    cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
                    if serie_pronosticar not in df.columns:
                        # Si no está disponible, usar la primera serie de CETES disponible
                        for serie in cetes_series:
                            if serie in df.columns:
                                serie_pronosticar = serie
                                break
                    
                    df_pronostico, estadisticas, modelo = generar_pronostico_sarimax(
                        df, 
                        serie_pronosticar=serie_pronosticar,
                        semanas_pronostico=13,
                        usar_exogenas=True
                    )
                    
                    if df_pronostico is not None:
                        return "", "✅ Datos y pronósticos actualizados correctamente", df, df_pronostico, ""
                    else:
                        return "", "⚠️ Datos cargados pero error al generar pronósticos", df, None, ""
                        
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    error_msg = f"Error: {str(e)}"
                    return "", f"❌ {error_msg}", None, None, ""
            
            actualizar_datos_btn.click(
                actualizar_datos,
                outputs=[datos_info, status_text, datos_historicos, pronosticos_globales, pronostico_info]
            )
        
        # SEGMENTO 2: ASESOR EXPERTO
        with gr.Tab("💬 Asesor Experto"):
            chatbot = gr.Chatbot(label="Chat", height=500)
            
            with gr.Row():
                with gr.Column(scale=3):
                    msg = gr.Textbox(
                        label="Mensaje",
                        placeholder="Escribe tu mensaje aquí...",
                        scale=4
                    )
                with gr.Column(scale=1):
                    audio_input = gr.Audio(
                        label="Grabar audio",
                        type="filepath",
                        sources=["microphone"]
                    )
            
            with gr.Row():
                send_btn = gr.Button("Enviar", variant="primary")
                clear_btn = gr.Button("Limpiar")
            
            audio_output = gr.Audio(
                label="🔊 Respuesta en audio (se genera automáticamente)", 
                type="filepath", 
                visible=True
            )
            error_msg = gr.Textbox(label="Mensajes", visible=False)
            
            def respond(message, audio, history, datos_df, pronosticos_df):
                # Asegurar que history sea una lista válida
                if history is None:
                    history = []
                
                # Limpiar el historial de entrada para asegurar formato correcto (tuplas)
                clean_input_history = []
                if history:
                    for entry in history:
                        if isinstance(entry, dict):
                            # Si viene en formato dict, extraer el contenido correctamente
                            role = entry.get("role", "")
                            content = entry.get("content", "")
                            # Si content es una lista o dict, extraer el texto
                            if isinstance(content, list) and len(content) > 0:
                                if isinstance(content[0], dict):
                                    content = content[0].get("text", str(content[0]))
                                else:
                                    content = str(content[0])
                            elif isinstance(content, dict):
                                content = content.get("text", str(content))
                            else:
                                content = str(content)
                            
                            if role == "user":
                                clean_input_history.append((content, None))
                            elif role == "assistant":
                                if clean_input_history:
                                    clean_input_history[-1] = (clean_input_history[-1][0], content)
                                else:
                                    clean_input_history.append(("", content))
                        elif isinstance(entry, tuple) and len(entry) >= 2:
                            user_msg = str(entry[0]) if entry[0] is not None else ""
                            bot_msg = str(entry[1]) if entry[1] is not None else ""
                            clean_input_history.append((user_msg, bot_msg))
                        elif isinstance(entry, (list, tuple)) and len(entry) > 0:
                            user_msg = str(entry[0]) if entry[0] is not None else ""
                            bot_msg = str(entry[1]) if len(entry) > 1 and entry[1] is not None else ""
                            clean_input_history.append((user_msg, bot_msg))
                
                new_history, empty_msg, audio_data, error = process_message(message, audio, clean_input_history, datos_df, pronosticos_df)
                
                # Convertir de tuplas a formato de diccionarios que espera Gradio 6.0
                # El contenido debe ser texto plano, no estructuras anidadas
                cleaned_history = []
                if new_history and isinstance(new_history, list):
                    for entry in new_history:
                        if isinstance(entry, tuple) and len(entry) >= 2:
                            user_msg = entry[0]
                            bot_msg = entry[1]
                            # Asegurar que el contenido sea texto plano
                            if user_msg is not None:
                                user_text = str(user_msg).strip()
                                # Si es una estructura, extraer el texto
                                if user_text.startswith("[{") or user_text.startswith("{'text'"):
                                    try:
                                        import json
                                        parsed = json.loads(user_text.replace("'", '"'))
                                        if isinstance(parsed, list) and len(parsed) > 0:
                                            user_text = parsed[0].get("text", user_text)
                                        elif isinstance(parsed, dict):
                                            user_text = parsed.get("text", user_text)
                                    except:
                                        pass
                                if user_text:
                                    cleaned_history.append({"role": "user", "content": user_text})
                            
                            if bot_msg is not None:
                                bot_text = str(bot_msg).strip()
                                # Si es una estructura, extraer el texto
                                if bot_text.startswith("[{") or bot_text.startswith("{'text'"):
                                    try:
                                        import json
                                        parsed = json.loads(bot_text.replace("'", '"'))
                                        if isinstance(parsed, list) and len(parsed) > 0:
                                            bot_text = parsed[0].get("text", bot_text)
                                        elif isinstance(parsed, dict):
                                            bot_text = parsed.get("text", bot_text)
                                    except:
                                        pass
                                if bot_text:
                                    cleaned_history.append({"role": "assistant", "content": bot_text})
                        elif isinstance(entry, (list, tuple)) and len(entry) > 0:
                            user_msg = str(entry[0]) if entry[0] is not None else ""
                            bot_msg = str(entry[1]) if len(entry) > 1 and entry[1] is not None else ""
                            if user_msg.strip():
                                cleaned_history.append({"role": "user", "content": user_msg.strip()})
                            if bot_msg.strip():
                                cleaned_history.append({"role": "assistant", "content": bot_msg.strip()})
                
                # Asegurar que siempre devolvamos una lista válida
                if not isinstance(cleaned_history, list):
                    cleaned_history = []
                
                return cleaned_history, empty_msg or "", audio_data, error or ""
            
            def safe_respond(message, audio, history, datos_df, pronosticos_df):
                """Wrapper para asegurar formato correcto"""
                try:
                    result = respond(message, audio, history, datos_df, pronosticos_df)
                    # Validar que el historial sea una lista de diccionarios
                    hist, msg, aud, err = result
                    if hist and isinstance(hist, list):
                        # Validar cada entrada sea un diccionario con role y content
                        valid_hist = []
                        for item in hist:
                            if isinstance(item, dict) and "role" in item and "content" in item:
                                valid_hist.append({"role": str(item["role"]), "content": str(item["content"])})
                            elif isinstance(item, tuple) and len(item) == 2:
                                # Convertir tuplas a diccionarios
                                if item[0]:
                                    valid_hist.append({"role": "user", "content": str(item[0])})
                                if item[1]:
                                    valid_hist.append({"role": "assistant", "content": str(item[1])})
                        return valid_hist, msg, aud, err
                    return hist or [], msg, aud, err
                except Exception as e:
                    return [], "", None, f"Error: {str(e)}"
            
            msg.submit(safe_respond, [msg, audio_input, chatbot, datos_historicos, pronosticos_globales], [chatbot, msg, audio_output, error_msg])
            send_btn.click(safe_respond, [msg, audio_input, chatbot, datos_historicos, pronosticos_globales], [chatbot, msg, audio_output, error_msg])
            clear_btn.click(clear_chat, None, [chatbot, audio_output])
        
        # SEGMENTO 3: GRÁFICAS Y PRONÓSTICOS
        with gr.Tab("📈 Gráficas y Pronósticos"):
            gr.Markdown("## Visualización de Datos Históricos y Pronósticos")
            gr.Markdown("Aquí podrás visualizar gráficas históricas y comparativas de diferentes plazos de CETES.")
            
            with gr.Row():
                tipo_grafica = gr.Radio(
                    choices=["Histórica y Pronósticos", "Comparativa de Plazos", "Análisis de Tendencia"],
                    value="Histórica y Pronósticos",
                    label="Tipo de Gráfica"
                )
                tipo_cetes = gr.Dropdown(
                    choices=["CETE_28D", "CETE_91D", "CETE_182D", "CETE_364D"],
                    value="CETE_28D",
                    label="Tipo de CETES",
                    info="Selecciona el tipo de CETES a visualizar"
                )
            
            grafica_output = gr.Plot(label="Gráfica Interactiva")
            
            def generar_grafica(datos_df, pronosticos_df, tipo, tipo_cetes):
                if datos_df is None:
                    return None
                try:
                    import plotly.graph_objects as go
                    from plotly.subplots import make_subplots
                    import pandas as pd
                    
                    # Mostrar todos los datos disponibles (ya no hay filtro por período)
                    datos_filtrados = datos_df.copy()
                    
                    # Verificar que el tipo de CETES seleccionado esté disponible
                    if tipo_cetes not in datos_filtrados.columns:
                        # Si no está disponible, usar el primero disponible
                        cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
                        for serie in cetes_series:
                            if serie in datos_filtrados.columns:
                                tipo_cetes = serie
                                break
                        else:
                            return None
                    
                    # Etiquetas y colores para los diferentes tipos de CETES
                    etiquetas = {
                        'CETE_28D': 'CETES a 28 Días',
                        'CETE_91D': 'CETES a 91 Días',
                        'CETE_182D': 'CETES a 182 Días',
                        'CETE_364D': 'CETES a 364 Días'
                    }
                    colores = {
                        'CETE_28D': '#2E86AB',
                        'CETE_91D': '#F18F01',
                        'CETE_182D': '#C73E1D',
                        'CETE_364D': '#A23B72'
                    }
                    
                    if tipo == "Histórica y Pronósticos":
                        fig = go.Figure()
                        
                        # Graficar datos históricos
                        fig.add_trace(go.Scatter(
                            x=datos_filtrados.index,
                            y=datos_filtrados[tipo_cetes],
                            mode='lines+markers',
                            name=f'Datos Históricos ({etiquetas.get(tipo_cetes, tipo_cetes)})',
                            line=dict(color=colores.get(tipo_cetes, '#2E86AB'), width=2),
                            marker=dict(size=4)
                        ))
                        
                        # Graficar pronósticos si existen
                        if (pronosticos_df is not None and len(pronosticos_df) > 0 and 
                            'pronostico' in pronosticos_df.columns):
                            fig.add_trace(go.Scatter(
                                x=pronosticos_df.index,
                                y=pronosticos_df['pronostico'],
                                mode='lines+markers',
                                name='Pronóstico',
                                line=dict(color='#A23B72', width=2.5, dash='dash'),
                                marker=dict(size=5, symbol='square')
                            ))
                            
                            # Intervalo de confianza
                            if 'limite_inferior' in pronosticos_df.columns and 'limite_superior' in pronosticos_df.columns:
                                fig.add_trace(go.Scatter(
                                    x=pronosticos_df.index.tolist() + pronosticos_df.index.tolist()[::-1],
                                    y=pronosticos_df['limite_superior'].tolist() + pronosticos_df['limite_inferior'].tolist()[::-1],
                                    fill='toself',
                                    fillcolor='rgba(162, 59, 114, 0.2)',
                                    line=dict(color='rgba(255,255,255,0)'),
                                    name='Intervalo de Confianza (95%)',
                                    showlegend=True
                                ))
                        
                        fig.update_layout(
                            title=f'{etiquetas.get(tipo_cetes, tipo_cetes)} - Datos Históricos y Pronósticos',
                            xaxis_title='Fecha',
                            yaxis_title='Tasa de Interés (%)',
                            hovermode='x unified',
                            template='plotly_white',
                            height=600,
                            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                        )
                        
                    elif tipo == "Comparativa de Plazos":
                        fig = go.Figure()
                        
                        # Graficar todos los plazos de CETES disponibles
                        cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
                        for serie in cetes_series:
                            if serie in datos_filtrados.columns:
                                fig.add_trace(go.Scatter(
                                    x=datos_filtrados.index,
                                    y=datos_filtrados[serie],
                                    mode='lines',
                                    name=etiquetas.get(serie, serie),
                                    line=dict(color=colores.get(serie, '#000000'), width=2)
                                ))
                        
                        fig.update_layout(
                            title='Comparativa de CETES por Plazo',
                            xaxis_title='Fecha',
                            yaxis_title='Tasa de Interés (%)',
                            hovermode='x unified',
                            template='plotly_white',
                            height=600,
                            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                        )
                        
                    elif tipo == "Análisis de Tendencia":
                        fig = make_subplots(
                            rows=2, cols=1,
                            subplot_titles=('Tendencia con Media Móvil', 'Análisis de Volatilidad'),
                            vertical_spacing=0.1,
                            row_heights=[0.6, 0.4]
                        )
                        
                        # Gráfica 1: Datos con media móvil
                        fig.add_trace(go.Scatter(
                            x=datos_filtrados.index,
                            y=datos_filtrados[tipo_cetes],
                            mode='lines',
                            name=f'Tasa Semanal ({etiquetas.get(tipo_cetes, tipo_cetes)})',
                            line=dict(color='#2E86AB', width=1.5),
                            opacity=0.6
                        ), row=1, col=1)
                        
                        # Media móvil de 12 semanas (~3 meses)
                        if len(datos_filtrados) >= 12:
                            media_movil = datos_filtrados[tipo_cetes].rolling(window=12).mean()
                            fig.add_trace(go.Scatter(
                                x=datos_filtrados.index,
                                y=media_movil,
                                mode='lines',
                                name='Media Móvil (12 semanas)',
                                line=dict(color='#A23B72', width=2.5)
                            ), row=1, col=1)
                        
                        # Gráfica 2: Volatilidad (desviación estándar móvil)
                        if len(datos_filtrados) >= 12:
                            volatilidad = datos_filtrados[tipo_cetes].rolling(window=12).std()
                            fig.add_trace(go.Scatter(
                                x=datos_filtrados.index,
                                y=volatilidad,
                                mode='lines',
                                name='Volatilidad (12 semanas)',
                                line=dict(color='#F18F01', width=2),
                                fill='tozeroy',
                                fillcolor='rgba(241, 143, 1, 0.3)'
                            ), row=2, col=1)
                        
                        fig.update_xaxes(title_text="Fecha", row=2, col=1)
                        fig.update_yaxes(title_text="Tasa de Interés (%)", row=1, col=1)
                        fig.update_yaxes(title_text="Desviación Estándar (%)", row=2, col=1)
                        
                        fig.update_layout(
                            title=f'Análisis de Tendencia - {etiquetas.get(tipo_cetes, tipo_cetes)}',
                            hovermode='x unified',
                            template='plotly_white',
                            height=800,
                            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                        )
                    
                    return fig
                except Exception as e:
                    print(f"Error al generar gráfica: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    return None
            
            actualizar_grafica_btn = gr.Button("🔄 Actualizar Gráfica", variant="primary", size="lg")
            actualizar_grafica_btn.click(
                generar_grafica,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output]
            )
            
            # Auto-actualizar cuando cambian los datos o el tipo de gráfica
            tipo_grafica.change(
                generar_grafica,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output]
            )
            
            tipo_cetes.change(
                generar_grafica,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output]
            )

if __name__ == "__main__":
    demo.launch()
