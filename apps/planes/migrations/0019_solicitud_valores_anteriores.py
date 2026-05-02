from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0018_solicitud_estado_realizada'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='presidente_anterior_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='Presidente anterior (nombre)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='presidente_anterior_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='Presidente anterior (DNI)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_1_anterior_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='1er. Vocal anterior (nombre)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_1_anterior_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='1er. Vocal anterior (DNI)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_2_anterior_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='2do. Vocal anterior (nombre)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_2_anterior_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='2do. Vocal anterior (DNI)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='dia_semana_anterior',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                choices=[(1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes')],
                verbose_name='Día de la semana anterior',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='hora_anterior',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora anterior'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='permite_libres_anterior',
            field=models.BooleanField(blank=True, null=True, verbose_name='Modalidad anterior'),
        ),
    ]
