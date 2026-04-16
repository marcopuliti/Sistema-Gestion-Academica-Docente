from django.urls import path
from . import views

app_name = 'tramites'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
