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
]
