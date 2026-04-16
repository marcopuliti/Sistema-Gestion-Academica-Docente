"""
Importa materias para un plan de estudio específico dado su URL.

Uso:
    python manage.py importar_desde_url <plan_id> <url>
    python manage.py importar_desde_url <plan_id> <url> --limpiar

Ejemplo:
    python manage.py importar_desde_url 3 "http://planesestudio.unsl.edu.ar/index.php?action=car_g3&fac=3&car=03062&plan=28/12&version=3&version_id=884"
"""

from django.core.management.base import BaseCommand, CommandError

from apps.planes.models import PlanEstudio, Materia, MateriaEnPlan
from apps.planes.management.commands.importar_materias import PlanParser, fetch_html


class Command(BaseCommand):
    help = 'Importa materias para un plan de estudio dado su URL'

    def add_arguments(self, parser):
        parser.add_argument('plan_id', type=int, help='ID del plan de estudio')
        parser.add_argument('url', type=str, help='URL de la página del plan en planesestudio.unsl.edu.ar')
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Elimina las materias existentes del plan antes de importar',
        )

    def handle(self, *args, **options):
        plan_id = options['plan_id']
        url = options['url']
        limpiar = options['limpiar']

        try:
            plan = PlanEstudio.objects.select_related('carrera').get(pk=plan_id)
        except PlanEstudio.DoesNotExist:
            raise CommandError(f'No existe un plan con id={plan_id}.')

        self.stdout.write(f'Plan: {plan}')

        if limpiar:
            count = MateriaEnPlan.objects.filter(plan=plan).delete()[0]
            self.stdout.write(f'  Eliminadas {count} materias del plan.')

        self.stdout.write(f'Descargando: {url}')
        try:
            html = fetch_html(url)
        except Exception as e:
            raise CommandError(f'No se pudo obtener la página: {e}')

        parser = PlanParser()
        parser.feed(html)

        if not parser.materias:
            self.stdout.write(self.style.WARNING('No se encontraron materias en la página.'))
            return

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
            f'{creadas} materias vinculadas, {existentes} ya existían.'
        ))
