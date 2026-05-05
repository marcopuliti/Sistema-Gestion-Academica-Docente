from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from apps.planes.models import Carrera

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea un usuario director de carrera por cada carrera registrada en la base de datos.'

    def handle(self, *args, **options):
        carreras = Carrera.objects.order_by('nombre')
        if not carreras.exists():
            self.stdout.write(self.style.WARNING('No hay carreras registradas en la base de datos.'))
            return

        creados = 0
        existentes = 0
        for carrera in carreras:
            username = f'carrera_{carrera.codigo.lower()}'
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'  Ya existe: {username}')
                existentes += 1
                continue
            User.objects.create_user(
                username=username,
                password=username,
                first_name='Director/a de',
                last_name=carrera.nombre,
                rol=User.DIRECTOR_CARRERA,
                carrera=carrera,
            )
            self.stdout.write(self.style.SUCCESS(
                f'  Creado: {username} / Carrera: {carrera.nombre} ({carrera.codigo})'
            ))
            creados += 1

        self.stdout.write(f'\nListo. Creados: {creados} | Ya existían: {existentes}')
        if creados:
            self.stdout.write(self.style.WARNING(
                'Recordá pedirles que cambien la contraseña en el primer acceso.'
            ))
