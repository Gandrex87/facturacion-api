import os
import psycopg
from psycopg.rows import dict_row
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# --- CONFIGURACIÓN MCP PARA SSE (Server-Sent Events) ---
# Esto crea un servidor web compatible con n8n
mcp = FastMCP("Agente Inmobiliario Billing")

# --- CONEXIÓN BD Y RESOLUCIÓN DE IDENTIDAD ---
def get_db_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        row_factory=dict_row
    )

def resolve_cif_from_email(email: str, conn) -> str:
    """Gatekeeper: Traduce Email -> CIF y valida acceso."""
    with conn.cursor() as cur:
        cur.execute("SELECT cif FROM contacto_agentes WHERE LOWER(email) = LOWER(%s)", [email])
        result = cur.fetchone()
        if not result:
            raise ValueError(f"ACCESO DENEGADO: El email {email} no está autorizado.")
        return result['cif']

# --- HERRAMIENTA 1: CONSULTAR FACTURAS ---
@mcp.tool()
def consultar_mis_facturas(
    email_agente: str,  # <--- n8n inyectará esto
    estado: Optional[str] = None, 
    fecha_inicio: Optional[str] = None, 
    limit: int = 5
) -> str:
    """
    Consulta facturas. 
    IMPORTANTE: 'email_agente' debe ser provisto por el sistema, no por el usuario.
    """
    if estado and estado not in ['PENDIENTE', 'PAGADA']:
        return "Error: Estado inválido."

    try:
        with get_db_connection() as conn:
            real_cif = resolve_cif_from_email(email_agente, conn)
            
            with conn.cursor() as cur:
                query = """
                    SELECT numero_factura, estado_legible, fecha_emision, moneda, total
                    FROM view_ai_facturas
                    WHERE emisor_cif = %s 
                """
                params = [real_cif]

                if estado:
                    query += " AND estado_legible = %s"
                    params.append(estado)
                if fecha_inicio:
                    query += " AND fecha_emision >= %s"
                    params.append(fecha_inicio)
                
                query += " ORDER BY fecha_emision DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                rows = cur.fetchall()
                
                if not rows: return "No se encontraron facturas."
                return str(rows) # MCP maneja el string resultante

    except Exception as e:
        return f"Error del sistema: {str(e)}"

# --- HERRAMIENTA 2: BÚSQUEDA DIFUSA ---
@mcp.tool()
def buscar_factura_por_propiedad(
    email_agente: str, # <--- n8n inyectará esto
    query_direccion: str
) -> str:
    """Busca facturas por dirección aproximada."""
    try:
        with get_db_connection() as conn:
            real_cif = resolve_cif_from_email(email_agente, conn)
            
            with conn.cursor() as cur:
                query = """
                    SELECT numero_factura, estado_legible, total, moneda, 
                           emisor_direccion_calle,
                           similarity(emisor_direccion_calle, %s) as score
                    FROM view_ai_facturas
                    WHERE emisor_cif = %s 
                    AND emisor_direccion_calle %% %s 
                    ORDER BY score DESC LIMIT 3;
                """
                params = [query_direccion, real_cif, query_direccion]
                cur.execute(query, params)
                rows = cur.fetchall()
                
                if not rows: return "No se encontró nada."
                return str(rows)

    except Exception as e:
        return f"Error: {str(e)}"

# --- EL COMANDO DE EJECUCIÓN CAMBIA ---
# FastMCP ya trae un servidor web incluido para SSE
# --- INICIO DE SERVIDOR CORREGIDO ---
if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Iniciando Servidor MCP en 0.0.0.0:8000 (Modo SSE)...")
    
    # TRUCO: Accedemos a la aplicación Starlette interna de FastMCP (_sse_app)
    # y la ejecutamos manualmente con uvicorn para tener control total de la IP.
    uvicorn.run(mcp.sse_app, host="0.0.0.0", port=8000)