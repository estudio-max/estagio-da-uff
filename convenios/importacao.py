"""RF07: importação dos convênios do estagio.uff.br (exportação XML do Drupal).

Idempotente: a chave é o nó do Drupal (`id_drupal`); rodar de novo atualiza em vez de duplicar.
Nada é inventado: registro sem dado obrigatório vai para o relatório como rejeitado, e o que
entra com ressalva vira aviso. O valor original do Drupal fica nas observações internas.
"""

import html
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from django.db import IntegrityError, transaction

from convenios import documentos
from convenios.models import (
    UFS,
    VIGENCIA_MAXIMA_ANOS,
    Concedente,
    Convenio,
    Situacao,
    TipoConcedente,
    somar_anos,
)

# D11 (premissa, a confirmar com a PROGRAD): tipo do Drupal -> 9 tipos oficiais.
# O Drupal não distingue empresa de microempresa nem ensino de órgão público.
MAPA_TIPOS = {
    "PRIVADA": TipoConcedente.EMPRESA_PRIVADA,
    "PPRIVADA": TipoConcedente.EMPRESA_PRIVADA,
    "PÚBLICA": TipoConcedente.ORGAO_PUBLICO,
    "INTEGRADORA": TipoConcedente.AGENTE_INTEGRACAO,
    "AGENTE DE INTEGRAÇÃO": TipoConcedente.AGENTE_INTEGRACAO,
    "PROFISSIONAL LIBERAL": TipoConcedente.PROFISSIONAL_LIBERAL,
    "ONG/OSCIP": TipoConcedente.ONG_OSCIP,
    "OSCIP": TipoConcedente.ONG_OSCIP,
    "ORGANIZAÇÃO DA SOCIEDADE CIVIL": TipoConcedente.ONG_OSCIP,
    "ORGANIZAÇÃO DE SOCIEDADE CIVIL": TipoConcedente.ONG_OSCIP,
}
MAPA_UF = {"RIO DE JANEIRO": "RJ", "BH": "MG"}
UFS_VALIDAS = {uf for uf, _ in UFS}


@dataclass
class Registro:
    id_drupal: int
    titulo: str
    numero: str
    processo: str
    inicio: date | None
    fim: date | None
    cidade: str
    uf: str
    ramo: str
    objeto: str
    tipo_drupal: str
    cnpj: str
    corpo: str
    email: str
    resolucao: str
    resolucao_url: str


@dataclass
class Relatorio:
    criados: int = 0
    atualizados: int = 0
    rejeitados: list[tuple[int, str, str]] = field(default_factory=list)
    avisos: list[tuple[int, str, str]] = field(default_factory=list)
    tipos: Counter[str] = field(default_factory=Counter)

    def aviso(self, r: Registro, motivo: str) -> None:
        self.avisos.append((r.id_drupal, r.titulo, motivo))


def _texto(valor: str | None) -> str:
    """Tira HTML e entidades: o export mistura texto com links da taxonomia."""
    sem_tags = re.sub(r"<[^>]+>", " ", valor or "")
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


def _data(valor: str) -> date | None:
    """dd/mm/aa do Drupal. Ano de 2 dígitos é sempre 20aa (convênios a partir de 2015)."""
    if not valor:
        return None
    lida = datetime.strptime(valor.strip(), "%d/%m/%y").date()  # strptime põe 69-99 em 19xx
    return lida.replace(year=2000 + lida.year % 100)


def ler_xml(caminho: Path) -> list[Registro]:
    registros = []
    for no in ET.parse(caminho).getroot().iter("node"):  # noqa: S314 — arquivo da própria UFF

        def campo(tag: str, no: ET.Element = no) -> str:
            return (no.findtext(tag) or "").strip()

        resolucao_bruta = campo("Resolu-o-CEP")
        link = re.search(r'href="(https?://[^"]+)"', resolucao_bruta)
        email = re.search(r"mailto:([^\"'>]+)", campo("Email"))
        registros.append(
            Registro(
                id_drupal=int(campo("url").rstrip("/").rsplit("/", 1)[-1]),
                titulo=_texto(campo("Titulo")),
                numero=_texto(campo("Nr-CONVENIO")),
                processo=_texto(campo("N-MERO-DO-PROCESSO")),
                inicio=_data(campo("In-cio")),
                fim=_data(campo("Termino")),
                cidade=_texto(campo("Cidade")),
                uf=_texto(campo("UF")).upper(),
                ramo=_texto(campo("Ramo-de-atividade")),
                objeto=_texto(campo("Objeto")),
                tipo_drupal=_texto(campo("Tipo-da-Institui-o")),
                cnpj=documentos.normalizar(_texto(campo("CNPJ"))),
                corpo=_texto(campo("Corpo")),
                email=email.group(1) if email else _texto(campo("Email")),
                resolucao=_texto(resolucao_bruta),
                resolucao_url=link.group(1) if link else "",
            )
        )
    return registros


def _motivo_de_rejeicao(r: Registro) -> str | None:
    if not r.numero:
        return "sem nº do convênio"
    if not r.inicio or not r.fim:
        return "sem data de início ou de término"
    if r.fim <= r.inicio:
        return f"término ({r.fim:%d/%m/%Y}) não é depois do início ({r.inicio:%d/%m/%Y})"
    if r.cnpj and not (
        (len(r.cnpj) == 14 and documentos.cnpj_valido(r.cnpj))
        or (len(r.cnpj) == 11 and documentos.cpf_valido(r.cnpj))
    ):
        return f"CNPJ/CPF com dígito verificador inválido: {r.cnpj}"
    return None


def _concedente(r: Registro, relatorio: Relatorio) -> Concedente:
    tipo = MAPA_TIPOS.get(r.tipo_drupal.upper(), TipoConcedente.OUTROS)
    if tipo == TipoConcedente.OUTROS:
        relatorio.aviso(r, f'tipo "{r.tipo_drupal}" sem correspondência; ficou "Outros"')
    uf = MAPA_UF.get(r.uf, r.uf)
    if uf not in UFS_VALIDAS:
        relatorio.aviso(r, f'UF "{r.uf}" inválida; ficou em branco')
        uf = ""
    dados = {
        "razao_social": r.titulo[:255],
        "tipo": tipo,
        "uf": uf,
        "cidade": r.cidade[:100],
        "ramo_atividade": r.ramo[:255],
    }
    if r.email:
        dados["email"] = r.email
    if r.cnpj:
        concedente, _ = Concedente.objects.update_or_create(documento=r.cnpj, defaults=dados)
        return concedente
    # D20: sem CNPJ, agrupa pelo nome exato para não criar uma concedente por renovação.
    relatorio.aviso(r, "sem CNPJ: concedente criada sem documento")
    existente = Concedente.objects.filter(
        documento__isnull=True, razao_social__iexact=r.titulo[:255]
    ).first()
    if existente:
        return existente
    return Concedente.objects.create(documento=None, **dados)


def _observacoes(r: Registro) -> str:
    linhas = [f"Importado do estagio.uff.br (nó {r.id_drupal}). Tipo no Drupal: {r.tipo_drupal}."]
    if r.corpo and r.corpo != r.objeto:
        linhas.append(f"Corpo no Drupal: {r.corpo}")
    return "\n".join(linhas)


def importar(registros: list[Registro]) -> Relatorio:
    """Grava os registros. Cada um num savepoint: um erro não derruba os demais."""
    relatorio = Relatorio()
    for r in registros:
        relatorio.tipos[r.tipo_drupal] += 1
        if motivo := _motivo_de_rejeicao(r):
            relatorio.rejeitados.append((r.id_drupal, r.titulo, motivo))
            continue
        assert r.inicio and r.fim  # garantido por _motivo_de_rejeicao  # noqa: S101
        if r.fim >= somar_anos(r.inicio, VIGENCIA_MAXIMA_ANOS):
            relatorio.aviso(r, f"vigência acima de {VIGENCIA_MAXIMA_ANOS} anos (RN07)")
        avisos_antes = len(relatorio.avisos)
        try:
            with transaction.atomic():
                existente = Convenio.objects.filter(id_drupal=r.id_drupal).first()
                convenio = existente or Convenio(id_drupal=r.id_drupal)
                convenio.concedente = _concedente(r, relatorio)
                convenio.numero = r.numero
                convenio.processo_sei = r.processo[:25]
                convenio.inicio_vigencia = r.inicio
                convenio.fim_vigencia = r.fim
                convenio.situacao = Situacao.FINALIZADO
                convenio.objeto = r.objeto
                convenio.resolucao_cep = r.resolucao[:100]
                convenio.resolucao_cep_url = r.resolucao_url
                convenio.observacoes_internas = _observacoes(r)
                # D19: data de finalização desconhecida; não entra no tempo de tramitação.
                convenio._situacao_carregada = Situacao.FINALIZADO
                convenio.save()
        except IntegrityError:
            del relatorio.avisos[avisos_antes:]  # registro não entrou: avisos dele não valem
            relatorio.rejeitados.append(
                (r.id_drupal, r.titulo, f"nº do convênio {r.numero} já usado por outro registro")
            )
            continue
        if existente:
            relatorio.atualizados += 1
        else:
            relatorio.criados += 1
    return relatorio
