import csv
import io as io_module
from flask import Flask, render_template, request, jsonify, make_response, Response
from database import obtener_empresas, actualizar_empresa, crear_tablas
from sender import enviar_empresa
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER
import re, json

app = Flask(__name__)
import json as json_module

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

@app.route("/enviar/<int:empresa_id>", methods=["POST"])
def enviar(empresa_id):
    exito, msg = enviar_empresa(empresa_id)
    return jsonify({"ok": exito, "msg": msg})

@app.route("/rechazar/<int:empresa_id>", methods=["POST"])
def rechazar(empresa_id):
    actualizar_empresa(empresa_id, {"estado": "rechazada"})
    return jsonify({"ok": True})

@app.route("/editar_mensaje/<int:empresa_id>", methods=["POST"])
def editar_mensaje(empresa_id):
    nuevo_mensaje = request.json.get("mensaje", "")
    actualizar_empresa(empresa_id, {"mensaje_generado": nuevo_mensaje})
    return jsonify({"ok": True})

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

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)