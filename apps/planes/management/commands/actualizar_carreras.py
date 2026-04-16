"""
Crea o actualiza las carreras de la FCFMyN-UNSL.

Uso:
    python manage.py actualizar_carreras
"""

from django.core.management.base import BaseCommand
from apps.planes.models import Carrera

CARRERAS = [
    ('03025', 'Ingeniería Electrónica con Orientación en Sistemas Digitales', 5),
    ('03062', 'Ingeniería en Computación', 5),
    ('03061', 'Ingeniería en Informática', 5),
    ('03054', 'Ingeniería en Minas', 5),
    ('16001', 'Licenciatura en Análisis y Gestión de Datos', 5),
    ('03003', 'Licenciatura en Ciencias de la Computación', 5),
    ('03004', 'Licenciatura en Ciencias Geológicas', 5),
    ('03002', 'Licenciatura en Ciencias Matemáticas', 4),
    ('03001', 'Licenciatura en Física', 5),
    ('03024', 'Profesorado en Ciencias de la Computación', 4),
    ('03014', 'Profesorado en Física', 4),
    ('03060', 'Profesorado en Matemática', 4),
    ('03027', 'Profesorado en Tecnología Electrónica', 4),
    ('03TUE', 'Tecnicatura Universitaria en Electrónica', 3),
    ('03TER', 'Tecnicatura Universitaria en Energías Renovables', 3),
    ('03063', 'Tecnicatura Universitaria en Fotografía', 3),
    ('03TUM', 'Tecnicatura Universitaria en Minería', 3),
    ('03TOV', 'Tecnicatura Universitaria en Obras Viales', 3),
    ('03053', 'Tecnicatura Universitaria en Redes de Computadoras', 3),
    ('03TUT', 'Tecnicatura Universitaria en Telecomunicaciones', 3),
    ('03064', 'Tecnicatura Universitaria en Teledetección y Sistemas de Información Geográfica', 3),
    ('03052', 'Tecnicatura Universitaria en Web', 3),
]


class Command(BaseCommand):
    help = 'Crea o actualiza las carreras de la FCFMyN-UNSL'

    def handle(self, *args, **options):
        creadas = 0
        actualizadas = 0
        for codigo, nombre, duracion in CARRERAS:
            _, created = Carrera.objects.update_or_create(
                codigo=codigo,
                defaults={'nombre': nombre, 'duracion_anos': duracion},
            )
            if created:
                creadas += 1
            else:
                actualizadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'Carreras: {creadas} creadas, {actualizadas} actualizadas.'
        ))
