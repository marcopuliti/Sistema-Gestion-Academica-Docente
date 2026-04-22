from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

DIRECTORES = [
    ('matematica',   'Matemática'),
    ('fisica',       'Física'),
    ('geologia',     'Geología'),
    ('electronica',  'Electrónica'),
    ('informatica',  'Informática'),
    ('mineria',      'Minería'),
]


class Command(BaseCommand):
    help = 'Crea los 6 usuarios directores de departamento con credenciales iniciales.'

    def handle(self, *args, **options):
        creados = 0
        existentes = 0
        for username, departamento in DIRECTORES:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'  Ya existe: {username}')
                existentes += 1
                continue
            User.objects.create_user(
                username=username,
                password=username,
                first_name='Director de',
                last_name=f'Departamento de {departamento}',
                rol=User.DIRECTOR_DEPARTAMENTO,
                departamento=departamento,
            )
            self.stdout.write(self.style.SUCCESS(f'  Creado: {username} / Departamento: {departamento}'))
            creados += 1

        self.stdout.write(f'\nListo. Creados: {creados} | Ya existían: {existentes}')
        if creados:
            self.stdout.write(self.style.WARNING(
                'Recordá pedirles que cambien la contraseña en el primer acceso.'
            ))
