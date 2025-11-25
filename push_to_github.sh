#!/bin/bash
# Script para hacer push a GitHub usando token de acceso personal

echo "🚀 Configurando push a GitHub..."
echo ""
echo "Si aún no tienes un token de acceso personal:"
echo "1. Ve a: https://github.com/settings/tokens"
echo "2. Clic en 'Generate new token' > 'Generate new token (classic)'"
echo "3. Nombre: 'Mi Asesor CETES'"
echo "4. Selecciona scope: 'repo' (todos los permisos)"
echo "5. Genera y copia el token"
echo ""
read -p "¿Ya tienes el token? (s/n): " tiene_token

if [ "$tiene_token" != "s" ] && [ "$tiene_token" != "S" ]; then
    echo "Por favor, genera el token primero y luego ejecuta este script de nuevo."
    exit 1
fi

read -sp "Pega tu token de acceso personal: " GITHUB_TOKEN
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: No se proporcionó el token"
    exit 1
fi

# Configurar el remote con el token
echo "🔧 Configurando remote con token..."
git remote set-url origin https://${GITHUB_TOKEN}@github.com/Vazqmi02/Proyecto-MiAsesorCETES.git

# Verificar que se configuró correctamente
echo "✅ Remote configurado"
echo ""

# Hacer push (force push porque es una versión nueva)
read -p "¿Hacer force push? (Esto reemplazará el contenido remoto) (s/n): " hacer_force

if [ "$hacer_force" == "s" ] || [ "$hacer_force" == "S" ]; then
    echo "📤 Haciendo force push..."
    git push -u origin main --force
else
    echo "📤 Haciendo push normal..."
    git push -u origin main
fi

echo ""
echo "✅ ¡Listo! Verifica en: https://github.com/Vazqmi02/Proyecto-MiAsesorCETES"

