import os
import subprocess
import sys

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.security
def test_testes_rodam_sem_debug() -> None:
    assert settings.DEBUG is False
    assert settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE


@pytest.mark.security
def test_sem_secret_key_fora_do_debug_a_app_nao_sobe() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("DJANGO_SECRET_KEY", "DJANGO_DEBUG")}
    resultado = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode != 0
    assert "DJANGO_SECRET_KEY" in resultado.stderr


@pytest.mark.security
@pytest.mark.django_db
def test_admin_exige_login(client: Client) -> None:
    resposta = client.get("/admin/", secure=True)
    assert resposta.status_code == 302
    assert "/admin/login/" in resposta["Location"]


@pytest.mark.e2e
@pytest.mark.django_db
def test_staff_faz_login_no_admin(client: Client, django_user_model: type[User]) -> None:
    django_user_model.objects.create_user(
        username="divisao", password="senha-teste-123", is_staff=True
    )
    assert client.login(username="divisao", password="senha-teste-123")
    assert client.get("/admin/", secure=True).status_code == 200


@pytest.mark.security
@pytest.mark.django_db
def test_http_e_redirecionado_para_https(client: Client) -> None:
    resposta = client.get("/admin/")
    assert resposta.status_code == 301
    assert resposta["Location"].startswith("https://")
