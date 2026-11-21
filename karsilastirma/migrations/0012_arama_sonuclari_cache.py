from django.core.management import call_command
from django.db import migrations


def arama_cache_tablosu_olustur(apps, schema_editor):
    call_command('createcachetable', 'arama_sonuclari_cache', database=schema_editor.connection.alias)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('karsilastirma', '0011_create_cache_table')]
    operations = [migrations.RunPython(arama_cache_tablosu_olustur, migrations.RunPython.noop)]
