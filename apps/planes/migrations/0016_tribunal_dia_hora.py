from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0015_tribunal_docentes_nullable'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tribunalexaminador',
            name='fecha_hora',
        ),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='dia_semana',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                choices=[(1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes')],
                verbose_name='Día de la semana',
            ),
        ),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='hora',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora del examen'),
        ),
        migrations.RemoveField(
            model_name='solicitudcambiotribunal',
            name='fecha_hora_propuesta',
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='dia_semana_propuesto',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                choices=[(1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes')],
                verbose_name='Día de la semana propuesto',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='hora_propuesta',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora propuesta'),
        ),
    ]
