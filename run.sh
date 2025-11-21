#!/bin/bash

# Script para ejecutar la aplicación Streamlit

# Activar el entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Entorno virtual activado"
else
    echo "Creando entorno virtual..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Instalando dependencias..."
    pip install -r requirements.txt
fi

# Ejecutar la aplicación
streamlit run main.py

