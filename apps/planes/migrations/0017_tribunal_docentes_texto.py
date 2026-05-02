from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0016_tribunal_dia_hora'),
    ]

    operations = [
        # TribunalExaminador: remove FK fields, add text fields
        migrations.RemoveField(model_name='tribunalexaminador', name='presidente'),
        migrations.RemoveField(model_name='tribunalexaminador', name='vocal_1'),
        migrations.RemoveField(model_name='tribunalexaminador', name='vocal_2'),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='presidente_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='Presidente (nombre)'),
        ),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='presidente_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='Presidente (DNI)'),
        ),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='vocal_1_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='1er. Vocal (nombre)'),
        ),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='vocal_1_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='1er. Vocal (DNI)'),
        ),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='vocal_2_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='2do. Vocal (nombre)'),
        ),
        migrations.AddField(
            model_name='tribunalexaminador',
            name='vocal_2_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='2do. Vocal (DNI)'),
        ),
        # SolicitudCambioTribunal: remove FK fields, add text fields
        migrations.RemoveField(model_name='solicitudcambiotribunal', name='presidente_propuesto'),
        migrations.RemoveField(model_name='solicitudcambiotribunal', name='vocal_1_propuesto'),
        migrations.RemoveField(model_name='solicitudcambiotribunal', name='vocal_2_propuesto'),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='presidente_propuesto_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='Presidente propuesto (nombre)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='presidente_propuesto_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='Presidente propuesto (DNI)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_1_propuesto_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='1er. Vocal propuesto (nombre)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_1_propuesto_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='1er. Vocal propuesto (DNI)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_2_propuesto_nombre',
            field=models.CharField(blank=True, max_length=250, verbose_name='2do. Vocal propuesto (nombre)'),
        ),
        migrations.AddField(
            model_name='solicitudcambiotribunal',
            name='vocal_2_propuesto_dni',
            field=models.CharField(blank=True, max_length=15, verbose_name='2do. Vocal propuesto (DNI)'),
        ),
    ]
