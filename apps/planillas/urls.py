from django.urls import path
from . import views

app_name = 'planillas'

urlpatterns = [
    path('', views.lista_planillas, name='lista'),
    path('nueva/', views.crear_planilla, name='crear'),
    path('<int:pk>/', views.detalle_planilla, name='detalle'),
    path('<int:pk>/editar/', views.editar_planilla, name='editar'),
    path('<int:pk>/revisar/', views.revisar_planilla, name='revisar'),
    path('<int:pk>/pdf/', views.descargar_pdf_planilla, name='pdf'),
]
