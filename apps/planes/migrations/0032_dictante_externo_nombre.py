from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0031_convocatoria_servicio'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudservicio',
            name='dictante_externo_nombre',
            field=models.CharField(
                blank=True, max_length=250,
                verbose_name='Nombre del receptor externo',
                help_text='Solo cuando el departamento dictante es "Externo".',
            ),
        ),
    ]
