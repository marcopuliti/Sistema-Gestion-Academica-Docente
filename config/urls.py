from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.tramites.urls', namespace='tramites')),
    path('cuentas/', include('apps.accounts.urls', namespace='accounts')),
    path('solicitudes/', include('apps.solicitudes.urls', namespace='solicitudes')),
    path('notificaciones/', include('apps.notifications.urls', namespace='notifications')),
    path('', include('apps.planes.urls', namespace='planes')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
