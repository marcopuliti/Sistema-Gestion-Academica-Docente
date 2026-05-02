from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0008_materia_departamento'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='materiaenplan',
            name='nombre',
        ),
    ]
