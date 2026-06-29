import sqlite3
from datetime import datetime

DB_PATH = "prospector.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def crear_tablas():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            whatsapp_message_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            mensaje TEXT,
            estado TEXT DEFAULT 'pendiente',
            fecha TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)

    # Migración segura — añade columnas nuevas si no existen
    columnas_nuevas = [
        "ALTER TABLE empresas ADD COLUMN zona TEXT",
        "ALTER TABLE empresas ADD COLUMN dafo TEXT",
        "ALTER TABLE empresas ADD COLUMN email TEXT",
        "ALTER TABLE empresas ADD COLUMN gmb_url TEXT",
    ]
    for sql in columnas_nuevas:
        try:
            cursor.execute(sql)
        except Exception:
            pass  # La columna ya existe

    conn.commit()
    conn.close()
    print("Base de datos lista.")

def insertar_empresa(datos):
    conn = get_connection()
    cursor = conn.cursor()
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
    conn.commit()
    empresa_id = cursor.lastrowid
    conn.close()
    return empresa_id

def obtener_empresas(estado=None):
    conn = get_connection()
    cursor = conn.cursor()
    if estado:
        cursor.execute("SELECT * FROM empresas WHERE estado = ? ORDER BY score DESC", (estado,))
    else:
        cursor.execute("SELECT * FROM empresas ORDER BY score DESC")
    empresas = cursor.fetchall()
    conn.close()
    return [dict(e) for e in empresas]

def actualizar_empresa(empresa_id, datos):
    conn = get_connection()
    cursor = conn.cursor()
    campos = ", ".join([f"{k} = ?" for k in datos.keys()])
    valores = list(datos.values()) + [empresa_id]
    cursor.execute(f"UPDATE empresas SET {campos} WHERE id = ?", valores)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    crear_tablas()