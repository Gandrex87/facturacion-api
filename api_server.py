
import os
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = FastAPI(
    title="Agente Inmobiliario API Gatekeeper",
    description="API para consulta de facturas de agentes inmobiliarios",
    version="1.0.0"
)

# --- FUNCIÓN DE VALIDACIÓN ---
def validar_fecha(fecha_str: str) -> bool:
    """Valida que la fecha tenga formato YYYY-MM-DD"""
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

# --- MODELOS DE DATOS (SCHEMA IS LAW) ---
class FacturasRequest(BaseModel):
    estado: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    limit: int = 5

class BusquedaRequest(BaseModel):
    query_direccion: str

# --- CONEXIÓN BD ---
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
        print(f"❌ Error DB: {e}")
        raise HTTPException(status_code=500, detail="Error de conexión con el sistema de facturación")

# --- HEALTH CHECK ---
@app.get("/health")
def health_check():
    """Endpoint para verificar que la API está funcionando"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "service": "facturacion-api"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

# --- ENDPOINT 1: CONSULTAR FACTURAS ---
@app.post("/tools/consultar-facturas")
def consultar_facturas(
    req: FacturasRequest, 
    x_agent_cif: str = Header(default=os.getenv("TEST_AGENT_CIF"))
):
    """
    Consulta facturas del agente con filtros opcionales.
    
    Args:
        req: Parámetros de búsqueda (estado, fechas, límite)
        x_agent_cif: CIF del agente (header HTTP)
    
    Returns:
        JSON con count, data y filtros aplicados
    """
    # Validación de estado
    if req.estado and req.estado not in ['PENDIENTE', 'PAGADA']:
        raise HTTPException(status_code=400, detail="Estado inválido. Usa 'PENDIENTE' o 'PAGADA'.")

    # Validaciones de fecha
    if req.fecha_inicio and not validar_fecha(req.fecha_inicio):
        raise HTTPException(status_code=400, detail="Formato de fecha_inicio inválido. Usa 'YYYY-MM-DD' (ej: 2024-11-01).")
    
    if req.fecha_fin and not validar_fecha(req.fecha_fin):
        raise HTTPException(status_code=400, detail="Formato de fecha_fin inválido. Usa 'YYYY-MM-DD' (ej: 2024-11-30).")
    
    # Validación de lógica de rango
    if req.fecha_inicio and req.fecha_fin and req.fecha_inicio > req.fecha_fin:
        raise HTTPException(status_code=400, detail="La fecha_inicio no puede ser posterior a fecha_fin.")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT numero_factura, estado_legible, fecha_emision, moneda, total
                    FROM view_ai_facturas
                    WHERE emisor_cif = %s 
                """
                params = [x_agent_cif]

                if req.estado:
                    query += " AND estado_legible = %s"
                    params.append(req.estado)
                
                if req.fecha_inicio:
                    query += " AND fecha_emision >= %s"
                    params.append(req.fecha_inicio)
                
                if req.fecha_fin:
                    query += " AND fecha_emision <= %s"
                    params.append(req.fecha_fin)

                query += " ORDER BY fecha_emision DESC LIMIT %s"
                params.append(req.limit)

                cur.execute(query, params)
                rows = cur.fetchall()
                
                return {
                    "count": len(rows), 
                    "data": rows,
                    "filtros_aplicados": {
                        "estado": req.estado,
                        "fecha_inicio": req.fecha_inicio,
                        "fecha_fin": req.fecha_fin,
                        "limit": req.limit,
                        "agent_cif": x_agent_cif
                    }
                }

    except Exception as e:
        print(f"❌ Error en consultar_facturas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# # --- ENDPOINT 2: BÚSQUEDA DIFUSA ---
# @app.post("/tools/buscar-propiedad")
# def buscar_propiedad(
#     req: BusquedaRequest,
#     x_agent_cif: str = Header(default=os.getenv("TEST_AGENT_CIF"))
# ):
#     """
#     Busca facturas por dirección de propiedad usando búsqueda fuzzy.
    
#     Args:
#         req: Query de búsqueda (dirección)
#         x_agent_cif: CIF del agente (header HTTP)
    
#     Returns:
#         JSON con resultados ordenados por similitud
#     """
#     try:
#         with get_db_connection() as conn:
#             with conn.cursor() as cur:
#                 query = """
#                     SELECT numero_factura, estado_legible, total, moneda, 
#                            emisor_direccion_calle,
#                            similarity(emisor_direccion_calle, %s) as score
#                     FROM view_ai_facturas
#                     WHERE emisor_cif = %s 
#                     AND emisor_direccion_calle %% %s 
#                     ORDER BY score DESC
#                     LIMIT 3;
#                 """
#                 params = [req.query_direccion, x_agent_cif, req.query_direccion]
#                 cur.execute(query, params)
#                 rows = cur.fetchall()
                
#                 return {
#                     "encontrados": len(rows) > 0, 
#                     "resultados": rows,
#                     "query_original": req.query_direccion
#                 }

#     except Exception as e:
#         print(f"❌ Error en buscar_propiedad: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT ROOT ---
@app.get("/")
def root():
    return {
        "service": "Facturación API - Agentes Inmobiliarios",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "consultar_facturas": "/tools/consultar-facturas",
            "buscar_propiedad": "/tools/buscar-propiedad"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
