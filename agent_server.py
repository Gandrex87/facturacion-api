import os
import psycopg
from psycopg.rows import dict_row
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Optional

from datetime import datetime

# Cargar variables de entorno
load_dotenv()

# Inicializar el servidor MCP
mcp = FastMCP("Agente Inmobiliario Billing")

# --- CONEXIÓN A BASE DE DATOS ---
def get_db_connection():
    try:
        conn = psycopg.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            row_factory=dict_row,
            connect_timeout=5
        )
        return conn
    except Exception as e:
        raise RuntimeError(f"Error conectando a la BD: {e}")

# --- SIMULACIÓN DE SEGURIDAD (CONTEXTO) ---
CURRENT_AGENT_CIF = os.getenv("TEST_AGENT_CIF")


# --- FUNCIÓN DE VALIDACIÓN ---
def validar_fecha(fecha_str: str) -> bool:
    """Valida que la fecha tenga formato YYYY-MM-DD"""
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

# --- HERRAMIENTA 1: CONSULTAS GENERALES (MEJORADA) ---
@mcp.tool()
def consultar_mis_facturas(
    estado: Optional[str] = None, 
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    limit: int = 5
) -> str:
    """
    Consulta el listado de facturas generales.
    Args:
        estado: 'PENDIENTE' o 'PAGADA'.
        fecha_inicio: Fecha mínima 'YYYY-MM-DD' (ej: '2024-11-01').
        fecha_fin: Fecha máxima 'YYYY-MM-DD' (ej: '2024-11-30').
        limit: Max resultados (default 5).
    
    Ejemplos de uso:
        - Facturas pagadas de noviembre: estado='PAGADA', fecha_inicio='2024-11-01', fecha_fin='2024-11-30'
        - Facturas desde octubre: fecha_inicio='2024-10-01'
        - Últimas 10 facturas: limit=10
    """
    # Validación de estado
    if estado and estado not in ['PENDIENTE', 'PAGADA']:
        return "Error: Estado inválido. Usa 'PENDIENTE' o 'PAGADA'."

    # Validación de fechas
    if fecha_inicio and not validar_fecha(fecha_inicio):
        return "Error: Formato de fecha_inicio inválido. Usa 'YYYY-MM-DD' (ej: 2024-11-01)."
    
    if fecha_fin and not validar_fecha(fecha_fin):
        return "Error: Formato de fecha_fin inválido. Usa 'YYYY-MM-DD' (ej: 2024-11-30)."
    
    # Validación de lógica de rango
    if fecha_inicio and fecha_fin:
        if fecha_inicio > fecha_fin:
            return "Error: La fecha_inicio no puede ser posterior a fecha_fin."

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT numero_factura, estado_legible, fecha_emision, 
                           moneda, total
                    FROM view_ai_facturas
                    WHERE emisor_cif = %s 
                """
                params = [CURRENT_AGENT_CIF]

                if estado:
                    query += " AND estado_legible = %s"
                    params.append(estado)
                
                if fecha_inicio:
                    query += " AND fecha_emision >= %s"
                    params.append(fecha_inicio)
                
                if fecha_fin:
                    query += " AND fecha_emision <= %s"
                    params.append(fecha_fin)

                query += " ORDER BY fecha_emision DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                rows = cur.fetchall()

                if not rows:
                    return "No se encontraron facturas con esos criterios."

                # Construir respuesta más informativa
                resultado = f"Encontré {len(rows)} factura(s)"
                
                # Añadir contexto de los filtros aplicados
                filtros = []
                if estado:
                    filtros.append(f"estado: {estado}")
                if fecha_inicio and fecha_fin:
                    filtros.append(f"periodo: {fecha_inicio} a {fecha_fin}")
                elif fecha_inicio:
                    filtros.append(f"desde: {fecha_inicio}")
                elif fecha_fin:
                    filtros.append(f"hasta: {fecha_fin}")
                
                if filtros:
                    resultado += f" ({', '.join(filtros)})"
                resultado += ":\n\n"

                for row in rows:
                    resultado += (
                        f"- Factura {row['numero_factura']} ({row['estado_legible']}): "
                        f"{row['total']} {row['moneda']}. "
                        f"Fecha: {row['fecha_emision']}\n"
                    )
                return resultado

    except Exception as e:
        return f"Error en sistema de facturación: {str(e)}"

# --- HERRAMIENTA 2: BÚSQUEDA SEMÁNTICA/DIFUSA ---
@mcp.tool()
def buscar_factura_por_propiedad(query_direccion: str) -> str:
    """
    Busca facturas por dirección o nombre de calle, tolerando errores ortográficos.
    Úsalo cuando el usuario pregunte por una propiedad específica.
    
    Args:
        query_direccion: Texto de búsqueda (ej: 'Calle Velazquez', 'Ricard Vicent').
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Lógica 'Creed': Usamos pg_trgm para ordenar por similitud
                # El umbral 0.3 filtra resultados que no se parecen en nada
                query = """
                    SELECT 
                        numero_factura, 
                        estado_legible, 
                        total, 
                        moneda,
                        emisor_direccion_calle,
                        similarity(emisor_direccion_calle, %s) as score
                    FROM view_ai_facturas
                    WHERE emisor_cif = %s 
                    AND emisor_direccion_calle %% %s  -- <--- AQUÍ ESTÁ EL CAMBIO (%%)
                    ORDER BY score DESC
                    LIMIT 3;
                """
                # Pasamos la query dos veces: una para calcular score, otra para filtrar
                params = [query_direccion, CURRENT_AGENT_CIF, query_direccion]
                
                cur.execute(query, params)
                rows = cur.fetchall()

                if not rows:
                    return f"No encontré ninguna factura relacionada con la dirección '{query_direccion}'."

                resultado = f"Resultados para '{query_direccion}':\n"
                for row in rows:
                    # Mostramos la dirección real encontrada para que el Agente confirme
                    resultado += (
                        f"- [Coincidencia: {int(row['score']*100)}%] "
                        f"Propiedad: '{row['emisor_direccion_calle']}' -> "
                        f"Factura {row['numero_factura']} ({row['estado_legible']}): "
                        f"{row['total']} {row['moneda']}.\n"
                    )
                return resultado

    except Exception as e:
        return f"Error buscando propiedad: {str(e)}"

if __name__ == "__main__":
    mcp.run()