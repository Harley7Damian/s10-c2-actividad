# Chatbot Gemini para Railway

Aplicacion Streamlit con Gemini, PostgreSQL y Redis. Incluye historial de chat, cache de respuestas y carga de fuentes para que el chatbot responda usando archivos subidos por el usuario.

## Servicios

- `app`: interfaz Streamlit y conexion con Gemini.
- `postgres`: guarda historial y fuentes subidas.
- `redis`: cachea respuestas durante 1 hora.

## Variables de entorno

Configura estas variables en Railway:

```env
GEMINI_API_KEY=tu_api_key
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=postgresql://usuario:password@host:puerto/db
REDIS_URL=redis://host:puerto
```

`GEMINI_MODEL` es opcional. Si no se define, la app usa `gemini-2.5-flash`.

## Ejecutar localmente

```bash
docker compose up --build
```

Luego abre:

```text
http://localhost:8501
```

## Fuentes soportadas

La interfaz permite subir archivos `PDF`, `TXT`, `MD`, `CSV` y `JSON`. El texto extraido se agrega al prompt de Gemini y tambien se guarda en PostgreSQL para auditoria basica.
