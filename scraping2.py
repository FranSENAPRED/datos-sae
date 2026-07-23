import os
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
import requests

# =========================
# Configuración
# =========================
# En GitHub, SOURCE_URL se configura como un secreto del repositorio.
# Para una ejecución local también puede definirse como variable de entorno.
URL = os.getenv("SOURCE_URL", "").strip()

# Por defecto, los archivos se generan junto a este script. OUTPUT_DIR permite
# cambiar la carpeta de salida durante una ejecución local o automatizada.
DESTINO = Path(
    os.getenv("OUTPUT_DIR", str(Path(__file__).resolve().parent))
).expanduser().resolve()
ARCHIVO_DESCARGA = "Datos_SAE.xls"           # Se reemplaza siempre (aunque sea CSV)
ARCHIVO_SALIDA = "Datos_SAE_filtrado.csv"    # Salida final CSV multiamenaza

# Nombres de columnas según el archivo de origen
COL_FECHA = "Fecha del mensaje"  # Serial Excel, ej. 46007
COL_HORA = "Hora"                # Fracción de día, ej. 0.7472222
COL_EVENTO = "Evento"            # Ej. Incendio Forestal, Inundación

# Clasificación de eventos SAE.
# Las claves deben escribirse normalizadas: minúsculas y sin tildes.
CLASIFICACION_EVENTOS = {
    "incendio forestal": {
        "Amenaza": "Incendios Forestales",
        "Variable_amenaza": "Incendio Forestal",
    },
    "incendios forestales": {
        "Amenaza": "Incendios Forestales",
        "Variable_amenaza": "Incendio Forestal",
    },
    "inundacion": {
        "Amenaza": "Meteorológica",
        "Variable_amenaza": "Inundación",
    },
    "inundaciones": {
        "Amenaza": "Meteorológica",
        "Variable_amenaza": "Inundación",
    },
    "remocion en masa": {
        "Amenaza": "Meteorológica",
        "Variable_amenaza": "Remoción en masa",
    },
    "remociones en masa": {
        "Amenaza": "Meteorológica",
        "Variable_amenaza": "Remoción en masa",
    },
}

# Periodos de análisis por amenaza. Las fechas FIN_EXCLUSIVA no se incluyen.
# Incendios Forestales: desde 01-06-2026 hasta antes del 01-07-2027.
FECHA_INICIO_INCENDIOS = pd.Timestamp("2026-06-01")
FECHA_FIN_EXCLUSIVA_INCENDIOS = pd.Timestamp("2027-07-01")

# Meteorológica: desde 01-05-2026 hasta antes del 31-12-2026.
FECHA_INICIO_METEOROLOGICA = pd.Timestamp("2026-05-01")
FECHA_FIN_EXCLUSIVA_METEOROLOGICA = pd.Timestamp("2026-12-31")

TIMEOUT = 60


# =========================
# Descarga segura con reemplazo
# =========================
def descargar_y_reemplazar(url: str, carpeta: Path, nombre: str) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    final_path = carpeta / nombre
    tmp_path = carpeta / f"{nombre}.tmp"

    try:
        with requests.get(
            url,
            stream=True,
            timeout=TIMEOUT,
            allow_redirects=True,
        ) as respuesta:
            respuesta.raise_for_status()
            with open(tmp_path, "wb") as archivo:
                for chunk in respuesta.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        archivo.write(chunk)

        os.replace(tmp_path, final_path)
        return final_path
        
    except requests.RequestException:
        # Evita mostrar la URL protegida en los registros de GitHub Actions.
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(
            "No fue posible descargar el archivo de origen."
        ) from None
    
    except Exception:
        # Evita dejar un archivo temporal incompleto si falla la descarga.
        if tmp_path.exists():
            tmp_path.unlink()
        raise


# =========================
# Normalización y conversión
# =========================
def normalizar_texto(valor) -> str:
    """
    Convierte un texto a minúsculas, elimina tildes y normaliza espacios.

    Ejemplos:
        "  Remoción EN masa " -> "remocion en masa"
        "INUNDACIÓN"          -> "inundacion"
    """
    if pd.isna(valor):
        return ""

    texto = " ".join(str(valor).strip().lower().split())
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def fraccion_dia_a_segundos(valor):
    """
    Convierte una fracción de día (0..1) a segundos enteros usando Decimal.
    Evita errores de precisión como 17:55:59.999999998.
    """
    if pd.isna(valor):
        return None

    if isinstance(valor, str):
        valor = valor.strip().replace(",", ".")

    try:
        fraccion = Decimal(str(valor))
        segundos = (fraccion * Decimal("86400")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        return int(segundos)
    except (ValueError, TypeError, ArithmeticError):
        return None


def excel_serial_a_fecha(serie: pd.Series) -> pd.Series:
    """
    Convierte un serial Excel, con base 1899-12-30, a fecha.
    Ejemplo: 46007 -> 2025-12-16.
    """
    valores = pd.to_numeric(serie, errors="coerce")
    return pd.to_datetime(valores, unit="D", origin="1899-12-30", errors="coerce")


def clasificar_eventos(df: pd.DataFrame) -> pd.DataFrame:
    """Añade las columnas Amenaza y Variable_amenaza según el campo Evento."""
    resultado = df.copy()
    resultado["_evento_normalizado"] = resultado[COL_EVENTO].apply(normalizar_texto)

    resultado["Amenaza"] = resultado["_evento_normalizado"].map(
        lambda evento: CLASIFICACION_EVENTOS.get(evento, {}).get("Amenaza")
    )
    resultado["Variable_amenaza"] = resultado["_evento_normalizado"].map(
        lambda evento: CLASIFICACION_EVENTOS.get(evento, {}).get("Variable_amenaza")
    )

    return resultado


# =========================
# Proceso principal
# =========================
def main() -> None:
    if not URL:
        raise RuntimeError(
            "No se encontró la variable de entorno SOURCE_URL. "
            "Configúrala con el enlace de descarga del archivo de origen."
        )

    # 1) Descargar archivo fuente
    ruta = descargar_y_reemplazar(URL, DESTINO, ARCHIVO_DESCARGA)
    print(f"OK descarga: {ruta}")

    # 2) Leer como CSV: el archivo es texto con BOM aunque use extensión .xls
    df = pd.read_csv(ruta, encoding="utf-8-sig")

    # 3) Validar columnas mínimas
    columnas_requeridas = [COL_FECHA, COL_HORA, COL_EVENTO]
    faltantes = [columna for columna in columnas_requeridas if columna not in df.columns]
    if faltantes:
        raise ValueError(
            f"Faltan columnas requeridas: {faltantes}\n"
            f"Columnas disponibles: {list(df.columns)}"
        )

    # 4) Normalizar campos vacíos: "" o espacios -> NA
    df = df.replace(r"^\s*$", pd.NA, regex=True)

    # 5) Construir fecha y hora real del mensaje
    df["Fecha_dt"] = excel_serial_a_fecha(df[COL_FECHA])
    segundos = df[COL_HORA].apply(fraccion_dia_a_segundos)
    df["FechaHora_del_mensaje"] = df["Fecha_dt"] + pd.to_timedelta(
        segundos,
        unit="s",
        errors="coerce",
    )

    # 6) Clasificar eventos en las dos amenazas definidas
    df = clasificar_eventos(df)

    # 7) Aplicar el periodo correspondiente a cada amenaza
    mask_incendios = (
        df["Amenaza"].eq("Incendios Forestales")
        & (df["FechaHora_del_mensaje"] >= FECHA_INICIO_INCENDIOS)
        & (df["FechaHora_del_mensaje"] < FECHA_FIN_EXCLUSIVA_INCENDIOS)
    )

    mask_meteorologica = (
        df["Amenaza"].eq("Meteorológica")
        & (df["FechaHora_del_mensaje"] >= FECHA_INICIO_METEOROLOGICA)
        & (df["FechaHora_del_mensaje"] < FECHA_FIN_EXCLUSIVA_METEOROLOGICA)
    )

    df_filtrado = df.loc[mask_incendios | mask_meteorologica].copy()

    # 8) Eliminar registros incompletos, manteniendo el comportamiento original
    df_filtrado = df_filtrado.dropna(how="any")

    # 9) Crear campos útiles para visualización
    df_filtrado["Fecha_real"] = df_filtrado["FechaHora_del_mensaje"].dt.strftime(
        "%d/%m/%Y"
    )
    df_filtrado["Hora_real"] = df_filtrado["FechaHora_del_mensaje"].dt.strftime(
        "%H:%M"
    )

    # Orden cronológico y eliminación de columna auxiliar interna
    df_filtrado = df_filtrado.sort_values("FechaHora_del_mensaje")
    df_filtrado = df_filtrado.drop(columns=["_evento_normalizado"])

    # 10) Guardar CSV final
    salida = DESTINO / ARCHIVO_SALIDA
    df_filtrado.to_csv(salida, index=False, encoding="utf-8-sig")

    print(f"OK salida CSV: {salida}")
    print(f"Filas salida (periodos por amenaza + completas): {len(df_filtrado):,}")
    print(
        "Periodo Incendios Forestales: "
        f"{FECHA_INICIO_INCENDIOS.date()} a "
        f"{FECHA_FIN_EXCLUSIVA_INCENDIOS.date()} (fin exclusivo)"
    )
    print(
        "Periodo Meteorológica: "
        f"{FECHA_INICIO_METEOROLOGICA.date()} a "
        f"{FECHA_FIN_EXCLUSIVA_METEOROLOGICA.date()} (fin exclusivo)"
    )

    if not df_filtrado.empty:
        resumen = (
            df_filtrado.groupby(["Amenaza", "Variable_amenaza"])
            .size()
            .reset_index(name="Cantidad")
            .sort_values(["Amenaza", "Variable_amenaza"])
        )
        print("\nResumen de registros exportados:")
        print(resumen.to_string(index=False))
    else:
        print("ADVERTENCIA: no se encontraron registros para el periodo y eventos definidos.")


if __name__ == "__main__":
    main()
