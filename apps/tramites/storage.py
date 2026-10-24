"""Storage de Django que guarda los archivos subidos en la base de datos."""
import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    """Cada archivo es una fila de ArchivoAlmacenado. Los archivos se sirven con la vista
    tramites:archivo (solo usuarios autenticados)."""

    @staticmethod
    def _modelo():
        from .models import ArchivoAlmacenado
        return ArchivoAlmacenado

    def _open(self, name, mode='rb'):
        archivo = self._modelo().objects.get(nombre=name)
        return ContentFile(bytes(archivo.contenido), name=name)

    def _save(self, name, content):
        if hasattr(content, 'seek'):
            content.seek(0)
        datos = b''.join(content.chunks()) if hasattr(content, 'chunks') else content.read()
        tipo = getattr(content, 'content_type', '') or mimetypes.guess_type(name)[0] or ''
        self._modelo().objects.update_or_create(
            nombre=name, defaults={'contenido': datos, 'tipo': tipo, 'tamanio': len(datos)},
        )
        return name

    def get_available_name(self, name, max_length=None):
        # os.path.join usa '\' en Windows; los nombres se guardan siempre con '/'
        return super().get_available_name(name.replace('\\', '/'), max_length).replace('\\', '/')

    def exists(self, name):
        return self._modelo().objects.filter(nombre=name).exists()

    def delete(self, name):
        self._modelo().objects.filter(nombre=name).delete()

    def size(self, name):
        return self._modelo().objects.values_list('tamanio', flat=True).get(nombre=name)

    def url(self, name):
        return reverse('tramites:archivo', args=[name])
