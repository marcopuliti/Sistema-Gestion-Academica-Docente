from django.apps import AppConfig


class TramitesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tramites'
    verbose_name = 'Trámites'

    def ready(self):
        # Python 3.14 + Django 4.2 compatibility fix:
        # copy(super()) fails in Python 3.14 because super() objects no longer
        # expose __dict__. Patch BaseContext.__copy__ to avoid it.
        from django.template.context import BaseContext

        def _fixed_copy(self):
            duplicate = self.__class__.__new__(self.__class__)
            duplicate.__dict__ = self.__dict__.copy()
            duplicate.dicts = self.dicts[:]
            return duplicate

        BaseContext.__copy__ = _fixed_copy
