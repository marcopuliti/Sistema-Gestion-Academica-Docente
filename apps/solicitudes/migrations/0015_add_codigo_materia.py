from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0014_add_dni_to_miembro'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudprotocolizacion',
            name='codigo_materia',
            field=models.CharField(blank=True, max_length=30, verbose_name='Código de materia'),
        ),
    ]
