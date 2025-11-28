import os
import json
import gradio as gr
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
    if chat_history is None:
        chat_history = []
    
    user_prompt = None
    user_display_content = None
    if message and message.strip():
        user_prompt = message.strip()
        user_display_content = user_prompt
    
    elif audio_input is not None:
        try:
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
    
    user_msg_str = str(user_display_content or user_prompt)
    chat_history.append((user_msg_str, None))
    
    system_prompt = str(stronger_prompt)
    if pronosticos_df is not None:
        pronostico_info = "\n\nINFORMACIÓN DE PRONÓSTICOS DISPONIBLE:"
        
        if isinstance(pronosticos_df, dict):
            for serie, df_pronostico in pronosticos_df.items():
                if df_pronostico is not None and len(df_pronostico) > 0 and 'pronostico' in df_pronostico.columns:
                    serie_nombre = serie.replace('CETE_', 'CETES a ').replace('D', ' días')
                    pronostico_info += f"\n\n{serie_nombre}:"
                    pronostico_info += f"\n- Pronóstico para la próxima semana: {df_pronostico['pronostico'].iloc[0]:.2f}%"
                    pronostico_info += f"\n- Pronóstico promedio ({len(df_pronostico)} semanas): {df_pronostico['pronostico'].mean():.2f}%"
                    pronostico_info += f"\n- Pronóstico máximo: {df_pronostico['pronostico'].max():.2f}%"
                    pronostico_info += f"\n- Pronóstico mínimo: {df_pronostico['pronostico'].min():.2f}%"
                    if 'limite_inferior' in df_pronostico.columns and 'limite_superior' in df_pronostico.columns:
                        pronostico_info += f"\n- Intervalo de confianza (próxima semana): {df_pronostico['limite_inferior'].iloc[0]:.2f}% - {df_pronostico['limite_superior'].iloc[0]:.2f}%"
        elif hasattr(pronosticos_df, 'columns') and len(pronosticos_df) > 0:
            if 'pronostico' in pronosticos_df.columns:
                pronostico_info += f"\n- Pronóstico para la próxima semana: {pronosticos_df['pronostico'].iloc[0]:.2f}%"
                pronostico_info += f"\n- Pronóstico promedio ({len(pronosticos_df)} semanas): {pronosticos_df['pronostico'].mean():.2f}%"
                pronostico_info += f"\n- Pronóstico máximo: {pronosticos_df['pronostico'].max():.2f}%"
                pronostico_info += f"\n- Pronóstico mínimo: {pronosticos_df['pronostico'].min():.2f}%"
                if 'limite_inferior' in pronosticos_df.columns and 'limite_superior' in pronosticos_df.columns:
                    pronostico_info += f"\n- Intervalo de confianza (próxima semana): {pronosticos_df['limite_inferior'].iloc[0]:.2f}% - {pronosticos_df['limite_superior'].iloc[0]:.2f}%"
        
        system_prompt += pronostico_info
    
    if datos_df is not None and len(datos_df) > 0:
        datos_info_lines = ["\nINFORMACIÓN DE DATOS HISTÓRICOS DISPONIBLE:"]
        cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
        for serie in cetes_series:
            if serie in datos_df.columns:
                serie_clean = serie.replace('CETE_', '').replace('D', ' días')
                ultima_tasa = datos_df[serie].iloc[-1]
                promedio = datos_df[serie].mean()
                datos_info_lines.append(f"- {serie_clean}: Última tasa {ultima_tasa:.2f}%, Promedio {promedio:.2f}%")
        
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
        
        system_prompt += "\n".join(datos_info_lines)
    
    conversation = [{"role": "system", "content": system_prompt}]
    for entry in chat_history:
        if isinstance(entry, tuple) and len(entry) >= 2:
            user_msg, bot_msg = entry[0], entry[1]
            
            if user_msg is not None:
                user_content = str(user_msg).strip()
                if user_content:
                    conversation.append({"role": "user", "content": user_content})
            
            if bot_msg is not None:
                bot_content = str(bot_msg).strip()
                if bot_content:
                    conversation.append({"role": "assistant", "content": bot_content})
    
    done = False
    response = ""
    
    while not done:
        try:
            cleaned_conversation = []
            for msg in conversation:
                if not isinstance(msg, dict):
                    continue
                
                cleaned_msg = {"role": str(msg.get("role", ""))}
                
                if "content" in msg and msg["content"] is not None:
                    cleaned_msg["content"] = str(msg["content"])
                elif "content" in msg and msg["content"] is None:
                    if "tool_calls" in msg:
                        cleaned_msg["content"] = None
                
                if "tool_calls" in msg:
                    cleaned_msg["tool_calls"] = msg["tool_calls"]
                
                if "tool_call_id" in msg:
                    cleaned_msg["tool_call_id"] = str(msg["tool_call_id"])
                
                if cleaned_msg["role"] and ("content" in cleaned_msg or "tool_calls" in cleaned_msg):
                    cleaned_conversation.append(cleaned_msg)
            
            stream = client_openai.chat.completions.create(
                model=model_openai,
                messages=cleaned_conversation,
                tools=tools,
                stream=True,
            )
            
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
            
            class SimulatedMessage:
                def __init__(self, role, content, tool_calls=None):
                    self.role = role
                    self.content = content
                    self.tool_calls = tool_calls
            
            message = SimulatedMessage(message_role or "assistant", full_response, tool_calls)
            
            if finish_reason == "tool_calls" and tool_calls:
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
    
    response_str = str(response) if response else ""
    
    if chat_history and len(chat_history) > 0:
        user_msg = str(chat_history[-1][0]) if chat_history[-1][0] else ""
        chat_history[-1] = (user_msg, response_str)
    
    audio_output = None
    if response_str and response_str.strip():
        try:
            speech = client_openai.audio.speech.create(
                model=model_tts,
                voice="shimmer",
                input=response_str
            )
            audio_bytes = speech.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_file.write(audio_bytes)
                audio_output = tmp_file.name
        except Exception as e:
            pass
    
    return chat_history, "", audio_output, None

def clear_chat():
    return [], None

with gr.Blocks(title="Mi Asesor CETES") as demo:
    gr.Markdown("# Mi Asesor CETES")
    
    pronosticos_globales = gr.State(value=None)
    datos_historicos = gr.State(value=None)
    
    with gr.Tabs():
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
                    
                    try:
                        df = obtener_datos_banxico()
                    except ValueError as e:
                        error_msg = str(e)
                        return "", f"❌ {error_msg}", None, None, ""
                    except Exception as e:
                        error_msg = f"Error inesperado al obtener datos de Banxico: {str(e)}"
                        return "", f"❌ {error_msg}", None, None, ""
                    
                    if df is None or len(df) == 0:
                        return "", "❌ Error: No se obtuvieron datos de Banxico", None, None, ""
                    
                    cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
                    pronosticos_dict = {}
                    series_exitosas = []
                    series_fallidas = []
                    
                    for serie in cetes_series:
                        if serie in df.columns:
                            try:
                                df_pronostico, estadisticas, modelo = generar_pronostico_sarimax(
                                    df, 
                                    serie_pronosticar=serie,
                                    semanas_pronostico=13,
                                    usar_exogenas=True
                                )
                                
                                if df_pronostico is not None:
                                    pronosticos_dict[serie] = df_pronostico
                                    series_exitosas.append(serie)
                                else:
                                    series_fallidas.append(serie)
                            except Exception as e:
                                series_fallidas.append(serie)
                    
                    pronosticos_final = pronosticos_dict if len(pronosticos_dict) > 0 else None
                    
                    if pronosticos_final is not None:
                        mensaje = f"✅ Datos y pronósticos actualizados correctamente"
                        if series_fallidas:
                            mensaje += f"\n⚠️ No se pudieron generar pronósticos para: {', '.join(series_fallidas)}"
                        return "", mensaje, df, pronosticos_final, ""
                    else:
                        return "", "⚠️ Datos cargados pero error al generar pronósticos", df, None, ""
                        
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    return "", f"❌ {error_msg}", None, None, ""
            
            actualizar_datos_btn.click(
                actualizar_datos,
                outputs=[datos_info, status_text, datos_historicos, pronosticos_globales, pronostico_info]
            )
        
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
                if history is None:
                    history = []
                
                clean_input_history = []
                if history:
                    for entry in history:
                        if isinstance(entry, dict):
                            role = entry.get("role", "")
                            content = entry.get("content", "")
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
                
                cleaned_history = []
                if new_history and isinstance(new_history, list):
                    for entry in new_history:
                        if isinstance(entry, tuple) and len(entry) >= 2:
                            user_msg = entry[0]
                            bot_msg = entry[1]
                            if user_msg is not None:
                                user_text = str(user_msg).strip()
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
                
                if not isinstance(cleaned_history, list):
                    cleaned_history = []
                
                return cleaned_history, empty_msg or "", audio_data, error or ""
            
            def safe_respond(message, audio, history, datos_df, pronosticos_df):
                try:
                    result = respond(message, audio, history, datos_df, pronosticos_df)
                    hist, msg, aud, err = result
                    if hist and isinstance(hist, list):
                        valid_hist = []
                        for item in hist:
                            if isinstance(item, dict) and "role" in item and "content" in item:
                                valid_hist.append({"role": str(item["role"]), "content": str(item["content"])})
                            elif isinstance(item, tuple) and len(item) == 2:
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
            recomendacion_output = gr.Markdown(label="Recomendación de Inversión", visible=True)
            
            def generar_recomendacion(datos_df, pronosticos_df, tipo_cetes):
                CAUTIOUS_THRESHOLD = 0.5
                
                if datos_df is None or len(datos_df) == 0:
                    return "⚠️ No hay datos históricos disponibles para generar una recomendación."
                
                if pronosticos_df is None:
                    return "⚠️ No hay pronósticos disponibles. Actualiza los datos para obtener recomendaciones."
                
                if tipo_cetes not in datos_df.columns:
                    cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
                    for serie in cetes_series:
                        if serie in datos_df.columns:
                            tipo_cetes = serie
                            break
                    else:
                        return "⚠️ No se encontró la serie de CETES especificada."
                
                pronostico_actual = None
                if isinstance(pronosticos_df, dict):
                    pronostico_actual = pronosticos_df.get(tipo_cetes)
                    if pronostico_actual is None:
                        return f"⚠️ No hay pronóstico disponible para {tipo_cetes}. Actualiza los datos."
                elif hasattr(pronosticos_df, 'columns') and 'pronostico' in pronosticos_df.columns:
                    pronostico_actual = pronosticos_df
                else:
                    return "⚠️ Los pronósticos no tienen el formato esperado."
                
                if pronostico_actual is None or len(pronostico_actual) == 0:
                    return f"⚠️ No hay pronóstico disponible para {tipo_cetes}."
                
                if 'pronostico' not in pronostico_actual.columns:
                    return "⚠️ Los pronósticos no tienen el formato esperado."
                
                tasa_actual = datos_df[tipo_cetes].iloc[-1]
                pronostico_proxima = pronostico_actual['pronostico'].iloc[0]
                change = pronostico_proxima - tasa_actual
                
                etiquetas = {
                    'CETE_28D': 'CETES a 28 Días',
                    'CETE_91D': 'CETES a 91 Días',
                    'CETE_182D': 'CETES a 182 Días',
                    'CETE_364D': 'CETES a 364 Días'
                }
                nombre_cetes = etiquetas.get(tipo_cetes, tipo_cetes)
                
                if change > CAUTIOUS_THRESHOLD:
                    recommendation = "🤔 ESPERAR"
                    explanation = f"Se predice un alza significativa en la próxima subasta (> {CAUTIOUS_THRESHOLD:.2f}pp). Esperar podría darte un mayor rendimiento."
                    return f"### {recommendation}\n\n{explanation}\n\n**Tasa actual:** {tasa_actual:.2f}%\n**Pronóstico próxima subasta:** {pronostico_proxima:.2f}%\n**Cambio previsto:** +{change:.2f} puntos porcentuales"
                elif change < -CAUTIOUS_THRESHOLD:
                    recommendation = "✅ ¡INVERTIR AHORA!"
                    explanation = f"La tasa actual es atractiva. Nuestro modelo predice que podría bajar pronto (< -{CAUTIOUS_THRESHOLD:.2f}pp), ¡asegura este rendimiento!"
                    return f"### {recommendation}\n\n{explanation}\n\n**Tasa actual:** {tasa_actual:.2f}%\n**Pronóstico próxima subasta:** {pronostico_proxima:.2f}%\n**Cambio previsto:** {change:.2f} puntos porcentuales"
                else:
                    recommendation = "⚖️ INVERTIR (ESTABLE)"
                    explanation = "El cambio previsto es mínimo. Invierte ahora para evitar que tu capital pierda tiempo en efectivo."
                    return f"### {recommendation}\n\n{explanation}\n\n**Tasa actual:** {tasa_actual:.2f}%\n**Pronóstico próxima subasta:** {pronostico_proxima:.2f}%\n**Cambio previsto:** {change:+.2f} puntos porcentuales"
            
            def generar_grafica(datos_df, pronosticos_df, tipo, tipo_cetes):
                if datos_df is None:
                    return None
                try:
                    import plotly.graph_objects as go
                    from plotly.subplots import make_subplots
                    import pandas as pd
                    
                    datos_filtrados = datos_df.copy()
                    
                    if tipo_cetes not in datos_filtrados.columns:
                        cetes_series = ['CETE_28D', 'CETE_91D', 'CETE_182D', 'CETE_364D']
                        for serie in cetes_series:
                            if serie in datos_filtrados.columns:
                                tipo_cetes = serie
                                break
                        else:
                            return None
                    
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
                        
                        fig.add_trace(go.Scatter(
                            x=datos_filtrados.index,
                            y=datos_filtrados[tipo_cetes],
                            mode='lines+markers',
                            name=f'Datos Históricos ({etiquetas.get(tipo_cetes, tipo_cetes)})',
                            line=dict(color=colores.get(tipo_cetes, '#2E86AB'), width=2),
                            marker=dict(size=4)
                        ))
                        
                        pronostico_actual = None
                        if pronosticos_df is not None:
                            if isinstance(pronosticos_df, dict):
                                pronostico_actual = pronosticos_df.get(tipo_cetes)
                            elif hasattr(pronosticos_df, 'columns') and 'pronostico' in pronosticos_df.columns:
                                pronostico_actual = pronosticos_df
                        
                        if (pronostico_actual is not None and len(pronostico_actual) > 0 and 
                            'pronostico' in pronostico_actual.columns):
                            fig.add_trace(go.Scatter(
                                x=pronostico_actual.index,
                                y=pronostico_actual['pronostico'],
                                mode='lines+markers',
                                name='Pronóstico',
                                line=dict(color='#A23B72', width=2.5, dash='dash'),
                                marker=dict(size=5, symbol='square')
                            ))
                            
                            if 'limite_inferior' in pronostico_actual.columns and 'limite_superior' in pronostico_actual.columns:
                                fig.add_trace(go.Scatter(
                                    x=pronostico_actual.index.tolist() + pronostico_actual.index.tolist()[::-1],
                                    y=pronostico_actual['limite_superior'].tolist() + pronostico_actual['limite_inferior'].tolist()[::-1],
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
                        
                        fig.add_trace(go.Scatter(
                            x=datos_filtrados.index,
                            y=datos_filtrados[tipo_cetes],
                            mode='lines',
                            name=f'Tasa Semanal ({etiquetas.get(tipo_cetes, tipo_cetes)})',
                            line=dict(color='#2E86AB', width=1.5),
                            opacity=0.6
                        ), row=1, col=1)
                        
                        if len(datos_filtrados) >= 12:
                            media_movil = datos_filtrados[tipo_cetes].rolling(window=12).mean()
                            fig.add_trace(go.Scatter(
                                x=datos_filtrados.index,
                                y=media_movil,
                                mode='lines',
                                name='Media Móvil (12 semanas)',
                                line=dict(color='#A23B72', width=2.5)
                            ), row=1, col=1)
                        
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
                except Exception:
                    return None
            
            def actualizar_grafica_y_recomendacion(datos_df, pronosticos_df, tipo, tipo_cetes):
                grafica = generar_grafica(datos_df, pronosticos_df, tipo, tipo_cetes)
                if tipo == "Histórica y Pronósticos":
                    recomendacion = generar_recomendacion(datos_df, pronosticos_df, tipo_cetes)
                else:
                    recomendacion = ""
                return grafica, recomendacion
            
            actualizar_grafica_btn = gr.Button("🔄 Actualizar Gráfica", variant="primary", size="lg")
            actualizar_grafica_btn.click(
                actualizar_grafica_y_recomendacion,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output, recomendacion_output]
            )
            
            tipo_grafica.change(
                actualizar_grafica_y_recomendacion,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output, recomendacion_output]
            )
            
            tipo_cetes.change(
                actualizar_grafica_y_recomendacion,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output, recomendacion_output]
            )
            
            datos_historicos.change(
                actualizar_grafica_y_recomendacion,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output, recomendacion_output]
            )
            
            pronosticos_globales.change(
                actualizar_grafica_y_recomendacion,
                inputs=[datos_historicos, pronosticos_globales, tipo_grafica, tipo_cetes],
                outputs=[grafica_output, recomendacion_output]
            )

if __name__ == "__main__":
    demo.launch()
