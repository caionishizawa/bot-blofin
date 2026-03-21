# Deploy — NPK Sinais

## Pré-requisitos

- VPS ou servidor Linux (Ubuntu 22.04 recomendado)
- Docker + Docker Compose instalados
- Domínio apontando para o IP do servidor
- Portas 80 e 443 abertas no firewall

---

## 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
nano .env   # preencha todos os campos
```

Campos obrigatórios:
- `TELEGRAM_BOT_TOKEN` — token do bot (BotFather)
- `TELEGRAM_CHANNEL_ID` — ID do canal/grupo
- `DASHBOARD_SECRET` — gere com: `python -c "import secrets; print(secrets.token_hex(32))"`
- `DASHBOARD_USER_1` — ex: `admin:senha-forte`
- `DASHBOARD_USER_2` — ex: `socio:outra-senha`

---

## 2. Configurar domínio no Nginx

Edite `nginx/nginx.conf` e substitua `seudominio.com` pelo seu domínio real.

---

## 3. Obter certificado SSL (Let's Encrypt)

### Opção A: Certbot automático

```bash
# Instalar certbot
sudo apt install certbot

# Obter certificado (antes de subir o nginx com SSL)
sudo certbot certonly --standalone -d seudominio.com -d www.seudominio.com

# Copiar certificados para a pasta do projeto
sudo cp /etc/letsencrypt/live/seudominio.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/seudominio.com/privkey.pem nginx/ssl/
sudo chmod 644 nginx/ssl/*.pem
```

### Opção B: Teste local sem SSL

Para testar localmente sem SSL, descomente o bloco "HTTP local" no nginx.conf
e comente os blocos de redirect e HTTPS.

---

## 4. Subir os serviços

```bash
make docker-build   # build das imagens (primeira vez)
make docker-up      # sobe bot + web + nginx em background
make docker-logs    # acompanha os logs
```

---

## 5. Verificar

```bash
docker compose ps             # status dos containers
docker compose logs bot       # logs do bot
docker compose logs web       # logs do dashboard
curl https://seudominio.com   # testa se o dashboard responde
```

---

## 6. Renovação automática do SSL

Adicione ao crontab do servidor:

```bash
# crontab -e
0 3 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/seudominio.com/*.pem /caminho/projeto/nginx/ssl/ && docker compose -f /caminho/projeto/docker-compose.yml restart nginx
```

---

## Comandos úteis

| Comando | O que faz |
|---------|-----------|
| `make docker-up` | Sobe tudo |
| `make docker-down` | Para tudo |
| `make docker-logs` | Ver logs em tempo real |
| `make docker-build` | Rebuild das imagens |
| `docker compose restart bot` | Reinicia só o bot |
| `docker compose restart web` | Reinicia só o dashboard |

---

## Acesso ao Dashboard

Após o deploy, acesse:
```
https://seudominio.com
```

Login com as credenciais definidas em `DASHBOARD_USER_1` e `DASHBOARD_USER_2`.

---

## Estrutura de arquivos persistentes

```
data/trades.db    → banco de dados SQLite (bot + dashboard compartilham)
logs/             → logs do bot
nginx/ssl/        → certificados SSL
```

> ⚠️ Faça backup regular de `data/trades.db` — é onde fica todo o histórico.
