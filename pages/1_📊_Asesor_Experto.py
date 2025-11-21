import os
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import tempfile
import base64

from prompts import cetes_prompt
from audiorecorder import audiorecorder
from utils.common import (
    client_openai, client_deepseek, model_deepseek,
    audio_player_with_speed, get_image_path,
    obtener_resumen_pronosticos_sarimax,
    obtener_datos_banxico, generar_todos_los_pronosticos
)

# Configuración de la página
st.set_page_config(
    page_title="Asesor Experto - Mi Asesor CETES",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.header("💡 Asesor Experto en CETES")
st.markdown("Chatea con un experto en CETES, Banxico e inflación.")
st.divider()

# NO generar pronósticos aquí - deben estar en session_state desde main.py
# Si no están, mostrar mensaje y no generar para evitar cálculos duplicados
if "pronosticos_generados" not in st.session_state:
    st.warning("⚠️ Los pronósticos no están disponibles. Por favor, primero visita la página principal para que se generen los pronósticos.")
    st.info("💡 Esto asegura que los cálculos solo se hagan una vez y la aplicación sea más rápida.")
    st.stop()

# Cargar el prompt base del sistema
SYSTEM_PROMPT_BASE = cetes_prompt

# Generar prompt del sistema con pronósticos
def generar_system_prompt_con_pronosticos():
    """Genera el prompt del sistema incluyendo los pronósticos SARIMAX desde session_state"""
    # Usar pronósticos generados al inicio de la aplicación
    pronosticos_dict = st.session_state.get('pronosticos_generados', None)
    
    if pronosticos_dict:
         # Determinar el número máximo de semanas disponibles en los pronósticos
        max_semanas = 0
        for columna, datos in pronosticos_dict.items():
            if 'pronostico_series' in datos:
                semanas_disponibles = len(datos['pronostico_series'])
                max_semanas = max(max_semanas, semanas_disponibles)
        
        # Usar el máximo disponible o 13 como default
        periodos_a_mostrar = max_semanas if max_semanas > 0 else 13
        
        resumen_pronosticos = obtener_resumen_pronosticos_sarimax(
            pronosticos_dict=pronosticos_dict,
            periodos_pronostico=periodos_a_mostrar
        )
        
        # Agregar nota sobre disponibilidad de pronósticos extendidos
        if max_semanas > 4:
            resumen_pronosticos += f"\n\n💡 NOTA: Los pronósticos están disponibles hasta {max_semanas} semanas. Puedes preguntar sobre cualquier semana dentro de este rango."
    else:
        resumen_pronosticos = None
    
    prompt_completo = SYSTEM_PROMPT_BASE
    
    if resumen_pronosticos:
        prompt_completo += "\n\n"
        prompt_completo += "=" * 60 + "\n"
        prompt_completo += "📊 DATOS DE PRONÓSTICOS SARIMAX DISPONIBLES\n"
        prompt_completo += "=" * 60 + "\n"
        prompt_completo += "\n"
        prompt_completo += "Tienes acceso a pronósticos generados por el modelo SARIMAX para todos los plazos de CETES.\n"
        prompt_completo += "Los pronósticos están disponibles hasta 13 semanas en el futuro. Puedes responder preguntas sobre\n"
        prompt_completo += "cualquier semana dentro de este rango (semana 1, semana 2, hasta semana 13).\n"
        prompt_completo += "Usa estos datos para responder preguntas sobre tendencias futuras, recomendaciones de inversión\n"
        prompt_completo += "y análisis de pronósticos. SIEMPRE menciona que estos son pronósticos basados en modelos estadísticos\n"
        prompt_completo += "y que no garantizan resultados futuros.\n"
        prompt_completo += "\n"
        prompt_completo += resumen_pronosticos
        prompt_completo += "\n"
        prompt_completo += "=" * 60 + "\n"
    else:
        prompt_completo += "\n\n"
        prompt_completo += "⚠️ NOTA: Los pronósticos SARIMAX no están disponibles en este momento.\n"
        prompt_completo += "Puedes responder preguntas generales sobre CETES, pero no tienes acceso a pronósticos específicos.\n"
    
    return prompt_completo

# --- Lógica del Chatbot ---

# Sidebar con botón de limpiar 
with st.sidebar:
    st.subheader("⚙️ Configuración")
    
    if st.button("🗑️ Limpiar Chat"):
        # Limpiar todos los mensajes
        st.session_state.cetes_messages = []
        # Reinicializar con el disclaimer
        st.session_state.cetes_messages.append({
            "role": "assistant",
            "content": "💡 Este asistente tiene fines **educativos e informativos**. Úsalo para comprender tu perfil de riesgo y para aprender a analizar instrumentos de deuda."
        })
        st.rerun()
    
    st.divider()
    st.subheader("📊 Pronósticos")
    
    # Verificar estado de los pronósticos desde session_state
    pronosticos_dict = st.session_state.get('pronosticos_generados', None)
    if pronosticos_dict:
        st.success("✅ Pronósticos disponibles")
        st.caption("El asesor tiene acceso a pronósticos actualizados de todos los plazos de CETES.")
    else:
        st.warning("⚠️ Pronósticos no disponibles")
        st.caption("Los pronósticos no están disponibles. El asesor responderá con información general.")

# Inicializar el historial si no existe
if "cetes_messages" not in st.session_state:
    st.session_state.cetes_messages = [] 
    # Añadir el disclaimer como primer mensaje
    st.session_state.cetes_messages.append({
        "role": "assistant",
        "content": "💡 Este asistente tiene fines **educativos e informativos**. Úsalo para comprender tu perfil de riesgo y para aprender a analizar instrumentos de deuda."
    })

# Mostrar mensajes antiguos en la UI
for message in st.session_state.cetes_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Reproducir audio si existe para mensajes del asistente
        if message["role"] == "assistant" and "audio_bytes" in message:
            st.markdown(audio_player_with_speed(message["audio_bytes"], 1.25), unsafe_allow_html=True)

# Sección de entrada: texto y grabación de voz
col_input, col_audio = st.columns([4, 1])

with col_input:
    user_input = st.chat_input("Escribe o graba un mensaje de voz, ¿Qué quieres saber sobre CETES?")

with col_audio:
    st.write("🎤")
    audio = audiorecorder("Grabar", "Detener")

# Procesar audio grabado (STT) - SOLO si no hay entrada de texto
if user_input is None and audio is not None and len(audio) > 0:
    try:
        # Convertir audio a formato WAV
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            try:
                audio.export(tmp_file.name, format="wav")
            except Exception as export_error:
                # Si la exportación falla (por ejemplo, sin FFmpeg), intentar obtener los bytes directamente
                try:
                    audio_bytes = audio.tobytes() if hasattr(audio, 'tobytes') else bytes(audio)
                    tmp_file.write(audio_bytes)
                except:
                    raise export_error
            audio_path = tmp_file.name
        
        # Transcribir audio usando OpenAI Whisper
        with st.spinner("🎤 Transcribiendo audio..."):
            if client_openai:
                try:
                    with open(audio_path, "rb") as audio_file:
                        transcript = client_openai.audio.transcriptions.create(
                            model="whisper-1",  # Usar whisper-1 como modelo estándar
                            file=audio_file,
                            language="es"
                        )
                    user_input = transcript.text
                except Exception as api_error:
                    error_msg = str(api_error)
                    # Verificar si es un error de API key
                    if "401" in error_msg or "invalid_api_key" in error_msg.lower() or "Incorrect API key" in error_msg:
                        st.error("❌ **Error: API Key de OpenAI inválida o expirada**")
                        st.info("""
                        **💡 Solución:**
                        1. Verifica que tu API key de OpenAI sea válida
                        2. Puedes obtener una nueva clave en: https://platform.openai.com/account/api-keys
                        3. Actualiza el archivo `.env` con tu nueva clave:
                           ```
                           OPENAI_API_KEY=tu_nueva_clave_aqui
                           ```
                        4. Reinicia la aplicación
                        """)
                        # Limpiar archivo temporal antes de salir
                        if os.path.exists(audio_path):
                            os.unlink(audio_path)
                        raise
                    else:
                        # Otro tipo de error
                        raise
            else:
                st.error("❌ **API Key de OpenAI no configurada**")
                st.info("""
                **💡 Para habilitar la transcripción de audio:**
                1. Obtén tu API key en: https://platform.openai.com/account/api-keys
                2. Agrega la clave al archivo `.env`:
                   ```
                   OPENAI_API_KEY=tu_clave_aqui
                   ```
                3. Reinicia la aplicación
                """)
        
        # Limpiar archivo temporal
        if os.path.exists(audio_path):
            os.unlink(audio_path)
        
    except Exception as e:
        # Solo mostrar error genérico si no se mostró un error específico arriba
        error_msg = str(e)
        if "401" not in error_msg and "invalid_api_key" not in error_msg.lower():
            st.error(f"❌ Error al transcribir audio: {e}")
            st.info("💡 Tip: Asegúrate de tener permisos de micrófono y que el audio esté en formato compatible.")

# Obtener nueva entrada del usuario (texto o voz)
if user_input:
    # Mostrar y guardar el mensaje del usuario
    st.session_state.cetes_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        # 1. Generar prompt del sistema con pronósticos actualizados
        system_prompt = generar_system_prompt_con_pronosticos()
        
        # 2. Preparar el historial para la API
        messages_for_api = [{"role": "system", "content": system_prompt}]
        for msg in st.session_state.cetes_messages:
            messages_for_api.append({"role": msg["role"], "content": msg["content"]})

        # 2. Llamar a la API de OpenAI
        if client_openai:
            with st.spinner("Pensando..."):
                response = client_openai.chat.completions.create(
                    model="gpt-5.1",
                    messages=messages_for_api
                )
                assistant_response = response.choices[0].message.content
        else:
            st.error("❌ API Key de OpenAI no configurada")
            assistant_response = "Lo siento, no tengo acceso a la API de OpenAI en este momento."
        
        # 3. Mostrar y guardar la respuesta del modelo
        with st.chat_message("assistant"):
            st.markdown(assistant_response)
        
        # 4. Generar audio TTS siempre activo
        audio_bytes = None
        if client_openai:
            try:
                with st.spinner("🔊 Generando audio..."):
                    # Generar audio usando OpenAI TTS
                    tts_response = client_openai.audio.speech.create(
                        model="tts-1",  # Usar modelo TTS estándar
                        voice="shimmer",
                        input=assistant_response,
                        speed=1.25
                    )
                    audio_bytes = tts_response.content
                
                # Reproducir audio con velocidad 1.25
                st.markdown(audio_player_with_speed(audio_bytes, 1.25), unsafe_allow_html=True)
        
            except Exception as e:
                st.warning(f"⚠️ No se pudo generar audio: {e}")
        
        # Guardar mensaje con audio si existe
        message_to_save = {"role": "assistant", "content": assistant_response}
        if audio_bytes:
            message_to_save["audio_bytes"] = audio_bytes
        st.session_state.cetes_messages.append(message_to_save)

    except Exception as e:
        st.error(f"Error al generar respuesta: {e}")
