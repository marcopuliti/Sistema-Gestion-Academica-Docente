from django.contrib import admin
from .models import PlanificacionActividades


@admin.register(PlanificacionActividades)
class PlanificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'anno', 'cargo', 'dedicacion', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'anno', 'cargo')
    search_fields = ('usuario__last_name', 'usuario__first_name')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
