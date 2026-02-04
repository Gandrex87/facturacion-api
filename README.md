python api_server.py
Ejecutar MCP Inspector

npx @modelcontextprotocol/inspector python agent_server.py


## agent_server.py - Servidor MCP (Model Context Protocol)
Este es el servidor que implementa el protocolo MCP usando FastMCP. Está diseñado para que Claude Desktop u otros clientes MCP puedan conectarse directamente y usar las herramientas como si fueran funciones nativas.
Características principales:

Dos herramientas MCP (@mcp.tool()):

consultar_mis_facturas() - Consultas generales con filtros (estado, fecha)
buscar_factura_por_propiedad() - Búsqueda fuzzy por dirección usando PostgreSQL pg_trgm


Seguridad simulada: Usa CURRENT_AGENT_CIF de variable de entorno para filtrar facturas del agente autenticado
Conexión directa a PostgreSQL con psycopg contra la vista view_ai_facturas
Retorna strings formateados para que el LLM los presente al usuario

Cuándo usarlo: Cuando quieras que Claude Desktop o un cliente MCP nativo acceda directamente a las facturas.

## api_server.py - API REST con FastAPI
Este es un intermediario HTTP que expone las mismas funcionalidades como endpoints REST. Está pensado para integrarse con n8n u otros sistemas que consuman APIs HTTP.
Características principales:

Dos endpoints POST:

/tools/consultar-facturas - Recibe JSON con filtros
/tools/buscar-propiedad - Recibe JSON con query de búsqueda


Validación con Pydantic (FacturasRequest, BusquedaRequest) - "Schema is Law"
Autenticación por header x-agent-cif (simulada, usa variable de entorno por defecto)
Retorna JSON estructurado en lugar de strings, ideal para procesamiento automatizado:


## ¿Diferencias?
Dado que desarrollo (chatbot con n8n + LangChain), probablemente el api_server.py es más útil porque:

n8n puede hacer llamadas HTTP fácilmente
El JSON estructurado es más fácil de procesar en flujos n8n
Puedes pasar el CIF del agente autenticado en el header desde tu frontend Next.js

El agent_server.py sería ideal si quisieras que los agentes usaran Claude Desktop directamente, pero tu arquitectura actual apunta a un chatbot web centralizado.


# Asegúrate de estar en /home/chatbot/CHATBOT_FINANZAS/facturacion_api

# 1. Construir la imagen
docker-compose build

# 2. Levantar el servicio
docker-compose up -d

# 3. Ver los logs en tiempo real
docker-compose logs -f