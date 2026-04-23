# SC Češtinátor Linux

Jednoduchý GUI nástroj pro Linux pro instalaci a aktualizaci české lokalizace hry Star Citizen.

## Aktuální stav
První verze umí:

- vybrat cestu ke hře
- pracovat s větví LIVE
- zkontrolovat přítomnost `data/Localization/english/global.ini`
- zjistit lokální verzi češtiny
- zjistit dostupnou verzi na GitHubu
- stáhnout a nainstalovat lokalizaci
- volitelně vytvořit zálohu staré lokalizace

## Spuštění

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
