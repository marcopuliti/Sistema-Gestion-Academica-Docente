from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0004_materiaenplan_es_optativa'),
    ]

    operations = [
        migrations.AddField(
            model_name='planestudio',
            name='activo',
            field=models.BooleanField(
                default=False,
                verbose_name='Activo',
                help_text='Sin nuevas inscripciones, pero estudiantes inscriptos pueden cursar últimos años y rendir cualquier materia.',
            ),
        ),
    ]
