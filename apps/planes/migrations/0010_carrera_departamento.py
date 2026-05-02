from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0009_remove_materiaenplan_nombre'),
    ]

    operations = [
        migrations.AddField(
            model_name='carrera',
            name='departamento',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', '---------'),
                    ('Matemática', 'Matemática'),
                    ('Física', 'Física'),
                    ('Geología', 'Geología'),
                    ('Electrónica', 'Electrónica'),
                    ('Informática', 'Informática'),
                    ('Minería', 'Minería'),
                ],
                max_length=50,
                verbose_name='Departamento',
            ),
        ),
    ]
