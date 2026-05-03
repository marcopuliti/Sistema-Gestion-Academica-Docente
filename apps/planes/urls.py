from django.urls import path
from . import views

app_name = 'planes'

urlpatterns = [
    path('planes/materias-servicio/', views.materias_servicio, name='materias_servicio'),
    path('planes/tribunales/', views.lista_tribunales, name='lista_tribunales'),
    path('planes/tribunales/<int:pk>/modificar/', views.modificar_tribunal, name='modificar_tribunal'),
    path('planes/tribunales/<int:pk>/copiar/', views.copiar_tribunal, name='copiar_tribunal'),
    path('planes/admin/tribunales/', views.lista_comparacion_tribunales, name='lista_comparacion_tribunales'),
    path('planes/admin/tribunales/<int:pk>/', views.detalle_tribunal_admin, name='detalle_tribunal_admin'),
    path('planes/admin/tribunales/<int:pk>/sincronizar/', views.sincronizar_tribunal, name='sincronizar_tribunal'),
    path('planes/admin/tribunales/<int:pk>/admin-modificar/', views.admin_modificar_tribunal, name='admin_modificar_tribunal'),
    path('planes/admin/tribunales/solicitar-informe/', views.solicitar_informe_tribunales, name='solicitar_informe_tribunales'),
    path('planes/tribunales/enviar-informe/', views.enviar_informe_tribunales, name='enviar_informe_tribunales'),
    path('planes/tribunales/descargar-informe/', views.descargar_informe_tribunales, name='descargar_informe_tribunales'),
    path('planes/tribunales/pdf-modificaciones/', views.generar_pdf_modificaciones, name='generar_pdf_modificaciones'),
]
