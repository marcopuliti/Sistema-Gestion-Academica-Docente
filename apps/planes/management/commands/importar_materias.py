"""
Importa materias desde planesestudio.unsl.edu.ar y las vincula a planes de estudio.

Uso:
    python manage.py importar_materias
    python manage.py importar_materias --carrera 03062
    python manage.py importar_materias --limpiar
"""

import re
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser

from django.core.management.base import BaseCommand

from apps.planes.models import Carrera, PlanEstudio, Materia, MateriaEnPlan

BASE_URL = 'http://planesestudio.unsl.edu.ar/'

# codigo_carrera → URL relativa del plan vigente más reciente
PLANES_VIGENTES = {
    '03025': 'index.php?action=car_g3&fac=3&car=03025&plan=6/24&version=1&version_id=1206',
    '03062': 'index.php?action=car_g3&fac=3&car=03062&plan=28/12&version=3&version_id=884',
    '03061': 'index.php?action=car_g3&fac=3&car=03061&plan=2/25&version=3&version_id=1253',
    '03054': 'index.php?action=car_g3&fac=3&car=03054&plan=11/23&version=1&version_id=878',
    '16001': 'index.php?action=car_g3&fac=16&car=16001&plan=27/22&version=2&version_id=614',
    '03003': 'index.php?action=car_g3&fac=3&car=03003&plan=1/23&version=3&version_id=1248',
    '03004': 'index.php?action=car_g3&fac=3&car=03004&plan=02/22&version=5&version_id=1115',
    '03002': 'index.php?action=car_g3&fac=3&car=03002&plan=09/17&version=3&version_id=629',
    '03001': 'index.php?action=car_g3&fac=3&car=03001&plan=15/06&version=5&version_id=246',
    '03058': 'index.php?action=car_g3&fac=3&car=03058&plan=12/14&version=3&version_id=338',
    '03034': 'index.php?action=car_g3&fac=3&car=03034&plan=14/05&version=2&version_id=116',
    '03024': 'index.php?action=car_g3&fac=3&car=03024&plan=02/16&version=2&version_id=232',
    '03014': 'index.php?action=car_g3&fac=3&car=03014&plan=16/06&version=3&version_id=682',
    '03060': 'index.php?action=car_g3&fac=3&car=03060&plan=21/13&version=3&version_id=1198',
    '03027': 'index.php?action=car_g3&fac=3&car=03027&plan=5/09&version=5&version_id=248',
    '03035': 'index.php?action=car_g3&fac=3&car=03035&plan=13/05&version=2&version_id=115',
    '03TUE': 'index.php?action=car_g3&fac=3&car=03TUE&plan=15/13&version=1&version_id=178',
    '03TER': 'index.php?action=car_g3&fac=3&car=03TER&plan=05/13&version=2&version_id=327',
    '03TEM': 'index.php?action=car_g3&fac=3&car=03TEM&plan=14/13&version=2&version_id=221',
    '03063': 'index.php?action=car_g3&fac=3&car=03063&plan=15/15&version=4&version_id=866',
    '03059': 'index.php?action=car_g3&fac=3&car=03059&plan=09/13&version=3&version_id=340',
    '03TUM': 'index.php?action=car_g3&fac=3&car=03TUM&plan=4/20&version=4&version_id=1168',
    '03TOV': 'index.php?action=car_g3&fac=3&car=03TOV&plan=01/18&version=6&version_id=1234',
    '03TPM': 'index.php?action=car_g3&fac=3&car=03TPM&plan=11/13&version=3&version_id=333',
    '03053': 'index.php?action=car_g3&fac=3&car=03053&plan=12/15&version=3&version_id=1189',
    '03TUT': 'index.php?action=car_g3&fac=3&car=03TUT&plan=16/13&version=2&version_id=180',
    '03064': 'index.php?action=car_g3&fac=3&car=03064&plan=13/22&version=2&version_id=627',
    '03052': 'index.php?action=car_g3&fac=3&car=03052&plan=08/13&version=1&version_id=174',
    '03008': 'index.php?action=car_g3&fac=3&car=03008&plan=8/01&version=2&version_id=111',
}

ANO_PALABRAS = {
    'primer': 1, 'primero': 1, 'primera': 1,
    'segundo': 2, 'segunda': 2,
    'tercer': 3, 'tercero': 3, 'tercera': 3,
    'cuarto': 4, 'cuarta': 4,
    'quinto': 5, 'quinta': 5,
}


def _parsear_plan_desde_url(url_relativa):
    """Extrae el codigo de plan desde la URL relativa."""
    qs = urllib.parse.parse_qs(urllib.parse.urlparse('?' + url_relativa.split('?', 1)[-1]).query)
    return qs.get('plan', [''])[0]


def parsear_cuatrimestre(texto):
    t = texto.lower().strip()
    if 'anual' in t:
        return 3
    if re.search(r'2[°.]?\s*(cuatrimestre|cuat)|2do\s*cuat', t):
        return 2
    if re.search(r'1[°.]?\s*(cuatrimestre|cuat)|1er\s*cuat', t):
        return 1
    return 1


def parsear_ano_desde_titulo(titulo):
    titulo_lower = titulo.lower()
    for palabra, numero in ANO_PALABRAS.items():
        if palabra in titulo_lower:
            return numero
    return None


class PlanParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.materias = []
        self._en_tabla_ano = False
        self._ano_actual = None
        self._en_fila = False
        self._col = 0
        self._en_celda = False
        self._texto_celda = ''
        self._fila_actual = []
        self._es_optativa = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self._en_tabla_ano = False
            self._es_optativa = False
        elif tag == 'tr':
            self._en_fila = True
            self._col = 0
            self._fila_actual = []
        elif tag in ('td', 'th'):
            self._en_celda = True
            self._texto_celda = ''

    def _procesar_celda(self, texto):
        texto_lower = texto.lower()
        if 'materias del' in texto_lower:
            ano = parsear_ano_desde_titulo(texto_lower)
            if ano:
                self._en_tabla_ano = True
                self._ano_actual = ano
                self._es_optativa = False
        elif 'materias optativas de' in texto_lower:
            self._es_optativa = True
            self._en_tabla_ano = False

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self._en_celda = False
            texto = re.sub(r'\s+', ' ', self._texto_celda).strip()
            if tag == 'td':
                self._fila_actual.append(texto)
            self._procesar_celda(texto)
            self._col += 1

        elif tag == 'tr':
            self._en_fila = False
            if self._en_tabla_ano and not self._es_optativa and len(self._fila_actual) >= 3:
                cod_raw = self._fila_actual[0]
                nombre = self._fila_actual[1].strip()
                periodo = self._fila_actual[2] if len(self._fila_actual) > 2 else ''
                m = re.search(r'\(([^)]+)\)', cod_raw)
                codigo = m.group(1).strip() if m else cod_raw.strip()
                cuatrimestre = parsear_cuatrimestre(periodo)
                if nombre and self._ano_actual and not nombre.lower().startswith('materias'):
                    self.materias.append({
                        'codigo': codigo,
                        'nombre': nombre,
                        'ano': self._ano_actual,
                        'cuatrimestre': cuatrimestre,
                    })

        elif tag == 'table':
            self._en_tabla_ano = False

    def handle_data(self, data):
        if self._en_celda:
            self._texto_celda += data


def fetch_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    # Charset del header HTTP (no siempre es correcto)
    http_charset = resp.headers.get_content_charset()
    # Charset del <meta> del HTML (más confiable)
    meta_match = re.search(rb'charset["\s]*=["\s]*([a-zA-Z0-9_-]+)', raw)
    meta_charset = meta_match.group(1).decode('ascii') if meta_match else None
    charset = meta_charset or http_charset or 'latin-1'
    try:
        return raw.decode(charset)
    except (UnicodeDecodeError, LookupError):
        return raw.decode('latin-1')


class Command(BaseCommand):
    help = 'Importa materias de los planes vigentes desde planesestudio.unsl.edu.ar'

    def add_arguments(self, parser):
        parser.add_argument('--carrera', type=str, help='Código de carrera (ej: 03062)')
        parser.add_argument('--limpiar', action='store_true',
                            help='Elimina materias y planes existentes antes de importar')

    def handle(self, *args, **options):
        carrera_filter = options.get('carrera')
        limpiar = options.get('limpiar')

        if limpiar:
            if carrera_filter:
                count = MateriaEnPlan.objects.filter(plan__carrera__codigo=carrera_filter).delete()[0]
                PlanEstudio.objects.filter(carrera__codigo=carrera_filter).delete()
                self.stdout.write(f'  Eliminadas {count} relaciones materia-plan de {carrera_filter}.')
            else:
                MateriaEnPlan.objects.all().delete()
                PlanEstudio.objects.all().delete()
                self.stdout.write('  Eliminados todos los planes y sus materias.')

        planes = PLANES_VIGENTES
        if carrera_filter:
            planes = {k: v for k, v in PLANES_VIGENTES.items() if k == carrera_filter}
            if not planes:
                self.stderr.write(f'Carrera {carrera_filter} no encontrada en el mapa de planes.')
                return

        total_mat_creadas = 0
        total_mat_existentes = 0

        for codigo_carrera, url_relativa in planes.items():
            try:
                carrera = Carrera.objects.get(codigo=codigo_carrera)
            except Carrera.DoesNotExist:
                self.stderr.write(f'  [SKIP] Carrera {codigo_carrera} no existe. Ejecutá actualizar_carreras primero.')
                continue

            cod_plan = _parsear_plan_desde_url(url_relativa)
            plan, plan_creado = PlanEstudio.objects.update_or_create(
                carrera=carrera,
                codigo=cod_plan,
                defaults={'vigente': True},
            )
            accion = 'creado' if plan_creado else 'actualizado'
            self.stdout.write(f'>> {carrera.nombre} — Plan {cod_plan} ({accion})')

            url = BASE_URL + url_relativa
            try:
                html = fetch_html(url)
            except Exception as e:
                self.stderr.write(f'  [ERROR] {url}: {e}')
                continue

            parser = PlanParser()
            parser.feed(html)

            if not parser.materias:
                self.stdout.write(self.style.WARNING('  Sin materias encontradas.'))
                continue

            creadas = 0
            existentes = 0
            for m in parser.materias:
                nombre = m['nombre'].title()
                materia, _ = Materia.objects.get_or_create(
                    codigo=m['codigo'],
                    defaults={'nombre': nombre},
                )
                _, rel_creada = MateriaEnPlan.objects.get_or_create(
                    materia=materia,
                    plan=plan,
                    defaults={'ano': m['ano'], 'cuatrimestre': m['cuatrimestre']},
                )
                if rel_creada:
                    creadas += 1
                else:
                    existentes += 1

            self.stdout.write(self.style.SUCCESS(
                f'  {creadas} materias vinculadas, {existentes} ya existían.'
            ))
            total_mat_creadas += creadas
            total_mat_existentes += existentes

            time.sleep(0.5)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Total: {total_mat_creadas} vínculos creados, {total_mat_existentes} ya existían.'
        ))
