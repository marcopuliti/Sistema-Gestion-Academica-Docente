from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0007_docente_tribunalexaminador'),
    ]

    operations = [
        migrations.AddField(
            model_name='materia',
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
