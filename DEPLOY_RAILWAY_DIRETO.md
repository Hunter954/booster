# Deploy direto no Railway pelo GitHub

Esta versão já tem `Dockerfile` e `railway.json` na raiz do projeto.

## Passo a passo

1. Suba todos os arquivos para o GitHub.
2. No Railway, clique em **New Project**.
3. Escolha **Deploy from GitHub repo**.
4. Selecione o repositório.
5. O Railway deve detectar o `Dockerfile` da raiz.
6. Adicione um banco **PostgreSQL** no mesmo projeto.
7. Vá no serviço do backend > **Variables** e configure:

```env
SECRET_KEY=troque_essa_chave_grande_aqui
ADMIN_EMAIL=seuemail@seudominio.com
ADMIN_PASSWORD=sua_senha_forte
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

8. Garanta que exista a variável `DATABASE_URL`.
   - Quando você adiciona PostgreSQL no Railway, normalmente ele cria automaticamente.
   - Se não criar, copie a URL pública/interna do PostgreSQL e coloque como `DATABASE_URL`.

9. Faça redeploy.

## URL do painel

Depois do deploy:

```txt
https://SEU-PROJETO.up.railway.app/admin
```

## Login admin

Será o que você colocou nas variáveis:

```txt
ADMIN_EMAIL
ADMIN_PASSWORD
```

Se você não configurar, fica o padrão:

```txt
admin@frameboost.local
admin123
```

Não use o padrão em produção.

## App cliente

Depois que o backend estiver online, no app Python edite:

```txt
client_app/config.json
```

Coloque:

```json
{
  "API_BASE_URL": "https://SEU-PROJETO.up.railway.app",
  "APP_NAME": "FRAME Boost PUBG"
}
```

Depois compilamos o `.exe`.
