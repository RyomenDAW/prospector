"""
database.py — Base de datos del Prospector

Soporta PostgreSQL (producción en Railway) y SQLite (desarrollo local).
Detecta automáticamente cuál usar según la variable DATABASE_URL.
"""

import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

# Si hay DATABASE_URL → PostgreSQL (Railway)
# Si no → SQLite local
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

USE_POSTGRES = bool(DATABASE_URL)


def get_connection():
    """Devuelve conexión a PostgreSQL o SQLite según el entorno."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect("prospector.db")
        conn.row_factory = sqlite3.Row
        return conn


def _execute(conn, sql, params=None):
    """Ejecuta SQL compatible con ambos motores."""
    cursor = conn.cursor()
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    return cursor


def _fetchall_as_dicts(cursor):
    """Convierte resultados a lista de dicts (compatible con ambos)."""
    if USE_POSTGRES:
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        return [dict(row) for row in cursor.fetchall()]


def _fetchone_as_dict(cursor):
    """Convierte un resultado a dict."""
    if USE_POSTGRES:
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    else:
        row = cursor.fetchone()
        return dict(row) if row else None


def crear_tablas():
    """Crea las tablas si no existen. Compatible con PostgreSQL y SQLite."""
    conn = get_connection()
    cursor = conn.cursor()

    # AUTO_INCREMENT en SQLite vs SERIAL en PostgreSQL
    if USE_POSTGRES:
        id_type = "SERIAL PRIMARY KEY"
        id_type_fk = "SERIAL"
    else:
        id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        id_type_fk = "INTEGER PRIMARY KEY AUTOINCREMENT"

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS empresas (
            id {id_type},
            nombre TEXT NOT NULL,
            sector TEXT,
            direccion TEXT,
            telefono TEXT,
            web TEXT,
            valoracion REAL,
            num_resenas INTEGER,
            tiene_web INTEGER DEFAULT 0,
            tiene_ssl INTEGER DEFAULT 0,
            velocidad_movil INTEGER,
            gmb_activo INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            debilidades TEXT,
            mensaje_generado TEXT,
            estado TEXT DEFAULT 'detectada',
            fecha_deteccion TEXT,
            fecha_envio TEXT,
            whatsapp_message_id TEXT,
            zona TEXT,
            dafo TEXT,
            email TEXT,
            gmb_url TEXT,
            intentos_contacto INTEGER DEFAULT 0,
            fecha_ultimo_intento TEXT,
            fecha_respuesta TEXT,
            telefono_normalizado TEXT,
            tiene_whatsapp INTEGER DEFAULT -1,
            opt_out INTEGER DEFAULT 0,
            motivo_opt_out TEXT,
            mensaje_followup_1 TEXT,
            mensaje_followup_2 TEXT,
            lead_crm_id INTEGER
        )
    """)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS envios (
            id {id_type},
            empresa_id INTEGER,
            mensaje TEXT,
            estado TEXT DEFAULT 'pendiente',
            fecha TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"Base de datos lista ({'PostgreSQL' if USE_POSTGRES else 'SQLite'}).")


def insertar_empresa(datos):
    conn = get_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute("""
            INSERT INTO empresas
            (nombre, sector, direccion, telefono, web, valoracion, num_resenas, fecha_deteccion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (
            datos.get('nombre'),
            datos.get('sector'),
            datos.get('direccion'),
            datos.get('telefono'),
            datos.get('web'),
            datos.get('valoracion'),
            datos.get('num_resenas'),
            datetime.now().isoformat(),
        ))
        row = cursor.fetchone()
        empresa_id = row[0] if row else None
    else:
        cursor.execute("""
            INSERT OR IGNORE INTO empresas
            (nombre, sector, direccion, telefono, web, valoracion, num_resenas, fecha_deteccion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos.get('nombre'),
            datos.get('sector'),
            datos.get('direccion'),
            datos.get('telefono'),
            datos.get('web'),
            datos.get('valoracion'),
            datos.get('num_resenas'),
            datetime.now().isoformat(),
        ))
        empresa_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return empresa_id


def obtener_empresas(estado=None):
    conn = get_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        placeholder = "%s"
    else:
        placeholder = "?"

    if estado:
        cursor.execute(
            f"SELECT * FROM empresas WHERE estado = {placeholder} ORDER BY score DESC",
            (estado,)
        )
    else:
        cursor.execute("SELECT * FROM empresas ORDER BY score DESC")

    empresas = _fetchall_as_dicts(cursor)
    conn.close()
    return empresas


def obtener_empresa_por_id(empresa_id):
    conn = get_connection()
    cursor = conn.cursor()
    ph = "%s" if USE_POSTGRES else "?"
    cursor.execute(f"SELECT * FROM empresas WHERE id = {ph}", (empresa_id,))
    empresa = _fetchone_as_dict(cursor)
    conn.close()
    return empresa


def obtener_empresas_pendientes_followup(dias_sin_respuesta=4):
    conn = get_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute("""
            SELECT * FROM empresas
            WHERE estado = 'enviada'
              AND opt_out = 0
              AND intentos_contacto < 3
              AND fecha_ultimo_intento IS NOT NULL
              AND EXTRACT(EPOCH FROM (NOW() - fecha_ultimo_intento::timestamp)) / 86400 >= %s
            ORDER BY fecha_ultimo_intento ASC
        """, (dias_sin_respuesta,))
    else:
        cursor.execute("""
            SELECT * FROM empresas
            WHERE estado = 'enviada'
              AND opt_out = 0
              AND intentos_contacto < 3
              AND fecha_ultimo_intento IS NOT NULL
              AND julianday('now') - julianday(fecha_ultimo_intento) >= ?
            ORDER BY fecha_ultimo_intento ASC
        """, (dias_sin_respuesta,))

    empresas = _fetchall_as_dicts(cursor)
    conn.close()
    return empresas


def obtener_empresas_enviadas_hoy():
    conn = get_connection()
    cursor = conn.cursor()
    hoy = datetime.now().strftime('%Y-%m-%d')

    if USE_POSTGRES:
        cursor.execute("""
            SELECT COUNT(*) FROM empresas
            WHERE fecha_ultimo_intento LIKE %s
        """, (f"{hoy}%",))
    else:
        cursor.execute("""
            SELECT COUNT(*) FROM empresas
            WHERE fecha_ultimo_intento LIKE ?
        """, (f"{hoy}%",))

    count = cursor.fetchone()[0]
    conn.close()
    return count


def actualizar_empresa(empresa_id, datos):
    conn = get_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        campos = ", ".join([f"{k} = %s" for k in datos.keys()])
        valores = list(datos.values()) + [empresa_id]
        cursor.execute(f"UPDATE empresas SET {campos} WHERE id = %s", valores)
    else:
        campos = ", ".join([f"{k} = ?" for k in datos.keys()])
        valores = list(datos.values()) + [empresa_id]
        cursor.execute(f"UPDATE empresas SET {campos} WHERE id = ?", valores)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    crear_tablas()