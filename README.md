# PUBG Booster Platform

MVP com:

- Backend FastAPI com painel admin
- Cadastro de usuários, planos, chaves e presets
- API de login/ativação para o app Windows
- App Python com interface em CustomTkinter
- Validação por login, senha, chave e HWID
- Otimizações seguras de Windows para PUBG
- Sem fechar navegador, Discord ou apps pessoais automaticamente
- Preparação de preset NVIDIA baseado nas configurações enviadas

> Importante: este projeto não altera memória do jogo, não injeta DLL, não mexe no anti-cheat e não modifica arquivos internos do PUBG.

---

## Estrutura

```txt
backend/
  app/
    main.py
    database.py
    models.py
    auth.py
    seed.py
    templates/
  requirements.txt
  Procfile
  railway.json
  .env.example

client_app/
  pubg_booster_client.py
  requirements.txt
  config.json
```

---

## Rodar backend local

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.seed
uvicorn app.main:app --reload
```

Acesse:

```txt
http://127.0.0.1:8000/admin
```

Login admin padrão local:

```txt
Email: admin@frameboost.local
Senha: admin123
```

Troque isso no `.env` antes de publicar.

---

## Rodar app cliente

```bash
cd client_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python pubg_booster_client.py
```

No `config.json`, altere:

```json
{
  "API_BASE_URL": "http://127.0.0.1:8000"
}
```

Depois que subir no Railway, coloque a URL pública do backend.

---

## Subir no Railway

1. Crie um repositório no GitHub com esta pasta.
2. No Railway, crie um projeto a partir do repositório.
3. Adicione PostgreSQL.
4. Configure as variáveis de ambiente do `.env.example`.
5. Rode o deploy.
6. Acesse `/admin`.

---

## Próxima etapa

Depois do MVP funcionando:
- compilar o app com PyInstaller;
- assinar o executável se possível;
- adicionar pagamento;
- adicionar sistema de reset de dispositivo;
- criar módulo NVIDIA via NVAPI/ferramenta auxiliar.
