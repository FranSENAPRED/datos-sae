# Actualización automática de datos SAE

Este repositorio descarga el archivo SAE desde SharePoint, procesa sus registros
y actualiza `Datos_SAE_filtrado.csv` automáticamente cada 15 minutos mediante
GitHub Actions.

## Archivos

- `scraping2.py`: descarga, transforma y filtra los datos.
- `requirements.txt`: dependencias de Python.
- `.github/workflows/actualizar-datos.yml`: automatización programada.
- `.gitignore`: evita publicar archivos temporales.

## Configuración

### 1. Crear el repositorio

1. Ingresar a GitHub y seleccionar **New repository**.
2. Escribir un nombre, por ejemplo `datos-sae`.
3. Elegir si será público o privado.
4. No marcar la creación automática de README, `.gitignore` o licencia.
5. Seleccionar **Create repository**.

### 2. Subir los archivos

1. Descomprimir el paquete entregado.
2. En el repositorio, seleccionar **Add file > Upload files**.
3. Arrastrar todos los archivos y carpetas descomprimidos.
4. Verificar que también se haya incorporado:
   `.github/workflows/actualizar-datos.yml`.
5. Seleccionar **Commit changes**.

> GitHub puede ocultar visualmente la carpeta `.github` en algunos selectores,
> pero debe conservarse su estructura exacta.

### 3. Configurar el enlace de SharePoint

1. Abrir **Settings** en el repositorio.
2. Seleccionar **Secrets and variables > Actions**.
3. Presionar **New repository secret**.
4. En **Name**, escribir exactamente `SOURCE_URL`.
5. En **Secret**, pegar el enlace completo de descarga de SharePoint.
6. Presionar **Add secret**.

El enlace no debe escribirse dentro del script ni publicarse en el README.

### 4. Permitir la actualización del CSV

1. En **Settings**, abrir **Actions > General**.
2. Bajar hasta **Workflow permissions**.
3. Seleccionar **Read and write permissions**.
4. Guardar con **Save**.

El flujo también solicita únicamente el permiso `contents: write`.

### 5. Realizar la primera prueba

1. Abrir la pestaña **Actions**.
2. Seleccionar **Actualizar datos SAE**.
3. Presionar **Run workflow** y nuevamente **Run workflow**.
4. Esperar que la ejecución muestre un indicador verde.
5. Volver a **Code** y comprobar que exista
   `Datos_SAE_filtrado.csv`.

Después de la prueba, GitHub ejecutará el proceso en los minutos 07, 22, 37 y
52 de cada hora. Son intervalos de 15 minutos; GitHub puede iniciar una
ejecución con algunos minutos de retraso.

## Dirección del CSV

En un repositorio público, la dirección directa tendrá esta estructura:

```text
https://raw.githubusercontent.com/USUARIO/REPOSITORIO/main/Datos_SAE_filtrado.csv
```

Hay que reemplazar `USUARIO` y `REPOSITORIO` por los valores reales. Un visor
web público no podrá leer directamente el archivo desde un repositorio privado
sin autenticación.

## Solución de problemas

- **Falta SOURCE_URL**: revisar que el secreto tenga exactamente ese nombre.
- **Error 401 o 403**: regenerar el enlace de SharePoint o revisar sus permisos.
- **Error al hacer push**: comprobar `Workflow permissions` y las reglas de
  protección de la rama principal.
- **No aparece el flujo en Actions**: comprobar la ruta exacta
  `.github/workflows/actualizar-datos.yml`.
- **El CSV no cambia**: esto es normal cuando la fuente no contiene registros
  nuevos; el flujo evita crear commits innecesarios.

## Ejecución local opcional

En Windows PowerShell:

```powershell
python -m pip install -r requirements.txt
$env:SOURCE_URL = "ENLACE_DE_DESCARGA"
python scraping2.py
```

No se debe guardar el enlace real en archivos que se subirán al repositorio.
