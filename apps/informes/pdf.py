from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO


COLOR_PRIMARIO = colors.HexColor('#1a3a5c')
COLOR_SECUNDARIO = colors.HexColor('#2e86c1')
COLOR_GRIS = colors.HexColor('#f2f3f4')


def generar_pdf_informe(informe):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'Titulo',
        parent=styles['Title'],
        fontSize=16,
        textColor=COLOR_PRIMARIO,
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    estilo_subtitulo = ParagraphStyle(
        'Subtitulo',
        parent=styles['Normal'],
        fontSize=11,
        textColor=COLOR_SECUNDARIO,
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    estilo_seccion = ParagraphStyle(
        'Seccion',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=COLOR_PRIMARIO,
        spaceBefore=12,
        spaceAfter=4,
    )
    estilo_normal = ParagraphStyle(
        'Normal2',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        leading=14,
    )
    estilo_label = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=2,
    )

    elementos = []

    # Encabezado
    elementos.append(Paragraph("FACULTAD", estilo_subtitulo))
    elementos.append(Paragraph("Informe de Actividad Anual Docente", estilo_titulo))
    elementos.append(Paragraph(f"Año Académico: {informe.anno_academico}", estilo_subtitulo))
    elementos.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARIO))
    elementos.append(Spacer(1, 0.4*cm))

    # Datos del docente
    elementos.append(Paragraph("Datos del Docente", estilo_seccion))
    datos_docente = [
        ['Apellido y Nombre:', informe.get_nombre_docente],
        ['Legajo:', (informe.usuario.legajo if informe.usuario else None) or informe.legajo_docente or '-'],
        ['Departamento:', (informe.usuario.departamento if informe.usuario else None) or informe.departamento_docente or '-'],
        ['Categoría:', informe.categoria],
        ['Dedicación:', informe.get_dedicacion_display()],
        ['Email:', (informe.usuario.email if informe.usuario else None) or informe.email_docente or '-'],
    ]
    tabla_datos = Table(datos_docente, colWidths=[5*cm, 12*cm])
    tabla_datos.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [COLOR_GRIS, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla_datos)
    elementos.append(Spacer(1, 0.3*cm))

    def agregar_seccion(titulo, contenido):
        if contenido:
            elementos.append(Paragraph(titulo, estilo_seccion))
            elementos.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SECUNDARIO))
            elementos.append(Spacer(1, 0.2*cm))
            elementos.append(Paragraph(contenido.replace('\n', '<br/>'), estilo_normal))

    # Docencia
    elementos.append(Paragraph("Actividades de Docencia", estilo_seccion))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SECUNDARIO))
    elementos.append(Spacer(1, 0.2*cm))
    elementos.append(Paragraph(f"<b>Carga horaria semanal:</b> {informe.carga_horaria_docencia} hs", estilo_normal))
    elementos.append(Paragraph("<b>Materias dictadas:</b>", estilo_normal))
    elementos.append(Paragraph(informe.materias_dictadas.replace('\n', '<br/>'), estilo_normal))

    agregar_seccion("Actividades de Investigación", informe.actividades_investigacion)
    agregar_seccion("Actividades de Extensión", informe.actividades_extension)
    agregar_seccion("Actividades de Gestión", informe.actividades_gestion)
    agregar_seccion("Formación y Capacitación", informe.actividades_formacion)
    agregar_seccion("Observaciones Adicionales", informe.observaciones)

    # Firma
    elementos.append(Spacer(1, 1.5*cm))
    elementos.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARIO))
    elementos.append(Spacer(1, 0.2*cm))
    firma_data = [
        [f'Estado: {informe.get_estado_display()}', f'Fecha: {informe.fecha_creacion.strftime("%d/%m/%Y")}'],
    ]
    tabla_firma = Table(firma_data, colWidths=[8.5*cm, 8.5*cm])
    tabla_firma.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elementos.append(tabla_firma)

    doc.build(elementos)
    buffer.seek(0)
    return buffer
