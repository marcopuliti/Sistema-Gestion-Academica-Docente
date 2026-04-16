from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.lista_notificaciones, name='lista'),
    path('marcar-leidas/', views.marcar_todas_leidas, name='marcar_leidas'),
]
