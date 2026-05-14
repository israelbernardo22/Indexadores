"""
Monitor de indexadores do Banco Central (SGS).
Roda 1x por mês via GitHub Actions, compara com o último valor salvo
e envia notificação por e-mail E WhatsApp quando há atualização.
"""

import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

import requests

# ---------- Configuração dos indexadores ----------
# Códigos do SGS: https://www3.bcb.gov.br/sgspub/localizarseries/localizarSeries.do
INDICADORES = {
    "CDI":    {"codigo": 12,   "periodicidade": "diario"},
    "IPCA":   {"codigo": 433,  "periodicidade": "mensal"},
    "IGP-M":  {"codigo": 189,  "periodicidade": "mensal"},
    "INCC":   {"codigo": 192,  "periodicidade": "mensal"},
    "INCC-M": {"codigo": 7456, "periodicidade": "mensal"},
}

SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/1?formato=json"
ESTADO_FILE = Path("estado.json")

# ---------- Secrets (vindos do GitHub Actions) ----------
# E-mail (obrigatório)
SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]
EMAIL_TO  = os.environ["EMAIL_TO"]

# WhatsApp via CallMeBot (opcional — se não configurar, só manda e-mail)
WHATSAPP_PHONE  = os.environ.get("WHATSAPP_PHONE", "").strip()   # ex: 5531999999999
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY", "").strip()  # API key da CallMeBot


# ---------- Coleta de dados ----------
def buscar_ultimo_valor(codigo: int) -> dict | None:
    """Busca o último valor publicado de uma série no SGS."""
    url = SGS_URL.format(codigo=codigo)
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        dados = resp.json()
        return dados[0] if dados else None
    except (requests.RequestException, ValueError, IndexError) as e:
        print(f"  ! Erro ao buscar série {codigo}: {e}")
        return None


def carregar_estado() -> dict:
    if ESTADO_FILE.exists():
        return json.loads(ESTADO_FILE.read_text(encoding="utf-8"))
    return {}


def salvar_estado(estado: dict) -> None:
    ESTADO_FILE.write_text(
        json.dumps(estado, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------- Notificações ----------
def enviar_email(novidades: list[dict]) -> None:
    """Envia e-mail com as novidades detectadas."""
    linhas_txt = [f"• {n['nome']}: {n['valor']} (data {n['data']})" for n in novidades]
    linhas_html = [
        f"<li><b>{n['nome']}</b>: "
        f"<span style='color:#0a6'>{n['valor']}</span> "
        f"<span style='color:#666'>(referência: {n['data']})</span></li>"
        for n in novidades
    ]

    corpo_txt = (
        "Novos valores de indexadores foram publicados:\n\n"
        + "\n".join(linhas_txt)
        + "\n\nFonte: Banco Central — SGS"
    )
    corpo_html = f"""
    <html><body style="font-family: sans-serif">
      <h3>📊 Novos indexadores publicados</h3>
      <ul>{''.join(linhas_html)}</ul>
      <p style="color:#888;font-size:12px">Fonte: Banco Central — SGS</p>
    </body></html>
    """

    msg = EmailMessage()
    msg["Subject"] = f"[Indexadores] {len(novidades)} atualização(ões)"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg.set_content(corpo_txt)
    msg.add_alternative(corpo_html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls(context=ctx)
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    print(f"  ✓ E-mail enviado para {EMAIL_TO}")


def enviar_whatsapp(novidades: list[dict]) -> bool:
    """Envia mensagem WhatsApp via CallMeBot. Retorna True se enviou."""
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
        print("  ⚠ WhatsApp não configurado (WHATSAPP_PHONE/APIKEY vazios), pulando.")
        return False

    linhas = [f"• *{n['nome']}*: {n['valor']}  _(ref. {n['data']})_" for n in novidades]
    texto = (
        "📊 *Indexadores atualizados*\n\n"
        + "\n".join(linhas)
        + "\n\n_Fonte: Banco Central — SGS_"
    )

    url = "https://api.callmebot.com/whatsapp.php"
    params = {
        "phone": WHATSAPP_PHONE,
        "text": texto,
        "apikey": WHATSAPP_APIKEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        # CallMeBot devolve 200 com HTML mesmo em erro; checa o conteúdo.
        if resp.status_code == 200 and "Message queued" in resp.text:
            print(f"  ✓ WhatsApp enviado para {WHATSAPP_PHONE}")
            return True
        print(f"  ! CallMeBot respondeu inesperadamente "
              f"(HTTP {resp.status_code}): {resp.text[:200]}")
        return False
    except requests.RequestException as e:
        print(f"  ! Erro ao enviar WhatsApp: {e}")
        return False


def notificar(novidades: list[dict]) -> bool:
    """
    Dispara e-mail e WhatsApp (isolados — falha de um não impede o outro).
    Retorna True se pelo menos um canal funcionou.
    """
    print("\nEnviando notificações:")
    email_ok = False
    whats_ok = False

    try:
        enviar_email(novidades)
        email_ok = True
    except Exception as e:
        print(f"  ! Falha no e-mail: {e}")

    try:
        whats_ok = enviar_whatsapp(novidades)
    except Exception as e:
        print(f"  ! Falha no WhatsApp: {e}")

    return email_ok or whats_ok


# ---------- Fluxo principal ----------
def main() -> int:
    estado = carregar_estado()
    novidades = []

    for nome, cfg in INDICADORES.items():
        print(f"→ Checando {nome} (cód. {cfg['codigo']})...")
        ultimo = buscar_ultimo_valor(cfg["codigo"])
        if ultimo is None:
            continue

        data_atual = ultimo["data"]      # formato "DD/MM/YYYY"
        valor_atual = ultimo["valor"]
        data_salva = estado.get(nome, {}).get("data")

        if data_salva != data_atual:
            print(f"  ✓ NOVO! {data_atual} → {valor_atual}")
            novidades.append({"nome": nome, "data": data_atual, "valor": valor_atual})
            estado[nome] = {"data": data_atual, "valor": valor_atual}
        else:
            print(f"  = sem mudança (último: {data_atual})")

    if not novidades:
        print("\nNenhuma novidade neste mês.")
        return 0

    enviou = notificar(novidades)
    # Só salva o estado se ao menos uma notificação foi entregue, pra não
    # "perder" a novidade caso ambos os canais tenham falhado.
    if enviou:
        salvar_estado(estado)
    else:
        print("! Nenhum canal funcionou — estado NÃO foi salvo (tentará de novo).")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
