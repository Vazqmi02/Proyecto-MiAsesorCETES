import io
import streamlit as st

from utils.common import (
    client_openai,
    audio_player_with_speed,
    obtener_resumen_pronosticos_sarimax,
    obtener_datos_banxico, generar_todos_los_pronosticos
)
from prompts import cetes_prompt, generar_seccion_pronosticos

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
                            st.warning(f"⚠️ No se pudieron generar los pronósticos: {str(pronostico_error)}")
                            st.session_state.pronosticos_generados = None
                            st.session_state.pronosticos_listos = False
                else:
                    st.session_state.pronosticos_generados = None
                    st.session_state.df_banxico = None
                    st.session_state.pronosticos_listos = False
        except Exception as e:
            # Manejo de error general
            st.error(f"❌ Error al cargar datos: {str(e)}")
            st.session_state.pronosticos_generados = None
            st.session_state.df_banxico = None
            st.session_state.pronosticos_listos = False
        finally:
            st.session_state.cargando_datos = False

# Generar prompt del sistema con pronósticos
def generar_system_prompt_con_pronosticos():
    """Genera el prompt del sistema incluyendo los pronósticos SARIMAX desde session_state"""
    # Usar pronósticos generados al inicio de la aplicación
    pronosticos_dict = st.session_state.get('pronosticos_generados', None)
    
    max_semanas = 13  # Default
    resumen_pronosticos = None
    
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
    
    # Construir el prompt completo usando la función de prompts.py
    prompt_completo = cetes_prompt
    prompt_completo += generar_seccion_pronosticos(resumen_pronosticos, max_semanas)
    
    return prompt_completo

# --- Lógica del Chatbot ---

# Sidebar con configuración y entrada de audio
with st.sidebar:
    st.subheader("🎤 Entrada de Audio")
    # Verificar si st.audio_input está disponible (requiere Streamlit >= 1.29.0)
    # Manejo robusto para Streamlit Cloud y entornos locales
    audio_value = None
    send_audio = False
    
    # Inicializar en session_state si no existe (para evitar errores)
    if 'audio_input_available' not in st.session_state:
        st.session_state.audio_input_available = False
        try:
            # Verificar si el método existe
            if hasattr(st, 'audio_input'):
                st.session_state.audio_input_available = True
        except:
            st.session_state.audio_input_available = False
    
    # Intentar usar audio_input solo si está disponible
    if st.session_state.audio_input_available:
        try:
            audio_value = st.audio_input("Graba un mensaje de voz (opcional)")
            send_audio = st.button("Enviar audio", key="send_audio_button", use_container_width=True)
        except Exception as e:
            # Si falla, deshabilitar para evitar errores repetidos
            st.session_state.audio_input_available = False
            st.warning("⚠️ La entrada de audio no está disponible en este entorno.")
            st.caption("💡 Usa la entrada de texto en su lugar.")
            audio_value = None
            send_audio = False
    else:
        # Mostrar mensaje solo la primera vez, no en cada recarga
        if 'audio_input_message_shown' not in st.session_state:
            st.info("💡 La entrada de audio no está disponible. Usa la entrada de texto.")
            st.session_state.audio_input_message_shown = True
    
    st.divider()
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

# Sección de entrada de texto
user_input = st.chat_input("Escribe o graba un mensaje de voz, ¿Qué quieres saber sobre CETES?")

# Procesar entrada de texto o audio
user_prompt = None
user_display_content = None

# Priorizar entrada de texto
if user_input:
    user_prompt = user_input
    user_display_content = user_input
elif send_audio:
    # Procesar audio grabado
    raw_audio = None
    filename = None
    source = None
    
    if audio_value is not None:
        raw_audio = audio_value.getvalue()
        filename = audio_value.name or "voz_usuario.wav"
        source = "Audio grabado"
    
    if raw_audio:
        # Crear objeto de archivo para OpenAI
        audio_file = io.BytesIO(raw_audio)
        audio_file.name = filename or "voz_usuario.wav"
        
        # Transcribir audio usando OpenAI Whisper
        with st.spinner("🎤 Transcribiendo audio..."):
            if client_openai:
                try:
                    transcription = client_openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="es"
                    )
                    user_prompt = transcription.text.strip()
                    if user_prompt:
                        user_display_content = f"({source}) {user_prompt}" if source else user_prompt
                    else:
                        st.info("La transcripción no contiene texto interpretable. Intenta nuevamente.")
                except Exception as transcribe_error:
                    st.error(f"❌ Error al transcribir audio: {transcribe_error}")
                    st.info("💡 Tip: Si el problema persiste, intenta usar la entrada de texto.")
            else:
                st.error("❌ API Key de OpenAI no configurada para transcripción")
    else:
        st.warning("Graba un mensaje de voz antes de enviarlo.")

# Obtener nueva entrada del usuario (texto o voz)
if user_prompt:
    # Mostrar y guardar el mensaje del usuario
    st.session_state.cetes_messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_display_content or user_prompt)

    try:
        # 1. Generar prompt del sistema con pronósticos actualizados
        system_prompt = generar_system_prompt_con_pronosticos()
        
        # 2. Preparar el historial para la API
        messages_for_api = [{"role": "system", "content": system_prompt}]
        for msg in st.session_state.cetes_messages:
            messages_for_api.append({"role": msg["role"], "content": msg["content"]})

        # 2. Llamar a la API de OpenAI
        assistant_response = None
        if client_openai:
            try:
                with st.spinner("Pensando..."):
                    response = client_openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        temperature=0.7,
                        max_tokens=1000
                    )
                    if response and response.choices and len(response.choices) > 0:
                        assistant_response = response.choices[0].message.content
                    else:
                        assistant_response = "Lo siento, no recibí una respuesta válida de la API."
            except Exception as api_error:
                st.error(f"❌ Error al conectar con OpenAI: {str(api_error)}")
                assistant_response = "Lo siento, ocurrió un error al generar la respuesta. Por favor, intenta nuevamente."
        else:
            st.error("❌ API Key de OpenAI no configurada")
            assistant_response = "Lo siento, no tengo acceso a la API de OpenAI en este momento. Por favor, configura tu API key en Streamlit Cloud secrets o en las variables de entorno."
        
        if not assistant_response:
            assistant_response = "Lo siento, no pude generar una respuesta. Por favor, intenta nuevamente."
        
        # 3. Mostrar y guardar la respuesta del modelo
        if assistant_response:
            with st.chat_message("assistant"):
                st.markdown(assistant_response)
            
            # 4. Generar audio TTS (siempre intentar, pero no bloquear si falla)
            audio_bytes_response = None
            if client_openai and assistant_response:
                try:
                    with st.spinner("🔊 Generando audio..."):
                        # Generar audio usando OpenAI TTS (adaptado del código de referencia)
                        speech = client_openai.audio.speech.create(
                            model="tts-1",
                            voice="shimmer",
                            input=assistant_response,
                            speed=1.25
                        )
                        audio_bytes_response = speech.read()
                        
                        if audio_bytes_response:
                            # Reproducir audio (adaptado del código de referencia)
                            st.audio(audio_bytes_response, format="audio/mp3", autoplay=True)
                        else:
                            st.info("No se pudo obtener audio para esta respuesta.")
                
                except Exception as tts_error:
                    st.error(f"No se pudo generar la voz sintética: {tts_error}")
            
            # Guardar mensaje con audio si existe
            message_to_save = {"role": "assistant", "content": assistant_response}
            if audio_bytes_response:
                message_to_save["audio_bytes"] = audio_bytes_response
            st.session_state.cetes_messages.append(message_to_save)
        else:
            st.error("❌ No se pudo generar una respuesta. Por favor, intenta nuevamente.")

    except Exception as e:
        st.error(f"❌ Error al generar respuesta: {str(e)}")
        st.info("💡 Si el problema persiste, verifica tu conexión a internet y que las API keys estén configuradas correctamente.")
        # No agregar mensaje vacío al historial si hay un error