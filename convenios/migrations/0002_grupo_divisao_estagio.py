"""RN04: só a Divisão de Estágio escreve. Basta adicionar o usuário (com is_staff) a este grupo."""

from django.apps.registry import Apps
from django.contrib.auth.management import create_permissions
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

GRUPO = "Divisão de Estágio"

# Convênio e concedente não são excluídos: convênio errado vira "cancelado" e fica no histórico.
PERMISSOES = [
    "add_concedente",
    "change_concedente",
    "view_concedente",
    "add_convenio",
    "change_convenio",
    "view_convenio",
    "add_etapaconvenio",
    "change_etapaconvenio",
    "delete_etapaconvenio",
    "view_etapaconvenio",
]


def criar_grupo(apps: Apps, _schema_editor: BaseDatabaseSchemaEditor) -> None:
    # Permissões normalmente só existem após o post_migrate; aqui precisamos delas já.
    config = apps.get_app_config("convenios")
    config.models_module = True
    create_permissions(config, verbosity=0, apps=apps)

    group = apps.get_model("auth", "Group")
    permission = apps.get_model("auth", "Permission")
    grupo, _ = group.objects.get_or_create(name=GRUPO)
    grupo.permissions.set(
        permission.objects.filter(content_type__app_label="convenios", codename__in=PERMISSOES)
    )


def remover_grupo(apps: Apps, _schema_editor: BaseDatabaseSchemaEditor) -> None:
    apps.get_model("auth", "Group").objects.filter(name=GRUPO).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("convenios", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(criar_grupo, remover_grupo)]
