from django.urls import path
from . import views

app_name = 'solicitudes'

TIPOS_VALIDOS = 'optativa|taller|curso|jornada|congreso'

urlpatterns = [
    path('', views.lista_solicitudes, name='lista'),
    path('nueva/', views.seleccionar_tipificacion, name='crear'),
    path('nueva/<str:tipificacion>/', views.crear_solicitud, name='crear_con_tipo'),
    path('<int:pk>/', views.detalle_solicitud, name='detalle'),
    path('<int:pk>/editar/', views.editar_solicitud, name='editar'),
    path('<int:pk>/revisar/', views.revisar_solicitud, name='revisar'),
    path('<int:pk>/revisar-director/', views.revisar_director, name='revisar_director'),
    path('<int:pk>/pdf/', views.descargar_pdf_solicitud, name='pdf'),
    path('<int:pk>/docx/', views.descargar_docx_solicitud, name='docx'),
    path('<int:pk>/nota-elevacion/pdf/', views.descargar_pdf_nota_elevacion, name='nota_elevacion_pdf'),
    path('<int:pk>/nota-elevacion/docx/', views.descargar_docx_nota_elevacion, name='nota_elevacion_docx'),
    path('<int:pk>/solicitud-completa/pdf/', views.descargar_pdf_solicitud_completa, name='solicitud_completa_pdf'),
    path('<int:pk>/solicitud-completa/docx/', views.descargar_docx_solicitud_completa, name='solicitud_completa_docx'),
    path('<int:pk>/nota-comision/pdf/', views.descargar_pdf_nota_comision, name='nota_comision_pdf'),
    path('<int:pk>/nota-comision/docx/', views.descargar_docx_nota_comision, name='nota_comision_docx'),
    path('departamento/', views.lista_solicitudes_departamento, name='lista_departamento'),
    path('<int:pk>/codigo-materia/', views.agregar_codigo_materia, name='agregar_codigo_materia'),
    path('<int:pk>/actas-aval/', views.subir_actas_aval, name='subir_actas_aval'),
    path('ajax/planes-por-carrera/', views.planes_por_carrera, name='planes_por_carrera'),
    path('ajax/optativas-por-plan/', views.optativas_por_plan, name='optativas_por_plan'),
    path('ajax/materias-por-plan/', views.materias_por_plan, name='materias_por_plan'),
    # Talleres
    path('talleres/', views.lista_talleres, name='lista_talleres'),
    path('talleres/nuevo/', views.crear_taller, name='crear_taller'),
    path('talleres/<int:pk>/', views.detalle_taller, name='detalle_taller'),
    path('talleres/<int:pk>/editar/', views.editar_taller, name='editar_taller'),
    path('talleres/<int:pk>/revisar/', views.revisar_taller, name='revisar_taller'),
    path('talleres/<int:pk>/revisar-director/', views.revisar_director_taller, name='revisar_director_taller'),
    path('talleres/<int:pk>/acta-aval/', views.subir_acta_taller, name='subir_acta_taller'),
    path('talleres/<int:pk>/pdf/', views.descargar_pdf_taller, name='pdf_taller'),
]
