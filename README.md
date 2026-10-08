# Pokémon Platformer: Poké Ball Quest

Joc de plataformes fet amb **Python i Pygame**. Recull totes les Poké Balls de cada
nivell, esquiva (o trepitja!) els enemics i derrota el Boss Final.

## Com jugar-hi

### Opció 1: descarregar el joc (Windows)
Ves a **Releases**, descarrega el `.zip`, descomprimeix-lo i executa `PokemonPlatformer.exe`.

### Opció 2: des del codi
1. Instal·la [Python 3.8 o superior](https://www.python.org/downloads/).
2. Descarrega aquest repositori (botó verd **Code → Download ZIP**) i descomprimeix-lo.
3. Obre una terminal a la carpeta del joc i executa:

```bash
pip install -r requirements.txt
python main.py
```

> La carpeta `assets/` ha d'estar al costat de `main.py`.

## Controls

| Acció | Tecles |
|---|---|
| Moure's | A / D o fletxes esquerra i dreta |
| Saltar (doble salt) | W, espai o fletxa amunt |
| Ajupir-se | Fletxa avall |
| Atac | X o J (es desbloqueja a la botiga) |
| Atac especial | C o K (es desbloqueja a la botiga) |
| Pausa | P o ESC |
| Silenci | N |

Saltar a sobre dels enemics els mata. Les Poké Balls donen punts que es gasten a la
**botiga d'habilitats** del menú.

## Crear l'executable (per a qui vulgui compartir-lo)

```bash
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name PokemonPlatformer --add-data "assets;assets" main.py
```

(A Mac i Linux, escriu `assets:assets` en comptes de `assets;assets`.)
L'executable queda a `dist/PokemonPlatformer/`. Comprimeix aquesta carpeta en un `.zip`
i puja'l a **Releases**.

## Crèdits
Creadors del joc: Arnau, Moha i Sergio. Música: TikTok i músiques sense copyright.
