from django.contrib import admin
from .models import InformeActividadAnual


@admin.register(InformeActividadAnual)
class InformeAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'anno_academico', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'anno_academico')
    search_fields = ('usuario__last_name', 'usuario__first_name')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
