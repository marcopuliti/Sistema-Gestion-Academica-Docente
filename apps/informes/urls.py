from django.urls import path
from . import views

app_name = 'informes'

urlpatterns = [
    path('', views.lista_informes, name='lista'),
    path('nuevo/', views.crear_informe, name='crear'),
    path('<int:pk>/', views.detalle_informe, name='detalle'),
    path('<int:pk>/editar/', views.editar_informe, name='editar'),
    path('<int:pk>/revisar/', views.revisar_informe, name='revisar'),
    path('<int:pk>/pdf/', views.descargar_pdf_informe, name='pdf'),
]
