from django.urls import path

from convenios.views import DetalhePublico, ListaPublica

app_name = "convenios"

urlpatterns = [
    path("", ListaPublica.as_view(), name="lista"),
    path("convenios/<int:pk>/", DetalhePublico.as_view(), name="detalhe"),
]
