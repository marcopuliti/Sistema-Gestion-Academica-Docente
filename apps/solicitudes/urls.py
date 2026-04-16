from django.urls import path
from . import views

app_name = 'solicitudes'

TIPOS_VALIDOS = 'obligatoria|optativa|electiva|extracurricular'

urlpatterns = [
    path('', views.lista_solicitudes, name='lista'),
    path('nueva/', views.seleccionar_tipificacion, name='crear'),
    path('nueva/<str:tipificacion>/', views.crear_solicitud, name='crear_con_tipo'),
    path('<int:pk>/', views.detalle_solicitud, name='detalle'),
    path('<int:pk>/editar/', views.editar_solicitud, name='editar'),
    path('<int:pk>/revisar/', views.revisar_solicitud, name='revisar'),
    path('<int:pk>/pdf/', views.descargar_pdf_solicitud, name='pdf'),
    path('<int:pk>/docx/', views.descargar_docx_solicitud, name='docx'),
    path('ajax/planes-por-carrera/', views.planes_por_carrera, name='planes_por_carrera'),
    path('ajax/optativas-por-plan/', views.optativas_por_plan, name='optativas_por_plan'),
]
