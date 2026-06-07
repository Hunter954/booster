# Como compilar o app cliente em .exe

Dentro da pasta `client_app`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name FRAMEBoostPUBG pubg_booster_client.py
```

O executável ficará em:

```txt
client_app/dist/FRAMEBoostPUBG.exe
```

Antes de compilar, edite o `config.json` com a URL do seu backend no Railway.

Observação: quando usar `--onefile`, pode ser necessário adaptar o caminho do `config.json`.
Na próxima versão podemos embutir a URL direto no código ou carregar por arquivo externo.
