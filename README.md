# Lanzador de Procesos y Ejecutables

Aplicación gráfica Windows en Python (Tkinter / ttk) para la gestión y ejecución de scripts, comandos de consola y programas externos según acciones definidas dinámicamente en ficheros JSON.

## Características Principales

- **Filtro por Categorías / Temas:** Agrupa y filtra las acciones disponibles por categorías (por ejemplo: `GPS`, `Multimedia`, `Otros`).
- **Visualización del Título Completo:** Muestra de forma destacada el nombre completo de la acción seleccionada con ajuste de texto automático.
- **Parámetros Dinámicos:** Genera los campos de entrada requeridos según los parámetros configurados para cada acción (con soporte para selector gráfico de archivos/carpetas y botones de ayuda/ejemplos).
- **Historial de Ejecuciones:** Guarda y permite restaurar los últimos parámetros ejecutados por cada acción.
- **Salida / Consola Integrada:** Muestra los resultados de ejecución (`stdout`, `stderr` y códigos de retorno) en tiempo real en una consola integrada.
- **Interfaz Moderna:** Diseño estructurado, limpio y adaptable con estilos `ttk`.

---

## Estructura de Ficheros y Configuración

Para el correcto funcionamiento de la aplicación, los ficheros deben organizarse según la siguiente estructura:

### 1. Ubicación del Ejecutable y `config.json`
El ejecutable (`Lanzador ejecutables.exe` o script `.py`) y el archivo `config.json` deben encontrarse **en la misma carpeta raíz**.

#### Configuración de `config.json`:
El fichero `config.json` define la ruta absoluta (`APP_DIR`) donde se encuentran los ficheros de datos y acciones:

```json
{
  "APP_DIR": "C:\\Ruta\\A\\Tu\\CarpetaDeDatos"
}
```

### 2. Ubicación de los Ficheros de Datos (`APP_DIR`)
En la carpeta especificada en `APP_DIR` deben residir los siguientes ficheros JSON:

- **`actions.json`**: Define las acciones, categoría, ejecutable a lanzar, argumentos y parámetros dinámicos.
- **`help.json`**: Contiene los textos de ayuda detallados asociados a cada ID de acción.
- **`history.json`**: Fichero generado automáticamente con el historial de las últimas ejecuciones por acción.

---

## Ejemplo de Estructura de Carpetas

```text
[Carpeta del Ejecutable]
 ├── Lanzador ejecutables.exe
 └── config.json

[Carpeta de Datos / APP_DIR (ej. C:\Data\Lanzador-ejecutables)]
 ├── actions.json
 ├── help.json
 └── history.json
```

---

## Cómo Crear el Ejecutable (`.exe`)

Para compilar el programa Python en un archivo ejecutable independiente para Windows, se utiliza **PyInstaller**.

### Pasos para compilar:

1. **Instalar PyInstaller** (si no está instalado):
   ```bash
   pip install pyinstaller
   ```

2. **Generar el ejecutable sin consola auxiliar (modo GUI):**
   ```bash
   pyinstaller --noconfirm --onedir --windowed --name "Lanzador ejecutables" "Lanzador ejecutables.py"
   ```

3. **Ubicación del resultado:**
   El ejecutable compilado se generará dentro de la subcarpeta `dist/Lanzador ejecutables/Lanzador ejecutables.exe` (o `dist/Lanzador ejecutables.exe` si se usa la opción `--onefile`).

4. **Despliegue:**
   Copia el archivo `config.json` a la misma carpeta donde sitúes el ejecutable generado.
