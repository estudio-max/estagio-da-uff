from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.test import Client


@pytest.mark.smoke
@pytest.mark.django_db
def test_health_responde_ok_com_banco_disponivel(client: Client) -> None:
    resposta = client.get("/health/")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


@pytest.mark.unit
def test_health_responde_503_quando_banco_cai(client: Client) -> None:
    with patch("core.views.connection.cursor", side_effect=DatabaseError):
        resposta = client.get("/health/")
    assert resposta.status_code == 503
    assert resposta.json()["banco"] == "indisponivel"
