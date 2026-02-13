import os
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Agente Inmobiliario - Performance API",
    description="API para consultar métricas de ventas, facturación y cobros de agentes",
    version="1.0.0"
)

# --- MODELOS ---
class PerformanceRequest(BaseModel):
    anyo: Optional[int] = None  # Si es None, devuelve histórico total

# --- MODELO DE REQUEST ---
class ZonaStatsRequest(BaseModel):
    nombre_zona: Optional[str] = None # Si es null, trae el top general
    limit: int = 10

# --- CONEXIÓN BD ---
def get_db_connection():
    try:
        conn = psycopg.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME_2"),  # ← Usamos DB_NAME, no DB_NAME_2
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            row_factory=dict_row,
            connect_timeout=5
        )
        return conn
    except Exception as e:
        print(f"❌ Error DB: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Error de conexión con el sistema de performance"
        )

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
            "service": "performance-api"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

# --- ENDPOINT 1: MI PERFORMANCE ---
@app.post("/tools/mi-performance")
def obtener_performance(
    req: PerformanceRequest,
    x_agent_email: str = Header(..., description="Email del agente (usado como identificador)")
):
    """
    Consulta el performance financiero del agente:
    - Si recibe 'anyo': Devuelve datos de ese año específico
    - Si NO recibe 'anyo': Devuelve el histórico total (toda la carrera)
    
    Args:
        req: Parámetros de búsqueda (anyo opcional)
        x_agent_email: Email del agente en header HTTP
    
    Returns:
        JSON con ventas, facturado y cobrado
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                
                # Caso A: Año específico
                if req.anyo:
                    query = """
                        SELECT ventas, facturado, cobrado
                        FROM view_agente_performance_anual
                        WHERE correo = %s AND anyo = %s
                    """
                    cur.execute(query, [x_agent_email, req.anyo])
                    row = cur.fetchone()
                    
                    if not row:
                        return {
                            "periodo": req.anyo,
                            "tipo": "Anual",
                            "mensaje": f"No hay datos registrados para el año {req.anyo}.",
                            "data": {
                                "ventas": 0, 
                                "facturado": 0.0, 
                                "cobrado": 0.0
                            }
                        }
                    
                    return {
                        "periodo": req.anyo,
                        "tipo": "Anual",
                        "data": {
                            "ventas": row['ventas'],
                            "facturado": float(row['facturado']),
                            "cobrado": float(row['cobrado']),
                            "pendiente_cobro": float(row['facturado']) - float(row['cobrado'])
                        }
                    }

                # Caso B: Histórico Total (toda la carrera)
                else:
                    query_total = """
                        SELECT 
                            SUM(ventas) as total_ventas,
                            SUM(facturado) as total_facturado,
                            SUM(cobrado) as total_cobrado
                        FROM view_agente_performance_anual
                        WHERE correo = %s
                    """
                    cur.execute(query_total, [x_agent_email])
                    row = cur.fetchone()

                    if not row or row['total_ventas'] is None:
                        return {
                            "periodo": "Histórico Total",
                            "tipo": "Acumulado",
                            "mensaje": "No hay datos registrados para este agente.",
                            "data": {
                                "ventas": 0,
                                "facturado": 0.0,
                                "cobrado": 0.0,
                                "pendiente_cobro": 0.0
                            }
                        }

                    ventas = int(row['total_ventas'])
                    facturado = float(row['total_facturado']) if row['total_facturado'] else 0.0
                    cobrado = float(row['total_cobrado']) if row['total_cobrado'] else 0.0

                    return {
                        "periodo": "Histórico Total",
                        "tipo": "Acumulado",
                        "data": {
                            "ventas": ventas,
                            "facturado": facturado,
                            "cobrado": cobrado,
                            "pendiente_cobro": facturado - cobrado
                        }
                    }

    except Exception as e:
        print(f"❌ Error en mi-performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT 2: MI ZONA ---
@app.get("/tools/mi-zona")
def obtener_zona(
    x_agent_email: str = Header(..., description="Email del agente")
):
    """
    Consulta la zona asignada al agente.
    
    Args:
        x_agent_email: Email del agente en header HTTP
    
    Returns:
        JSON con información de la zona asignada
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        a.nombre as agente_nombre,
                        z.nombre as zona_nombre,
                        z.ciudad
                    FROM agentes a
                    LEFT JOIN zonas z ON z.id = a.zona_id
                    WHERE a.correo = %s
                """
                cur.execute(query, [x_agent_email])
                row = cur.fetchone()
                
                if not row:
                    raise HTTPException(
                        status_code=404, 
                        detail="Agente no encontrado en el sistema."
                    )
                
                if not row['zona_nombre']:
                    return {
                        "agente": row['agente_nombre'],
                        "tiene_zona": False,
                        "mensaje": "No tienes una zona asignada actualmente."
                    }
                
                return {
                    "agente": row['agente_nombre'],
                    "tiene_zona": True,
                    "zona": {
                        "nombre": row['zona_nombre'],
                       # "descripcion": row['zona_descripcion']
                    }
                }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en mi-zona: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ENDPOINT 3 ESTADISTICAS ZONAS ---
@app.post("/tools/stats-zonas")
def consultar_stats_zonas(req: ZonaStatsRequest):
    """
    Entrega estadísticas de mercado por zona.
    Útil para responder: "¿Cuál es la zona más cara?", "¿Precio m2 en Camins al Grau?"
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                
                query = """
                    SELECT zona, num_ventas, precio_medio, precio_m2_medio, total_honorarios
                    FROM view_stats_zonas
                """
                params = []

                # Búsqueda difusa si el agente pregunta por una zona específica
                if req.nombre_zona:
                    query += " WHERE zona ILIKE %s"
                    # El % permite buscar "Camins" y encontrar "Camins al Grau"
                    params.append(f"%{req.nombre_zona}%")
                
                query += " ORDER BY num_ventas DESC LIMIT %s"
                params.append(req.limit)

                cur.execute(query, params)
                rows = cur.fetchall()

                if not rows:
                    return {
                        "mensaje": f"No se encontraron datos para la zona '{req.nombre_zona}'",
                        "data": []
                    }

                return {
                    "count": len(rows),
                    "tipo_busqueda": "Específica" if req.nombre_zona else "Top Mercado",
                    "data": rows
                }

    except Exception as e:
        print(f"❌ Error en stats-zonas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ENDPOINT ROOT ---
@app.get("/")
def root():
    return {
        "service": "Performance API - Agentes Inmobiliarios",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "mi_performance": "/tools/mi-performance",
            "mi_zona": "/tools/mi-zona",
            "stats_zonas": "/tools/stats-zonas"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)