import csv
import io as io_module
import threading
from flask import Flask, render_template, request, jsonify, make_response, Response
from database import obtener_empresas, actualizar_empresa, crear_tablas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER
import re, json

app = Flask(__name__)
import json as json_module

# ─────────────────────────────────────────────
# ESTADO DE TAREAS EN SEGUNDO PLANO
# ─────────────────────────────────────────────
tareas_estado = {}

def ejecutar_en_hilo(nombre, funcion):
    """Ejecuta una función pesada en un hilo separado para no bloquear la web."""
    tareas_estado[nombre] = {"estado": "ejecutando", "mensaje": "Iniciando..."}
    def wrapper():
        try:
            funcion()
            tareas_estado[nombre] = {"estado": "completado", "mensaje": "Completado correctamente"}
        except Exception as e:
            tareas_estado[nombre] = {"estado": "error", "mensaje": str(e)[:200]}
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()


# ─────────────────────────────────────────────
# FILTROS Y UTILIDADES
# ─────────────────────────────────────────────

@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json_module.loads(value) if value else []
    except Exception:
        return []

def limpiar_emojis(texto):
    if not texto:
        return ""
    return re.sub(r'[^\x00-\x7F\u00C0-\u024F\u00A0-\u00FF]', '', texto)


# ─────────────────────────────────────────────
# VISTA PRINCIPAL — LISTADO DE EMPRESAS
# ─────────────────────────────────────────────

@app.route("/")
def index():
    estado = request.args.get("estado", "lista")
    zona   = request.args.get("zona", "todas")
    empresas = obtener_empresas(estado=estado)

    if zona != "todas":
        empresas = [e for e in empresas if e.get("zona") == zona]

    total_enviadas_hoy = len([
        e for e in obtener_empresas(estado="enviada")
        if e.get("fecha_envio", "").startswith(
            __import__("datetime").date.today().isoformat()
        )
    ])
    return render_template("index.html",
        empresas=empresas,
        estado=estado,
        zona=zona,
        total_enviadas_hoy=total_enviadas_hoy,
        limite=50,
    )


# ─────────────────────────────────────────────
# ACCIONES SOBRE EMPRESAS
# ─────────────────────────────────────────────

@app.route("/enviar/<int:empresa_id>", methods=["POST"])
def enviar(empresa_id):
    return jsonify({"ok": False, "msg": "El envío se hace desde el CRM. Añade este lead al CRM y envía desde ahí."})

@app.route("/rechazar/<int:empresa_id>", methods=["POST"])
def rechazar(empresa_id):
    actualizar_empresa(empresa_id, {"estado": "rechazada"})
    return jsonify({"ok": True})

@app.route("/editar_mensaje/<int:empresa_id>", methods=["POST"])
def editar_mensaje(empresa_id):
    nuevo_mensaje = request.json.get("mensaje", "")
    actualizar_empresa(empresa_id, {"mensaje_generado": nuevo_mensaje})
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# EXPORTACIONES
# ─────────────────────────────────────────────

@app.route("/exportar-csv")
def exportar_csv():
    empresas = obtener_empresas()
    output = io_module.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Nombre", "Sector", "Direccion", "Zona", "Telefono", "Web", "Email", "Valoracion", "Resenas", "Score"])
    for e in empresas:
        writer.writerow([
            e.get("nombre", ""),
            e.get("sector", ""),
            e.get("direccion", ""),
            e.get("zona", ""),
            e.get("telefono", ""),
            e.get("web", ""),
            e.get("email", ""),
            e.get("valoracion", ""),
            e.get("num_resenas", ""),
            e.get("score", ""),
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=empresas.csv"}
    )

@app.route("/exportar-pdf")
def exportar_pdf():
    estado = request.args.get("estado", "lista")
    empresas = obtener_empresas(estado=estado)
    buffer = io_module.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('t', fontSize=18, textColor=colors.HexColor('#1a1a2e'),
        spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica-Bold')
    subtitulo = ParagraphStyle('s', fontSize=10, textColor=colors.grey,
        spaceAfter=16, alignment=TA_CENTER)
    empresa_nombre = ParagraphStyle('en', fontSize=13, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a1a2e'), spaceBefore=14, spaceAfter=2)
    detalle = ParagraphStyle('d', fontSize=9, textColor=colors.grey, spaceAfter=2)
    mensaje_style = ParagraphStyle('m', fontSize=10, textColor=colors.HexColor('#333333'),
        leading=16, spaceAfter=10, spaceBefore=8,
        backColor=colors.HexColor('#f8f9fa'), borderPadding=8)
    score_style = ParagraphStyle('sc', fontSize=10, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#c0392b'), spaceAfter=2)
    story = []
    story.append(Paragraph("Prospector — La Guia de Sevilla", titulo))
    story.append(Paragraph(
        f"Informe · Estado: {estado.capitalize()} · Total: {len(empresas)}",
        subtitulo))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a1a2e')))
    for e in empresas:
        story.append(Paragraph(limpiar_emojis(e['nombre']), empresa_nombre))
        story.append(Paragraph(f"{e['sector']} · {e['direccion']} · Zona: {e.get('zona','')}", detalle))
        story.append(Paragraph(f"Tel: {e['telefono'] or 'Sin telefono'} · Web: {e['web'] or 'Sin web'}", detalle))
        story.append(Paragraph(f"Score: {e['score']}/100", score_style))
        if e.get('mensaje_generado'):
            story.append(Paragraph(limpiar_emojis(e['mensaje_generado']), mensaje_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
            color=colors.HexColor('#dee2e6'), spaceBefore=6))
    doc.build(story)
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=prospector_{estado}.pdf'
    return response


# ─────────────────────────────────────────────
# PANEL DE CONTROL — EJECUTAR PIPELINE
# ─────────────────────────────────────────────

@app.route("/panel")
def panel():
    """Panel de control para ejecutar el pipeline de prospección."""
    # Estadísticas rápidas
    stats = {}
    for estado in ["detectada", "auditada", "cualificada", "lista", "enviada", "rechazada"]:
        stats[estado] = len(obtener_empresas(estado=estado))
    stats["total"] = sum(stats.values())
    return render_template("panel.html", tareas=tareas_estado, stats=stats)


@app.route("/accion/buscar", methods=["POST"])
def accion_buscar():
    sector = request.json.get("sector", "restaurantes")
    zona = request.json.get("zona", "Sevilla")
    max_res = request.json.get("max_resultados", 20)
    def tarea():
        from searcher import buscar_empresas
        tareas_estado["buscar"]["mensaje"] = f"Buscando {sector} en {zona}..."
        buscar_empresas(sector, zona, max_resultados=max_res)
    ejecutar_en_hilo("buscar", tarea)
    return jsonify({"ok": True, "msg": f"Buscando {sector} en {zona}..."})


@app.route("/accion/buscar-todo", methods=["POST"])
def accion_buscar_todo():
    def tarea():
        from searcher import buscar_todo
        tareas_estado["buscar"]["mensaje"] = "Buscando todos los sectores y zonas..."
        buscar_todo()
    ejecutar_en_hilo("buscar", tarea)
    return jsonify({"ok": True, "msg": "Buscando en todos los sectores y zonas..."})


@app.route("/accion/auditar", methods=["POST"])
def accion_auditar():
    def tarea():
        from auditor import auditar_todas
        auditar_todas()
    ejecutar_en_hilo("auditar", tarea)
    return jsonify({"ok": True, "msg": "Auditando empresas detectadas..."})


@app.route("/accion/puntuar", methods=["POST"])
def accion_puntuar():
    def tarea():
        from scorer import puntuar_todas
        puntuar_todas()
    ejecutar_en_hilo("puntuar", tarea)
    return jsonify({"ok": True, "msg": "Puntuando empresas auditadas..."})


@app.route("/accion/generar", methods=["POST"])
def accion_generar():
    def tarea():
        from messenger import generar_mensajes_todos
        generar_mensajes_todos(min_score=40)
    ejecutar_en_hilo("generar", tarea)
    return jsonify({"ok": True, "msg": "Generando mensajes con Claude..."})


@app.route("/accion/validar", methods=["POST"])
def accion_validar():
    def tarea():
        from phone_validator import validar_todas
        validar_todas()
    ejecutar_en_hilo("validar", tarea)
    return jsonify({"ok": True, "msg": "Validando teléfonos..."})


@app.route("/accion/duplicados", methods=["POST"])
def accion_duplicados():
    def tarea():
        from dedup import marcar_duplicados
        marcar_duplicados(dry_run=False)
    ejecutar_en_hilo("duplicados", tarea)
    return jsonify({"ok": True, "msg": "Eliminando duplicados..."})


@app.route("/accion/pipeline", methods=["POST"])
def accion_pipeline():
    """Ejecuta TODO el pipeline en orden: buscar → auditar → puntuar → generar."""
    sector = request.json.get("sector", "restaurantes")
    zona = request.json.get("zona", "Sevilla")
    max_res = request.json.get("max_resultados", 20)
    def tarea():
        from searcher import buscar_empresas
        from auditor import auditar_todas
        from scorer import puntuar_todas
        from messenger import generar_mensajes_todos

        tareas_estado["pipeline"]["mensaje"] = f"1/4 — Buscando {sector} en {zona}..."
        buscar_empresas(sector, zona, max_resultados=max_res)

        tareas_estado["pipeline"]["mensaje"] = "2/4 — Auditando webs y presencia digital..."
        auditar_todas()

        tareas_estado["pipeline"]["mensaje"] = "3/4 — Calculando scores..."
        puntuar_todas()

        tareas_estado["pipeline"]["mensaje"] = "4/4 — Generando mensajes con IA..."
        generar_mensajes_todos(min_score=40)

    ejecutar_en_hilo("pipeline", tarea)
    return jsonify({"ok": True, "msg": f"Pipeline iniciado: {sector} en {zona}"})


@app.route("/accion/estado")
def accion_estado():
    """Devuelve el estado actual de todas las tareas (polling desde el frontend)."""
    return jsonify(tareas_estado)


# ─────────────────────────────────────────────
# ARRANQUE
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)