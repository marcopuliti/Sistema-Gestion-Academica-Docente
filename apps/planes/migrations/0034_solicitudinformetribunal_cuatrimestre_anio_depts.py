from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0033_alter_carrera_departamento_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudinformetribunal',
            name='cuatrimestre',
            field=models.PositiveSmallIntegerField(
                choices=[(1, 'Primer cuatrimestre'), (2, 'Segundo cuatrimestre')],
                default=1,
                verbose_name='Cuatrimestre',
            ),
        ),
        migrations.AddField(
            model_name='solicitudinformetribunal',
            name='anio',
            field=models.PositiveIntegerField(default=2025, verbose_name='Año'),
        ),
        migrations.AddField(
            model_name='solicitudinformetribunal',
            name='departamentos_notificados',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Q1: vacío (todos). Q2: lista de departamentos con nuevos tribunales.',
                verbose_name='Departamentos notificados',
            ),
        ),
    ]
