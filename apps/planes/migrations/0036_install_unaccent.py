from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0035_solicitudservicio_carrera'),
    ]

    operations = [
        UnaccentExtension(),
    ]
