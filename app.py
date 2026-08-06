import csv
import io as io_module
import threading
from flask import Flask, render_template, request, jsonify, make_response, Response
from database import obtener_empresas, actualizar_empresa, crear_tablas, obtener_empresa_por_id
from sender import enviar_whatsapp, enviar_lote
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER
import re, json
import os
import tempfile


app = Flask(__name__)
import json as json_module

# ─────────────────────────────────────────────
# ESTADO DE TAREAS EN SEGUNDO PLANO
# ─────────────────────────────────────────────
tareas_estado = {}

estado_lote = {
    "activo": False,
    "total": 0,
    "enviados": 0,
    "fallidos": 0,
    "omitidos": 0,
    "mensaje": "",
}


TERRITORIO_SCHEDULER = "andalucia"
_zona_index = 0

scheduler_pausado = False

def ejecutar_en_hilo(nombre, funcion):
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
# VISTA PRINCIPAL
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

    stats = {}
    for est in ["detectada", "auditada", "cualificada", "lista", "enviada", "rechazada"]:
        stats[est] = len(obtener_empresas(estado=est))
    stats["total"] = sum(stats.values())

    return render_template("index.html",
        empresas=empresas,
        estado=estado,
        zona=zona,
        total_enviadas_hoy=total_enviadas_hoy,
        limite=50,
        stats=stats,
        estado_lote=estado_lote,
    )


# ─────────────────────────────────────────────
# ACCIONES SOBRE EMPRESAS
# ─────────────────────────────────────────────

@app.route("/enviar/<int:empresa_id>", methods=["POST"])
def enviar(empresa_id):
    empresa = obtener_empresa_por_id(empresa_id)
    if not empresa:
        return jsonify({"ok": False, "msg": "Empresa no encontrada"}), 404
    if empresa.get("estado") == "enviada":
        return jsonify({"ok": False, "msg": "Ya fue enviada anteriormente"}), 400
    if not empresa.get("telefono"):
        return jsonify({"ok": False, "msg": "Sin teléfono registrado"}), 400
    resultado = enviar_whatsapp(empresa_id=empresa_id, telefono=empresa["telefono"], empresa=empresa)
    if resultado["ok"]:
        return jsonify({"ok": True, "message_id": resultado.get("message_id", "")})
    else:
        return jsonify({"ok": False, "msg": resultado.get("error", "Error desconocido")}), 500


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
# ENVIO EN LOTE — lista
# ─────────────────────────────────────────────

@app.route("/accion/enviar-lote", methods=["POST"])
def accion_enviar_lote():
    global estado_lote
    if estado_lote["activo"]:
        return jsonify({"ok": False, "msg": "Ya hay un lote en curso"}), 400
    empresas = obtener_empresas(estado="lista")
    empresas = [e for e in empresas if e.get("telefono")]
    if not empresas:
        return jsonify({"ok": False, "msg": "No hay empresas pendientes con teléfono"}), 400
    estado_lote.update({"activo": True, "total": len(empresas), "enviados": 0, "fallidos": 0, "omitidos": 0, "mensaje": f"Iniciando envío de {len(empresas)} empresas..."})
    def tarea():
        global estado_lote
        import time as time_module
        for i, empresa in enumerate(empresas):
            if empresa.get("estado") == "enviada":
                estado_lote["omitidos"] += 1
                continue
            estado_lote["mensaje"] = f"Enviando {i + 1}/{len(empresas)}: {empresa.get('nombre', '')}..."
            resultado = enviar_whatsapp(empresa_id=empresa["id"], telefono=empresa["telefono"], empresa=empresa)
            if resultado["ok"]:
                estado_lote["enviados"] += 1
            else:
                estado_lote["fallidos"] += 1
            if i < len(empresas) - 1:
                estado_lote["mensaje"] = f"Esperando 60s antes del siguiente ({i + 1}/{len(empresas)} enviados)..."
                time_module.sleep(60)
        estado_lote["activo"] = False
        estado_lote["mensaje"] = f"Lote completado: {estado_lote['enviados']} enviados, {estado_lote['fallidos']} fallidos, {estado_lote['omitidos']} omitidos."
    thread = threading.Thread(target=tarea, daemon=True)
    thread.start()
    return jsonify({"ok": True, "msg": f"Lote iniciado: {len(empresas)} empresas. 1 minuto entre cada mensaje."})


# ─────────────────────────────────────────────
# ENVIO EN LOTE — cualificada
# ─────────────────────────────────────────────

@app.route("/accion/enviar-cualificadas", methods=["POST"])
def accion_enviar_cualificadas():
    global estado_lote
    if estado_lote["activo"]:
        return jsonify({"ok": False, "msg": "Ya hay un lote en curso"}), 400
    empresas = obtener_empresas(estado="cualificada")
    empresas = [e for e in empresas if e.get("telefono")]
    if not empresas:
        return jsonify({"ok": False, "msg": "No hay cualificadas con teléfono"}), 400
    estado_lote.update({"activo": True, "total": len(empresas), "enviados": 0, "fallidos": 0, "omitidos": 0, "mensaje": f"Iniciando envío de {len(empresas)} cualificadas..."})
    def tarea():
        global estado_lote
        import time as time_module
        for i, empresa in enumerate(empresas):
            estado_lote["mensaje"] = f"Enviando {i + 1}/{len(empresas)}: {empresa.get('nombre', '')}..."
            resultado = enviar_whatsapp(empresa_id=empresa["id"], telefono=empresa["telefono"], empresa=empresa)
            if resultado["ok"]:
                estado_lote["enviados"] += 1
            else:
                estado_lote["fallidos"] += 1
            if i < len(empresas) - 1:
                estado_lote["mensaje"] = f"Esperando 60s antes del siguiente ({i + 1}/{len(empresas)} enviados)..."
                time_module.sleep(60)
        estado_lote["activo"] = False
        estado_lote["mensaje"] = f"Lote completado: {estado_lote['enviados']} enviados, {estado_lote['fallidos']} fallidos, {estado_lote['omitidos']} omitidos."
    thread = threading.Thread(target=tarea, daemon=True)
    thread.start()
    return jsonify({"ok": True, "msg": f"Lote iniciado: {len(empresas)} cualificadas. 1 minuto entre mensajes."})


@app.route("/accion/estado-lote")
def accion_estado_lote():
    return jsonify(estado_lote)


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
        writer.writerow([e.get("nombre",""), e.get("sector",""), e.get("direccion",""), e.get("zona",""), e.get("telefono",""), e.get("web",""), e.get("email",""), e.get("valoracion",""), e.get("num_resenas",""), e.get("score","")])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=empresas.csv"})


@app.route("/exportar-pdf")
def exportar_pdf():
    estado = request.args.get("estado", "lista")
    empresas = obtener_empresas(estado=estado)
    buffer = io_module.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('t', fontSize=18, textColor=colors.HexColor('#1a1a2e'), spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica-Bold')
    subtitulo = ParagraphStyle('s', fontSize=10, textColor=colors.grey, spaceAfter=16, alignment=TA_CENTER)
    empresa_nombre = ParagraphStyle('en', fontSize=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a1a2e'), spaceBefore=14, spaceAfter=2)
    detalle = ParagraphStyle('d', fontSize=9, textColor=colors.grey, spaceAfter=2)
    mensaje_style = ParagraphStyle('m', fontSize=10, textColor=colors.HexColor('#333333'), leading=16, spaceAfter=10, spaceBefore=8, backColor=colors.HexColor('#f8f9fa'), borderPadding=8)
    score_style = ParagraphStyle('sc', fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#c0392b'), spaceAfter=2)
    story = []
    story.append(Paragraph("Prospector — La Guia de Sevilla", titulo))
    story.append(Paragraph(f"Informe · Estado: {estado.capitalize()} · Total: {len(empresas)}", subtitulo))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a1a2e')))
    for e in empresas:
        story.append(Paragraph(limpiar_emojis(e['nombre']), empresa_nombre))
        story.append(Paragraph(f"{e['sector']} · {e['direccion']} · Zona: {e.get('zona','')}", detalle))
        story.append(Paragraph(f"Tel: {e['telefono'] or 'Sin telefono'} · Web: {e['web'] or 'Sin web'}", detalle))
        story.append(Paragraph(f"Score: {e['score']}/100", score_style))
        if e.get('mensaje_generado'):
            story.append(Paragraph(limpiar_emojis(e['mensaje_generado']), mensaje_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#dee2e6'), spaceBefore=6))
    doc.build(story)
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=prospector_{estado}.pdf'
    return response


# ─────────────────────────────────────────────
# PANEL DE CONTROL
# ─────────────────────────────────────────────

@app.route("/panel")
def panel():
    stats = {}
    for estado in ["detectada", "auditada", "cualificada", "lista", "enviada", "rechazada"]:
        stats[estado] = len(obtener_empresas(estado=estado))
    stats["total"] = sum(stats.values())
    return render_template("panel.html", tareas=tareas_estado, stats=stats, estado_lote=estado_lote)


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
        generar_mensajes_todos(min_score=20)
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
        generar_mensajes_todos(min_score=20)
    ejecutar_en_hilo("pipeline", tarea)
    return jsonify({"ok": True, "msg": f"Pipeline iniciado: {sector} en {zona}"})


@app.route("/accion/estado")
def accion_estado():
    return jsonify(tareas_estado)


# ─────────────────────────────────────────────
# SCHEDULER AUTOMÁTICO
#
# Ciclo completo cada hora L-V 9:00-18:00:
#   1/5 Buscar 60 empresas (general, Sevilla Provincia)
#   2/5 Auditar webs
#   3/5 Puntuar scores
#   4/5 Generar mensajes con IA
#   5/5 Enviar las nuevas de esa hora (máx 55)
#
# A las 10:00 además lanza seguimiento automático
# a prospectos sin respuesta tras 4 días.
#
# El switch manual pausa solo el automático.
# Búsquedas y envíos manuales siguen funcionando siempre.
# ─────────────────────────────────────────────

def _ejecutar_seguimiento(ahora):
    """
    Envía plantilla 'seguimiento' a empresas enviadas hace +4 días sin respuesta.
    Solo se ejecuta a las 10:00.
    """
    from database import obtener_empresas, actualizar_empresa
    from crm_client import conversacion_tiene_respuesta
    from phone_validator import normalizar_telefono
    import sender as sender_module
    import time as time_module
    from datetime import datetime as dt

    if ahora.hour != 10:
        return

    print("[Seguimiento] Iniciando revisión...", flush=True)
    empresas = obtener_empresas(estado="enviada")
    enviados = 0

    for empresa in empresas:
        fecha_envio_str = empresa.get("fecha_envio", "")
        if not fecha_envio_str:
            continue
        try:
            fecha_envio = dt.fromisoformat(fecha_envio_str)
        except ValueError:
            continue

        if (ahora - fecha_envio).days < 4:
            continue
        if (empresa.get("intentos_contacto") or 0) >= 2:
            continue

        telefono = normalizar_telefono(empresa.get("telefono", ""))
        if not telefono:
            continue

        if conversacion_tiene_respuesta(telefono):
            print(f"[Seguimiento] Omitida empresa_id={empresa['id']} — ya respondió", flush=True)
            continue

        plantilla_original = sender_module.PLANTILLA_ACTIVA
        sender_module.PLANTILLA_ACTIVA = "seguimiento"
        resultado = sender_module.enviar_whatsapp(
            empresa_id=empresa["id"], telefono=telefono, empresa=empresa
        )
        sender_module.PLANTILLA_ACTIVA = plantilla_original

        if resultado["ok"]:
            actualizar_empresa(empresa["id"], {
                "intentos_contacto": (empresa.get("intentos_contacto") or 1) + 1,
            })
            enviados += 1
            print(f"[Seguimiento] Enviado empresa_id={empresa['id']}", flush=True)
            time_module.sleep(60)
        else:
            print(f"[Seguimiento] Fallo empresa_id={empresa['id']}: {resultado.get('error')}", flush=True)

    print(f"[Seguimiento] Completado — {enviados} enviados", flush=True)



def _scheduler_loop():
    import time as time_module
    from datetime import datetime
    from searcher import TERRITORIO_SEVILLA, TERRITORIO_ANDALUCIA, TERRITORIO_ESPANA
 
    global _zona_index
 
    HORA_INICIO = 9
    HORA_FIN    = 18
    INTERVALO   = 18000
    MAX_ENVIOS  = 55
 
    TERRITORIOS = {
        "sevilla":   TERRITORIO_SEVILLA,
        "andalucia": TERRITORIO_ANDALUCIA,
        "espana":    TERRITORIO_ESPANA,
    }
 
    time_module.sleep(30) #30
 
    while True:
        ahora = datetime.now()
        en_horario = (ahora.weekday() <= 4 and HORA_INICIO <= ahora.hour < HORA_FIN)
        pipeline_activo = (tareas_estado.get("pipeline", {}).get("estado") == "ejecutando")
 
        if scheduler_pausado:
            print(f"[Scheduler] Pausado — {ahora.strftime('%H:%M')}", flush=True)
 
        elif en_horario and not pipeline_activo:
 
            territorio_actual = TERRITORIOS.get(TERRITORIO_SCHEDULER, TERRITORIO_ANDALUCIA)
            zonas_lista = list(territorio_actual.keys())
            zona_ciclo = zonas_lista[_zona_index % len(zonas_lista)]
            _zona_index += 1
 
            print(f"[Scheduler] Ciclo {ahora.strftime('%H:%M:%S')} | territorio={TERRITORIO_SCHEDULER} | zona={zona_ciclo}", flush=True)
 
            try:
                from searcher import buscar_empresas
                from auditor import auditar_todas
                from scorer import puntuar_todas
                from messenger import generar_mensajes_todos
                from database import obtener_empresas
 
                # 1/5 BUSCAR
                tareas_estado["pipeline"] = {"estado": "ejecutando", "mensaje": f"1/5 — [AUTO] Buscando en {zona_ciclo}..."}
                print(f"[Scheduler] 1/5 Buscando en {zona_ciclo}...", flush=True)
                buscar_empresas("general", zona_ciclo, max_resultados=60)
 
                # 2/5 AUDITAR
                tareas_estado["pipeline"]["mensaje"] = "2/5 — [AUTO] Auditando webs..."
                print("[Scheduler] 2/5 Auditando...", flush=True)
                auditar_todas()
 
                # 3/5 PUNTUAR
                tareas_estado["pipeline"]["mensaje"] = "3/5 — [AUTO] Calculando scores..."
                print("[Scheduler] 3/5 Puntuando...", flush=True)
                puntuar_todas()
 
                # 4/5 GENERAR
                tareas_estado["pipeline"]["mensaje"] = "4/5 — [AUTO] Generando mensajes..."
                print("[Scheduler] 4/5 Generando mensajes...", flush=True)
                generar_mensajes_todos(min_score=20)
 
                # 5/5 ENVIAR
                tareas_estado["pipeline"]["mensaje"] = "5/5 — [AUTO] Enviando mensajes..."
                print("[Scheduler] 5/5 Enviando...", flush=True)
                todas_listas = obtener_empresas(estado="lista")
                nuevas = [
                    e for e in todas_listas
                    if not e.get("fecha_envio") and e.get("mensaje_generado")
                ][:MAX_ENVIOS]
                resumen = enviar_lote(nuevas) if nuevas else {"enviados": 0, "fallidos": 0, "omitidos": 0}
 
                tareas_estado["pipeline"] = {
                    "estado": "completado",
                    "mensaje": (
                        f"[AUTO] {ahora.strftime('%H:%M')} | {zona_ciclo} | "
                        f"enviados: {resumen.get('enviados', 0)}, "
                        f"fallidos: {resumen.get('fallidos', 0)}"
                    ),
                }
                print(f"[Scheduler] OK — zona={zona_ciclo} enviados={resumen.get('enviados',0)}", flush=True)
 
                try:
                    _ejecutar_seguimiento(datetime.now())
                except Exception as e_seg:
                    print(f"[Seguimiento] Error: {e_seg}", flush=True)
 
            except Exception as e:
                tareas_estado["pipeline"] = {"estado": "error", "mensaje": f"[AUTO] Error en {zona_ciclo}: {str(e)[:200]}"}
                print(f"[Scheduler] Error ({zona_ciclo}): {e}", flush=True)
 
        else:
            if not en_horario:
                print(f"[Scheduler] Fuera de horario ({ahora.strftime('%H:%M')})", flush=True)
            elif pipeline_activo:
                print("[Scheduler] Pipeline en curso — saltando", flush=True)
 
        time_module.sleep(INTERVALO)
 
 
_scheduler_iniciado = False
_scheduler_lock = threading.Lock()
 
_lock_file = os.path.join(tempfile.gettempdir(), "prospector_scheduler.lock")
 
@app.before_request
def _lanzar_scheduler():
    _iniciar_scheduler_una_vez()

def _iniciar_scheduler_una_vez():
    global _scheduler_iniciado
    with _scheduler_lock:
        if _scheduler_iniciado:
            return
        # Evitar doble arranque con gunicorn (múltiples workers)
        if os.path.exists(_lock_file):
            return
        try:
            open(_lock_file, 'w').close()
        except Exception:
            pass
        _scheduler_iniciado = True
        t = threading.Thread(target=_scheduler_loop, daemon=True)
        t.start()
        print("[Scheduler] Scheduler automático iniciado", flush=True)

# ─────────────────────────────────────────────
# SCHEDULER — CONTROL
# ─────────────────────────────────────────────

@app.route("/accion/scheduler-toggle", methods=["POST"])
def accion_scheduler_toggle():
    global scheduler_pausado
    scheduler_pausado = not scheduler_pausado
    estado = "pausado" if scheduler_pausado else "activo"
    print(f"[Scheduler] Toggle → {estado}", flush=True)
    return jsonify({"ok": True, "scheduler_pausado": scheduler_pausado})


@app.route("/accion/scheduler-estado")
def accion_scheduler_estado():
    return jsonify({
        "scheduler_pausado": scheduler_pausado,
        "territorio": TERRITORIO_SCHEDULER,
        "zona_actual": _zona_actual(),
    })

# ── Añadir estas dos rutas junto a las otras de /accion/scheduler-* ──────────

@app.route("/accion/scheduler-territorio", methods=["POST"])
def accion_scheduler_territorio():
    """Cambia el territorio del scheduler desde el panel."""
    global TERRITORIO_SCHEDULER, _zona_index
    nuevo = request.json.get("territorio", "andalucia")
    if nuevo not in ("sevilla", "andalucia", "espana"):
        return jsonify({"ok": False, "msg": "Territorio inválido"}), 400
    TERRITORIO_SCHEDULER = nuevo
    _zona_index = 0  # Resetea el índice para empezar desde el principio del nuevo territorio
    print(f"[Scheduler] Territorio cambiado a: {nuevo}", flush=True)
    return jsonify({"ok": True, "territorio": nuevo})



def _zona_actual():
    """Devuelve el nombre de la zona que se usará en el próximo ciclo."""
    from searcher import TERRITORIO_SEVILLA, TERRITORIO_ANDALUCIA, TERRITORIO_ESPANA
    territorios = {
        "sevilla":   TERRITORIO_SEVILLA,
        "andalucia": TERRITORIO_ANDALUCIA,
        "espana":    TERRITORIO_ESPANA,
    }
    t = territorios.get(TERRITORIO_SCHEDULER, TERRITORIO_ANDALUCIA)
    zonas = list(t.keys())
    return zonas[_zona_index % len(zonas)]


# ─────────────────────────────────────────────
# ARRANQUE
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import os
    _iniciar_scheduler_una_vez()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)