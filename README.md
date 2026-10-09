# Pokémon Platformer: Poké Ball Quest

Joc de plataformes fet amb **Python i Pygame**. Recull totes les Poké Balls de cada
nivell, esquiva (o trepitja!) els enemics i derrota el Boss Final.

## ▶ Juga-hi online

**https://arcaro123.github.io/PokemonQuest/**

Funciona directament al navegador, sense instal·lar res.

## Com jugar-hi

### Opció 1: al navegador

Obre l'enllaç de dalt i prem **JUGA ARA**.

### Opció 2: descarregar el joc (Windows)

Ves a **Releases**, descarrega el `.zip`, descomprimeix-lo i executa `PokemonPlatformer.exe`.

### Opció 3: des del codi

1. Instal·la [Python 3.8 o superior](https://www.python.org/downloads/).
2. Descarrega aquest repositori (botó verd **Code → Download ZIP**) i descomprimeix-lo.
3. Obre una terminal a la carpeta del joc i executa:

```
pip install -r requirements.txt
python main.py
```
> La carpeta `assets/` ha d'estar al costat de `main.py`.

## Controls

| Acció               | Tecles                             |
| ------------------- | ---------------------------------- |
| Moure's             | A / D o fletxes esquerra i dreta   |
| Saltar (doble salt) | W, espai o fletxa amunt            |
| Ajupir-se           | Fletxa avall                       |
| Atac                | X o J (es desbloqueja a la botiga) |
| Atac especial       | C o K (es desbloqueja a la botiga) |
| Pausa               | P o ESC                            |
| Silenci             | N                                  |
| Dificultat (menú)   | D                                  |

Saltar a sobre dels enemics els mata. Les Poké Balls donen punts que es gasten a la **botiga d'habilitats** del menú.

## Com es publica al navegador

El joc es converteix a WebAssembly amb [pygbag](https://github.com/pygame-web/pygbag) i es publica
a GitHub Pages automàticament amb cada `push` a `main` (vegeu `.github/workflows/pages.yml`).

Per al navegador, la música ha de ser **`.ogg`**: al costat de cada `.mp3` de `assets/`
(`musica1`, `musica2`, `musica_mort`) hi ha d'haver el mateix fitxer en `.ogg`.
El joc fa servir l'`.ogg` si existeix i, si no, l'`.mp3` (a l'escriptori).

## Crear l'executable (per a qui vulgui compartir-lo)

```
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name PokemonPlatformer --add-data "assets;assets" main.py
```

(A Mac i Linux, escriu `assets:assets` en comptes de `assets;assets`.)
L'executable queda a `dist/PokemonPlatformer/`. Comprimeix aquesta carpeta en un `.zip` i puja'l a **Releases**.

## Crèdits

Creadors del joc: Arnau, Moha i Sergio. Música: TikTok i músiques sense copyright.

Projecte fet per fans, sense afiliació amb Nintendo, Game Freak ni The Pokémon Company.
