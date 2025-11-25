# Instrucciones para subir a GitHub

## Pasos para subir el proyecto a GitHub

### 1. Crear el repositorio en GitHub

1. Ve a https://github.com/Vazqmi02
2. Haz clic en "New repository" o "Nuevo repositorio"
3. Nombre del repositorio: `Proyecto-MiAsesorCETES`
4. Descripción: "Chatbot experto en CETES con pronósticos SARIMAX y análisis de datos de Banxico"
5. Elige si quieres que sea público o privado
6. **NO** inicialices con README, .gitignore o licencia (ya los tenemos)
7. Haz clic en "Create repository"

### 2. Conectar el repositorio local con GitHub

Ejecuta estos comandos en la terminal (reemplaza `TU_USUARIO` con tu usuario de GitHub si es diferente):

```bash
cd /home/vazqmi01/Proyecto-MiAsesorCETES

# Agregar el repositorio remoto
git remote add origin https://github.com/Vazqmi02/Proyecto-MiAsesorCETES.git

# Verificar que se agregó correctamente
git remote -v
```

### 3. Subir el código

```bash
# Subir el código a GitHub
git push -u origin main
```

Si te pide autenticación, puedes usar:
- Tu token de acceso personal de GitHub (recomendado)
- O configurar SSH keys

### 4. Verificar

Ve a https://github.com/Vazqmi02/Proyecto-MiAsesorCETES y verifica que todos los archivos estén ahí.

## Notas importantes

- El archivo `.env` NO se subirá a GitHub (está en .gitignore)
- El archivo `.env.example` SÍ se subirá para que otros sepan qué variables necesitan
- El directorio `venv/` NO se subirá (está en .gitignore)
- Los archivos `__pycache__/` NO se subirán (están en .gitignore)

## Comandos útiles para futuras actualizaciones

```bash
# Ver qué archivos han cambiado
git status

# Agregar cambios
git add .

# Hacer commit
git commit -m "Descripción de los cambios"

# Subir cambios
git push
```

