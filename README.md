# Monitor de Indexadores (CDI, IPCA, IGP-M, INCC, INCC-M)

Script que consulta mensalmente a [API SGS do Banco Central](https://api.bcb.gov.br/dados/serie/) e te avisa por **e-mail e WhatsApp** quando há novos valores publicados.

## Como funciona

1. GitHub Actions roda `check_indices.py` **todo dia 10**, às 12h BRT.
2. O script consulta o último valor de cada indexador via SGS.
3. Compara com o `estado.json` versionado no próprio repo.
4. Se houver novidade → envia e-mail + WhatsApp e commita o `estado.json`.

Os dois canais são independentes: se um falhar, o outro ainda vai. O estado só é gravado se pelo menos um canal funcionar (assim você não perde uma novidade por bug temporário).

Tudo grátis dentro dos limites do GitHub Actions (2.000 min/mês para repos privados; ilimitado para repos públicos).

## Setup (~10 minutos)

### 1. Criar o repo

Crie um repositório no GitHub (privado ou público) e suba estes arquivos:

```
.
├── .github/workflows/monitor.yml
├── check_indices.py
└── README.md
```

### 2. Configurar o e-mail (senha de app do Gmail)

A senha normal do Gmail **não funciona** via SMTP — precisa gerar uma "senha de app":

1. Ative verificação em 2 etapas: <https://myaccount.google.com/security>
2. Gere a senha de app: <https://myaccount.google.com/apppasswords>
3. Copie a senha de 16 caracteres.

(Outros provedores funcionam igual — só ajustar `SMTP_HOST` e `SMTP_PORT`.)

### 3. Configurar o WhatsApp (CallMeBot)

A CallMeBot é uma API gratuita que envia mensagens **pra você mesmo** (não pra outras pessoas) — exatamente o que você quer.

1. Adicione o número **+34 621 331 709** nos seus contatos do WhatsApp (com qualquer nome, ex: "CallMeBot").
   - ⚠️ Esse número às vezes muda; confira o atual em <https://www.callmebot.com/blog/free-api-whatsapp-messages/>
2. Mande exatamente esta mensagem pra esse contato: `I allow callmebot to send me messages`
3. Aguarde o bot responder com a sua **API key** (geralmente em 2 minutos; se demorar, tente de novo em 24h).
4. Anote seu telefone no formato internacional **sem `+` e sem espaços**, ex: `5531999999999`.

### 4. Cadastrar secrets no repositório

No GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Nome              | Valor exemplo                          | Obrigatório? |
| ----------------- | -------------------------------------- | ------------ |
| `SMTP_HOST`       | `smtp.gmail.com`                       | sim          |
| `SMTP_PORT`       | `587`                                  | sim          |
| `SMTP_USER`       | `seu.email@gmail.com`                  | sim          |
| `SMTP_PASS`       | `xxxx xxxx xxxx xxxx` (senha de app)   | sim          |
| `EMAIL_TO`        | `destino@exemplo.com`                  | sim          |
| `WHATSAPP_PHONE`  | `5531999999999`                        | opcional     |
| `WHATSAPP_APIKEY` | a chave que a CallMeBot te enviou      | opcional     |

Se não preencher os dois últimos, o script silenciosamente pula o WhatsApp e manda só e-mail.

### 5. Rodar a primeira vez

Vá em **Actions → Monitor Indexadores → Run workflow** para disparar manualmente. Na primeira execução, como `estado.json` ainda não existe, **todos** os indexadores serão considerados "novidade" e você vai receber a foto inicial nos dois canais. A partir daí, só vem mensagem quando algo mudar de fato.

## Indexadores monitorados

| Nome    | Código SGS | Periodicidade |
| ------- | ---------- | ------------- |
| CDI     | 12         | diária        |
| IPCA    | 433        | mensal        |
| IGP-M   | 189        | mensal        |
| INCC    | 192        | mensal        |
| INCC-M  | 7456       | mensal        |

> O CDI é diário, então rodando 1x por mês ele **sempre** vai aparecer como "novo". Se isso incomodar, basta remover a linha do CDI do dicionário `INDICADORES` no `check_indices.py`.

Para adicionar outros: <https://www3.bcb.gov.br/sgspub/localizarseries/> (ex: Selic = 11, INPC = 188, IGP-DI = 190).

## Notas

- **Cron**: `0 15 10 * *` = dia 10 de cada mês às 15h UTC (= 12h BRT). Pra mudar o dia ou horário, edite essa linha no workflow.
- **Calendário do IPCA**: o IBGE publica o IPCA do mês anterior por volta do dia 10 de cada mês, então rodar nesse dia já costuma pegar o valor fresco. Se algum mês atrasar, o próximo dia 10 detecta normalmente (`estado.json` só guarda o que já viu).
- **CallMeBot**: o serviço é grátis, mas é mantido por uma pessoa só — pode pedir uma contribuição simbólica (~40 centavos/mês) depois de alguns dias de uso. Se preferir algo mais oficial, dá pra trocar por Twilio depois (só substituir a função `enviar_whatsapp`).
- **Limite de chamadas no SGS**: 5 chamadas por mês é zero risco de bloqueio.
