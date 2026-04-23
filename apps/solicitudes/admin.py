from django.contrib import admin
from .models import SolicitudProtocolizacion, MiembroEquipoDocente, SolicitudTaller


class MiembroInline(admin.TabularInline):
    model = MiembroEquipoDocente
    extra = 1


@admin.register(SolicitudProtocolizacion)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ('nombre_curso', 'usuario', 'periodo', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'periodo', 'tipificacion')
    search_fields = ('nombre_curso', 'usuario__last_name', 'usuario__first_name')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    inlines = [MiembroInline]


@admin.register(SolicitudTaller)
class SolicitudTallerAdmin(admin.ModelAdmin):
    list_display = ('denominacion_curso', 'get_nombre_docente', 'estado', 'fecha_creacion')
    list_filter = ('estado',)
    search_fields = ('denominacion_curso', 'responsable_nombre')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
