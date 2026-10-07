"""Divisão de Estágio vê (só vê) os alertas de vencimento enviados."""

from django.apps.registry import Apps
from django.contrib.auth.management import create_permissions
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def dar_permissao(apps: Apps, _schema_editor: BaseDatabaseSchemaEditor) -> None:
    config = apps.get_app_config("convenios")
    config.models_module = True
    create_permissions(config, verbosity=0, apps=apps)
    permissao = apps.get_model("auth", "Permission").objects.get(
        content_type__app_label="convenios", codename="view_alertavencimento"
    )
    grupo = apps.get_model("auth", "Group").objects.get(name="Divisão de Estágio")
    grupo.permissions.add(permissao)


class Migration(migrations.Migration):
    dependencies = [("convenios", "0003_alerta_vencimento")]

    operations = [migrations.RunPython(dar_permissao, migrations.RunPython.noop)]
