"""
Corrige acentos faltantes y numerales romanos en los nombres de Materia.
Uso: python manage.py corregir_nombres_materias [--dry-run]
"""
import re

from django.core.management.base import BaseCommand

from apps.planes.models import Materia

FIXES = {
    'Administracion': 'Administración',
    'Adquisicion': 'Adquisición',
    'Algebra': 'Álgebra',
    'Ambito': 'Ámbito',
    'Analogica': 'Analógica',
    'Analogico': 'Analógico',
    'Analisis': 'Análisis',
    'Analitica': 'Analítica',
    'Analitico': 'Analítico',
    'Anatomia': 'Anatomía',
    'Aritmetica': 'Aritmética',
    'Astrofisica': 'Astrofísica',
    'Atomica': 'Atómica',
    'Auditoria': 'Auditoría',
    'Automatas': 'Autómatas',
    'Automatizacion': 'Automatización',
    'Basica': 'Básica',
    'Basico': 'Básico',
    'Biologia': 'Biología',
    'Calculo': 'Cálculo',
    'Cartografia': 'Cartografía',
    'Clasica': 'Clásica',
    'Clasico': 'Clásico',
    'Comunicacion': 'Comunicación',
    'Computacion': 'Computación',
    'Cuantica': 'Cuántica',
    'Curriculo': 'Currículo',
    'Didactica': 'Didáctica',
    'Didacticas': 'Didácticas',
    'Didactico': 'Didáctico',
    'Direccion': 'Dirección',
    'Dinamica': 'Dinámica',
    'Economia': 'Economía',
    'Economica': 'Económica',
    'Economico': 'Económico',
    'Educacion': 'Educación',
    'Electricas': 'Eléctricas',
    'Electricos': 'Eléctricos',
    'Electronica': 'Electrónica',
    'Electronico': 'Electrónico',
    'Energeticos': 'Energéticos',
    'Energia': 'Energía',
    'Eolica': 'Eólica',
    'Eolico': 'Eólico',
    'Epistemologia': 'Epistemología',
    'Especificacion': 'Especificación',
    'Especifica': 'Específica',
    'Especifico': 'Específico',
    'Estadistica': 'Estadística',
    'Estadisticas': 'Estadísticas',
    'Estatica': 'Estática',
    'Estratigrafia': 'Estratigrafía',
    'Etica': 'Ética',
    'Evaluacion': 'Evaluación',
    'Expresion': 'Expresión',
    'Extension': 'Extensión',
    'Fisica': 'Física',
    'Fisicoquimica': 'Fisicoquímica',
    'Fisiologia': 'Fisiología',
    'Fotografia': 'Fotografía',
    'Formacion': 'Formación',
    'Geofisica': 'Geofísica',
    'Geoinformatica': 'Geoinformática',
    'Geologia': 'Geología',
    'Geologico': 'Geológico',
    'Geologica': 'Geológica',
    'Geomorfologia': 'Geomorfología',
    'Geoquimica': 'Geoquímica',
    'Gestion': 'Gestión',
    'Grafica': 'Gráfica',
    'Grafico': 'Gráfico',
    'Hidrogeologia': 'Hidrogeología',
    'Historica': 'Histórica',
    'Historico': 'Histórico',
    'Hormigon': 'Hormigón',
    'Ignea': 'Ígnea',
    'Inalambricas': 'Inalámbricas',
    'Inalambrico': 'Inalámbrico',
    'Informacion': 'Información',
    'Informatica': 'Informática',
    'Informatico': 'Informático',
    'Informaticos': 'Informáticos',
    'Ingenieria': 'Ingeniería',
    'Ingles': 'Inglés',
    'Inorganica': 'Inorgánica',
    'Integracion': 'Integración',
    'Introduccion': 'Introducción',
    'Investigacion': 'Investigación',
    'Legislacion': 'Legislación',
    'Logica': 'Lógica',
    'Matematica': 'Matemática',
    'Matematicas': 'Matemáticas',
    'Matematico': 'Matemático',
    'Matematicos': 'Matemáticos',
    'Mecanica': 'Mecánica',
    'Mecanico': 'Mecánico',
    'Metodologia': 'Metodología',
    'Metodologias': 'Metodologías',
    'Metodos': 'Métodos',
    'Metrologia': 'Metrología',
    'Metamorfica': 'Metamórfica',
    'Mineralogia': 'Mineralogía',
    'Mineria': 'Minería',
    'Modulo': 'Módulo',
    'Numerico': 'Numérico',
    'Numerica': 'Numérica',
    'Organica': 'Orgánica',
    'Organico': 'Orgánico',
    'Organizacion': 'Organización',
    'Paleontologia': 'Paleontología',
    'Pedagogia': 'Pedagogía',
    'Pedagogica': 'Pedagógica',
    'Pedagogico': 'Pedagógico',
    'Petrografia': 'Petrografía',
    'Petrologia': 'Petrología',
    'Practica': 'Práctica',
    'Practicas': 'Prácticas',
    'Problematica': 'Problemática',
    'Produccion': 'Producción',
    'Prospeccion': 'Prospección',
    'Programacion': 'Programación',
    'Psicologia': 'Psicología',
    'Quimica': 'Química',
    'Reingenieria': 'Reingeniería',
    'Representacion': 'Representación',
    'Sedimentologia': 'Sedimentología',
    'Semiotica': 'Semiótica',
    'Simulacion': 'Simulación',
    'Solido': 'Sólido',
    'Tecnica': 'Técnica',
    'Tecnicas': 'Técnicas',
    'Tecnico': 'Técnico',
    'Tecnologia': 'Tecnología',
    'Tecnologias': 'Tecnologías',
    'Tecnologica': 'Tecnológica',
    'Tecnologico': 'Tecnológico',
    'Termica': 'Térmica',
    'Termico': 'Térmico',
    'Termodinamica': 'Termodinámica',
    'Teoria': 'Teoría',
    'Topicos': 'Tópicos',
    'Topografia': 'Topografía',
    'Transmision': 'Transmisión',
}

# Orden importa: patrones más largos primero para evitar sustituciones parciales
ROMAN_FIXES = [
    (r'\bXiii\b', 'XIII'),
    (r'\bXii\b',  'XII'),
    (r'\bXi\b',   'XI'),
    (r'\bIx\b',   'IX'),
    (r'\bViii\b', 'VIII'),
    (r'\bVii\b',  'VII'),
    (r'\bVi\b',   'VI'),
    (r'\bIv\b',   'IV'),
    (r'\bIii\b',  'III'),
    (r'\bIi\b',   'II'),
]

_WORD_PATTERNS = [(re.compile(r'\b' + k + r'\b'), v) for k, v in FIXES.items()]


def _fix(nombre):
    for pattern, replacement in _WORD_PATTERNS:
        nombre = pattern.sub(replacement, nombre)
    for pattern, replacement in ROMAN_FIXES:
        nombre = re.sub(pattern, replacement, nombre)
    return nombre


class Command(BaseCommand):
    help = 'Corrige acentos y numerales romanos en los nombres de Materia.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra cambios sin guardarlos.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        changed = 0
        for materia in Materia.objects.order_by('nombre'):
            nuevo = _fix(materia.nombre)
            if nuevo != materia.nombre:
                self.stdout.write(f'  [{materia.codigo}] "{materia.nombre}" -> "{nuevo}"')
                if not dry:
                    materia.nombre = nuevo
                    materia.save(update_fields=['nombre'])
                changed += 1
        tag = 'Dry-run' if dry else 'Listo'
        self.stdout.write(self.style.SUCCESS(f'{tag}: {changed} materia{"s" if changed != 1 else ""} modificada{"s" if changed != 1 else ""}.'))
