from django.urls import path
from . import views

app_name = 'planes'

urlpatterns = [
    # Director: materias
    path('planes/materias-servicio/', views.materias_servicio, name='materias_servicio'),

    # Director: tribunales
    path('planes/tribunales/', views.lista_tribunales, name='lista_tribunales'),
    path('planes/tribunales/<int:pk>/proponer-cambio/', views.proponer_cambio_tribunal, name='proponer_cambio_tribunal'),
    path('planes/tribunales/enviar-solicitud/', views.enviar_solicitud_cambio, name='enviar_solicitud_cambio'),
    path('planes/tribunales/solicitudes/<int:pk>/descargar/', views.descargar_solicitud_cambio, name='descargar_solicitud_cambio'),

    # Director: solicitudes de cambio propias
    path('planes/tribunales/mis-solicitudes/', views.mis_solicitudes_cambio, name='mis_solicitudes_cambio'),

    # Director: informe anual
    path('planes/tribunales/enviar-informe/', views.enviar_informe_tribunales, name='enviar_informe_tribunales'),
    path('planes/tribunales/descargar-informe/', views.descargar_informe_tribunales, name='descargar_informe_tribunales'),

    # Admin: informe anual
    path('planes/admin/tribunales/solicitar-informe/', views.solicitar_informe_tribunales, name='solicitar_informe_tribunales'),

    # Admin: materias en plan
    path('planes/admin/materias-en-plan/', views.admin_lista_materias_en_plan, name='admin_lista_materias_en_plan'),
    path('planes/admin/materias-en-plan/<int:pk>/crear-tribunal/', views.admin_crear_tribunal, name='admin_crear_tribunal'),

    # Admin: solicitudes de cambio
    path('planes/admin/solicitudes-cambio/', views.lista_solicitudes_cambio, name='lista_solicitudes_cambio'),
    path('planes/admin/solicitudes-cambio/<int:pk>/', views.detalle_solicitud_cambio, name='detalle_solicitud_cambio'),
    path('planes/admin/solicitudes-cambio/<int:pk>/aplicar/', views.aplicar_solicitud, name='aplicar_solicitud'),
    path('planes/admin/solicitudes-cambio/<int:pk>/descargar/', views.admin_descargar_solicitud_cambio, name='admin_descargar_solicitud_cambio'),

    # Solicitudes de servicio (director de departamento — solo lectura)
    path('planes/solicitudes-servicio/', views.lista_solicitudes_servicio, name='lista_solicitudes_servicio'),
    path('planes/solicitudes-servicio/<int:pk>/', views.detalle_solicitud_servicio, name='detalle_solicitud_servicio'),
    path('planes/solicitudes-servicio/<int:pk>/descargar/', views.descargar_solicitud_servicio, name='descargar_solicitud_servicio'),
    path('planes/admin/solicitudes-servicio/', views.admin_lista_solicitudes_servicio, name='admin_lista_solicitudes_servicio'),
    path('planes/admin/solicitudes-servicio/convocar/', views.convocar_solicitudes_servicio, name='convocar_solicitudes_servicio'),

    # Director de carrera
    path('planes/carrera/materias/', views.materias_carrera, name='materias_carrera'),
    path('planes/carrera/solicitudes-servicio/', views.lista_solicitudes_servicio_carrera, name='lista_solicitudes_servicio_carrera'),
    path('planes/carrera/solicitudes-servicio/nueva/', views.nueva_solicitud_servicio_carrera, name='nueva_solicitud_servicio_carrera'),
]
