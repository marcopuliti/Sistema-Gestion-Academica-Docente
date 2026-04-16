from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

AZUL = colors.HexColor('#1a3a5c')
AZUL2 = colors.HexColor('#2e86c1')
GRIS = colors.HexColor('#f2f3f4')
GRIS2 = colors.HexColor('#6a7978')


def generar_pdf_planificacion(p):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('T', parent=styles['Title'], fontSize=13,
                            textColor=AZUL, spaceAfter=4, alignment=TA_CENTER)
    subtit = ParagraphStyle('S', parent=styles['Normal'], fontSize=10,
                            textColor=AZUL2, spaceAfter=4, alignment=TA_CENTER)
    sec = ParagraphStyle('Sec', parent=styles['Heading2'], fontSize=11,
                         textColor=AZUL, spaceBefore=10, spaceAfter=3)
    subsec = ParagraphStyle('Sub', parent=styles['Heading3'], fontSize=10,
                            textColor=AZUL2, spaceBefore=6, spaceAfter=2)
    normal = ParagraphStyle('N', parent=styles['Normal'], fontSize=9,
                            spaceAfter=4, leading=13)

    el = []

    # Encabezado
    el.append(Paragraph("FACULTAD", subtit))
    el.append(Paragraph(
        f"Planificación de Actividades Docentes para el Año {p.anno}", titulo))
    el.append(Paragraph(
        f"Período: {p.fecha_desde.strftime('%d/%m/%Y')} — {p.fecha_hasta.strftime('%d/%m/%Y')}",
        subtit))
    el.append(HRFlowable(width="100%", thickness=2, color=AZUL))
    el.append(Spacer(1, 0.3*cm))

    # Datos docente
    datos = [
        ['Docente', 'Cargo', 'Dedicación', 'Designación', 'Departamento', 'Área'],
        [
            p.get_nombre_docente,
            p.get_cargo_display(),
            p.get_dedicacion_display(),
            p.get_designacion_display(),
            (p.usuario.departamento if p.usuario else None) or p.departamento_docente or '—',
            p.area or '—',
        ],
    ]
    t = Table(datos, colWidths=[4*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS2),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, 1), GRIS),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.3*cm))

    def seccion_item(codigo, titulo_item, desc, hs1, hs2):
        el.append(Paragraph(f"{codigo} {titulo_item}", subsec))
        el.append(HRFlowable(width="100%", thickness=0.5, color=AZUL2))
        if desc:
            el.append(Paragraph(desc.replace('\n', '<br/>'), normal))
        hs = Table(
            [['Hs. 1º Cuatrimestre', 'Hs. 2º Cuatrimestre'], [str(hs1), str(hs2)]],
            colWidths=[4.5*cm, 4.5*cm],
        )
        hs.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GRIS),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        el.append(hs)
        el.append(Spacer(1, 0.15*cm))

    # A. Docencia
    el.append(Paragraph("A. DOCENCIA", sec))
    el.append(HRFlowable(width="100%", thickness=1, color=AZUL))
    seccion_item("A.1", "Actividades curriculares de grado y pregrado",
                 p.a1_descripcion, p.a1_hs_1c, p.a1_hs_2c)
    seccion_item("A.2", "Cursos extracurriculares",
                 p.a2_descripcion, p.a2_hs_1c, p.a2_hs_2c)
    seccion_item("A.3", "Tareas de posgrado",
                 p.a3_descripcion, p.a3_hs_1c, p.a3_hs_2c)
    seccion_item("A.4", "Formación de recursos humanos",
                 p.a4_descripcion, p.a4_hs_1c, p.a4_hs_2c)

    for letra, nombre_sec in [
        ('B', 'INVESTIGACIÓN'),
        ('C', 'TRANSFERENCIAS O SERVICIOS'),
        ('D', 'EXTENSIÓN UNIVERSITARIA'),
        ('E', 'PERFECCIONAMIENTO'),
        ('F', 'GOBIERNO Y GESTIÓN'),
        ('G', 'OTROS'),
    ]:
        el.append(Paragraph(f"{letra}. {nombre_sec}", sec))
        el.append(HRFlowable(width="100%", thickness=1, color=AZUL))
        desc = getattr(p, f'{letra.lower()}_descripcion')
        hs1 = getattr(p, f'{letra.lower()}_hs_1c')
        hs2 = getattr(p, f'{letra.lower()}_hs_2c')
        seccion_item('', '', desc, hs1, hs2)

    # Tabla resumen
    el.append(Spacer(1, 0.4*cm))
    el.append(Paragraph("Resumen de horas planificadas", sec))
    resumen_data = [['Ítem', 'Hs. 1º Cuat.', 'Hs. 2º Cuat.']]
    for label, h1, h2 in p.resumen_items:
        bold = label.startswith('A. ') or label == 'TOTAL'
        resumen_data.append([label, str(h1), str(h2)])

    tr = Table(resumen_data, colWidths=[10*cm, 2.5*cm, 2.5*cm])
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), GRIS2),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [GRIS, colors.white]),
        ('BACKGROUND', (0, -1), (-1, -1), AZUL),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]
    # Negrita en filas de sección (A. Docencia)
    for i, row in enumerate(resumen_data[1:], 1):
        if row[0].startswith('A. '):
            style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
            style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#dce8f5')))
    tr.setStyle(TableStyle(style))
    el.append(tr)

    # Pie
    el.append(Spacer(1, 0.5*cm))
    el.append(HRFlowable(width="100%", thickness=1, color=AZUL))
    pie = Table(
        [[f'Estado: {p.get_estado_display()}', f'N° {p.pk} — {p.fecha_creacion.strftime("%d/%m/%Y")}']],
        colWidths=[8.5*cm, 8.5*cm],
    )
    pie.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    el.append(pie)

    doc.build(el)
    buffer.seek(0)
    return buffer
