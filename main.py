# Versió preparada per al navegador (pygbag / WebAssembly) i també per a l'escriptori.
import asyncio
import json
import math
import os
import random
import sys
import time

import pygame

# True quan el joc corre dins el navegador
IS_WEB = sys.platform == 'emscripten'


def music_file(path):
    """Al navegador l'mp3 no sol funcionar: si hi ha un .ogg amb el mateix nom, el fem servir."""

    ogg = os.path.splitext(path)[0] + '.ogg'

    if os.path.exists(ogg):
        return ogg

    return path


pygame.init()

try:
    pygame.mixer.music.load(music_file('assets/musica2.mp3'))
    pygame.mixer.music.play(-1)
except (pygame.error, FileNotFoundError):
    pass

WIDTH, HEIGHT = 1024, 720
AMPLADA, ALTURA = WIDTH, HEIGHT

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pantalla = screen

pygame.display.set_caption("Pokémon Platformer: Poké Ball Quest")

_cache_fons = {}


def imprimir_pantalla_fons(image):
    if image not in _cache_fons:

        try:
            original = pygame.image.load(image).convert()
            _cache_fons[image] = pygame.transform.scale(original, (AMPLADA, ALTURA))

        except (FileNotFoundError, pygame.error):

            # Si falta un fons, no es trenca el joc: es pinta un color llis
            print('AVÍS: falta la imatge', image)

            fallback = pygame.Surface((AMPLADA, ALTURA))
            fallback.fill((30, 60, 110))

            _cache_fons[image] = fallback

    pantalla.blit(_cache_fons[image], (0, 0))


# ---------------------------------------------------------------
# FONTS AMB CACHE (s'usen a tot el joc)
# ---------------------------------------------------------------

_boss_fonts = {}

FONT_FILE = 'assets/font.ttf'  # opcional: una font pròpia (recomanat per al navegador)


def _font(size, bold=False):
    key = (size, bold)

    if key not in _boss_fonts:

        if os.path.exists(FONT_FILE):

            f = pygame.font.Font(FONT_FILE, size)
            f.set_bold(bold)

        elif IS_WEB:

            # Al navegador no hi ha Arial: font per defecte una mica més gran
            f = pygame.font.Font(None, int(size * 1.3))
            f.set_bold(bold)

        else:

            f = pygame.font.SysFont('Arial', size, bold=bold)

        _boss_fonts[key] = f

    return _boss_fonts[key]


# ---------------------------------------------------------------
# COLORS I CONSTANTS
# ---------------------------------------------------------------

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

C1 = (20, 70, 120)
C4 = (0, 50, 100)
C3 = (0, 0, 0)
C2 = (30, 0, 70)

YELLOW = (255, 255, 0)
BROWN = (139, 69, 19)
DARK_BROWN = (100, 50, 10)
GOLD = (255, 215, 0)

PLAYER_SIZE = (40, 40)
PLAYER_SIZE_DUCKING = (40, 40)

PLAYER_SPEED = 6
GRAVITY = 0.6
JUMP_STRENGTH = -14
DOUBLE_JUMP_STRENGTH = -12
MAX_FALL_SPEED = 10

# Salt: buffer i salt variable
JUMP_BUFFER_MS = 120
JUMP_CUT_FACTOR = 0.5

# Combo de pokeballs: agafar-ne una dins d'aquest temps
# de l'anterior puja el combo. Amb COMBO_MIN o més, +1 punt per bola.
COMBO_WINDOW_MS = 1500
COMBO_MIN = 3

# ---------------------------------------------------------------
# ATACS
#   X / J = atac bàsic (tots els personatges)
#   C / K = atac especial (s'ha de comprar a la botiga)
# ---------------------------------------------------------------

ATTACK_KEYS = (pygame.K_x, pygame.K_j)
SPECIAL_KEYS = (pygame.K_c, pygame.K_k)

ATTACK_COOLDOWN_MS = 800  # Cooldown augmentat
ATTACK_SPEED = 11
ATTACK_LIFE_FRAMES = 45  # ~0,75 s de vol

ENEMY_HP_BY_KIND = {0: 2, 1: 3, 2: 4, 3: 2}  # 0 = abella, 1 = volador gran, 2 = llop, 3 = abella perseguidora

# ---------------------------------------------------------------
# ENEMIC TERRESTRE (llop, assets/terra.png)
# ---------------------------------------------------------------

GROUND_ENEMY_LEVELS = {4, 5, 6}
GROUND_ENEMY_KIND = 2
GROUND_ENEMY_SPEED = 2
GROUND_ENEMY_HEIGHT = 84  # alçada en píxels (la hitbox fa la mida de la imatge)
GROUND_ENEMY_FACES_LEFT = True  # a terra.png el llop mira cap a l'ESQUERRA
GROUND_ENEMY_FRAME_MS = 120  # temps de cada fotograma de caminar

# ---------------------------------------------------------------
# COMPORTAMENTS DELS ENEMICS
# ---------------------------------------------------------------

ENEMY_AI = {
    'patrol': {'speed': 2.0},
    'chaser': {'speed': 1.5, 'chase': 3.4, 'range': 380, 'y_range': 200},
    'ground_chaser': {'speed': GROUND_ENEMY_SPEED, 'chase': 2.8, 'range': 380, 'y_range': 160},
    'sine': {'speed': 2.5, 'amp': 45, 'freq': 0.0035},
}

ENEMY_AI_CYCLE = ['patrol', 'sine', 'chaser']

AI_KIND = {'patrol': 1, 'sine': 0, 'chaser': 3}  # quin sprite i vida fa servir cada tipus

# Mal en trepitjar un enemic (per tipus).
ENEMY_STOMP_DAMAGE = {0: 1, 1: 1, 2: 1, 3: 1}

# Mal de cada atac especial segons el nivell comprat (nivell 1, 2, 3)
SPECIAL_DAMAGE = {
    'cua': [1, 2, 3],
    'plasma': [1, 2, 3],
    'foc': [1, 2, 3],
}


def special_damage(sid, lvl):
    table = SPECIAL_DAMAGE[sid]
    return table[min(lvl, len(table)) - 1]


# ---------------------------------------------------------------
# DIFICULTAT
#
#   hp_by_kind -> (opcional) vida fixa de cada tipus d'enemic
#   wolf_hp    -> vida fixa del llop (si no hi ha hp_by_kind)
#   hp         -> multiplicador de vida (si no hi ha cap dels dos)
# ---------------------------------------------------------------

DIFFICULTY_SETTINGS = {
    'facil': {
        'nom': 'FÀCIL', 'color': (80, 220, 100),
        'desc': ["La meitat d'enemics", 'Vida al 50 %', 'Velocitat al 60 %',
                 'Llop amb 2 de vida', 'Boss: 2 fases, atacs suaus'],
        'mode': 'frac', 'keep': 0.5,
        'speed': 0.6, 'hp': 0.5, 'wolf_hp': 2,
        'chase': False, 'wolf_chase': False, 'ground_enemy': True,
        'boss_hp_mult': 1.0,
    },
    'normal': {
        'nom': 'NORMAL', 'color': (255, 220, 60),
        'desc': ['2 enemics menys', 'No et persegueixen', 'Vida normal',
                 'Velocitat al 80 %', 'Boss: 3 fases i embestides'],
        'mode': 'minus', 'remove': 2,
        'speed': 0.8, 'hp': 1.0, 'wolf_hp': None,
        'chase': False, 'wolf_chase': False, 'ground_enemy': True,
        'boss_hp_mult': 2.0,  # Boss Vida x2
    },
    'dificil': {
        'nom': 'DIFÍCIL', 'color': (255, 80, 80),
        'desc': ['Tots els enemics', 'Velocitat màxima',
                 'Perseguidors i llop', 'Vida: 3 / 4 / 5',
                 'Boss: 4 fases, invoca i ràfegues'],
        'mode': 'all',
        'speed': 1.0, 'hp': 1.0, 'wolf_hp': None,
        'hp_by_kind': {0: 3, 1: 4, 2: 5, 3: 3},  # abella, volador gran, llop, abella vermella
        'chase': True, 'wolf_chase': True, 'ground_enemy': True,
        'boss_hp_mult': 3.5,  # Boss Vida x3.5
    },
}

DIFFICULTY_ORDER = ['facil', 'normal', 'dificil']

DIFFICULTY = {'key': 'normal'}  # dificultat activa


def diff():
    """Configuració de la dificultat activa."""
    return DIFFICULTY_SETTINGS[DIFFICULTY['key']]


def enemies_to_keep(n):
    """Quants enemics queden d'un nivell que en tindria n."""

    d = diff()

    if d['mode'] == 'frac':  # fàcil: la meitat (mínim 1)
        return min(n, max(1, math.ceil(n * d['keep'])))

    if d['mode'] == 'minus':  # normal: -2, però mai més del 50 %
        return n - min(d['remove'], n // 2)

    return n  # difícil: tots


def record_key(base):
    """Els rècords són separats per dificultat."""

    if DIFFICULTY['key'] == 'dificil':
        return str(base)

    return f"{base}_{DIFFICULTY['key']}"


# ---------------------------------------------------------------
# BOSS FINAL: CONFIGURACIÓ PER DIFICULTAT
# ---------------------------------------------------------------

BOSS_SETTINGS = {
    'facil': {
        'phase_at': [0.5],
        'invuln_ms': 1100,
        'windup': 1.4, 'cooldown': 1.4, 'proj': 0.8, 'walk': 0.8,
        'platform_damage': False, 'platform_attack': 0.0,
        'attacks': {
            1: {'orb': 3, 'fan': 2, 'wave': 2},
            2: {'orb': 2, 'fan': 2, 'wave': 2, 'meteors': 2},
        },
        'fan_n': [3, 4],
        'meteor_n': [3, 4], 'meteor_warn': 1200,
        'wave_speed': [5, 6],
        'homing_n': 0, 'burst_n': 0, 'summon_n': 0,
        'dash_speed': 0,
    },
    'normal': {
        'phase_at': [0.66, 0.33],
        'invuln_ms': 1400,
        'windup': 1.0, 'cooldown': 1.0, 'proj': 1.0, 'walk': 1.0,
        'platform_damage': True, 'platform_attack': 0.33,
        'attacks': {
            1: {'orb': 3, 'fan': 2, 'meteors': 1, 'wave': 2},
            2: {'orb': 1, 'fan': 2, 'meteors': 2, 'wave': 2, 'dash': 2, 'homing': 1},
            3: {'fan': 2, 'meteors': 2, 'wave': 2, 'dash': 2, 'homing': 2, 'burst': 2},
        },
        'fan_n': [3, 5, 7],
        'meteor_n': [4, 6, 8], 'meteor_warn': 900,
        'wave_speed': [6, 7, 8],
        'homing_n': [1, 1, 2], 'burst_n': [3, 3, 4], 'summon_n': 0,
        'dash_speed': 11,
    },
    'dificil': {
        'phase_at': [0.75, 0.5, 0.25],
        'invuln_ms': 1600,
        'windup': 0.8, 'cooldown': 0.75, 'proj': 1.2, 'walk': 1.15,
        'platform_damage': True, 'platform_attack': 0.5,
        'attacks': {
            1: {'orb': 3, 'fan': 2, 'meteors': 1, 'wave': 2, 'dash': 1},
            2: {'orb': 1, 'fan': 2, 'meteors': 2, 'wave': 2, 'dash': 2,
                'homing': 1, 'burst': 1, 'summon': 1},
            3: {'fan': 2, 'meteors': 2, 'wave': 2, 'dash': 2,
                'homing': 2, 'burst': 2, 'summon': 1},
            4: {'fan': 2, 'meteors': 3, 'wave': 2, 'dash': 2,
                'homing': 2, 'burst': 3, 'summon': 1},
        },
        'fan_n': [5, 6, 8, 10],
        'meteor_n': [5, 7, 9, 12], 'meteor_warn': 700,
        'wave_speed': [7, 8, 9, 10],
        'homing_n': [1, 1, 2, 3], 'burst_n': [3, 4, 5, 6], 'summon_n': [2, 2, 2, 3],
        'dash_speed': 14,
    },
}

# Aspecte de cada fase (1 = normal, sense color)
BOSS_PHASE_COLORS = {1: (230, 40, 60), 2: (255, 110, 0), 3: (255, 60, 160), 4: (190, 80, 255)}
BOSS_PHASE_TINT = {2: (70, 0, 0), 3: (100, 0, 40), 4: (110, 0, 90)}
BOSS_PHASE_AURA = {2: (255, 60, 20), 3: (255, 40, 130), 4: (180, 60, 255)}
BOSS_PHASE_TEXT = {2: 'ENFURISMAT!', 3: 'FÚRIA!', 4: 'FÚRIA TOTAL!'}


def boss_cfg():
    """Configuració del boss segons la dificultat activa."""
    return BOSS_SETTINGS[DIFFICULTY['key']]


def bp(values, phase):
    """Valor d'una llista per fase (o el número tal qual)."""

    if isinstance(values, (list, tuple)):
        return values[min(phase, len(values)) - 1]

    return values


def boss_phase_for_hp(gs, hp):
    """Fase del boss que li correspon a aquesta vida."""

    phase = 1

    for threshold in gs.boss_phase_hp:
        if hp <= threshold:
            phase += 1

    return phase


ATTACK_COLORS = {
    'Pikachu': (255, 230, 40),
    'Jolteon': (120, 200, 255),
    'Flareon': (255, 120, 30),
}

SPECIAL_BY_CHAR = {
    'Pikachu': 'cua',
    'Jolteon': 'plasma',
    'Flareon': 'foc',
}

MIN_POKEBALL_DISTANCE = 60
POKEBALL_SIZE = 40
BASIC_ATTACK_REQUIRES_SPECIAL = True
SPRITE_FACES_LEFT = set()

# Nivell d'inici corregit al Nivell 1
START_LEVEL = 1

RESUME_AT_NEXT_LEVEL = False
PROGRESS = {'level': None}


def resume_level():
    lvl = PROGRESS['level']

    if lvl is None:
        return START_LEVEL

    if RESUME_AT_NEXT_LEVEL:
        return min(lvl + 1, BOSS_LEVEL)

    return lvl


def reset_progress():
    PROGRESS['level'] = None


BOSS_LEVEL = 11

BOSS_BASE_HP = 11

# ---------------------------------------------------------------
# POKEBALLS I PUNTS
# ---------------------------------------------------------------

SIMPLE_POKEBALL_MAX_LEVEL = 5
POINTS_SIMPLE_POKEBALL = 1
POINTS_ULTRABALL = 2


def pokeball_points_for_level(level):
    if level <= SIMPLE_POKEBALL_MAX_LEVEL:
        return POINTS_SIMPLE_POKEBALL
    return POINTS_ULTRABALL


FACE_CROP_HEIGHT = 0.5

# ---------------------------------------------------------------
# PLATAFORMES DEL BOSS
# ---------------------------------------------------------------

BOSS_PLATFORM_DAMAGE_SCALE = 0.55

BOSS_PLATFORM_PRE_ROAR_MIN = 2000
BOSS_PLATFORM_PRE_ROAR_MAX = 3000

BOSS_PLATFORM_ROAR_TIME = 1200

BOSS_PLATFORM_SPECIAL_MIN = 5000
BOSS_PLATFORM_SPECIAL_MAX = 7000

BOSS_PLATFORM_RETURN_WARNING = 2000

BOSS_PHASE2_ROAR_TIME = 1600  # durada del rugit en canviar de fase

# ---------------------------------------------------------------
# DERROTA DEL BOSS I GAME OVER
# ---------------------------------------------------------------

BOSS_DEATH_MS = 4600  # durada de l'animació de derrota del boss
BOSS_DEATH_BLAST = 3000  # moment de l'explosió final
GO_INPUT_MS = 2200  # a la pantalla de GAME OVER, fins aquí no es llegeixen tecles

BOSS_SCALE = 4
BOSS_FRAMES = 4
BOSS_FRAME_MS = 500

LEVEL_BACKGROUNDS = {
    1: 'assets/dia.png',
    2: 'assets/dia.png',
    3: 'assets/nit.png',
    4: 'assets/dia.png',
    5: 'assets/dia.png',
    6: 'assets/nit.png',
    7: 'assets/dia.png',
    8: 'assets/dia.png',
    9: 'assets/nit.png',
    10: 'assets/dia.png',
    11: 'assets/dia.png',
}

# ---------------------------------------------------------------
# PARTIDA GUARDADA
# ---------------------------------------------------------------

SAVE_FILE = 'savegame.json'
SAVE = {'points': 0, 'upgrades': {}}


def load_save():
    try:
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        SAVE['points'] = int(data.get('points', 0))
        SAVE['upgrades'] = dict(data.get('upgrades', {}))
    except (OSError, ValueError, TypeError):
        SAVE['points'] = 0
        SAVE['upgrades'] = {}


def save_game():
    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(SAVE, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def delete_save_on_exit():
    try:
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
    except OSError:
        pass


def add_points(n):
    SAVE['points'] += int(n)
    save_game()


# ---------------------------------------------------------------
# RÈCORDS DE TEMPS PER NIVELL
# ---------------------------------------------------------------

RECORDS_FILE = 'records.json'
RECORDS = {}


def load_records():
    try:
        with open(RECORDS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        RECORDS.clear()
        RECORDS.update({str(k): float(v) for k, v in data.items()})
    except (OSError, ValueError, TypeError):
        RECORDS.clear()


def save_records():
    try:
        with open(RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(RECORDS, f, indent=2)
    except OSError:
        pass


def submit_record(key, t):
    key = str(key)
    best = RECORDS.get(key)

    if best is None or t < best:
        RECORDS[key] = round(t, 2)
        save_records()
        return True, RECORDS[key]

    return False, best


# ---------------------------------------------------------------
# HABILITATS (Preus multiplicats x2.5)
# ---------------------------------------------------------------

DEFAULT_ABILITIES = [
    {'id': 'hab1', 'nom': 'Habilitat 1', 'desc': 'Encara per definir',
     'costs': [10, 25, 50]},
]

ABILITIES = {
    'Pikachu': [
        {'id': 'triple_salt', 'nom': 'Triple salt',
         'desc': "Un salt extra a l'aire (3 salts)", 'costs': [8]},
        {'id': 'punts_extra', 'nom': 'Punts extra',
         'desc': '+1 punt per nivell a cada pokeball', 'costs': [6, 12]},
        {'id': 'rebot', 'nom': 'Rebot elèctric',
         'desc': 'Rebotes més alt en trepitjar el boss', 'costs': [5, 10]},
        {'id': 'vida_extra', 'nom': 'Vida extra',
         'desc': 'Reviu 1 cop per nivell quan mors', 'costs': [12, 20]},
        {'id': 'cua', 'nom': 'Llamp elèctric',
         'desc': 'Desbloqueja atacs. Especial C/K: llamp llarg', 'costs': [10, 18, 28]},
    ],
    'Jolteon': [
        {'id': 'velocitat', 'nom': 'Més ràpid',
         'desc': 'Corre més ràpid (+1 per nivell)', 'costs': [5, 10, 15]},
        {'id': 'planeig', 'nom': 'Planeig',
         'desc': 'Cau més a poc a poc', 'costs': [6, 12]},
        {'id': 'cos_agil', 'nom': 'Cos àgil',
         'desc': 'Hitbox més petita: més difícil tocar-lo', 'costs': [7, 14]},
        {'id': 'imant', 'nom': 'Imant',
         'desc': 'Atrau les pokeballs des de més lluny', 'costs': [5, 10, 15]},
        {'id': 'plasma', 'nom': 'Ona de plasma',
         'desc': 'Desbloqueja atacs. Especial C/K: anell que travessa', 'costs': [10, 18, 28]},
    ],
    'Flareon': [
        {'id': 'salt_alt', 'nom': 'Salt alt',
         'desc': 'El primer salt arriba més amunt', 'costs': [5, 10, 15]},
        {'id': 'doble_fort', 'nom': 'Doble salt potent',
         'desc': 'El segon salt és més fort', 'costs': [6, 12]},
        {'id': 'mal_boss', 'nom': 'Foc intens',
         'desc': 'Fa +1 de mal per nivell (enemics i boss)', 'costs': [12, 22]},
        {'id': 'enemics_lents', 'nom': 'Enemics lents',
         'desc': 'Els enemics volen més lents', 'costs': [5, 10]},
        {'id': 'foc', 'nom': 'Cometa de foc',
         'desc': 'Desbloqueja atacs. Especial C/K: cometa explosiu', 'costs': [10, 18, 28]},
    ],
}

# Multipliquem els preus de totes les habilitats per 2.5
for _char_abilities in ABILITIES.values():
    for _ab in _char_abilities:
        _ab['costs'] = [round(c * 2.5) for c in _ab['costs']]
for _ab in DEFAULT_ABILITIES:
    _ab['costs'] = [round(c * 2.5) for c in _ab['costs']]

ACTIVE = {'nom': 'Pikachu'}


def get_abilities(nom):
    return ABILITIES.get(nom, DEFAULT_ABILITIES)


def ability_level(nom, ab_id):
    return int(SAVE['upgrades'].get(nom, {}).get(ab_id, 0))


def buy_ability(nom, ab):
    level = ability_level(nom, ab['id'])

    if level >= len(ab['costs']):
        return False, 'Ja està al nivell màxim!'

    cost = ab['costs'][level]

    if SAVE['points'] < cost:
        return False, f'Et falten {cost - SAVE["points"]} punts'

    SAVE['points'] -= cost
    SAVE['upgrades'].setdefault(nom, {})[ab['id']] = level + 1

    save_game()

    return True, f'{ab["nom"]} millorada al nivell {level + 1}!'


# ---------------------------------------------------------------
# EFECTES DE SO
# ---------------------------------------------------------------

sfx = {}
MUTED = {'on': False}


def apply_volume():
    try:
        pygame.mixer.music.set_volume(0.0 if MUTED['on'] else 1.0)
    except pygame.error:
        pass


def music_pause():
    try:
        pygame.mixer.music.pause()
    except pygame.error:
        pass


def music_unpause():
    try:
        pygame.mixer.music.unpause()
    except pygame.error:
        pass


def music_replay():
    try:
        pygame.mixer.music.play()
    except pygame.error:
        pass


def toggle_mute():
    MUTED['on'] = not MUTED['on']
    apply_volume()


def load_sfx():
    if not pygame.mixer.get_init():
        return
    for name in ('salt', 'pokeball', 'hit', 'atac'):
        for ext in ('wav', 'ogg'):
            ruta = f'assets/{name}.{ext}'
            if os.path.exists(ruta):
                try:
                    snd = pygame.mixer.Sound(ruta)
                    snd.set_volume(0.5)
                    sfx[name] = snd
                except pygame.error:
                    pass
                break


def play_sfx(name):
    if MUTED['on']:
        return
    snd = sfx.get(name)
    if snd:
        snd.play()


# ---------------------------------------------------------------
# SISTEMA DE PARTÍCULES
# ---------------------------------------------------------------

particles = []


def spawn_particles(x, y, color, n=8, speed=3.0, life=500, size=4,
                    gravity=0.15, upward=False):
    for _ in range(n):
        if upward:
            ang = random.uniform(math.pi * 1.1, math.pi * 1.9)
        else:
            ang = random.uniform(0, math.pi * 2)
        sp = random.uniform(0.3, 1.0) * speed
        particles.append({
            'x': float(x),
            'y': float(y),
            'vx': math.cos(ang) * sp,
            'vy': math.sin(ang) * sp,
            'g': gravity,
            'life': float(life),
            'max': float(life),
            'size': size,
            'color': color
        })


def update_particles():
    for p in particles:
        p['x'] += p['vx']
        p['y'] += p['vy']
        p['vy'] += p['g']
        p['life'] -= 16.7
    particles[:] = [p for p in particles if p['life'] > 0]


def draw_particles():
    for p in particles:
        t = p['life'] / p['max']
        r = max(1, int(p['size'] * t))
        pygame.draw.circle(screen, p['color'], (int(p['x']), int(p['y'])), r)


# ---------------------------------------------------------------
# ONES EXPANSIVES
# ---------------------------------------------------------------

rings = []


def spawn_ring(x, y, color, max_r=60, life=380):
    rings.append({
        'x': x, 'y': y, 'color': color,
        'max_r': max_r, 'life': float(life), 'max': float(life)
    })


def update_rings():
    for rg in rings:
        rg['life'] -= 16.7
    rings[:] = [rg for rg in rings if rg['life'] > 0]


def draw_rings():
    for rg in rings:
        t = 1 - rg['life'] / rg['max']
        rad = int(rg['max_r'] * (t ** 0.5))
        width = max(1, int(6 * (1 - t)))
        if rad > 2:
            pygame.draw.circle(
                screen, rg['color'], (int(rg['x']), int(rg['y'])), rad, width
            )


# ---------------------------------------------------------------
# TEXTOS FLOTANTS
# ---------------------------------------------------------------

popups = []


def add_popup(x, y, text, color=WHITE, size=22):
    popups.append({
        'x': float(x),
        'y': float(y),
        'text': text,
        'color': color,
        'size': size,
        'life': 900.0,
        'max': 900.0
    })


def update_popups():
    for p in popups:
        p['y'] -= 0.8
        p['life'] -= 16.7
    popups[:] = [p for p in popups if p['life'] > 0]


def draw_popups():
    for p in popups:
        surf = _font(p['size'], True).render(p['text'], True, p['color'])
        shadow = _font(p['size'], True).render(p['text'], True, BLACK)
        alpha = int(255 * max(0.0, min(1.0, p['life'] / p['max'] * 1.6)))
        surf.set_alpha(alpha)
        shadow.set_alpha(alpha)
        x = int(p['x'] - surf.get_width() / 2)
        y = int(p['y'])
        screen.blit(shadow, (x + 2, y + 2))
        screen.blit(surf, (x, y))


# ---------------------------------------------------------------
# OMBRES
# ---------------------------------------------------------------

def blit_shadow(cx, ground_y, width, height=10, alpha=90):
    width = max(4, int(width))
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, alpha), (0, 0, width, height))
    screen.blit(surf, (cx - width // 2, ground_y - height // 2))


def draw_player_shadow(cx, feet_y, platforms):
    best = None
    for p in platforms:
        if p.left <= cx <= p.right and p.top >= feet_y - 2:
            if best is None or p.top < best:
                best = p.top
    if best is None:
        return
    dist = best - feet_y
    scale = max(0.4, 1 - dist / 400)
    blit_shadow(cx, best, 40 * scale)


# ---------------------------------------------------------------
# AMBIENT AMB PARALLAX
# ---------------------------------------------------------------

NIGHT_LEVELS = {3, 6, 9}
_cloud_cache = {}

CLOUDS = [
    {
        'x': random.uniform(0, WIDTH + 400),
        'y': random.randint(30, 280),
        'scale': random.uniform(0.7, 1.7),
        'speed': random.uniform(0.12, 0.45)
    }
    for _ in range(7)
]

STARS = [
    (
        random.randint(0, WIDTH),
        random.randint(0, HEIGHT - 160),
        random.choice((1, 1, 2)),
        random.uniform(0, 6.28)
    )
    for _ in range(80)
]


def _cloud_surface(scale):
    key = round(scale, 1)

    if key not in _cloud_cache:
        w = int(170 * key)
        h = int(70 * key)

        s = pygame.Surface((w, h), pygame.SRCALPHA)
        col = (255, 255, 255, 95)

        pygame.draw.ellipse(s, col, (0, int(h * 0.40), w, int(h * 0.55)))
        pygame.draw.ellipse(s, col, (int(w * 0.10), int(h * 0.15), int(w * 0.40), int(h * 0.60)))
        pygame.draw.ellipse(s, col, (int(w * 0.35), 0, int(w * 0.45), int(h * 0.70)))
        pygame.draw.ellipse(s, col, (int(w * 0.60), int(h * 0.25), int(w * 0.38), int(h * 0.55)))

        _cloud_cache[key] = s

    return _cloud_cache[key]


def draw_ambient(level, now, player_x):
    shift = player_x - WIDTH / 2

    if level in NIGHT_LEVELS:

        for x, y, r, ph in STARS:
            b = int(170 + 80 * math.sin(now / 450 + ph))

            pygame.draw.circle(
                screen,
                (b, b, min(255, b + 20)),
                (int(x - shift * 0.01 * r), y),
                r
            )

    else:

        for c in CLOUDS:
            surf = _cloud_surface(c['scale'])

            x = (c['x'] + now * c['speed'] * 0.06) % (WIDTH + 400) - 200
            x -= shift * 0.03 * c['scale']

            screen.blit(surf, (int(x), int(c['y'])))


# ---------------------------------------------------------------
# TRANSICIONS
# ---------------------------------------------------------------

_fade_in = {'start': 0, 'dur': 0}


async def fade_out(duration=350):
    snap = screen.copy()
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.fill(BLACK)
    clk = pygame.time.Clock()
    start = pygame.time.get_ticks()
    while True:
        t = (pygame.time.get_ticks() - start) / duration
        if t >= 1:
            break
        screen.blit(snap, (0, 0))
        overlay.set_alpha(int(255 * t))
        screen.blit(overlay, (0, 0))
        pygame.display.flip()
        pygame.event.pump()
        clk.tick(60)
        await asyncio.sleep(0)
    screen.fill(BLACK)
    pygame.display.flip()


def start_fade_in(duration=450):
    _fade_in['start'] = pygame.time.get_ticks()
    _fade_in['dur'] = duration


def draw_fade_in():
    if _fade_in['dur'] <= 0:
        return
    t = (pygame.time.get_ticks() - _fade_in['start']) / _fade_in['dur']
    if t >= 1:
        _fade_in['dur'] = 0
        return
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.fill(BLACK)
    overlay.set_alpha(int(255 * (1 - t)))
    screen.blit(overlay, (0, 0))


# ---------------------------------------------------------------
# PLATAFORMES
# ---------------------------------------------------------------

def build_platforms(level):
    H = HEIGHT
    R = pygame.Rect

    if level == 1:
        return [R(0, H - 50, 2000, 50)]

    if level == 2:
        return [R(0, H - 50, 2000, 50), R(350, H - 200, 400, 30)]

    if level == 3:
        return [
            R(0, H - 50, 2000, 50),
            R(600, H - 250, 350, 30),
            R(1400, H - 350, 350, 30),
            R(200, H - 150, 300, 30)
        ]

    if level == 4:
        return [
            R(0, H - 50, 2500, 50),
            R(150, H - 200, 400, 30),
            R(1100, H - 400, 400, 30),
            R(650, H - 300, 350, 30),
            R(1600, H - 500, 350, 30)
        ]

    if level == 5:
        return [
            R(100, H - 50, 250, 50),
            R(500, H - 50, 700, 50),
            R(300, H - 250, 400, 30),
            R(450, H - 450, 330, 30),
            R(100, H - 500, 200, 30),
            R(900, H - 500, 400, 30)
        ]

    if level == 6:
        return [
            R(100, H - 50, 100, 50),
            R(850, H - 50, 150, 50),
            R(500, H - 50, 150, 50),
            R(150, H - 250, 400, 30),
            R(500, H - 350, 350, 30),
            R(900, H - 300, 400, 30),
            R(100, H - 500, 400, 30)
        ]

    if level == 7:
        return [
            R(100, H - 50, 100, 50),
            R(850, H - 50, 150, 50),
            R(250, H - 200, 250, 30),
            R(600, H - 350, 200, 30),
            R(800, H - 600, 400, 30),
            R(50, H - 500, 200, 30)
        ]

    if level == 8:
        return [
            R(100, H - 50, 100, 50),
            R(850, H - 50, 100, 50),
            R(70, H - 680, 150, 30),
            R(270, H - 150, 150, 30),
            R(800, H - 530, 400, 30),
            R(100, H - 500, 50, 30),
            R(550, H - 350, 100, 30),
            R(1950, H - 350, 200, 30)
        ]

    if level == 9:
        return [
            R(100, H - 50, 50, 50),
            R(870, H - 50, 50, 50),
            R(1950, H - 200, 50, 50),
            R(570, H - 100, 50, 50),
            R(190, H - 420, 30, 30),
            R(800, H - 330, 100, 30),
            R(380, H - 650, 170, 30)
        ]

    if level == 10:
        return [
            R(1600, H - 500, 50, 50),
            R(100, H - 50, 50, 50),
            R(1950, H - 200, 50, 50),
            R(300, H - 250, 50, 50),
            R(750, H - 300, 50, 50),
            R(1600, H - 400, 50, 50)
        ]

    if level == BOSS_LEVEL:
        return [
            R(0, H - 50, WIDTH, 50),
            R(110, H - 190, 240, 30),
            R(674, H - 190, 240, 30),
            R(392, H - 310, 240, 30)
        ]

    return [R(0, H - 50, WIDTH, 50)]


# ---------------------------------------------------------------
# ESTAT DEL JOC
# ---------------------------------------------------------------

class GameState:

    def __init__(self, level=1):

        self.level = level
        self.is_boss = (level == BOSS_LEVEL)

        self.player_x = 100
        self.player_y = HEIGHT - PLAYER_SIZE[1] - 10

        self.velocity_y = 0
        self.jump_count = 0
        self.is_ducking = False

        self.jump_buffer_until = 0

        self.alive = True
        self.death_music_played = False
        self.death_fx = False
        self.game_over_at = 0

        self.extra_lives = ability_level(ACTIVE['nom'], 'vida_extra')
        self.player_invuln_until = 0

        self.lives_by_char = {ACTIVE['nom']: self.extra_lives}
        self.switch_ready_at = 0

        self.boss_damage = 1
        self.stomp_bounce = 0
        self.enemy_bonus = 0

        self.collected_pokeballs = 0
        self.level_points = 0

        self.combo = 0
        self.last_pickup_at = 0

        self.start_time = time.time()

        particles.clear()
        popups.clear()
        rings.clear()

        self.platforms = build_platforms(level)

        self.enemy_size = (30, 30)

        self.enemies = []
        self.enemy_speeds = []
        self.enemy_kind = []
        self.enemy_hp = []
        self.enemy_hp_max = []
        self.enemy_base_y = []
        self.enemy_phase = []
        self.enemy_ai = {}

        # Llistes per a l'animació de mort i respawn d'enemics voladors
        self.dying_enemies = []
        self.respawning_enemies = []

        self._spawn_enemies()
        self._spawn_ground_enemy()

        self.attacks = []
        self.attack_ready_at = 0
        self.special_ready_at = 0
        self.special_cd_total = 1

        if self.is_boss:
            self.pokeballs = []
        else:
            self.pokeballs = self.generate_pokeballs(8)

        self.pokeball_values = [
            pokeball_points_for_level(level) for _ in self.pokeballs
        ]

        self.total_pokeballs = len(self.pokeballs)

        # -------------------------------------------------------
        # BOSS: VIDA I FASES SEGONS DIFICULTAT
        # -------------------------------------------------------

        mult = diff().get('boss_hp_mult', 1.0)
        self.boss_max_hp = max(1, round(BOSS_BASE_HP * mult))
        self.boss_hp = self.boss_max_hp

        # vida a la qual comença cada fase nova (de més a menys)
        self.boss_phase_hp = [self.boss_max_hp * f for f in boss_cfg()['phase_at']]

        self.boss_platform_damage_hp = self.boss_max_hp * 0.75

        self.boss_w = 290
        self.boss_h = 260

        self.boss_x = float(WIDTH - 200 - self.boss_w)

        self.boss_dir = -1

        self.boss_speed = 1
        self.boss_walking = True

        self.boss_next_action = pygame.time.get_ticks() + 1500

        self.boss_walk_time = 800
        self.boss_stop_time = 400

        self.boss_rect = pygame.Rect(
            int(self.boss_x),
            HEIGHT - 40 - self.boss_h,
            self.boss_w,
            self.boss_h
        )

        self.boss_invuln_until = 0

        self.boss_next_shot = pygame.time.get_ticks() + 2500

        self.boss_shots = []

        self.boss_dead = False

        self.boss_platforms_deteriorated = False
        self.boss_platform_event = "active"
        self.boss_platform_event_until = 0
        self.boss_platform_roar_until = 0
        self.boss_edge_choice_done = False
        self.boss_platform_pre_roar = False
        self.boss_platform_origins = []
        self.boss_platform_damaged_rects = []
        self.boss_platform_debris = []

        if self.is_boss:
            self.boss_platform_origins = [p.copy() for p in self.platforms[1:]]

        init_boss_extras(self)

    def swap_lives(self, old_nom, new_nom):

        self.lives_by_char[old_nom] = self.extra_lives

        if new_nom not in self.lives_by_char:
            self.lives_by_char[new_nom] = ability_level(new_nom, 'vida_extra')

        self.extra_lives = self.lives_by_char[new_nom]

    def _add_enemy(self, rect, kind, ai, **extra):

        d = diff()

        table = d.get('hp_by_kind')

        if table:
            hp = table[kind]  # vida fixa per tipus
        elif kind == GROUND_ENEMY_KIND and d['wolf_hp']:
            hp = d['wolf_hp']  # llop: vida fixa
        else:
            hp = max(1, round(ENEMY_HP_BY_KIND[kind] * d['hp']))

        direction = random.choice([-1, 1])

        self.enemies.append(rect)
        self.enemy_speeds.append(direction * 3)
        self.enemy_kind.append(kind)
        self.enemy_hp.append(hp)
        self.enemy_hp_max.append(hp)
        self.enemy_base_y.append(rect.y)
        self.enemy_phase.append(random.uniform(0, 6.28))

        data = {
            'ai': ai,
            'fx': float(rect.x),
            'dir': direction,
            'phase': self.enemy_phase[-1],
            'base_y': rect.y,
            'alert': False,
        }

        data.update(extra)

        self.enemy_ai[id(rect)] = data

    def _spawn_flyer(self, kind, w, h):

        amp = ENEMY_AI['sine']['amp']

        rect = None

        for attempt in range(100):

            x = random.randint(150, WIDTH - 150 - w)
            y = random.randint(200, HEIGHT - 230)

            r = pygame.Rect(x, y, w, h)

            zone = r.inflate(0, 2 * amp) if attempt < 60 else r

            if zone.collidelist(self.platforms) == -1 and abs(x - 120) > 200:
                rect = r
                break

        if rect is None:
            rect = pygame.Rect(WIDTH // 2, 120, w, h)

        self._add_enemy(rect, kind, 'sine')

    def _spawn_flyer_side(self, kind, w, h):
        """Reaparició: entra per una vora, la més llunyana al jugador."""

        amp = ENEMY_AI['sine']['amp']

        from_left = self.player_x > WIDTH // 2

        x = 4 if from_left else WIDTH - w - 4

        rect = None

        for attempt in range(60):

            y = random.randint(150, HEIGHT - 230)

            r = pygame.Rect(x, y, w, h)

            zone = r.inflate(0, 2 * amp) if attempt < 40 else r

            if zone.collidelist(self.platforms) == -1:
                rect = r
                break

        if rect is None:
            rect = pygame.Rect(x, 150, w, h)

        self._add_enemy(rect, kind, 'sine')

        # va cap a dins de la pantalla
        self.enemy_ai[id(rect)]['dir'] = 1 if from_left else -1

        spawn_ring(rect.centerx, rect.centery, WHITE, 40, 300)

    def _spawn_enemies(self):

        if self.is_boss:
            return

        platforms = self.platforms[1:]

        keep = set(random.sample(range(len(platforms)), enemies_to_keep(len(platforms))))

        for i, p in enumerate(platforms):

            if i not in keep:
                continue

            ai = ENEMY_AI_CYCLE[i % len(ENEMY_AI_CYCLE)]

            if ai == 'chaser' and not diff()['chase']:
                ai = 'patrol'

            kind = AI_KIND[ai]

            w, h = enemy_hitbox_size(kind)

            left = max(p.left, 0)
            right = min(p.right, WIDTH)

            if ai in ('patrol', 'chaser') and right - left < w + 20:
                ai = 'sine'
                kind = AI_KIND[ai]
                w, h = enemy_hitbox_size(kind)

            if ai == 'sine':
                self._spawn_flyer(kind, w, h)
                continue

            x = random.randint(left, right - w)

            for _ in range(30):
                x = random.randint(left, right - w)
                if abs(x + w // 2 - 120) > 200:
                    break

            rect = pygame.Rect(x, p.top - h - 6, w, h)

            self._add_enemy(rect, kind, ai, bounds=(left, right))

    def _spawn_ground_enemy(self):

        if self.level not in GROUND_ENEMY_LEVELS or not ground_frames[0] or not diff()['ground_enemy']:
            return

        w, h = ground_info['size']

        floor = [p for p in self.platforms if p.top == HEIGHT - 50]

        if not floor:
            return

        def visible(p):
            return min(p.right, WIDTH) - max(p.left, 0)

        best = max(visible(p) for p in floor)

        plat = random.choice([p for p in floor if visible(p) == best])

        left = max(plat.left, 0)
        right = min(plat.right, WIDTH)

        if right - left < w + 10:
            return

        lo = max(left, 350)
        hi = right - w

        if lo > hi:
            lo = left

        rect = pygame.Rect(random.randint(lo, hi), plat.top - h, w, h)

        self._add_enemy(rect, GROUND_ENEMY_KIND, 'ground_chaser', bounds=(left, right))

    def generate_pokeballs(self, num_pokeballs):

        pokeballs = []

        for _ in range(num_pokeballs):

            attempts = 0

            while attempts < 100:

                pokeball_x = random.randint(100, WIDTH - 100)

                pokeball_y = random.choice(
                    [p.top - POKEBALL_SIZE - 12 for p in self.platforms]
                )

                new_pokeball = pygame.Rect(pokeball_x, pokeball_y, POKEBALL_SIZE, POKEBALL_SIZE)

                too_close = False

                for existing in pokeballs:
                    distance = (
                                       (new_pokeball.x - existing.x) ** 2
                                       + (new_pokeball.y - existing.y) ** 2
                               ) ** 0.5
                    if distance < MIN_POKEBALL_DISTANCE:
                        too_close = True
                        break

                if too_close:
                    attempts += 1
                    continue

                if all(
                        not new_pokeball.colliderect(p) for p in self.platforms
                ) and all(
                    not new_pokeball.colliderect(e) for e in self.enemies
                ):
                    pokeballs.append(new_pokeball)
                    break

                attempts += 1

        return pokeballs

    def reset(self, level=None, keep_boss_hp=False):

        if level is None:
            level = self.level

        old_boss_hp = self.boss_hp
        old_platforms_deteriorated = getattr(
            self, 'boss_platforms_deteriorated', False
        )

        self.__init__(level)

        if keep_boss_hp and level == BOSS_LEVEL:

            self.boss_hp = max(0, min(old_boss_hp, self.boss_max_hp))

            self.boss_hp_ghost = float(self.boss_hp)

            # el boss reapareix a la fase que li toca per la seva vida
            self.boss_phase = boss_phase_for_hp(self, self.boss_hp)

            boss_phase_timing(self)

            if (
                    old_platforms_deteriorated
                    or (
                    boss_cfg()['platform_damage']
                    and self.boss_hp <= self.boss_platform_damage_hp
            )
            ):
                deteriorate_boss_platforms(self)

            self.boss_platform_event = "active"
            self.boss_platform_event_until = 0
            self.boss_platform_roar_until = 0
            self.boss_edge_choice_done = False
            self.boss_platform_pre_roar = False

            self.boss_dead = False

            now = pygame.time.get_ticks()

            self.boss_invuln_until = now + 1000
            self.boss_next_shot = now + 1800


# ---------------------------------------------------------------
# SPRITES I PERSONATGES
# ---------------------------------------------------------------

class Sprite:

    def __init__(self, surf):
        self.surf = {0: surf, 1: pygame.transform.flip(surf, True, False)}

        self.bb = {
            0: self.surf[0].get_bounding_rect(),
            1: self.surf[1].get_bounding_rect()
        }

    def draw(self, target, direccio, centre_x, peus_y, dy=0):
        s = self.surf[direccio]
        bb = self.bb[direccio]

        target.blit(s, (centre_x - bb.centerx, peus_y - bb.bottom + dy))


class Character:

    def __init__(self, nom, idle, run, duck, bounce=None):
        self.nom = nom
        self.idle = Sprite(idle)
        self.run = [Sprite(s) for s in run]
        self.duck = Sprite(duck)
        self.bounce = bounce if bounce else [0] * len(run)


def lean_scale(surf, sx, sy, lean):
    w, h = surf.get_size()

    nw = max(1, int(w * sx))
    nh = max(1, int(h * sy))

    sc = pygame.transform.scale(surf, (nw, nh))

    if lean == 0:
        return sc

    out = pygame.Surface((nw + abs(lean), nh), pygame.SRCALPHA)

    for y in range(nh):
        off = round(((nh - 1 - y) / nh) * lean) + (abs(lean) if lean < 0 else 0)
        out.blit(sc, (off, y), (0, y, nw, 1))

    return out


def make_pikachu():
    idle = pygame.image.load('assets/pikachu.png').convert_alpha()

    run = [
        pygame.image.load('assets/pikachu_corre13.png').convert_alpha(),
        pygame.image.load('assets/pikachu_corre23.png').convert_alpha()
    ]

    if os.path.exists('assets/baix.png'):
        duck = pygame.image.load('assets/baix.png').convert_alpha()
    else:
        duck = lean_scale(idle, 1.12, 0.66, 0)

    return Character('Pikachu', idle, run, duck, bounce=[0, -3])


def make_eevee_evolution(nom, path):
    flip = nom in SPRITE_FACES_LEFT

    base = pygame.image.load(path).convert_alpha()

    if flip:
        base = pygame.transform.flip(base, True, False)

    base = lean_scale(base, 1.6, 1.6, 0)

    prefix = nom.lower()

    run = []

    for n in (1, 2):
        ruta = f'assets/{prefix}_corre{n}.png'
        if os.path.exists(ruta):
            img = pygame.image.load(ruta).convert_alpha()
            if flip:
                img = pygame.transform.flip(img, True, False)
            run.append(lean_scale(img, 1.6, 1.6, 0))

    if len(run) == 0:
        lean = -4 if nom == 'Flareon' else 4
        if flip:
            lean = -lean
        run = [
            lean_scale(base, 1.1, 0.95, lean),
            lean_scale(base, 0.98, 1.05, -lean // 2)
        ]

    duck = lean_scale(base, 1.2, 0.7, 0)

    return Character(nom, base, run, duck, bounce=[0, -3])


CHARACTERS = []

platform_texture = None
float_platform_texture = None
pokeball_texture = None
pokeball_small_texture = None
enemy_texture1 = None
enemy_texture2 = None
enemy_chaser_texture = None

ground_frames = {0: [], 1: []}
ground_bob = []
ground_info = {'size': None}

boss_frames = []

shot_texture = None
logo_texture = None


def remove_logo_background(surf):
    w, h = surf.get_size()

    to_bytes = getattr(pygame.image, 'tobytes', None) or pygame.image.tostring
    from_bytes = getattr(pygame.image, 'frombytes', None) or pygame.image.fromstring

    data = bytearray(to_bytes(surf, 'RGBA'))

    seen = bytearray(w * h)

    stack = []

    for x in range(w):
        stack.append(x)
        stack.append((h - 1) * w + x)

    for y in range(h):
        stack.append(y * w)
        stack.append(y * w + w - 1)

    last_row = w * (h - 1)

    while stack:

        i = stack.pop()

        if seen[i]:
            continue

        seen[i] = 1

        o = i * 4

        if data[o + 3]:

            r = data[o]
            g = data[o + 1]
            b = data[o + 2]

            blau_clar = (b >= r + 12 and g >= r - 5 and b > 145)
            blanc_fons = (r > 238 and g > 238 and b > 238)

            if not (blau_clar or blanc_fons):
                continue

        data[o] = 255
        data[o + 1] = 255
        data[o + 2] = 255
        data[o + 3] = 0

        x = i % w

        if x > 0:
            stack.append(i - 1)
        if x < w - 1:
            stack.append(i + 1)
        if i >= w:
            stack.append(i - w)
        if i < last_row:
            stack.append(i + w)

    return from_bytes(bytes(data), (w, h), 'RGBA').convert_alpha()


def load_boss_frames():
    imatges = []

    for i in range(1, BOSS_FRAMES + 1):
        ruta = f'assets/giratina_{i}.png'
        if os.path.exists(ruta):
            imatges.append(pygame.image.load(ruta).convert_alpha())

    if len(imatges) == 0:
        boss_raw = pygame.image.load('assets/BOSS.png').convert_alpha()
        bb = boss_raw.get_bounding_rect()
        imatges.append(boss_raw.subsurface(bb).copy())

    for img in imatges:
        gran = pygame.transform.scale(
            img,
            (img.get_width() * BOSS_SCALE, img.get_height() * BOSS_SCALE)
        )

        girada = pygame.transform.flip(gran, True, False)

        boss_frames.append({
            0: (gran, gran.get_bounding_rect()),
            1: (girada, girada.get_bounding_rect())
        })


def _scale_ground(img, crop, k):
    img = img.subsurface(crop).copy()

    img = pygame.transform.scale(
        img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k)))
    )

    if GROUND_ENEMY_FACES_LEFT:
        img = pygame.transform.flip(img, True, False)

    return img


def load_ground_enemy():
    ground_frames[0].clear()
    ground_frames[1].clear()
    ground_bob.clear()

    if not os.path.exists('assets/terra.png'):
        return

    raw_base = pygame.image.load('assets/terra.png').convert_alpha()

    base_bb = raw_base.get_bounding_rect()

    if base_bb.width <= 0 or base_bb.height <= 0:
        return

    k = GROUND_ENEMY_HEIGHT / base_bb.height

    ground_info['size'] = (
        max(1, int(base_bb.width * k)), max(1, int(base_bb.height * k))
    )

    raw_frames = []

    for n in range(1, 5):
        ruta = f'assets/terra_corre{n}.png'
        if os.path.exists(ruta):
            raw_frames.append(pygame.image.load(ruta).convert_alpha())

    if raw_frames:

        crop = base_bb.copy()

        for img in raw_frames:
            bb = img.get_bounding_rect()
            if bb.width > 0 and bb.height > 0:
                crop.union_ip(bb)

        frames = [_scale_ground(img, crop, k) for img in raw_frames]

        bob = [(-1 if i % 2 else 0) for i in range(len(frames))]

    else:

        base = _scale_ground(raw_base, base_bb, k)

        frames = [
            lean_scale(base, 1.05, 0.95, 3),
            lean_scale(base, 0.97, 1.04, 0),
            lean_scale(base, 1.05, 0.95, -3),
            lean_scale(base, 0.97, 1.04, 0),
        ]

        bob = [0, -2, 0, -2]

    ground_frames[0].extend(frames)
    ground_frames[1].extend(
        pygame.transform.flip(f, True, False) for f in frames
    )
    ground_bob.extend(bob)


def load_textures():
    global platform_texture
    global float_platform_texture
    global pokeball_texture
    global pokeball_small_texture
    global enemy_texture1
    global enemy_texture2
    global enemy_chaser_texture
    global shot_texture
    global logo_texture

    yield 'Carregant personatges'

    CHARACTERS.append(make_pikachu())

    if os.path.exists('assets/jolteon.png'):
        CHARACTERS.append(make_eevee_evolution('Jolteon', 'assets/jolteon.png'))

    if os.path.exists('assets/flareon.png'):
        CHARACTERS.append(make_eevee_evolution('Flareon', 'assets/flareon.png'))

    yield 'Carregant plataformes i enemics'

    platform_texture = pygame.image.load('assets/plataforma1.png')
    float_platform_texture = pygame.image.load('assets/plataforma1.png')

    enemy_texture1 = pygame.image.load('assets/volador1.png')

    enemy_chaser_texture = enemy_texture1.copy()
    enemy_chaser_texture.fill((90, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
    enemy_chaser_texture.fill((255, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
    enemy_texture2 = pygame.image.load('assets/volador2.png')

    yield 'Preparant el llop'

    load_ground_enemy()

    yield 'Carregant pokeballs'

    ultra_raw = pygame.image.load('assets/ultraball2.png').convert_alpha()

    ub = ultra_raw.get_bounding_rect()

    if ub.width > 0 and ub.height > 0:
        ultra_raw = ultra_raw.subsurface(ub).copy()

    pokeball_texture = pygame.transform.smoothscale(
        ultra_raw, (POKEBALL_SIZE, POKEBALL_SIZE)
    )

    if os.path.exists('assets/pokeball.png'):

        raw = pygame.image.load('assets/pokeball.png').convert_alpha()

        bbox = raw.get_bounding_rect()

        if bbox.width > 0 and bbox.height > 0:
            raw = raw.subsurface(bbox).copy()

        pokeball_small_texture = pygame.transform.smoothscale(
            raw, (POKEBALL_SIZE, POKEBALL_SIZE)
        )

    else:

        pokeball_small_texture = pokeball_texture

    yield 'Carregant el boss'

    load_boss_frames()

    shot_texture = pygame.Surface((28, 28), pygame.SRCALPHA)

    pygame.draw.circle(shot_texture, (70, 10, 120), (14, 14), 14)
    pygame.draw.circle(shot_texture, (170, 80, 230), (14, 14), 10)
    pygame.draw.circle(shot_texture, (255, 255, 255), (14, 14), 5)

    yield 'Preparant el logo'

    logo_texture = None
    logo_raw = None

    if os.path.exists('assets/logo_transparent.png'):

        logo_raw = pygame.image.load('assets/logo_transparent.png').convert_alpha()

    elif os.path.exists('assets/logo.png'):

        logo_raw = pygame.image.load('assets/logo.png').convert_alpha()

        if max(logo_raw.get_size()) > 400:
            k = 400 / max(logo_raw.get_size())
            logo_raw = pygame.transform.scale(
                logo_raw,
                (max(1, int(logo_raw.get_width() * k)), max(1, int(logo_raw.get_height() * k)))
            )

        logo_raw = remove_logo_background(logo_raw)

    else:

        print('AVÍS: no hi ha assets/logo.png; es mostrarà el títol en text')

    if logo_raw is not None:

        bbox = logo_raw.get_bounding_rect()

        if bbox.width > 0 and bbox.height > 0:
            logo_raw = logo_raw.subsurface(bbox).copy()

        logo_texture = pygame.transform.smoothscale(logo_raw, (280, 280))

    yield 'Llest!'


load_sfx()
load_save()
load_records()


def enemy_hitbox_size(kind):
    if kind == 1:
        return enemy_texture2.get_size()

    return (30, 30)


def get_player_hitbox(x, y, ducking):
    if ducking:
        return pygame.Rect(x + 10, y + 10, 20, 10)

    s = ability_level(ACTIVE['nom'], 'cos_agil') * 2

    return pygame.Rect(x + 5 + s, y + 5 + 2 * s, 30 - 2 * s, 30 - 2 * s)


def try_revive(gs, now):
    if gs.alive:
        return

    consumed = False

    if now < gs.player_invuln_until:
        gs.alive = True
    elif gs.extra_lives > 0:
        gs.extra_lives -= 1
        gs.alive = True
        gs.player_invuln_until = now + 2000
        consumed = True
    else:
        return

    if consumed or gs.player_y > HEIGHT - 20:
        gs.player_x = 100
        gs.player_y = HEIGHT - PLAYER_SIZE[1] - 10
        gs.velocity_y = 0
        gs.jump_count = 0
        gs.boss_shots.clear()
        gs.boss_meteors.clear()
        gs.boss_waves.clear()


# ===============================================================
# CARES DELS PERSONATGES
# ===============================================================

_face_cache = {}


def _to_gray(surf):
    if hasattr(pygame.transform, 'grayscale'):
        g = pygame.transform.grayscale(surf)
    else:
        g = surf.copy()

    g.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)

    return g


def get_face(index, size, gray=False):
    key = (index, size, gray)

    if key in _face_cache:
        return _face_cache[key]

    ch = CHARACTERS[index]

    custom = f'assets/cara_{ch.nom.lower()}.png'

    if os.path.exists(custom):

        src = pygame.image.load(custom).convert_alpha()

    else:

        s = ch.idle.surf[0]
        bb = ch.idle.bb[0]

        head = pygame.Rect(
            bb.x, bb.y, bb.width, max(1, int(bb.height * FACE_CROP_HEIGHT))
        )

        src = s.subsurface(head).copy()

    sw, sh = src.get_size()

    inner = size - 8

    k = min(inner / sw, inner / sh)

    face = pygame.transform.scale(
        src, (max(1, int(sw * k)), max(1, int(sh * k)))
    )

    icon = pygame.Surface((size, size), pygame.SRCALPHA)

    pygame.draw.rect(
        icon, (25, 25, 55, 200), (0, 0, size, size), border_radius=size // 5
    )

    icon.blit(
        face,
        ((size - face.get_width()) // 2, (size - face.get_height()) // 2)
    )

    if gray:
        icon = _to_gray(icon)

        pygame.draw.line(icon, (220, 30, 30), (5, 5), (size - 6, size - 6), 3)
        pygame.draw.line(icon, (220, 30, 30), (size - 6, 5), (5, size - 6), 3)

    _face_cache[key] = icon

    return icon


def draw_character_faces(current, used_characters, x, y, size=36, gap=8):
    for i in range(len(CHARACTERS)):

        is_used = i in used_characters

        pos = (x + i * (size + gap), y)

        screen.blit(get_face(i, size, is_used), pos)

        if is_used:
            border = (200, 40, 40)
            width = 2
        elif i == current:
            border = YELLOW
            width = 3
        else:
            border = (210, 210, 210)
            width = 2

        pygame.draw.rect(
            screen, border, (pos[0], pos[1], size, size), width,
            border_radius=size // 5
        )


# ---------------------------------------------------------------
# BARRA DE RECÀRREGA (HUD)
# ---------------------------------------------------------------

def draw_cd_bar(x, y, w, h, frac, color):
    frac = max(0.0, min(1.0, frac))

    pygame.draw.rect(screen, (40, 40, 40), (x, y, w, h))
    pygame.draw.rect(screen, color, (x, y, int(w * frac), h))
    pygame.draw.rect(screen, WHITE, (x, y, w, h), 1)


# ===============================================================
# ATACS DEL JUGADOR
# ===============================================================

def attacks_unlocked(nom):
    if not BASIC_ATTACK_REQUIRES_SPECIAL:
        return True

    sid = SPECIAL_BY_CHAR.get(nom)

    return bool(sid) and ability_level(nom, sid) > 0


def _add_attack(gs, kind, cx, cy, d, size, speed, life, color, dmg=1,
                pierce=False, splash=0, follow=False, w=None, h=None):
    w = w or size
    h = h or size

    rect = pygame.Rect(0, 0, w, h)
    rect.center = (cx, cy)

    gs.attacks.append({
        'kind': kind,
        'x': float(rect.x),
        'vx': d * speed,
        'dir': d,
        'life': life,
        'age': 0,
        'color': color,
        'dmg': dmg,
        'pierce': pierce,
        'splash': splash,
        'follow': follow,
        'hit': set(),
        'rect': rect
    })


def fire_basic(gs, nom, d):
    cx = gs.player_x + PLAYER_SIZE[0] // 2 + d * 20
    cy = gs.player_y + PLAYER_SIZE[1] // 2

    color = ATTACK_COLORS.get(nom, WHITE)

    if nom == 'Pikachu':

        _add_attack(
            gs, 'spark', cx, cy, d, 18, 13, ATTACK_LIFE_FRAMES, color,
            w=28, h=18
        )

    elif nom == 'Jolteon':

        _add_attack(
            gs, 'needle', cx, cy, d, 0, 17, 40, color, w=34, h=14
        )

    elif nom == 'Flareon':

        _add_attack(
            gs, 'ember', cx, cy, d, 22, 8, 55, color, w=24, h=24
        )

    else:

        _add_attack(
            gs, 'basic', cx, cy, d, 16, ATTACK_SPEED, ATTACK_LIFE_FRAMES, color
        )


def fire_special(gs, nom, d):
    sid = SPECIAL_BY_CHAR.get(nom)

    if not sid:
        return 0

    lvl = ability_level(nom, sid)

    if lvl <= 0:
        return 0

    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    color = ATTACK_COLORS.get(nom, WHITE)

    if sid == 'cua':
        reach = 220 + 60 * (lvl - 1)

        _add_attack(
            gs, 'bolt', px + d * (10 + reach // 2), py, d, 0, 0, 16, color,
            dmg=special_damage('cua', lvl), pierce=True, follow=True, w=reach, h=54
        )

        return 1500 - 150 * (lvl - 1)

    if sid == 'plasma':
        _add_attack(
            gs, 'ring', px + d * 24, py, d, 0, 14 + lvl, 70, color,
            dmg=special_damage('plasma', lvl), pierce=True, w=34, h=72
        )

        return 1300 - 150 * (lvl - 1)

    if sid == 'foc':
        _add_attack(
            gs, 'fire', px + d * 24, py, d, 26 + 4 * lvl, 9, 80, color,
            dmg=special_damage('foc', lvl),
            splash=(0, 0, 70, 110)[lvl]
        )

        return 1700 - 150 * (lvl - 1)

    return 0


def move_enemy(gs, i, enemy, player_hitbox, slow, now):
    d = gs.enemy_ai.get(id(enemy))

    if d is None:
        return

    ai = d['ai']
    cfg = ENEMY_AI[ai]

    reduce = min(slow, 2)
    mult = diff()['speed']

    if ai == 'sine':

        speed = max(mult, cfg['speed'] * mult - reduce)

        nx = d['fx'] + d['dir'] * speed

        test = enemy.copy()
        test.x = int(nx)

        if nx <= 0 or nx + enemy.width >= WIDTH or test.collidelist(gs.platforms) != -1:
            d['dir'] *= -1
        else:
            d['fx'] = nx
            enemy.x = int(nx)

        y = d['base_y'] + int(math.sin(now * cfg['freq'] + d['phase']) * cfg['amp'])

        test = enemy.copy()
        test.y = y

        if test.collidelist(gs.platforms) == -1:
            enemy.y = y

    else:

        left, right = d['bounds']

        speed = cfg['speed'] * mult

        chasing = False

        dx = player_hitbox.centerx - enemy.centerx

        if ai in ('chaser', 'ground_chaser'):

            can_chase = diff()['wolf_chase'] if ai == 'ground_chaser' else diff()['chase']

            near_y = abs(player_hitbox.bottom - enemy.bottom) <= cfg['y_range']

            if can_chase and abs(dx) <= cfg['range'] and near_y:
                chasing = True

        if chasing:
            speed = cfg['chase'] * mult
            d['dir'] = 1 if dx > 0 else -1

        if chasing and abs(dx) < 6:
            move = 0.0
        else:
            move = max(mult, speed - reduce)

        d['fx'] += d['dir'] * move

        if d['fx'] <= left:
            d['fx'] = left
            if not chasing:
                d['dir'] = 1
        elif d['fx'] + enemy.width >= right:
            d['fx'] = right - enemy.width
            if not chasing:
                d['dir'] = -1

        enemy.x = int(d['fx'])

        if ai == 'ground_chaser':

            enemy.y = d['base_y']

            if move and random.random() < 0.10:
                spawn_particles(
                    enemy.centerx - d['dir'] * (enemy.width // 3),
                    enemy.bottom, (205, 195, 170), 1,
                    speed=1.0, life=300, size=3, gravity=0.02, upward=True
                )

        else:

            enemy.y = d['base_y'] - int((1 + math.sin(now / 350 + d['phase'])) * 3)

        if chasing and not d['alert']:
            add_popup(enemy.centerx, enemy.top - 20, '!', (255, 70, 70), 28)

        d['alert'] = chasing

    gs.enemy_speeds[i] = d['dir'] * 3


def update_dying_enemies(gs):
    for de in gs.dying_enemies[:]:
        de['x'] += de['vx']
        de['y'] += de['vy']
        de['vy'] += de['gravity']
        de['angle'] = (de['angle'] + de['rot_speed']) % 360
        if de['y'] > HEIGHT + 120:
            gs.dying_enemies.remove(de)


def update_respawns(gs, now):
    for r in gs.respawning_enemies[:]:
        if now >= r['respawn_at']:
            gs._spawn_flyer_side(r['kind'], r['w'], r['h'])
            gs.respawning_enemies.remove(r)


def draw_dying_enemies(gs):
    for de in gs.dying_enemies:
        k = de['kind']
        flip = de['flip']
        if k == GROUND_ENEMY_KIND:
            frames = ground_frames[1 if flip else 0]
            base_tex = frames[0] if frames else enemy_texture1
        else:
            base = (
                enemy_texture2 if k == 1
                else (enemy_chaser_texture if k == 3 else enemy_texture1)
            )
            base_tex = pygame.transform.flip(base, flip, False)

        rot_img = pygame.transform.rotate(base_tex, de['angle'])
        cx = de['x'] + de['w'] / 2
        cy = de['y'] + de['h'] / 2
        rect = rot_img.get_rect(center=(int(cx), int(cy)))
        screen.blit(rot_img, rect.topleft)


def hit_enemy(gs, i, dmg, color):
    e = gs.enemies[i]

    shown = min(dmg, max(gs.enemy_hp[i], 0))

    gs.enemy_hp[i] -= dmg

    spawn_particles(
        e.centerx, e.centery, color, 8, speed=3, life=300, size=4, gravity=0.1
    )

    add_popup(e.centerx, e.top - 6, f'-{shown}', (255, 230, 120), 20)

    if gs.enemy_hp[i] <= 0:

        spawn_particles(
            e.centerx, e.centery, WHITE, 16, speed=4, life=450, size=5,
            gravity=0.1
        )
        play_sfx('hit')

        kind = gs.enemy_kind[i]
        facing_flip = (gs.enemy_speeds[i] < 0)

        # Animació de mort: impuls cap amunt, gravetat i gir
        gs.dying_enemies.append({
            'x': float(e.x),
            'y': float(e.y),
            'vx': random.uniform(-2.5, 2.5),
            'vy': -8.0,
            'gravity': 0.5,
            'angle': 0,
            'rot_speed': random.choice([-18, -12, 12, 18]),
            'kind': kind,
            'flip': facing_flip,
            'w': e.width,
            'h': e.height
        })

        if kind != GROUND_ENEMY_KIND and not gs.is_boss:
            now = pygame.time.get_ticks()
            gs.respawning_enemies.append({
                'respawn_at': now + 7000,
                'kind': kind,
                'w': e.width,
                'h': e.height
            })

        gs.enemy_ai.pop(id(e), None)

        del gs.enemies[i]
        del gs.enemy_speeds[i]
        del gs.enemy_hp[i]
        del gs.enemy_hp_max[i]
        del gs.enemy_kind[i]
        del gs.enemy_base_y[i]
        del gs.enemy_phase[i]


def damage_boss(gs, now):
    dmg = getattr(gs, 'boss_damage', 1)

    gs.boss_hp -= dmg
    gs.boss_invuln_until = now + boss_cfg()['invuln_ms']
    gs.boss_flash_until = now + 250

    spawn_particles(
        gs.boss_rect.centerx, gs.boss_rect.centery,
        (200, 90, 255), 22, speed=6, life=600, size=6, gravity=0.18
    )
    add_popup(gs.boss_rect.centerx, gs.boss_rect.top - 10, f'-{dmg}', WHITE, 34)
    play_sfx('hit')

    if gs.boss_hp <= 0:
        gs.boss_dead = True
    else:
        check_boss_phase(gs, now)


def update_attacks(gs, now):
    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    for a in gs.attacks[:]:

        r = a['rect']

        if a['follow']:
            if a['dir'] > 0:
                r.left = px + 10
            else:
                r.right = px - 10
            r.centery = py
        else:
            a['x'] += a['vx']
            r.x = int(a['x'])

        a['life'] -= 1
        a['age'] += 1

        if a['life'] <= 0 or r.right < 0 or r.left > WIDTH:
            gs.attacks.remove(a)
            continue

        kind = a['kind']

        if kind in ('ring', 'fire', 'ember') and random.random() < 0.7:
            spawn_particles(
                r.centerx, r.centery, a['color'], 1, speed=0.8, life=250,
                size=5, gravity=0
            )

        if kind == 'needle' and random.random() < 0.5:
            spawn_particles(
                r.centerx - a['dir'] * 12, r.centery, (200, 230, 255), 1,
                speed=0.3, life=180, size=3, gravity=0
            )

        if kind == 'bolt' and random.random() < 0.8:
            tip_x = r.right if a['dir'] > 0 else r.left
            spawn_particles(
                tip_x, r.centery, (255, 255, 150), 2, speed=3, life=250,
                size=3, gravity=0.1
            )

        consumed = False

        for i in range(len(gs.enemies) - 1, -1, -1):

            e = gs.enemies[i]

            if id(e) in a['hit'] or not r.colliderect(e):
                continue

            a['hit'].add(id(e))

            hit_id = id(e)
            ex, ey = e.centerx, e.centery

            # Foc intens (Flareon): +mal a tots els enemics
            dmg = a['dmg'] + gs.enemy_bonus

            hit_enemy(gs, i, dmg, a['color'])

            if a['splash']:

                spawn_particles(
                    ex, ey, a['color'], 24, speed=5, life=450, size=6,
                    gravity=0.05
                )

                spawn_ring(ex, ey, a['color'], a['splash'])

                for j in range(len(gs.enemies) - 1, -1, -1):
                    e2 = gs.enemies[j]
                    if id(e2) == hit_id:
                        continue
                    if math.hypot(e2.centerx - ex, e2.centery - ey) <= a['splash']:
                        hit_enemy(gs, j, dmg, a['color'])

                consumed = True
                break

            if not a['pierce']:
                consumed = True
                break

        if consumed:
            gs.attacks.remove(a)
            continue

        if gs.is_boss and 'boss' not in a['hit'] and r.colliderect(gs.boss_rect):

            a['hit'].add('boss')

            if now >= gs.boss_invuln_until:
                damage_boss(gs, now)

            if kind == 'fire':
                spawn_ring(r.centerx, r.centery, a['color'], 80)

            if not a['follow']:
                gs.attacks.remove(a)


def _zigzag(x0, x1, cy, amp, n):
    pts = []

    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        y = cy if k in (0, n) else cy + random.randint(-amp, amp)
        pts.append((x, y))

    return pts


def draw_attacks(gs):
    for a in gs.attacks:

        r = a['rect']
        kind = a['kind']
        d = a['dir']
        age = a['age']
        col = a['color']
        cx, cy = r.center

        if kind == 'bolt':

            x0, x1 = (r.left, r.right) if d > 0 else (r.right, r.left)

            n = max(6, r.width // 20)

            main = _zigzag(x0, x1, cy, r.height // 2 - 4, n)

            pygame.draw.lines(screen, (190, 140, 0), False, main, 11)
            pygame.draw.lines(screen, col, False, main, 6)
            pygame.draw.lines(screen, WHITE, False, main, 2)

            branch = _zigzag(x0, x1, cy, 14, n)

            pygame.draw.lines(screen, col, False, branch, 2)

        elif kind == 'spark':

            pts = []

            for k in range(5):
                x = cx + d * (-13 + k * 6.5)
                y = cy if k in (0, 4) else cy + (6 if k % 2 else -6) + random.randint(-2, 2)
                pts.append((x, y))

            pygame.draw.lines(screen, col, False, pts, 5)
            pygame.draw.lines(screen, WHITE, False, pts, 2)

        elif kind == 'needle':

            tip = (cx + d * 17, cy)
            t1 = (cx - d * 14, cy - 4)
            t2 = (cx - d * 14, cy + 4)

            pygame.draw.line(
                screen, (200, 230, 255), (cx - d * 14, cy), (cx - d * 32, cy), 1
            )
            pygame.draw.polygon(screen, col, [tip, t1, t2])
            pygame.draw.line(screen, WHITE, (cx - d * 14, cy), tip, 2)

        elif kind == 'ring':

            pulse = int(4 * math.sin(age * 0.5))

            pygame.draw.ellipse(
                screen, (60, 120, 220), r.inflate(pulse, pulse), 5
            )
            pygame.draw.ellipse(screen, col, r.inflate(-12, -14), 3)

            for k in range(3):
                ang = age * 0.35 + k * 2.09
                pygame.draw.circle(
                    screen, WHITE,
                    (int(cx + math.cos(ang) * r.width * 0.5),
                     int(cy + math.sin(ang) * r.height * 0.5)),
                    3
                )

        elif kind == 'ember':

            fl = random.randint(-2, 2)

            pygame.draw.polygon(
                screen, (230, 80, 10),
                [(cx - d * 24, cy + fl), (cx - d * 2, cy - 10), (cx - d * 2, cy + 10)]
            )
            pygame.draw.circle(screen, (200, 50, 10), (cx, cy), 11 + fl)
            pygame.draw.circle(screen, col, (cx, cy), 8)
            pygame.draw.circle(screen, (255, 230, 120), (cx, cy), 4)

        elif kind == 'fire':

            rad = r.width // 2
            fl = random.randint(-3, 3)

            pygame.draw.polygon(
                screen, (200, 50, 10),
                [(cx - d * rad * 3.4, cy + fl),
                 (cx - d * rad * 0.2, cy - rad - 2),
                 (cx - d * rad * 0.2, cy + rad + 2)]
            )
            pygame.draw.polygon(
                screen, col,
                [(cx - d * rad * 2.4, cy - fl),
                 (cx - d * rad * 0.2, cy - rad + 4),
                 (cx - d * rad * 0.2, cy + rad - 4)]
            )
            pygame.draw.circle(screen, (200, 50, 10), (cx, cy), rad + 3 + fl)
            pygame.draw.circle(screen, col, (cx, cy), rad)
            pygame.draw.circle(screen, (255, 230, 120), (cx, cy), rad // 2)

        else:

            pygame.draw.circle(screen, col, r.center, 8)
            pygame.draw.circle(screen, WHITE, r.center, 4)


# ===============================================================
# BOSS
# ===============================================================

_boss_tint_cache = {}


def init_boss_extras(gs):
    gs.boss_phase = 1

    gs.boss_phase_until = 0
    gs.boss_shake_until = 0
    gs.boss_after_roar = False

    gs.boss_pending = None
    gs.boss_windup_until = 0
    gs.boss_last_attack = None

    gs.boss_meteors = []
    gs.boss_waves = []

    gs.boss_dashing = False
    gs.boss_dash_dir = 1
    gs.boss_dash_speed = 0
    gs.boss_burst = None
    gs.boss_stun_until = 0

    gs.boss_static_frame = 0

    gs.boss_platform_event = "active"
    gs.boss_platform_event_until = 0
    gs.boss_platform_roar_until = 0
    gs.boss_edge_choice_done = False
    gs.boss_platform_pre_roar = False

    gs.boss_hp_ghost = float(gs.boss_hp)
    gs.boss_flash_until = 0

    gs.boss_dying = False
    gs.boss_death_start = 0
    gs.boss_death_end = 0
    gs.boss_death_next_boom = 0
    gs.boss_death_blasted = False


def _new_shot(gs, x, y, vx, vy, homing_until=0, speed=0.0):
    gs.boss_shots.append({
        'x': float(x),
        'y': float(y),
        'vx': vx,
        'vy': vy,
        'homing_until': homing_until,
        'speed': speed,
        'rect': pygame.Rect(int(x), int(y), 28, 28)
    })


def _choose_attack(gs, allow_dash=True):
    attacks = boss_cfg()['attacks']

    pool = dict(attacks[min(gs.boss_phase, max(attacks))])

    pool.pop(gs.boss_last_attack, None)

    if not allow_dash:
        pool.pop('dash', None)

    if len(gs.enemies) >= 3:
        pool.pop('summon', None)

    if not pool:
        pool = {'orb': 1}

    names = list(pool)

    return random.choices(names, weights=[pool[n] for n in names])[0]


_BOSS_TIMERS = (
    'boss_next_action', 'boss_invuln_until', 'boss_next_shot',
    'boss_phase_until', 'boss_shake_until', 'boss_windup_until',
    'boss_platform_event_until', 'boss_platform_roar_until',
    'boss_flash_until', 'boss_stun_until',
    'player_invuln_until', 'attack_ready_at', 'special_ready_at',
    'last_pickup_at', 'switch_ready_at',
    'boss_death_start', 'boss_death_end', 'boss_death_next_boom'
)


def shift_boss_timers(gs, dt):
    for attr in _BOSS_TIMERS:
        v = getattr(gs, attr, 0)
        if v > 0:
            setattr(gs, attr, v + dt)

    for m in gs.boss_meteors:
        m['warn_until'] += dt

    for s in gs.boss_shots:
        if s['homing_until'] > 0:
            s['homing_until'] += dt

    if gs.boss_burst:
        gs.boss_burst['next'] += dt

    for r in gs.respawning_enemies:
        r['respawn_at'] += dt


# ===============================================================
# PLATAFORMES: DETERIORAMENT
# ===============================================================

def deteriorate_boss_platforms(gs):
    if not gs.is_boss:
        return

    if gs.boss_platforms_deteriorated:
        return

    gs.boss_platforms_deteriorated = True

    gs.boss_platform_damaged_rects = []

    for platform in gs.platforms[1:]:

        old_centerx = platform.centerx
        old_bottom = platform.bottom

        new_width = max(90, int(platform.width * BOSS_PLATFORM_DAMAGE_SCALE))

        new_height = platform.height

        platform.width = new_width
        platform.height = new_height

        platform.centerx = old_centerx
        platform.bottom = old_bottom

        gs.boss_platform_damaged_rects.append(platform.copy())

        for _ in range(random.randint(10, 16)):
            piece_x = random.randint(platform.left, platform.right)
            piece_y = platform.bottom - random.randint(2, 8)

            gs.boss_platform_debris.append({
                'x': float(piece_x),
                'y': float(piece_y),
                'vx': random.uniform(-2.5, 2.5),
                'vy': random.uniform(-3.5, -1.0),
                'gravity': random.uniform(0.22, 0.38),
                'size': random.randint(4, 10),
                'color': random.choice([
                    (95, 75, 55),
                    (120, 90, 60),
                    (145, 105, 65),
                    (80, 80, 75),
                    (110, 95, 75),
                    (160, 120, 75)
                ]),
                'life': random.randint(900, 1700)
            })


def update_boss_platform_debris(gs):
    if not gs.is_boss:
        return

    for piece in gs.boss_platform_debris[:]:

        piece['x'] += piece['vx']
        piece['y'] += piece['vy']

        piece['vy'] += piece['gravity']

        piece['life'] -= 16

        if piece['life'] <= 0 or piece['y'] > HEIGHT + 30:
            gs.boss_platform_debris.remove(piece)


def draw_boss_platform_debris(gs):
    if not gs.is_boss:
        return

    for piece in gs.boss_platform_debris:
        size = piece['size']
        x = int(piece['x'])
        y = int(piece['y'])

        points = [
            (x - size, y),
            (x - size // 2, y - size),
            (x + size // 2, y - size + 2),
            (x + size, y),
            (x + size // 3, y + size),
            (x - size // 2, y + size)
        ]

        pygame.draw.polygon(screen, piece['color'], points)


def hide_boss_platforms(gs):
    if not gs.is_boss:
        return

    for i, platform in enumerate(gs.platforms[1:]):
        if i % 2 == 0:
            platform.x = -platform.width - 150
        else:
            platform.x = WIDTH + 150


def restore_boss_platforms(gs):
    if not gs.is_boss:
        return

    if not gs.boss_platform_damaged_rects:
        return

    for i, platform in enumerate(gs.platforms[1:]):
        damaged = gs.boss_platform_damaged_rects[i]
        platform.x = damaged.x
        platform.y = damaged.y
        platform.width = damaged.width
        platform.height = damaged.height


# ===============================================================
# ATAC ESPECIAL DE PLATAFORMES
# ===============================================================

def start_boss_platform_attack(gs, now):
    gs.boss_walking = False
    gs.boss_pending = None

    gs.boss_platform_event = "pre_roar"
    gs.boss_platform_pre_roar = True

    gs.boss_platform_event_until = now + random.randint(
        BOSS_PLATFORM_PRE_ROAR_MIN,
        BOSS_PLATFORM_PRE_ROAR_MAX
    )

    gs.boss_platform_roar_until = 0
    gs.boss_static_frame = 0


def update_boss_platform_attack(gs, now):
    if not gs.is_boss:
        return

    if gs.boss_platform_event == "pre_roar":

        gs.boss_walking = False
        gs.boss_static_frame = 0

        if now >= gs.boss_platform_event_until:
            gs.boss_platform_event = "special_attack"
            gs.boss_platform_pre_roar = False

            hide_boss_platforms(gs)

            gs.boss_platform_roar_until = now + BOSS_PLATFORM_ROAR_TIME
            gs.boss_shake_until = now + BOSS_PLATFORM_ROAR_TIME

            gs.boss_walking = False
            gs.boss_static_frame = 0

            gs.boss_platform_event_until = now + random.randint(
                BOSS_PLATFORM_SPECIAL_MIN,
                BOSS_PLATFORM_SPECIAL_MAX
            )

            gs.boss_next_shot = now + 400

    elif gs.boss_platform_event == "special_attack":

        hide_boss_platforms(gs)

        gs.boss_walking = False
        gs.boss_static_frame = 0

        if now >= gs.boss_platform_event_until:
            gs.boss_platform_event = "return_warning"
            gs.boss_platform_event_until = now + BOSS_PLATFORM_RETURN_WARNING

            gs.boss_walking = False

            hide_boss_platforms(gs)

    elif gs.boss_platform_event == "return_warning":

        gs.boss_walking = False
        gs.boss_static_frame = 0

        hide_boss_platforms(gs)

        if now >= gs.boss_platform_event_until:

            restore_boss_platforms(gs)

            gs.boss_platform_event = "active"

            gs.boss_walking = True
            gs.boss_static_frame = 0

            if gs.boss_x <= 30:
                gs.boss_dir = 1
            elif gs.boss_x >= WIDTH - 30 - gs.boss_w:
                gs.boss_dir = -1

            gs.boss_next_action = now + 300

            gs.boss_edge_choice_done = True


# ===============================================================
# FASES DEL BOSS
# ===============================================================

def boss_phase_timing(gs):
    gs.boss_walk_time = 800 + 250 * (gs.boss_phase - 1)
    gs.boss_stop_time = max(150, 400 - 80 * (gs.boss_phase - 1))


def _enter_phase(gs, phase, now):
    gs.boss_phase = phase

    gs.boss_shots.clear()
    gs.boss_meteors.clear()
    gs.boss_waves.clear()

    gs.boss_burst = None
    gs.boss_dashing = False
    gs.boss_pending = None
    gs.boss_stun_until = 0

    gs.boss_phase_until = now + BOSS_PHASE2_ROAR_TIME
    gs.boss_shake_until = now + BOSS_PHASE2_ROAR_TIME
    gs.boss_invuln_until = max(gs.boss_invuln_until, now + BOSS_PHASE2_ROAR_TIME)

    gs.boss_walking = False
    gs.boss_static_frame = 0
    gs.boss_after_roar = True

    gs.boss_next_shot = now + BOSS_PHASE2_ROAR_TIME + 800

    boss_phase_timing(gs)

    color = BOSS_PHASE_AURA.get(phase, (255, 60, 20))

    spawn_ring(gs.boss_rect.centerx, gs.boss_rect.centery, color, 260, 700)
    spawn_particles(
        gs.boss_rect.centerx, gs.boss_rect.centery, color, 40,
        speed=8, life=800, size=7, gravity=0.05
    )


def check_boss_phase(gs, now):
    target = boss_phase_for_hp(gs, gs.boss_hp)

    if target > gs.boss_phase:
        _enter_phase(gs, target, now)


# ===============================================================
# ATACS DEL BOSS
# ===============================================================

def _summon_minions(gs, n, now):
    w, h = enemy_hitbox_size(0)

    for i in range(n):
        side = i % 2

        x = 30 if side == 0 else WIDTH - 30 - w
        y = random.randint(130, 260)

        rect = pygame.Rect(x, y, w, h)

        gs._add_enemy(rect, 0, 'sine')

        gs.enemy_ai[id(rect)]['dir'] = 1 if side == 0 else -1

        gs.enemy_hp[-1] = 1
        gs.enemy_hp_max[-1] = 1

        spawn_ring(rect.centerx, rect.centery, (255, 220, 80), 50, 350)


def _launch_attack(gs, kind, prog, now):
    cfg = boss_cfg()

    phase = gs.boss_phase

    pm = cfg['proj']

    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    ox = gs.boss_rect.centerx
    oy = gs.boss_rect.top + 70

    if kind == 'orb':

        direction = -1 if px < gs.boss_rect.centerx else 1

        sx = gs.boss_rect.left - 28 if direction == -1 else gs.boss_rect.right

        vx = direction * (5 + 3 * prog + 1.2 * (phase - 1)) * pm

        alçades = [HEIGHT - 50 - 26, HEIGHT - 50 - 110]

        if phase == 1:
            alçades = [random.choice(alçades)]

        for y in alçades:
            _new_shot(gs, sx, y, vx, 0)

    elif kind == 'fan':

        n = bp(cfg['fan_n'], phase)

        spread = min(0.48, 0.28 + 0.07 * (n - 3), 3.3 / max(1, n - 1))

        speed = (5 + 2 * prog + 0.8 * (phase - 1)) * pm

        base = math.atan2(py - oy, px - ox)

        for i in range(n):
            ang = base + (i - (n - 1) / 2) * spread
            _new_shot(
                gs, ox - 14, oy - 14,
                    math.cos(ang) * speed, math.sin(ang) * speed
            )

    elif kind == 'homing':

        n = max(1, bp(cfg['homing_n'], phase))

        speed = (3.6 + 1.4 * prog) * pm

        base = math.atan2(py - oy, px - ox)

        for i in range(n):
            ang = base + (i - (n - 1) / 2) * 0.55

            _new_shot(
                gs, ox - 14, oy - 14,
                    math.cos(ang) * speed, math.sin(ang) * speed,
                homing_until=now + 1800 + 250 * i, speed=speed
            )

    elif kind == 'meteors':

        n = bp(cfg['meteor_n'], phase)

        warn = max(450, cfg['meteor_warn'] - 60 * (phase - 1))

        vy = (9 + 1.2 * (phase - 1)) * pm

        for i in range(n):
            x = px - 14 if i == 0 else random.randint(40, WIDTH - 70)

            gs.boss_meteors.append({
                'x': x,
                'y': -40.0,
                'vy': vy,
                'falling': False,
                'warn_until': now + warn + i * 110,
                'rect': pygame.Rect(int(x), -40, 28, 28)
            })

    elif kind == 'wave':

        gs.boss_shake_until = now + 350

        speed = bp(cfg['wave_speed'], phase) * pm

        wy = HEIGHT - 50 - 30

        direccions = (
            [-1, 1] if phase >= 2
            else [-1 if px < gs.boss_rect.centerx else 1]
        )

        for d in direccions:
            wx = gs.boss_rect.left - 40 if d == -1 else gs.boss_rect.right

            gs.boss_waves.append({
                'x': float(wx),
                'vx': d * speed,
                'rect': pygame.Rect(int(wx), wy, 40, 30)
            })

    elif kind == 'dash':

        gs.boss_dashing = True
        gs.boss_dash_speed = cfg['dash_speed'] * (1 + 0.08 * (phase - 1))
        gs.boss_walking = False
        gs.boss_shake_until = now + 250

    elif kind == 'burst':

        gs.boss_burst = {'left': bp(cfg['burst_n'], phase), 'next': now}

    elif kind == 'summon':

        _summon_minions(gs, bp(cfg['summon_n'], phase), now)


def _update_dash(gs, now, prog):
    gs.boss_x += gs.boss_dash_dir * gs.boss_dash_speed

    if random.random() < 0.7:
        spawn_particles(
            gs.boss_rect.centerx - gs.boss_dash_dir * (gs.boss_w // 2),
            HEIGHT - 50, (205, 195, 170), 2,
            speed=2.5, life=350, size=5, gravity=0.02, upward=True
        )

    if gs.boss_x <= 20 or gs.boss_x >= WIDTH - 20 - gs.boss_w:

        gs.boss_x = max(20, min(gs.boss_x, WIDTH - 20 - gs.boss_w))

        gs.boss_dashing = False
        gs.boss_dir = -gs.boss_dash_dir

        gs.boss_stun_until = now + 1000
        gs.boss_walking = False
        gs.boss_next_action = now + 1300
        gs.boss_edge_choice_done = True

        gs.boss_shake_until = now + 450

        spawn_ring(
            gs.boss_rect.centerx, HEIGHT - 60, (255, 230, 160), 120, 400
        )

        if gs.boss_phase >= 3:
            _launch_attack(gs, 'meteors', prog, now)


# ===============================================================
# UPDATE BOSS
# ===============================================================

def update_boss(gs, player_hitbox):
    now = pygame.time.get_ticks()

    cfg = boss_cfg()

    phase = gs.boss_phase

    prog = 1 - max(0, gs.boss_hp) / gs.boss_max_hp

    update_boss_platform_debris(gs)

    in_roar = (now < gs.boss_phase_until)

    charging = (gs.boss_pending is not None or gs.boss_burst is not None)

    if (
            cfg['platform_damage']
            and not gs.boss_platforms_deteriorated
            and gs.boss_hp <= gs.boss_platform_damage_hp
    ):
        deteriorate_boss_platforms(gs)

    update_boss_platform_attack(gs, now)

    platform_special = gs.boss_platform_event in (
        "pre_roar", "special_attack", "return_warning"
    )

    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    ox = gs.boss_rect.centerx
    oy = gs.boss_rect.top + 70

    if gs.boss_after_roar and now >= gs.boss_phase_until and not platform_special:
        gs.boss_after_roar = False
        gs.boss_walking = True
        gs.boss_next_action = now + gs.boss_walk_time

    if not platform_special:

        if gs.boss_dashing:

            _update_dash(gs, now, prog)

        else:

            if now >= gs.boss_next_action and now >= gs.boss_stun_until:
                gs.boss_walking = not gs.boss_walking

                gs.boss_next_action = now + (
                    gs.boss_walk_time if gs.boss_walking else gs.boss_stop_time
                )

            if (
                    gs.boss_walking
                    and not in_roar
                    and not charging
                    and now >= gs.boss_stun_until
            ):
                speed = (gs.boss_speed + 1.2 * prog) * cfg['walk'] * (1 + 0.35 * (phase - 1))

                gs.boss_x += gs.boss_dir * speed

    at_left = (gs.boss_x <= 20)
    at_right = (gs.boss_x >= WIDTH - 20 - gs.boss_w)

    if at_left:
        gs.boss_x = 20
    elif at_right:
        gs.boss_x = WIDTH - 20 - gs.boss_w

    if not at_left and not at_right:
        gs.boss_edge_choice_done = False

    if (
            (at_left or at_right)
            and not platform_special
            and not gs.boss_dashing
            and now >= gs.boss_stun_until
            and not gs.boss_edge_choice_done
    ):

        gs.boss_edge_choice_done = True

        if phase >= 2 and random.random() < cfg['platform_attack']:

            start_boss_platform_attack(gs, now)

        else:

            gs.boss_walking = True
            gs.boss_static_frame = 0
            gs.boss_dir = 1 if at_left else -1

    if gs.boss_walking:
        gs.boss_static_frame = 0

    gs.boss_rect.x = int(gs.boss_x)

    if (
            not in_roar
            and not gs.boss_dashing
            and gs.boss_burst is None
            and now >= gs.boss_stun_until
    ):

        if gs.boss_pending is None and now >= gs.boss_next_shot:

            kind = _choose_attack(gs, allow_dash=not platform_special)

            gs.boss_pending = kind
            gs.boss_last_attack = kind

            base = max(240, 520 - 70 * (phase - 1))

            if kind == 'dash':
                base = 1000
                gs.boss_dash_dir = -1 if px < gs.boss_rect.centerx else 1
            elif kind == 'summon':
                base = 750

            gs.boss_windup_until = now + int(base * cfg['windup'])

        elif gs.boss_pending is not None and now >= gs.boss_windup_until:

            kind = gs.boss_pending

            gs.boss_pending = None

            _launch_attack(gs, kind, prog, now)

            cooldown = max(650, (2300 - 1100 * prog - 120 * (phase - 1)) * cfg['cooldown'])

            gs.boss_next_shot = now + int(cooldown)

    b = gs.boss_burst

    if b and now >= b['next']:

        ang = math.atan2(py - oy, px - ox)

        speed = (6.5 + 1.5 * prog) * cfg['proj']

        _new_shot(
            gs, ox - 14, oy - 14,
                math.cos(ang) * speed, math.sin(ang) * speed
        )

        b['left'] -= 1
        b['next'] = now + 240

        if b['left'] <= 0:
            gs.boss_burst = None

    for shot in gs.boss_shots[:]:

        if shot['homing_until'] > now:
            dx = px - (shot['x'] + 14)
            dy = py - (shot['y'] + 14)

            d = math.hypot(dx, dy) or 1

            shot['vx'] += (dx / d * shot['speed'] - shot['vx']) * 0.06
            shot['vy'] += (dy / d * shot['speed'] - shot['vy']) * 0.06

        shot['x'] += shot['vx']
        shot['y'] += shot['vy']

        shot['rect'].x = int(shot['x'])
        shot['rect'].y = int(shot['y'])

        if random.random() < 0.6:
            spawn_particles(
                shot['rect'].centerx, shot['rect'].centery,
                (170, 80, 230), 1, speed=0.6, life=300, size=6, gravity=0
            )

        if (
                shot['rect'].right < -40
                or shot['rect'].left > WIDTH + 40
                or shot['rect'].top > HEIGHT + 40
                or shot['rect'].bottom < -80
        ):
            gs.boss_shots.remove(shot)

        elif player_hitbox.colliderect(shot['rect']):
            gs.alive = False

    for m in gs.boss_meteors[:]:

        if not m['falling']:
            if now >= m['warn_until']:
                m['falling'] = True
            continue

        m['y'] += m['vy']

        m['rect'].y = int(m['y'])

        if random.random() < 0.5:
            spawn_particles(
                m['rect'].centerx, m['rect'].top,
                (255, 120, 60), 1, speed=0.6, life=250, size=5, gravity=0
            )

        if m['rect'].top > HEIGHT:
            gs.boss_meteors.remove(m)
        elif player_hitbox.colliderect(m['rect']):
            gs.alive = False
        elif m['rect'].collidelist(gs.platforms) != -1:
            gs.boss_meteors.remove(m)

    for w in gs.boss_waves[:]:

        w['x'] += w['vx']

        w['rect'].x = int(w['x'])

        if w['rect'].right < -50 or w['rect'].left > WIDTH + 50:
            gs.boss_waves.remove(w)
        elif player_hitbox.colliderect(w['rect']):
            gs.alive = False

    if player_hitbox.colliderect(gs.boss_rect) and now >= gs.boss_invuln_until:

        if (
                gs.velocity_y > 0
                and player_hitbox.bottom <= gs.boss_rect.top + 35
        ):

            dmg = getattr(gs, 'boss_damage', 1)

            gs.boss_hp -= dmg

            gs.boss_invuln_until = now + cfg['invuln_ms']

            gs.boss_flash_until = now + 250
            spawn_particles(
                player_hitbox.centerx, gs.boss_rect.top + 20,
                (200, 90, 255), 26, speed=6, life=650, size=6, gravity=0.18
            )
            spawn_particles(
                player_hitbox.centerx, gs.boss_rect.top + 20,
                WHITE, 12, speed=7, life=450, size=4, gravity=0.1
            )
            add_popup(
                player_hitbox.centerx, gs.boss_rect.top - 10, f'-{dmg}',
                WHITE, 34
            )
            play_sfx('hit')

            gs.velocity_y = JUMP_STRENGTH - getattr(gs, 'stomp_bounce', 0)
            gs.jump_count = 1

            gs.boss_shots.clear()
            gs.boss_meteors.clear()
            gs.boss_waves.clear()

            if gs.boss_hp <= 0:
                gs.boss_dead = True
            else:
                check_boss_phase(gs, now)

        else:
            gs.alive = False


# ===============================================================
# DIBUIX BOSS
# ===============================================================

def _boss_tinted(idx, d, img, phase):
    key = (idx, d, phase)

    if key not in _boss_tint_cache:
        t = img.copy()
        t.fill(BOSS_PHASE_TINT.get(phase, (70, 0, 0)), special_flags=pygame.BLEND_RGB_ADD)
        _boss_tint_cache[key] = t

    return _boss_tint_cache[key]


def draw_dash_warning(gs, now):
    d = gs.boss_dash_dir

    if d > 0:
        x0, x1 = gs.boss_rect.right, WIDTH
    else:
        x0, x1 = 0, gs.boss_rect.left

    if x1 <= x0:
        return

    band = pygame.Surface((x1 - x0, 46), pygame.SRCALPHA)

    band.fill((255, 40, 40, 55 + int(45 * math.sin(now / 60))))

    screen.blit(band, (x0, HEIGHT - 50 - 46))

    offset = (now // 6) % 90

    for x in range(x0 - 90, x1 + 90, 90):

        cx = x + offset if d > 0 else x - offset

        if cx < x0 or cx > x1:
            continue

        cy = HEIGHT - 50 - 23

        pygame.draw.polygon(
            screen, (255, 110, 110),
            [(cx + d * 16, cy), (cx - d * 10, cy - 14), (cx - d * 10, cy + 14)]
        )


def draw_boss(gs):
    now = pygame.time.get_ticks()

    phase = gs.boss_phase

    if gs.boss_dying:
        draw_boss_dying(gs, now)
        return

    for m in gs.boss_meteors:

        if not m['falling']:

            alpha = 50 + int(40 * (1 + math.sin(now / 60)))

            col = pygame.Surface((28, HEIGHT - 50), pygame.SRCALPHA)

            col.fill((255, 40, 40, alpha))

            screen.blit(col, (m['rect'].x, 0))

            pygame.draw.polygon(
                screen,
                (255, 60, 60),
                [
                    (m['rect'].x + 14, HEIGHT - 70),
                    (m['rect'].x, HEIGHT - 52),
                    (m['rect'].x + 28, HEIGHT - 52)
                ]
            )

        else:
            screen.blit(shot_texture, m['rect'])

    for w in gs.boss_waves:
        r = w['rect']

        pygame.draw.polygon(
            screen,
            (200, 90, 255),
            [(r.left, r.bottom), (r.centerx, r.top), (r.right, r.bottom)]
        )

        pygame.draw.polygon(
            screen,
            WHITE,
            [
                (r.left + 12, r.bottom),
                (r.centerx, r.top + 12),
                (r.right - 12, r.bottom)
            ]
        )

    for shot in gs.boss_shots:

        screen.blit(shot_texture, shot['rect'])

        if shot['homing_until'] > 0:
            pygame.draw.circle(
                screen, (255, 60, 60), shot['rect'].center, 18, 3
            )

    if gs.boss_pending == 'dash':
        draw_dash_warning(gs, now)

    in_roar = (now < gs.boss_phase_until)
    charging = (gs.boss_pending is not None)

    boss_is_stationary = (
            not gs.boss_walking
            or gs.boss_platform_event in (
                "pre_roar", "special_attack", "return_warning"
            )
            or in_roar
    )

    if boss_is_stationary:
        idx = gs.boss_static_frame
    else:
        idx = (now // BOSS_FRAME_MS) % len(boss_frames)

    blit_shadow(gs.boss_rect.centerx, HEIGHT - 50, 230, 18, 100)

    if phase >= 2:
        pulse = 0.5 + 0.5 * math.sin(now / 200)
        aura = pygame.Surface((gs.boss_w + 120, gs.boss_h + 60), pygame.SRCALPHA)
        ar, ag, ab = BOSS_PHASE_AURA.get(phase, (255, 60, 20))
        pygame.draw.ellipse(
            aura,
            (ar, ag, ab, int(30 + 22 * (phase - 1) + 30 * pulse)),
            aura.get_rect()
        )
        screen.blit(
            aura,
            (gs.boss_rect.centerx - aura.get_width() // 2,
             gs.boss_rect.centery - aura.get_height() // 2)
        )

    if not (
            now < gs.boss_invuln_until
            and not in_roar
            and (now // 100) % 2 == 0
    ):

        d = 1 if gs.boss_dir > 0 else 0

        img, bb = boss_frames[idx][d]

        if phase >= 2:
            img = _boss_tinted(idx, d, img, min(phase, 4))

        if now < gs.boss_flash_until:
            img = img.copy()
            img.fill((140, 140, 140), special_flags=pygame.BLEND_RGB_ADD)

        shake = 8 if in_roar else (4 if charging else 0)

        ox = random.randint(-shake, shake) if shake else 0
        oy = random.randint(-shake, shake) if shake else 0

        bx = gs.boss_rect.centerx - img.get_width() // 2 + ox

        by = gs.boss_rect.bottom - bb.bottom + oy

        if gs.boss_dashing:

            for k in (3, 2, 1):
                ghost = img.copy()
                ghost.set_alpha(40 + 15 * (3 - k))

                screen.blit(ghost, (bx - gs.boss_dash_dir * 28 * k, by))

        screen.blit(img, (bx, by))

    if charging:
        mark = _font(60, True).render('!', True, (255, 60, 60))

        screen.blit(
            mark,
            (gs.boss_rect.centerx - mark.get_width() // 2,
             gs.boss_rect.top - 70)
        )

    if now < gs.boss_platform_roar_until:
        roar_text = _font(72, True).render('RUGIT!', True, (255, 50, 50))

        roar_x = WIDTH // 2 - roar_text.get_width() // 2 + random.randint(-5, 5)
        roar_y = 140 + random.randint(-5, 5)

        screen.blit(roar_text, (roar_x, roar_y))


def draw_boss_bar(gs):
    now = pygame.time.get_ticks()

    phase = gs.boss_phase

    cfg = boss_cfg()

    n_phases = len(cfg['phase_at']) + 1

    bar_w = 300
    bar_h = 18

    x = WIDTH // 2 - bar_w // 2
    y = 20

    gs.boss_hp_ghost = max(float(gs.boss_hp), gs.boss_hp_ghost - 0.03)

    pygame.draw.rect(screen, BLACK, (x - 3, y - 3, bar_w + 6, bar_h + 6))

    pygame.draw.rect(screen, (90, 0, 0), (x, y, bar_w, bar_h))

    ghost = max(0, gs.boss_hp_ghost) / gs.boss_max_hp

    pygame.draw.rect(
        screen, (255, 225, 190), (x, y, int(bar_w * ghost), bar_h)
    )

    vida = max(0, gs.boss_hp) / gs.boss_max_hp

    color = BOSS_PHASE_COLORS.get(phase, (230, 40, 60))

    pygame.draw.rect(screen, color, (x, y, int(bar_w * vida), bar_h))

    for f in cfg['phase_at']:
        tick_x = x + int(bar_w * f)

        pygame.draw.line(screen, WHITE, (tick_x, y - 3), (tick_x, y + bar_h + 3), 2)

    label = _font(24).render(
        f'BOSS FINAL - FASE {phase}/{n_phases}' if n_phases > 1 else 'BOSS FINAL',
        True,
        color if phase > 1 else WHITE
    )

    screen.blit(label, (WIDTH // 2 - label.get_width() // 2, y + bar_h + 6))

    if now < gs.boss_phase_until and phase in BOSS_PHASE_TEXT:
        txt = _font(72, True).render(BOSS_PHASE_TEXT[phase], True, color)

        screen.blit(
            txt,
            (WIDTH // 2 - txt.get_width() // 2 + random.randint(-4, 4),
             190 + random.randint(-4, 4))
        )


# ===============================================================
# DERROTA DEL BOSS (animació)
# ===============================================================

def _clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out_bounce(x):
    n1, d1 = 7.5625, 2.75

    if x < 1 / d1:
        return n1 * x * x
    if x < 2 / d1:
        x -= 1.5 / d1
        return n1 * x * x + 0.75
    if x < 2.5 / d1:
        x -= 2.25 / d1
        return n1 * x * x + 0.9375

    x -= 2.625 / d1
    return n1 * x * x + 0.984375


def start_boss_death(gs, now):
    gs.boss_dying = True
    gs.boss_death_start = now
    gs.boss_death_end = now + BOSS_DEATH_MS
    gs.boss_death_next_boom = now
    gs.boss_death_blasted = False

    gs.boss_invuln_until = now + BOSS_DEATH_MS + 5000
    gs.alive = True

    gs.boss_pending = None
    gs.boss_burst = None
    gs.boss_dashing = False
    gs.boss_walking = False
    gs.boss_static_frame = 0

    gs.boss_shots.clear()
    gs.boss_meteors.clear()
    gs.boss_waves.clear()
    gs.attacks.clear()

    if gs.boss_platform_event != "active":
        restore_boss_platforms(gs)
        gs.boss_platform_event = "active"

    for e in gs.enemies:
        spawn_particles(e.centerx, e.centery, WHITE, 10, speed=4, life=450, size=4, gravity=0.05)

    gs.enemies.clear()
    gs.enemy_speeds.clear()
    gs.enemy_kind.clear()
    gs.enemy_hp.clear()
    gs.enemy_hp_max.clear()
    gs.enemy_base_y.clear()
    gs.enemy_phase.clear()
    gs.enemy_ai.clear()
    gs.respawning_enemies.clear()


def update_boss_death(gs, now):
    t = now - gs.boss_death_start

    r = gs.boss_rect

    update_boss_platform_debris(gs)

    if not MUTED['on']:
        try:
            pygame.mixer.music.set_volume(max(0.0, 1 - t / BOSS_DEATH_MS))
        except pygame.error:
            pass

    if t < BOSS_DEATH_BLAST:

        gs.boss_shake_until = now + 80

        if now >= gs.boss_death_next_boom:
            x = random.randint(r.left, r.right)
            y = random.randint(r.top, r.bottom)

            color = random.choice([
                (255, 255, 255), (255, 200, 80), (255, 90, 40), (200, 90, 255)
            ])

            spawn_ring(x, y, color, random.randint(50, 110), 450)
            spawn_particles(x, y, color, 14, speed=6, life=600, size=5, gravity=0.12)
            play_sfx('hit')

            gs.boss_death_next_boom = now + max(70, int(330 - t * 0.09))

    if t >= BOSS_DEATH_BLAST and not gs.boss_death_blasted:

        gs.boss_death_blasted = True

        for k, rad in enumerate((140, 260, 420)):
            spawn_ring(r.centerx, r.centery, (255, 240, 200), rad, 700 + k * 150)

        spawn_particles(
            r.centerx, r.centery, (200, 90, 255), 60,
            speed=10, life=1000, size=8, gravity=0.04
        )
        spawn_particles(
            r.centerx, r.centery, WHITE, 40,
            speed=7, life=800, size=5, gravity=0.05
        )

        gs.boss_shake_until = now + 500
        play_sfx('hit')

    if BOSS_DEATH_BLAST <= t < BOSS_DEATH_BLAST + 900 and random.random() < 0.8:
        spawn_particles(
            random.randint(r.left, r.right), random.randint(r.top, r.bottom),
            (230, 200, 255), 2, speed=2.5, life=900, size=5,
            gravity=-0.05, upward=True
        )


def draw_boss_dying(gs, now):
    t = now - gs.boss_death_start

    fade = 1.0

    if t > BOSS_DEATH_BLAST:
        fade = max(0.0, 1 - (t - BOSS_DEATH_BLAST) / 900)

    if fade <= 0:
        return

    blit_shadow(gs.boss_rect.centerx, HEIGHT - 50, 20 + 210 * fade, 18, int(100 * fade))

    d = 1 if gs.boss_dir > 0 else 0

    img, bb = boss_frames[0][d]

    img = img.copy()

    if (t // 80) % 2 == 0:
        img.fill((130, 130, 130), special_flags=pygame.BLEND_RGB_ADD)
    else:
        img.fill((140, 0, 0), special_flags=pygame.BLEND_RGB_ADD)

    scale = 0.6 + 0.4 * fade

    if fade < 1.0:
        img = pygame.transform.scale(
            img,
            (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale)))
        )
        img.set_alpha(int(255 * fade))

    shake = (4 + int(10 * _clamp01(t / BOSS_DEATH_BLAST))) if t < BOSS_DEATH_BLAST else 0

    ox = random.randint(-shake, shake) if shake else 0
    oy = random.randint(-shake, shake) if shake else 0

    bx = gs.boss_rect.centerx - img.get_width() // 2 + ox
    by = gs.boss_rect.bottom - int(bb.bottom * scale) + oy

    screen.blit(img, (bx, by))


def draw_boss_death_overlay(gs, now):
    t = now - gs.boss_death_start

    if 500 < t < BOSS_DEATH_MS - 700:
        a = _clamp01((t - 500) / 400) * _clamp01((BOSS_DEATH_MS - 700 - t) / 300)

        txt = _font(80, True).render('BOSS DERROTAT!', True, GOLD)
        shd = _font(80, True).render('BOSS DERROTAT!', True, BLACK)

        txt.set_alpha(int(255 * a))
        shd.set_alpha(int(255 * a))

        bob = int(4 * math.sin(t / 120))

        x = WIDTH // 2 - txt.get_width() // 2

        screen.blit(shd, (x + 4, 184 + bob))
        screen.blit(txt, (x, 180 + bob))

    flash = 1 - abs(t - BOSS_DEATH_BLAST) / 450

    if flash > 0:
        ov = pygame.Surface((WIDTH, HEIGHT))
        ov.fill(WHITE)
        ov.set_alpha(int(255 * flash))
        screen.blit(ov, (0, 0))

    fade_start = BOSS_DEATH_MS - 700

    if t > fade_start:
        ov = pygame.Surface((WIDTH, HEIGHT))
        ov.fill(BLACK)
        ov.set_alpha(int(255 * _clamp01((t - fade_start) / 700)))
        screen.blit(ov, (0, 0))


def apply_boss_shake(gs):
    if gs.is_boss and pygame.time.get_ticks() < gs.boss_shake_until:
        frame = screen.copy()

        screen.fill(BLACK)

        screen.blit(frame, (random.randint(-6, 6), random.randint(-6, 6)))


# ===============================================================
# MENÚ
# ===============================================================

MENU_OPTIONS = ['JUGAR', 'BOTIGA', 'CRÈDITS', 'AJUDA', 'SORTIR']


def get_menu_buttons():
    start_y = 365
    gap = 62

    return [
        pygame.Rect(WIDTH // 2 - 200, start_y + i * gap, 400, 46)
        for i in range(len(MENU_OPTIONS))
    ]


def menu_play_label(used_characters):
    has_run = PROGRESS['level'] is not None or bool(used_characters)

    if not has_run:
        return 'JUGAR', False

    lvl = resume_level()

    where = 'BOSS' if lvl == BOSS_LEVEL else f'NIVELL {lvl}'

    return f'CONTINUAR ({where})', True


def return_to_menu(gs, used_characters):
    """Reseteja els nivells i personatges utilitzats en tornar al menú."""
    used_characters.clear()
    reset_progress()
    gs.reset(START_LEVEL)
    gs.start_time = time.time()


def show_start_menu(play_label='JUGAR', has_run=False):
    imprimir_pantalla_fons('assets/menu.png')

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 35))
    screen.blit(overlay, (0, 0))

    if logo_texture:
        logo_rect = logo_texture.get_rect()
        logo_rect.centerx = WIDTH // 2
        logo_rect.top = 25
        screen.blit(logo_texture, logo_rect)

    else:

        t1 = _font(64, True).render('POKÉMON PLATFORMER', True, YELLOW)
        t2 = _font(40, True).render('Poké Ball Quest', True, WHITE)

        screen.blit(t1, (WIDTH // 2 - t1.get_width() // 2, 90))
        screen.blit(t2, (WIDTH // 2 - t2.get_width() // 2, 170))

    font = _font(34, True)

    mouse_pos = pygame.mouse.get_pos()

    buttons = get_menu_buttons()

    options = [play_label] + MENU_OPTIONS[1:]

    for text, rect in zip(options, buttons):

        hover = rect.collidepoint(mouse_pos)

        surf = pygame.Surface(rect.size, pygame.SRCALPHA)

        surf.fill((45, 45, 45, 210) if hover else (0, 0, 0, 160))

        screen.blit(surf, rect.topleft)

        pygame.draw.rect(
            screen, YELLOW, rect, 4 if hover else 2, border_radius=8
        )

        text_surface = font.render(text, True, WHITE)

        if text_surface.get_width() > rect.width - 24:
            text_surface = _font(26, True).render(text, True, WHITE)

        screen.blit(
            text_surface,
            (WIDTH // 2 - text_surface.get_width() // 2,
             rect.centery - text_surface.get_height() // 2)
        )

    dcfg = diff()

    dl = _font(24, True).render(f"Dificultat: {dcfg['nom']}  (D)", True, dcfg['color'])

    screen.blit(dl, (WIDTH // 2 - dl.get_width() // 2, 322))

    if has_run:
        rh = _font(20, True).render('R = començar una partida nova', True, YELLOW)
        screen.blit(rh, (WIDTH // 2 - rh.get_width() // 2, HEIGHT - 52))

    pts = _font(26, True).render(f'Punts: {SAVE["points"]}', True, GOLD)

    screen.blit(pts, (WIDTH - pts.get_width() - 20, 20))

    if MUTED['on']:
        mt = _font(22, True).render('MUT (N)', True, (255, 120, 120))
        screen.blit(mt, (20, 20))

    small_font = _font(20, True)

    footer = small_font.render(
        'Aconsegueix totes les Poké Balls i derrota el Boss Final!',
        True,
        WHITE
    )

    screen.blit(footer, (WIDTH // 2 - footer.get_width() // 2, HEIGHT - 25))

    pygame.display.flip()


# ===============================================================
# PANTALLA DE DIFICULTAT
# ===============================================================

def get_difficulty_cards():
    card_w = 290
    card_h = 350
    gap = 30

    n = len(DIFFICULTY_ORDER)

    x0 = (WIDTH - (n * card_w + (n - 1) * gap)) // 2

    return [
        pygame.Rect(x0 + i * (card_w + gap), 190, card_w, card_h)
        for i in range(n)
    ]


def show_difficulty(selected_index):
    screen.fill(C4)

    imprimir_pantalla_fons('assets/menu.png')

    panel = pygame.Surface((WIDTH - 120, HEIGHT - 120), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 170))
    screen.blit(panel, (60, 60))

    title = _font(54).render('Tria la dificultat', True, WHITE)

    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 90))

    for i, (key, rect) in enumerate(zip(DIFFICULTY_ORDER, get_difficulty_cards())):

        cfg = DIFFICULTY_SETTINGS[key]

        is_sel = (i == selected_index)

        card = pygame.Surface(rect.size, pygame.SRCALPHA)

        card.fill((255, 255, 255, 60) if is_sel else (255, 255, 255, 22))

        screen.blit(card, rect.topleft)

        pygame.draw.rect(
            screen,
            cfg['color'] if is_sel else (140, 140, 140),
            rect,
            6 if is_sel else 2,
            border_radius=12
        )

        num = _font(24).render(str(i + 1), True, WHITE)

        screen.blit(num, (rect.x + 14, rect.y + 10))

        name = _font(42, True).render(cfg['nom'], True, cfg['color'])

        screen.blit(name, (rect.centerx - name.get_width() // 2, rect.y + 40))

        for j, line in enumerate(cfg['desc']):
            is_boss_line = (j == len(cfg['desc']) - 1)

            t = _font(22 if is_boss_line else 24, is_boss_line).render(
                line, True, cfg['color'] if is_boss_line else WHITE
            )

            screen.blit(
                t, (rect.centerx - t.get_width() // 2, rect.y + 125 + j * 42)
            )

    help_text = _font(26).render(
        'A/D o ratolí = triar    ENTER o clic = començar    ESC = enrere',
        True,
        WHITE
    )

    screen.blit(help_text, (WIDTH // 2 - help_text.get_width() // 2, HEIGHT - 80))

    pygame.display.flip()


# ===============================================================
# BOTIGA D'HABILITATS
# ===============================================================

def show_shop(char_index, ability_index, message, message_ok):
    screen.fill(C4)

    imprimir_pantalla_fons('assets/menu.png')

    panel = pygame.Surface((WIDTH - 100, HEIGHT - 30), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 195))
    screen.blit(panel, (50, 15))

    title = _font(40, True).render("BOTIGA D'HABILITATS", True, WHITE)

    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 25))

    pts = _font(28, True).render(f'Punts: {SAVE["points"]}', True, GOLD)

    screen.blit(pts, (WIDTH // 2 - pts.get_width() // 2, 74))

    n = len(CHARACTERS)

    card_w = 140
    card_h = 100
    gap = 30

    total = n * card_w + (n - 1) * gap

    start_x = (WIDTH - total) // 2

    card_y = 112

    for i, ch in enumerate(CHARACTERS):
        x = start_x + i * (card_w + gap)

        is_sel = (i == char_index)

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)

        card.fill((255, 255, 255, 60) if is_sel else (255, 255, 255, 20))

        screen.blit(card, (x, card_y))

        pygame.draw.rect(
            screen,
            YELLOW if is_sel else (150, 150, 150),
            (x, card_y, card_w, card_h),
            4 if is_sel else 2,
            border_radius=10
        )

        screen.blit(get_face(i, 56), (x + card_w // 2 - 28, card_y + 6))

        name = _font(24, True).render(
            ch.nom, True, YELLOW if is_sel else WHITE
        )

        screen.blit(
            name,
            (x + card_w // 2 - name.get_width() // 2, card_y + card_h - 32)
        )

    ch = CHARACTERS[char_index]

    abilities = get_abilities(ch.nom)

    row_y = card_y + card_h + 15
    row_h = 66
    row_gap = 8
    row_x = 90
    row_w = WIDTH - 180

    for j, ab in enumerate(abilities):

        y = row_y + j * (row_h + row_gap)

        level = ability_level(ch.nom, ab['id'])

        max_level = len(ab['costs'])

        is_sel = (j == ability_index)

        row = pygame.Surface((row_w, row_h), pygame.SRCALPHA)

        row.fill((255, 255, 255, 55) if is_sel else (255, 255, 255, 20))

        screen.blit(row, (row_x, y))

        pygame.draw.rect(
            screen,
            YELLOW if is_sel else (130, 130, 130),
            (row_x, y, row_w, row_h),
            3 if is_sel else 1,
            border_radius=8
        )

        name = _font(26, True).render(ab['nom'], True, WHITE)

        screen.blit(name, (row_x + 18, y + 8))

        desc = _font(19).render(ab['desc'], True, (210, 210, 210))

        screen.blit(desc, (row_x + 18, y + 38))

        for k in range(max_level):
            cx = row_x + row_w - 290 + k * 30
            cy = y + 20

            pygame.draw.circle(
                screen,
                GOLD if k < level else (70, 70, 70),
                (cx, cy), 10
            )

            pygame.draw.circle(screen, WHITE, (cx, cy), 10, 2)

        if level >= max_level:

            price = _font(24, True).render('MÀXIM', True, GREEN)

        else:

            cost = ab['costs'][level]

            can_buy = SAVE['points'] >= cost

            price = _font(24, True).render(
                f'{cost} punts',
                True,
                GOLD if can_buy else (200, 80, 80)
            )

        screen.blit(
            price,
            (row_x + row_w - price.get_width() - 20,
             y + row_h // 2 - price.get_height() // 2 + 10)
        )

    if message:
        msg = _font(26, True).render(
            message, True, GREEN if message_ok else (255, 90, 90)
        )

        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT - 95))

    help_text = _font(22).render(
        'A/D = personatge    W/S = habilitat    ENTER = comprar    ESC = enrere',
        True,
        WHITE
    )

    screen.blit(help_text, (WIDTH // 2 - help_text.get_width() // 2, HEIGHT - 55))

    pygame.display.flip()


# ===============================================================
# SELECCIÓ INICIAL
# ===============================================================

def get_select_card_rects():
    n = len(CHARACTERS)
    card_w = 240
    card_h = 330
    gap = 40
    total = n * card_w + (n - 1) * gap
    start_x = (WIDTH - total) // 2
    card_y = 190
    return [pygame.Rect(start_x + i * (card_w + gap), card_y, card_w, card_h) for i in range(n)]


def show_character_select(selected, used_characters):
    screen.fill(C4)

    imprimir_pantalla_fons('assets/menu.png')

    panel = pygame.Surface((WIDTH - 120, HEIGHT - 120), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 170))
    screen.blit(panel, (60, 60))

    title_font = _font(54)
    name_font = _font(36)
    small_font = _font(28)

    title = title_font.render('Tria el teu personatge', True, WHITE)

    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 90))

    available = len(CHARACTERS) - len(used_characters)

    attempts_text = small_font.render(
        f'Personatges disponibles: {available}/{len(CHARACTERS)}',
        True,
        YELLOW
    )

    screen.blit(
        attempts_text,
        (WIDTH // 2 - attempts_text.get_width() // 2, 145)
    )

    rects = get_select_card_rects()

    for i, ch in enumerate(CHARACTERS):

        rect = rects[i]
        x, card_y, card_w, card_h = rect.x, rect.y, rect.width, rect.height

        used = (i in used_characters)

        is_sel = (i == selected and not used)

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)

        if used:
            card.fill((40, 40, 40, 180))
        else:
            card.fill((255, 255, 255, 60) if is_sel else (255, 255, 255, 25))

        screen.blit(card, (x, card_y))

        pygame.draw.rect(
            screen,
            RED if used else (YELLOW if is_sel else (160, 160, 160)),
            (x, card_y, card_w, card_h),
            5 if is_sel else 2
        )

        spr = ch.idle
        dy = 0

        s = spr.surf[0]
        bb = spr.bb[0]

        big = pygame.transform.scale(
            s, (s.get_width() * 2, s.get_height() * 2)
        )

        if used:
            dark = pygame.Surface(big.get_size(), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 170))
            big = big.copy()
            big.blit(dark, (0, 0))

        peus = card_y + card_h - 80

        screen.blit(
            big,
            (x + card_w // 2 - bb.centerx * 2, peus - bb.bottom * 2 + dy)
        )

        name = name_font.render(
            f'{i + 1}. {ch.nom}',
            True,
            RED if used else (YELLOW if is_sel else WHITE)
        )

        screen.blit(
            name,
            (x + card_w // 2 - name.get_width() // 2, card_y + card_h - 60)
        )

        if used:
            used_text = small_font.render('UTILITZAT', True, RED)

            screen.blit(
                used_text,
                (x + card_w // 2 - used_text.get_width() // 2, card_y + 20)
            )

    help_text = small_font.render(
        'A/D, fletxes o ratolí = triar    ENTER o clic = començar    ESC = enrere',
        True,
        WHITE
    )

    screen.blit(help_text, (WIDTH // 2 - help_text.get_width() // 2, HEIGHT - 70))

    pygame.display.flip()


# ===============================================================
# SELECCIÓ DESPRÉS DE MORIR
# ===============================================================

def get_death_select_card_rects(used_characters):
    disponibles = [
        i for i in range(len(CHARACTERS)) if i not in used_characters
    ]
    card_w = 250
    card_h = 330
    gap = 30
    total = len(disponibles) * card_w + (len(disponibles) - 1) * gap
    start_x = (WIDTH - total) // 2
    card_y = 190
    return [(ch_idx, pygame.Rect(start_x + pos * (card_w + gap), card_y, card_w, card_h)) for pos, ch_idx in
            enumerate(disponibles)]


def show_death_character_select(selected, used_characters):
    screen.fill(C4)

    imprimir_pantalla_fons('assets/menu.png')

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    screen.blit(overlay, (0, 0))

    panel = pygame.Surface((WIDTH - 100, HEIGHT - 80), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 190))
    screen.blit(panel, (50, 40))

    title_font = _font(48, True)
    name_font = _font(30, True)
    small_font = _font(24)

    title = title_font.render('Has mort!', True, RED)

    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 65))

    subtitle = small_font.render(
        'Tria un altre personatge per continuar', True, WHITE
    )

    screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 125))

    disponibles = [
        i for i in range(len(CHARACTERS)) if i not in used_characters
    ]

    if not disponibles:
        return

    if selected not in disponibles:
        selected = disponibles[0]

    now = pygame.time.get_ticks()
    card_rects = get_death_select_card_rects(used_characters)

    for pos, (character_index, rect) in enumerate(card_rects):

        ch = CHARACTERS[character_index]
        x, card_y, card_w, card_h = rect.x, rect.y, rect.width, rect.height

        is_selected = (character_index == selected)

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)

        card.fill((255, 255, 255, 70) if is_selected else (255, 255, 255, 25))

        screen.blit(card, (x, card_y))

        pygame.draw.rect(
            screen,
            YELLOW if is_selected else (150, 150, 150),
            (x, card_y, card_w, card_h),
            6 if is_selected else 2,
            border_radius=10
        )

        if is_selected:
            idx = (now // 150) % len(ch.run)
            spr = ch.run[idx]
            dy = ch.bounce[idx] * 2
        else:
            spr = ch.idle
            dy = 0

        s = spr.surf[0]
        bb = spr.bb[0]

        big = pygame.transform.scale(
            s, (s.get_width() * 2, s.get_height() * 2)
        )

        peus = card_y + card_h - 85

        screen.blit(
            big,
            (x + card_w // 2 - bb.centerx * 2, peus - bb.bottom * 2 + dy)
        )

        name = name_font.render(
            ch.nom, True, YELLOW if is_selected else WHITE
        )

        screen.blit(
            name,
            (x + card_w // 2 - name.get_width() // 2, card_y + card_h - 55)
        )

        number = small_font.render(f'{pos + 1}', True, WHITE)

        screen.blit(number, (x + 12, card_y + 10))

    help_text = small_font.render(
        'A/D, fletxes o ratolí = triar     ENTER o clic = continuar     ESC = menú',
        True,
        WHITE
    )

    screen.blit(help_text, (WIDTH // 2 - help_text.get_width() // 2, HEIGHT - 55))

    pygame.display.flip()


# ===============================================================
# PANTALLA DE PAUSA
# ===============================================================

def show_pause(snapshot):
    screen.blit(snapshot, (0, 0))

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

    title = _font(80, True).render('PAUSA', True, WHITE)

    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 110))

    for i, line in enumerate((
            'P o ESC = continuar',
            'N = silenci' + (' (activat)' if MUTED['on'] else '')
    )):
        t = _font(32).render(line, True, YELLOW)
        screen.blit(
            t,
            (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 + 10 + i * 45)
        )

    pygame.display.flip()


# ===============================================================
# ALTRES PANTALLES
# ===============================================================

def draw_centered_lines(lines, font, start_y, step):
    for i, (text, color) in enumerate(lines):
        surf = font.render(text, True, color)

        screen.blit(
            surf,
            (WIDTH // 2 - surf.get_width() // 2, start_y + i * step)
        )


def show_credits():
    screen.fill(C4)

    imprimir_pantalla_fons('assets/fondocredits.png')

    font = _font(50)

    draw_centered_lines(
        [
            ('CREDITS', WHITE),
            ('Creadors del joc: Arnau, Moha i Sergio', WHITE),
            ('Disseny: Arnau i Moha', WHITE),
            ('Codi: Arnau, Sergio, Xavi', WHITE),
            ('Música: TikTok i músiques sense copyright', WHITE),
            ('ENTER - Menu', WHITE),
        ],
        font,
        HEIGHT // 4,
        80
    )

    pygame.display.flip()


def show_A():
    screen.fill(C4)

    imprimir_pantalla_fons('assets/fondo12.png')

    font = _font(28)

    draw_centered_lines(
        [
            ('Ajuda', WHITE),
            ('Objectiu del joc: aconseguir les 8', WHITE),
            ('pokeballs de tots els nivells', WHITE),
            ('i derrotar el boss final', WHITE),
            ('Moviment = A,D i fletxes esquerra/dreta', WHITE),
            ('Saltar = W, espai i fletxa amunt', WHITE),
            ('Ajupir = fletxa avall', WHITE),
            ('Atac = X o J (es desbloqueja a la botiga)', WHITE),
            ('Especial = C o K (cada personatge té el seu)', WHITE),
            ('Salta a sobre d\'un enemic per matar-lo', WHITE),
            ('Pokeballs seguides = COMBO (+1 punt a partir de x3)', WHITE),
            ('Pausa = P o ESC', WHITE),
            ('Silenci = N', WHITE),
            ('Canviar de personatge = 1, 2, 3 o TAB', WHITE),
            ('Entre nivells: B = botiga de millores', WHITE),
            ('Dificultat: en prémer JUGAR (o D al menú)', WHITE),
            ('Hi ha doble salt', WHITE),
            ('Tocar un enemic de costat = mort', WHITE),
            ('Pokeball petita = 1 punt, Ultraball = 2 punts', WHITE),
            ('Gasta els punts a la BOTIGA del menú', WHITE),
        ],
        font,
        20,
        34
    )

    pygame.display.flip()


def show_victory_screen(time_taken, collected_pokeballs, total_pokeballs,
                        level, points_gained=0, points_total=0,
                        best_time=None, is_record=False):
    screen.fill(BLACK)

    font = _font(50)

    next_text = (
        'ENTER - Lluitar contra el BOSS'
        if level + 1 == BOSS_LEVEL
        else 'ENTER - Següent Nivell'
    )

    if best_time is None:
        record_line = ('', WHITE)
    elif is_record:
        record_line = (f'NOU RÈCORD! {best_time:.2f} s', GREEN)
    else:
        record_line = (f'Rècord: {best_time:.2f} s', (200, 200, 200))

    draw_centered_lines(
        [
            (f'Level {level} Completed!', WHITE),
            (f'Poké Balls: {collected_pokeballs}/{total_pokeballs}', WHITE),
            (f'Punts: +{points_gained}  (total {points_total})', GOLD),
            (f'Time: {time_taken:.2f} seconds', WHITE),
            record_line,
            (next_text, WHITE),
            ('ESPAI - Tornar al Nivell', WHITE),
            ('B - Botiga: millorar habilitats', GOLD),
        ],
        font,
        HEIGHT // 6,
        62
    )

    pygame.display.flip()


CONFETTI_COLORS = ((255, 215, 0), (255, 90, 90), (90, 200, 255), (120, 255, 140), (255, 140, 255))


def show_final_screen(time_taken, best_time=None, is_record=False, t=9999):
    screen.fill((8, 8, 25))

    if random.random() < 0.8:
        spawn_particles(
            random.randint(0, WIDTH), -10, random.choice(CONFETTI_COLORS), 1,
            speed=2.5, life=3500, size=5, gravity=0.05
        )

    update_particles()
    draw_particles()

    sc = max(0.05, ease_out_bounce(_clamp01(t / 900)))

    title = _font(90, True).render('HAS GUANYAT!', True, GOLD)

    title = pygame.transform.smoothscale(
        title,
        (max(1, int(title.get_width() * sc)), max(1, int(title.get_height() * sc)))
    )

    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 150 - title.get_height() // 2))

    if best_time is None:
        record_line = ('', WHITE)
    elif is_record:
        record_line = (f'NOU RÈCORD! {best_time:.2f} s', GREEN)
    else:
        record_line = (f'Rècord: {best_time:.2f} s', (200, 200, 200))

    lines = [
        ('Has derrotat el boss final', WHITE),
        (f'Time: {time_taken:.2f} seconds', WHITE),
        record_line,
        ('ESPAI - Tornar a lluitar contra el boss', WHITE),
        ('ESC - Menu', WHITE),
    ]

    for i, (text, color) in enumerate(lines):
        surf = _font(44).render(text, True, color)

        surf.set_alpha(int(255 * _clamp01((t - 700 - i * 200) / 300)))

        screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, 260 + i * 62))

    pygame.display.flip()


def show_game_over(bg, t, info):
    screen.blit(bg, (0, 0))

    red = pygame.Surface((WIDTH, HEIGHT))
    red.fill((90, 0, 0))
    red.set_alpha(int(110 * min(1.0, t / 900)))
    screen.blit(red, (0, 0))

    if random.random() < 0.6:
        spawn_particles(
            random.randint(0, WIDTH), HEIGHT + 5,
            random.choice(((255, 100, 40), (210, 70, 30), (160, 160, 160))), 1,
            speed=3.0, life=3000, size=4, gravity=0.0, upward=True
        )

    update_particles()
    draw_particles()

    e = ease_out_bounce(_clamp01((t - 150) / 850))

    ty = int(-170 + 270 * e)

    sx = sy = 0

    if 440 <= t < 840:
        k = 1 - (t - 440) / 400
        sx = int(random.randint(-8, 8) * k)
        sy = int(random.randint(-6, 6) * k)

    pulse = 0.5 + 0.5 * math.sin(t / 220)

    title = _font(110, True).render('GAME OVER', True, (200 + int(55 * pulse), 25, 25))
    shadow = _font(110, True).render('GAME OVER', True, (20, 0, 0))

    tx = WIDTH // 2 - title.get_width() // 2 + sx

    screen.blit(shadow, (tx + 6, ty + 6 + sy))
    screen.blit(title, (tx, ty + sy))

    sub = _font(30).render('Tots els personatges han caigut...', True, (230, 200, 200))
    sub.set_alpha(int(255 * _clamp01((t - 1000) / 400)))
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 270))

    n = len(CHARACTERS)
    size = 96
    gap = 34

    x0 = (WIDTH - (n * size + (n - 1) * gap)) // 2

    for i in range(n):

        a = _clamp01((t - (1150 + i * 300)) / 300)

        if a <= 0:
            continue

        fx = x0 + i * (size + gap)
        fy = 330 + int((1 - a) * 30)

        face = get_face(i, size, True).copy()
        face.set_alpha(int(255 * a))
        screen.blit(face, (fx, fy))

        nm = _font(22, True).render(CHARACTERS[i].nom, True, (190, 190, 190))
        nm.set_alpha(int(255 * a))
        screen.blit(nm, (fx + size // 2 - nm.get_width() // 2, fy + size + 6))

    where = 'el BOSS FINAL' if info['boss'] else f"el nivell {info['level']}"

    lines = [(f'Has caigut a {where}', WHITE)]

    if info['boss']:
        lines.append((f"Vida que li quedava al boss: {info['boss_pct']} %", (255, 140, 140)))
    else:
        lines.append((f"Poké Balls d'aquest nivell: {info['balls'][0]}/{info['balls'][1]}", WHITE))

    lines.append((f"Punts: {SAVE['points']}", GOLD))

    if SAVE['points'] > 0:
        lines.append(("Gasta'ls a la botiga i torna-ho a provar!", (255, 230, 150)))

    for k, (text, color) in enumerate(lines):
        surf = _font(30).render(text, True, color)

        surf.set_alpha(int(255 * _clamp01((t - 1700 - k * 250) / 300)))

        screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, 465 + k * 40))

    if t >= GO_INPUT_MS:
        a = _clamp01((t - GO_INPUT_MS) / 300) * (0.65 + 0.35 * math.sin(t / 260))

        hint = _font(28, True).render(
            'ENTER = tornar-ho a provar     B = botiga     ESC = menú', True, YELLOW
        )

        hint.set_alpha(int(255 * a))

        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 60))

    pygame.display.flip()


# ===============================================================
# FUNCIONS AUXILIARS
# ===============================================================

def cycle_selection(current, step, used_characters):
    disponibles = [
        i for i in range(len(CHARACTERS)) if i not in used_characters
    ]

    if not disponibles:
        return current

    pos = disponibles.index(current) if current in disponibles else 0

    return disponibles[(pos + step) % len(disponibles)]


def play_music(path, loop=False):
    try:
        pygame.mixer.music.load(music_file(path))
    except (pygame.error, FileNotFoundError):
        return

    apply_volume()

    pygame.mixer.music.play(-1 if loop else 0)


JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)

# ===============================================================
# PANTALLA DE CÀRREGA I ERRORS
# ===============================================================

LOAD_STEPS = 7


def draw_loading(msg, step):
    screen.fill((10, 20, 45))

    big = pygame.font.Font(None, 56)
    small = pygame.font.Font(None, 34)

    title = big.render('Pokémon Platformer', True, WHITE)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 110))

    text = small.render(msg + '...', True, YELLOW)
    screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - 30))

    bar_w = 400
    x = WIDTH // 2 - bar_w // 2
    y = HEIGHT // 2 + 30

    pygame.draw.rect(screen, (60, 70, 100), (x, y, bar_w, 20))
    pygame.draw.rect(screen, GOLD, (x, y, int(bar_w * min(1.0, step / LOAD_STEPS)), 20))
    pygame.draw.rect(screen, WHITE, (x, y, bar_w, 20), 2)

    pygame.display.flip()


async def load_all():
    draw_loading('Iniciant', 0)

    await asyncio.sleep(0.05)

    step = 0

    for msg in load_textures():
        draw_loading(msg, step)

        step += 1

        await asyncio.sleep(0.05)


def show_fatal(err):
    import textwrap

    screen.fill((45, 0, 0))

    font = pygame.font.Font(None, 24)

    lines = ['ERROR - fes una captura d\'aquesta pantalla:', '']

    for raw in err.splitlines():
        lines.extend(textwrap.wrap(raw, 110) or [''])

    y = 8

    for line in lines[:2] + lines[2:][-28:]:
        screen.blit(font.render(line, True, WHITE), (10, y))
        y += 24

    pygame.display.flip()


async def main():
    try:

        await load_all()

        await game()

    except Exception:

        import traceback

        err = traceback.format_exc()

        print(err)

        while True:
            show_fatal(err)
            await asyncio.sleep(0.2)


# ===============================================================
# JOC
# ===============================================================

async def game():
    clock = pygame.time.Clock()

    running = True

    game_state = 'menu'

    gs = GameState(level=START_LEVEL)

    selected = 0

    player_char = CHARACTERS[0]

    used_characters = set()

    death_selected = 0

    sprite_index = 0

    animation_protagonist_speed = 100

    last_change_frame_time = 0

    direccio = 0

    final_time = 0
    final_best = None
    final_is_record = False

    pause_snapshot = None
    pause_started = 0
    prev_on_ground = True

    diff_index = DIFFICULTY_ORDER.index(DIFFICULTY['key'])

    shop_char = 0
    shop_ability = 0
    shop_msg = ''
    shop_msg_ok = True
    shop_msg_until = 0

    final_start = 0

    go_bg = None
    go_start = 0
    go_info = {}

    shop_return = 'menu'

    while running:

        await asyncio.sleep(0)

        pokemon_state = "peu"

        keys = pygame.key.get_pressed()

        current_time = pygame.time.get_ticks()

        # =====================================================
        # MENU
        # =====================================================

        if game_state == 'menu':

            play_label, has_run = menu_play_label(used_characters)

            show_start_menu(play_label, has_run)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
                    toggle_mute()

                if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                    k = DIFFICULTY_ORDER.index(DIFFICULTY['key'])

                    DIFFICULTY['key'] = DIFFICULTY_ORDER[(k + 1) % len(DIFFICULTY_ORDER)]

                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    reset_progress()
                    used_characters.clear()

                    gs.reset(START_LEVEL)
                    gs.start_time = time.time()

                    selected = 0
                    death_selected = 0

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

                    buttons = get_menu_buttons()

                    if buttons[0].collidepoint(event.pos):

                        diff_index = DIFFICULTY_ORDER.index(DIFFICULTY['key'])

                        game_state = 'difficulty'

                    elif buttons[1].collidepoint(event.pos):

                        shop_char = 0
                        shop_ability = 0
                        shop_msg = ''

                        game_state = 'shop'

                    elif buttons[2].collidepoint(event.pos):

                        game_state = 'credits'

                        gs.start_time = time.time()

                    elif buttons[3].collidepoint(event.pos):

                        game_state = 'ajuda'

                        gs.start_time = time.time()

                    elif buttons[4].collidepoint(event.pos):

                        running = False

        # =====================================================
        # DIFICULTAT
        # =====================================================

        elif game_state == 'difficulty':

            show_difficulty(diff_index)

            n_diff = len(DIFFICULTY_ORDER)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                confirm = False

                if event.type == pygame.MOUSEMOTION:

                    for k, r in enumerate(get_difficulty_cards()):
                        if r.collidepoint(event.pos):
                            diff_index = k

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

                    for k, r in enumerate(get_difficulty_cards()):
                        if r.collidepoint(event.pos):
                            diff_index = k
                            confirm = True

                if event.type == pygame.KEYDOWN:

                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        diff_index = (diff_index - 1) % n_diff

                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        diff_index = (diff_index + 1) % n_diff

                    elif event.key == pygame.K_RETURN:
                        confirm = True

                    elif event.key == pygame.K_ESCAPE:
                        return_to_menu(gs, used_characters)
                        game_state = 'menu'

                    for num_key, idx in (
                            (pygame.K_1, 0), (pygame.K_2, 1), (pygame.K_3, 2)
                    ):
                        if event.key == num_key and idx < n_diff:
                            diff_index = idx

                if confirm:
                    DIFFICULTY['key'] = DIFFICULTY_ORDER[diff_index]

                    selected = 0
                    death_selected = 0

                    game_state = 'select'

        # =====================================================
        # BOTIGA
        # =====================================================

        elif game_state == 'shop':

            if shop_msg and current_time > shop_msg_until:
                shop_msg = ''

            show_shop(shop_char, shop_ability, shop_msg, shop_msg_ok)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:

                    n_abilities = len(get_abilities(CHARACTERS[shop_char].nom))

                    if event.key in (pygame.K_LEFT, pygame.K_a):

                        shop_char = (shop_char - 1) % len(CHARACTERS)
                        shop_ability = 0
                        shop_msg = ''

                    elif event.key in (pygame.K_RIGHT, pygame.K_d):

                        shop_char = (shop_char + 1) % len(CHARACTERS)
                        shop_ability = 0
                        shop_msg = ''

                    elif event.key in (pygame.K_UP, pygame.K_w):

                        shop_ability = (shop_ability - 1) % n_abilities

                    elif event.key in (pygame.K_DOWN, pygame.K_s):

                        shop_ability = (shop_ability + 1) % n_abilities

                    elif event.key == pygame.K_RETURN:

                        ch = CHARACTERS[shop_char]

                        ab = get_abilities(ch.nom)[shop_ability]

                        shop_msg_ok, shop_msg = buy_ability(ch.nom, ab)

                        shop_msg_until = current_time + 2500

                    elif event.key == pygame.K_ESCAPE:

                        if shop_return == 'menu':
                            return_to_menu(gs, used_characters)
                        game_state = shop_return
                        shop_return = 'menu'

        # =====================================================
        # SELECCIÓ
        # =====================================================

        elif game_state == 'select':

            disponibles = [
                i for i in range(len(CHARACTERS)) if i not in used_characters
            ]

            if not disponibles:
                used_characters.clear()

                selected = 0

                disponibles = list(range(len(CHARACTERS)))

            if selected not in disponibles:
                selected = disponibles[0]

            show_character_select(selected, used_characters)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                # Selecció amb moviment de ratolí
                if event.type == pygame.MOUSEMOTION:
                    for i, rect in enumerate(get_select_card_rects()):
                        if rect.collidepoint(event.pos) and i not in used_characters:
                            selected = i

                # Selecció amb clic de ratolí
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, rect in enumerate(get_select_card_rects()):
                        if rect.collidepoint(event.pos) and i not in used_characters:
                            selected = i
                            player_char = CHARACTERS[selected]
                            ACTIVE['nom'] = player_char.nom
                            sprite_index = 0
                            last_change_frame_time = current_time

                            await fade_out()
                            game_state = 'playing'
                            gs.reset(gs.level)
                            gs.start_time = time.time()
                            prev_on_ground = True
                            start_fade_in()
                            play_music('assets/musica1.mp3')
                            break

                if event.type == pygame.KEYDOWN:

                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        selected = cycle_selection(selected, -1, used_characters)

                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        selected = cycle_selection(selected, 1, used_characters)

                    for num_key, idx in (
                            (pygame.K_1, 0),
                            (pygame.K_2, 1),
                            (pygame.K_3, 2)
                    ):
                        if (
                                event.key == num_key
                                and len(CHARACTERS) > idx
                                and idx not in used_characters
                        ):
                            selected = idx

                    if event.key == pygame.K_RETURN:

                        if selected not in used_characters:
                            player_char = CHARACTERS[selected]

                            ACTIVE['nom'] = player_char.nom

                            sprite_index = 0

                            last_change_frame_time = current_time

                            await fade_out()

                            game_state = 'playing'

                            gs.reset(gs.level)

                            gs.start_time = time.time()

                            prev_on_ground = True

                            start_fade_in()

                            play_music('assets/musica1.mp3')

                    if event.key == pygame.K_ESCAPE:
                        return_to_menu(gs, used_characters)
                        game_state = 'menu'

        # =====================================================
        # DEATH SELECT
        # =====================================================

        elif game_state == 'death_select':

            disponibles = [
                i for i in range(len(CHARACTERS)) if i not in used_characters
            ]

            if not disponibles:
                selected = 0
                death_selected = 0

                return_to_menu(gs, used_characters)

                game_state = 'menu'

                play_music('assets/musica2.mp3')

                continue

            if death_selected not in disponibles:
                death_selected = disponibles[0]

            show_death_character_select(death_selected, used_characters)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                # Selecció amb el ratolí després de morir
                if event.type == pygame.MOUSEMOTION:
                    for ch_idx, rect in get_death_select_card_rects(used_characters):
                        if rect.collidepoint(event.pos):
                            death_selected = ch_idx

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for ch_idx, rect in get_death_select_card_rects(used_characters):
                        if rect.collidepoint(event.pos):
                            death_selected = ch_idx
                            selected = death_selected
                            player_char = CHARACTERS[selected]
                            ACTIVE['nom'] = player_char.nom
                            sprite_index = 0
                            last_change_frame_time = pygame.time.get_ticks()

                            await fade_out()
                            gs.reset(gs.level, keep_boss_hp=True)
                            gs.start_time = time.time()
                            game_state = 'playing'
                            prev_on_ground = True
                            start_fade_in()
                            play_music('assets/musica1.mp3')
                            break

                if event.type == pygame.KEYDOWN:

                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        death_selected = cycle_selection(
                            death_selected, -1, used_characters
                        )

                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        death_selected = cycle_selection(
                            death_selected, 1, used_characters
                        )

                    if event.key == pygame.K_RETURN:

                        if death_selected in used_characters:
                            continue

                        selected = death_selected

                        player_char = CHARACTERS[selected]

                        ACTIVE['nom'] = player_char.nom

                        sprite_index = 0

                        last_change_frame_time = pygame.time.get_ticks()

                        await fade_out()

                        gs.reset(gs.level, keep_boss_hp=True)

                        gs.start_time = time.time()

                        game_state = 'playing'

                        prev_on_ground = True

                        start_fade_in()

                        play_music('assets/musica1.mp3')

                    if event.key == pygame.K_ESCAPE:
                        selected = 0
                        death_selected = 0

                        return_to_menu(gs, used_characters)

                        game_state = 'menu'

                        play_music('assets/musica2.mp3')

        # =====================================================
        # CREDITS
        # =====================================================

        elif game_state == 'credits':

            show_credits()

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    return_to_menu(gs, used_characters)
                    game_state = 'menu'

        # =====================================================
        # AJUDA
        # =====================================================

        elif game_state == 'ajuda':

            show_A()

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    return_to_menu(gs, used_characters)
                    game_state = 'menu'

        # =====================================================
        # GAME OVER (han mort tots els personatges)
        # =====================================================

        elif game_state == 'gameover':

            go_t = current_time - go_start

            show_game_over(go_bg, go_t, go_info)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN and go_t >= GO_INPUT_MS:

                    if event.key == pygame.K_RETURN:

                        reset_progress()
                        used_characters.clear()

                        selected = 0
                        death_selected = 0

                        gs.reset(START_LEVEL)
                        gs.start_time = time.time()

                        play_music('assets/musica2.mp3')

                        game_state = 'select'

                    elif event.key == pygame.K_b:

                        shop_char = 0
                        shop_ability = 0
                        shop_msg = ''

                        shop_return = 'gameover'

                        game_state = 'shop'

                    elif event.key == pygame.K_ESCAPE:

                        selected = 0
                        death_selected = 0

                        return_to_menu(gs, used_characters)

                        play_music('assets/musica2.mp3')

                        game_state = 'menu'

        # =====================================================
        # FINAL
        # =====================================================

        elif game_state == 'final':

            show_final_screen(
                final_time, final_best, final_is_record,
                pygame.time.get_ticks() - final_start
            )

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:

                    # Tornar a intentar amb l'Espai
                    if event.key == pygame.K_SPACE:
                        gs.reset(BOSS_LEVEL)

                        gs.start_time = time.time()

                        game_state = 'playing'

                        prev_on_ground = True

                        start_fade_in()

                        play_music('assets/musica1.mp3')

                    if event.key == pygame.K_ESCAPE:
                        return_to_menu(gs, used_characters)

                        game_state = 'menu'

                        play_music('assets/musica2.mp3')

        # =====================================================
        # PAUSA
        # =====================================================

        elif game_state == 'paused':

            show_pause(pause_snapshot)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:

                    if event.key == pygame.K_n:

                        toggle_mute()

                    elif event.key in (pygame.K_p, pygame.K_ESCAPE):

                        dt = pygame.time.get_ticks() - pause_started

                        gs.start_time += dt / 1000
                        shift_boss_timers(gs, dt)

                        music_unpause()

                        game_state = 'playing'

        # =====================================================
        # JUGANT
        # =====================================================

        elif game_state == 'playing':

            pause_requested = False

            nom = player_char.nom

            def lv(ab_id):
                return ability_level(player_char.nom, ab_id)

            speed = PLAYER_SPEED + lv('velocitat')
            max_jumps = 3 if lv('triple_salt') else 2
            jump_str = JUMP_STRENGTH - lv('salt_alt')
            dbl_str = DOUBLE_JUMP_STRENGTH - 1.5 * lv('doble_fort')
            max_fall = MAX_FALL_SPEED - 1.5 * lv('planeig')

            gs.boss_damage = 1 + lv('mal_boss')
            gs.enemy_bonus = lv('mal_boss')
            gs.stomp_bounce = 2 * lv('rebot')

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:

                    if event.key == pygame.K_n:
                        toggle_mute()

                    if event.key in (pygame.K_p, pygame.K_ESCAPE) and gs.alive:
                        pause_requested = True

                    if event.key in JUMP_KEYS and gs.alive and not gs.is_ducking:

                        if gs.jump_count < max_jumps:

                            if gs.jump_count == 0:
                                gs.velocity_y = jump_str
                            else:
                                gs.velocity_y = dbl_str

                            gs.jump_count += 1

                            play_sfx('salt')

                        else:
                            gs.jump_buffer_until = current_time + JUMP_BUFFER_MS

                    if (
                            event.key in ATTACK_KEYS
                            and gs.alive
                            and attacks_unlocked(nom)
                            and current_time >= gs.attack_ready_at
                    ):
                        fire_basic(gs, nom, -1 if direccio == 1 else 1)

                        gs.attack_ready_at = current_time + ATTACK_COOLDOWN_MS

                        play_sfx('atac')

                    if (
                            event.key in SPECIAL_KEYS
                            and gs.alive
                            and current_time >= gs.special_ready_at
                    ):
                        cd = fire_special(gs, nom, -1 if direccio == 1 else 1)

                        if cd:
                            gs.special_ready_at = current_time + cd
                            gs.special_cd_total = cd

                            play_sfx('atac')

                    if (
                            event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_TAB)
                            and gs.alive
                            and current_time >= gs.switch_ready_at
                    ):
                        if event.key == pygame.K_TAB:
                            target = cycle_selection(selected, 1, used_characters)
                        else:
                            target = event.key - pygame.K_1

                        if (
                                target != selected
                                and 0 <= target < len(CHARACTERS)
                                and target not in used_characters
                        ):
                            old_nom = player_char.nom

                            selected = target
                            player_char = CHARACTERS[selected]
                            nom = player_char.nom

                            ACTIVE['nom'] = nom
                            gs.swap_lives(old_nom, nom)

                            gs.switch_ready_at = current_time + 800

                            sprite_index = 0
                            last_change_frame_time = current_time

                            sw_col = ATTACK_COLORS.get(nom, WHITE)
                            sw_x = gs.player_x + PLAYER_SIZE[0] // 2
                            sw_y = gs.player_y + PLAYER_SIZE[1] // 2

                            spawn_particles(
                                sw_x, sw_y, sw_col, 18,
                                speed=4, life=450, size=5, gravity=0.05
                            )
                            spawn_ring(sw_x, sw_y, sw_col, 50, 300)
                            add_popup(sw_x, gs.player_y - 20, nom, sw_col, 24)

                if event.type == pygame.KEYUP and event.key in JUMP_KEYS:
                    if gs.velocity_y < -5:
                        gs.velocity_y *= JUMP_CUT_FACTOR

            if pause_requested:
                pause_snapshot = screen.copy()
                pause_started = pygame.time.get_ticks()
                music_pause()
                game_state = 'paused'

                continue

            if gs.alive:

                if keys[pygame.K_LEFT] and gs.player_x > 0:
                    pokemon_state = "camina"
                    direccio = 1

                    gs.player_x -= speed

                if keys[pygame.K_RIGHT] and gs.player_x < WIDTH - PLAYER_SIZE[0]:
                    pokemon_state = "camina"
                    direccio = 0

                    gs.player_x += speed

                if keys[pygame.K_DOWN]:
                    pokemon_state = "ajupit"

                if keys[pygame.K_s]:
                    pokemon_state = "ajupit"

                gs.is_ducking = keys[pygame.K_DOWN]

                if keys[pygame.K_a] and gs.player_x > 0:
                    pokemon_state = "camina"
                    direccio = 1

                    gs.player_x -= speed

                if keys[pygame.K_d] and gs.player_x < WIDTH - PLAYER_SIZE[0]:
                    pokemon_state = "camina"
                    direccio = 0

                    gs.player_x += speed

                next_y = gs.player_y + gs.velocity_y

                player_hitbox = get_player_hitbox(
                    gs.player_x, next_y, gs.is_ducking
                )

                on_ground = False

                if not (gs.is_ducking and gs.velocity_y > 0):

                    for platform_index, platform in enumerate(gs.platforms):

                        if (
                                gs.is_boss
                                and platform_index > 0
                                and gs.boss_platform_event != "active"
                        ):
                            continue

                        if player_hitbox.colliderect(platform):

                            if gs.velocity_y > 0:

                                gs.player_y = platform.top - (
                                    PLAYER_SIZE_DUCKING[1]
                                    if gs.is_ducking
                                    else PLAYER_SIZE[1]
                                )

                                gs.velocity_y = 6
                                gs.jump_count = 0

                                on_ground = True

                            elif gs.velocity_y < 0:

                                gs.player_y = platform.bottom
                                gs.velocity_y = 0

                            break

                if not on_ground:
                    gs.velocity_y = min(gs.velocity_y + GRAVITY, max_fall)

                    gs.player_y = next_y

                feet_cx = gs.player_x + PLAYER_SIZE[0] // 2
                feet_y = gs.player_y + PLAYER_SIZE[1]

                if on_ground and not prev_on_ground:
                    spawn_particles(
                        feet_cx, feet_y, (225, 225, 215), 7,
                        speed=2.2, life=380, size=4, gravity=0.05,
                        upward=True
                    )

                if on_ground and pokemon_state == "camina" and random.random() < 0.12:
                    spawn_particles(
                        feet_cx, feet_y, (225, 225, 215), 1,
                        speed=1.2, life=300, size=3, gravity=0.02,
                        upward=True
                    )

                prev_on_ground = on_ground

                if on_ground and gs.jump_buffer_until > current_time:
                    gs.velocity_y = jump_str
                    gs.jump_count = 1
                    gs.jump_buffer_until = 0

                    play_sfx('salt')

                if gs.player_y > HEIGHT:
                    gs.alive = False

                player_hitbox = get_player_hitbox(
                    gs.player_x, gs.player_y, gs.is_ducking
                )

                # Imant (Jolteon): les pokeballs properes volen cap al jugador
                mag = lv('imant')

                if mag:

                    mag_radius = 90 + 70 * mag  # 160 / 230 / 300 px
                    mag_pull = 4 + 2 * mag  # 6 / 8 / 10 px per frame

                    pcx, pcy = player_hitbox.center

                    for pokeball in gs.pokeballs:

                        dx = pcx - pokeball.centerx
                        dy = pcy - pokeball.centery

                        dist = math.hypot(dx, dy)

                        if 1 < dist <= mag_radius:

                            step = min(dist, mag_pull)

                            pokeball.centerx += int(round(dx / dist * step))
                            pokeball.centery += int(round(dy / dist * step))

                            if random.random() < 0.15:
                                spawn_particles(
                                    pokeball.centerx, pokeball.centery,
                                    (120, 200, 255), 1, speed=0.8, life=250,
                                    size=3, gravity=0
                                )

                for idx in range(len(gs.pokeballs) - 1, -1, -1):

                    pokeball = gs.pokeballs[idx]

                    if player_hitbox.colliderect(pokeball):

                        value = gs.pokeball_values[idx]

                        del gs.pokeballs[idx]
                        del gs.pokeball_values[idx]

                        gs.collected_pokeballs += 1

                        pick_now = pygame.time.get_ticks()

                        if (
                                gs.last_pickup_at > 0
                                and pick_now - gs.last_pickup_at <= COMBO_WINDOW_MS
                        ):
                            gs.combo += 1
                        else:
                            gs.combo = 1

                        gs.last_pickup_at = pick_now

                        bonus = 1 if gs.combo >= COMBO_MIN else 0

                        gained = value + lv('punts_extra') + bonus

                        gs.level_points += gained

                        spawn_particles(
                            pokeball.centerx, pokeball.centery,
                            GOLD if value >= 2 else (255, 90, 90), 14,
                            speed=4, life=450, size=4, gravity=0.1
                        )

                        add_popup(
                            pokeball.centerx, pokeball.top - 6, f'+{gained}',
                            GOLD if value >= 2 else (255, 130, 130), 22
                        )

                        if gs.combo >= 2:
                            add_popup(
                                feet_cx, gs.player_y - 24,
                                f'COMBO x{gs.combo}', (255, 160, 40), 26
                            )

                        play_sfx('pokeball')

                for i in range(len(gs.enemies) - 1, -1, -1):

                    enemy = gs.enemies[i]

                    move_enemy(
                        gs, i, enemy, player_hitbox, lv('enemics_lents'), current_time
                    )

                    if player_hitbox.colliderect(enemy):

                        if (
                                gs.velocity_y > 0
                                and not on_ground
                                and player_hitbox.bottom <= enemy.top + enemy.height * 0.6
                        ):

                            ex, etop = enemy.centerx, enemy.top

                            hit_enemy(
                                gs, i,
                                ENEMY_STOMP_DAMAGE.get(gs.enemy_kind[i], 99) + gs.enemy_bonus,
                                YELLOW
                            )

                            spawn_ring(ex, etop, YELLOW, 40, 250)

                            gs.velocity_y = jump_str * 0.8
                            gs.jump_count = 1

                        else:

                            gs.alive = False

                update_dying_enemies(gs)
                update_respawns(gs, current_time)
                update_attacks(gs, pygame.time.get_ticks())

                if gs.is_boss:

                    if gs.boss_dying:

                        update_boss_death(gs, pygame.time.get_ticks())

                        if pygame.time.get_ticks() >= gs.boss_death_end:
                            game_state = 'final'
                            final_start = pygame.time.get_ticks()

                            particles.clear()
                            rings.clear()
                            popups.clear()

                            apply_volume()
                            play_music('assets/musica2.mp3')

                    else:

                        if gs.alive:
                            update_boss(gs, player_hitbox)

                        if gs.boss_dead:
                            final_time = time.time() - gs.start_time

                            final_is_record, final_best = submit_record(
                                record_key('boss'), final_time
                            )

                            start_boss_death(gs, pygame.time.get_ticks())

                if not gs.pokeballs and not gs.is_boss:

                    time_taken = time.time() - gs.start_time

                    points_gained = gs.level_points

                    add_points(points_gained)

                    PROGRESS['level'] = max(PROGRESS['level'] or 0, gs.level)

                    is_record, best_time = submit_record(record_key(gs.level), time_taken)

                    def draw_victory():
                        show_victory_screen(
                            time_taken,
                            gs.collected_pokeballs,
                            gs.total_pokeballs,
                            gs.level,
                            points_gained,
                            SAVE['points'],
                            best_time,
                            is_record
                        )

                    draw_victory()

                    waiting = True

                    in_shop = False
                    shop_char = selected
                    shop_ability = 0
                    shop_msg = ''

                    while waiting:

                        await asyncio.sleep(0)

                        clock.tick(30)

                        if in_shop:

                            if shop_msg and pygame.time.get_ticks() > shop_msg_until:
                                shop_msg = ''

                            show_shop(shop_char, shop_ability, shop_msg, shop_msg_ok)

                        for event in pygame.event.get():

                            if event.type == pygame.QUIT:
                                delete_save_on_exit()
                                return

                            if event.type != pygame.KEYDOWN:
                                continue

                            if in_shop:

                                n_abilities = len(get_abilities(CHARACTERS[shop_char].nom))

                                if event.key in (pygame.K_LEFT, pygame.K_a):

                                    shop_char = (shop_char - 1) % len(CHARACTERS)
                                    shop_ability = 0
                                    shop_msg = ''

                                elif event.key in (pygame.K_RIGHT, pygame.K_d):

                                    shop_char = (shop_char + 1) % len(CHARACTERS)
                                    shop_ability = 0
                                    shop_msg = ''

                                elif event.key in (pygame.K_UP, pygame.K_w):

                                    shop_ability = (shop_ability - 1) % n_abilities

                                elif event.key in (pygame.K_DOWN, pygame.K_s):

                                    shop_ability = (shop_ability + 1) % n_abilities

                                elif event.key == pygame.K_RETURN:

                                    ch = CHARACTERS[shop_char]

                                    ab = get_abilities(ch.nom)[shop_ability]

                                    shop_msg_ok, shop_msg = buy_ability(ch.nom, ab)

                                    shop_msg_until = pygame.time.get_ticks() + 2500

                                elif event.key == pygame.K_ESCAPE:

                                    in_shop = False

                                    draw_victory()

                                continue

                            if event.key == pygame.K_b:
                                in_shop = True
                                shop_char = selected
                                shop_ability = 0
                                shop_msg = ''

                            # Següent nivell ara amb ENTER
                            if event.key == pygame.K_RETURN:
                                gs.reset(gs.level + 1)

                                gs.start_time = time.time()

                                waiting = False

                                prev_on_ground = True

                                start_fade_in()

                                music_replay()

                            # Reintentar mateix nivell ara amb ESPAI
                            if event.key == pygame.K_SPACE:
                                gs.reset(gs.level)

                                gs.start_time = time.time()

                                waiting = False

                                prev_on_ground = True

                                start_fade_in()

                                music_replay()

            try_revive(gs, pygame.time.get_ticks())

            screen.fill(BLACK)

            if gs.level in LEVEL_BACKGROUNDS:
                imprimir_pantalla_fons(LEVEL_BACKGROUNDS[gs.level])

            now = pygame.time.get_ticks()

            draw_ambient(gs.level, now, gs.player_x)

            for platform_index, platform in enumerate(gs.platforms):

                is_upper_boss_platform = gs.is_boss and platform_index > 0

                if (
                        is_upper_boss_platform
                        and gs.boss_platform_event == "special_attack"
                ):
                    continue

                if (
                        is_upper_boss_platform
                        and gs.boss_platform_event == "return_warning"
                ):

                    if (now // 120) % 2 == 0:

                        if (
                                gs.boss_platform_damaged_rects
                                and platform_index - 1
                                < len(gs.boss_platform_damaged_rects)
                        ):

                            preview = gs.boss_platform_damaged_rects[
                                platform_index - 1
                                ]

                            texture = (
                                platform_texture
                                if preview.height >= 30
                                else float_platform_texture
                            )

                            for x in range(0, preview.width, 50):
                                screen.blit(texture, (preview.x + x, preview.y))

                    continue

                texture = (
                    platform_texture
                    if platform.height == 50
                    else float_platform_texture
                )

                for x in range(0, platform.width, 50):
                    screen.blit(texture, (platform.x + x, platform.y))

            draw_boss_platform_debris(gs)

            for pokeball, value in zip(gs.pokeballs, gs.pokeball_values):
                tex = (
                    pokeball_small_texture
                    if value <= POINTS_SIMPLE_POKEBALL
                    else pokeball_texture
                )

                screen.blit(tex, (pokeball.x, pokeball.y))

            draw_dying_enemies(gs)

            for i, enemy in enumerate(gs.enemies):

                flip = gs.enemy_speeds[i] < 0

                if gs.enemy_kind[i] == GROUND_ENEMY_KIND:

                    frames = ground_frames[1 if flip else 0]

                    fi = (now // GROUND_ENEMY_FRAME_MS) % len(frames)

                    img = frames[fi]

                    blit_shadow(enemy.centerx, enemy.bottom, enemy.width * 0.9, 8, 80)

                    screen.blit(
                        img,
                        (enemy.centerx - img.get_width() // 2,
                         enemy.bottom - img.get_height() + ground_bob[fi])
                    )

                else:

                    k = gs.enemy_kind[i]

                    base_tex = (
                        enemy_texture2 if k == 1
                        else (enemy_chaser_texture if k == 3 else enemy_texture1)
                    )

                    screen.blit(
                        pygame.transform.flip(base_tex, flip, False),
                        (enemy.x, enemy.y)
                    )

                if gs.enemy_hp[i] < gs.enemy_hp_max[i]:
                    w = enemy.width
                    frac = gs.enemy_hp[i] / gs.enemy_hp_max[i]

                    pygame.draw.rect(
                        screen, (90, 0, 0),
                        (enemy.centerx - w // 2, enemy.y - 8, w, 4)
                    )
                    pygame.draw.rect(
                        screen, (60, 220, 60),
                        (enemy.centerx - w // 2, enemy.y - 8, int(w * frac), 4)
                    )

            if gs.is_boss:
                draw_boss(gs)

            if pokemon_state == "camina":

                if (
                        current_time - last_change_frame_time
                        >= animation_protagonist_speed
                ):
                    last_change_frame_time = current_time

                    sprite_index = (sprite_index + 1) % len(player_char.run)

                spr = player_char.run[sprite_index]

                dy = player_char.bounce[sprite_index]

            elif pokemon_state == "ajupit":

                spr = player_char.duck

                dy = 0

            else:

                spr = player_char.idle

                dy = 0

            draw_player_shadow(
                gs.player_x + PLAYER_SIZE[0] // 2,
                gs.player_y + PLAYER_SIZE[1],
                gs.platforms
            )

            if gs.alive and not (
                    current_time < gs.player_invuln_until
                    and (current_time // 100) % 2 == 0
            ):
                spr.draw(
                    screen,
                    direccio,
                    gs.player_x + PLAYER_SIZE[0] // 2,
                    gs.player_y + PLAYER_SIZE[1],
                    dy
                )

            draw_attacks(gs)

            update_particles()
            draw_particles()

            update_rings()
            draw_rings()

            update_popups()
            draw_popups()

            font = _font(30)

            shown_time = final_time if gs.boss_dying else time.time() - gs.start_time

            time_text = font.render(f'Time: {shown_time:.2f}s', True, WHITE)

            pokeball_text = font.render(
                f'Poké Balls: {gs.collected_pokeballs}/{gs.total_pokeballs}',
                True,
                WHITE
            )

            level_text = font.render(
                'BOSS FINAL' if gs.is_boss else f'Level: {gs.level}',
                True,
                WHITE
            )

            screen.blit(time_text, (850, 20))

            if not gs.is_boss:
                screen.blit(pokeball_text, (810, 60))

                points_text = font.render(
                    f'Punts: {SAVE["points"]} (+{gs.level_points})',
                    True,
                    GOLD
                )

                screen.blit(
                    points_text,
                    (WIDTH - points_text.get_width() - 20, 100)
                )

            screen.blit(level_text, (20, 20))

            hud_diff = diff()

            screen.blit(
                _font(20, True).render(hud_diff['nom'], True, hud_diff['color']),
                (level_text.get_width() + 34, 28)
            )

            draw_character_faces(selected, used_characters, 20, 62)

            if attacks_unlocked(nom):

                basic_left = max(0, gs.attack_ready_at - current_time)

                draw_cd_bar(
                    20, 104, 130, 6,
                    1 - basic_left / ATTACK_COOLDOWN_MS,
                    ATTACK_COLORS.get(nom, WHITE)
                )

            else:

                lock_text = _font(16, True).render(
                    'Atacs bloquejats (botiga)', True, (170, 170, 170)
                )

                screen.blit(lock_text, (20, 102))

            special_id = SPECIAL_BY_CHAR.get(nom)

            if special_id and lv(special_id) > 0:
                ready = current_time >= gs.special_ready_at

                sp_text = _font(20, True).render(
                    'Especial (C/K): ' + ('LLEST' if ready else '...'),
                    True,
                    GOLD if ready else (170, 170, 170)
                )

                screen.blit(sp_text, (20, 114))

                special_left = max(0, gs.special_ready_at - current_time)

                draw_cd_bar(
                    20, 138, 130, 6,
                    1 - special_left / max(1, gs.special_cd_total),
                    GOLD if ready else (200, 140, 40)
                )

            if gs.extra_lives > 0:
                life_text = _font(20, True).render(
                    f'Vides extra: {gs.extra_lives}', True, (255, 120, 160)
                )

                screen.blit(life_text, (20, 150))

            if (
                    gs.combo >= 2
                    and gs.last_pickup_at > 0
                    and current_time - gs.last_pickup_at <= COMBO_WINDOW_MS
            ):
                combo_text = _font(24, True).render(
                    f'COMBO x{gs.combo}', True, (255, 160, 40)
                )

                screen.blit(combo_text, (20, 176))

            if len(CHARACTERS) - len(used_characters) > 1:
                sw_hint = _font(16, True).render(
                    '1-2-3 / TAB = canviar de personatge', True, (200, 200, 200)
                )

                screen.blit(sw_hint, (20, HEIGHT - 54))

            if MUTED['on']:
                mute_text = _font(20, True).render(
                    'MUT (N)', True, (255, 120, 120)
                )

                screen.blit(mute_text, (20, HEIGHT - 30))

            if gs.is_boss:

                draw_boss_bar(gs)

                if time.time() - gs.start_time < 5:
                    hint = font.render(
                        f'Salta-li al cap {gs.boss_max_hp} cops! Esquiva els atacs!',
                        True,
                        YELLOW
                    )

                    screen.blit(
                        hint,
                        (WIDTH // 2 - hint.get_width() // 2, 110)
                    )

            # =====================================================
            # MORT
            # =====================================================

            if not gs.alive:

                used_characters.add(selected)

                all_dead = len(used_characters) >= len(CHARACTERS)

                if not gs.death_fx:
                    gs.death_fx = True

                    spawn_particles(
                        gs.player_x + PLAYER_SIZE[0] // 2,
                        gs.player_y + PLAYER_SIZE[1] // 2,
                        (255, 70, 70), 34, speed=7, life=700, size=6,
                        gravity=0.2
                    )
                    spawn_particles(
                        gs.player_x + PLAYER_SIZE[0] // 2,
                        gs.player_y + PLAYER_SIZE[1] // 2,
                        WHITE, 14, speed=5, life=500, size=4, gravity=0.1
                    )

                if not gs.death_music_played:
                    play_music('assets/musica_mort.mp3')

                    gs.death_music_played = True

                if all_dead:

                    if gs.game_over_at == 0:
                        gs.game_over_at = current_time + 1300

                    fade_k = _clamp01(1 - (gs.game_over_at - current_time) / 1300)

                    dark = pygame.Surface((WIDTH, HEIGHT))
                    dark.fill(BLACK)
                    dark.set_alpha(int(140 * fade_k))
                    screen.blit(dark, (0, 0))

                    if current_time >= gs.game_over_at:
                        go_bg = _to_gray(screen.copy())
                        go_start = current_time

                        go_info = {
                            'level': gs.level,
                            'boss': gs.is_boss,
                            'balls': (gs.collected_pokeballs, gs.total_pokeballs),
                            'boss_pct': int(100 * max(0, gs.boss_hp) / gs.boss_max_hp),
                        }

                        game_state = 'gameover'

                else:

                    death_text1 = font.render('GAME OVER', True, RED)

                    death_text2 = font.render(
                        'Prem ENTER per escollir un altre personatge', True, RED
                    )

                    death_text3 = font.render(
                        'Prem ESC per tornar al menú', True, RED
                    )

                    screen.blit(
                        death_text1,
                        (WIDTH // 2 - death_text1.get_width() // 2, int(HEIGHT // 2.3))
                    )

                    screen.blit(
                        death_text2,
                        (WIDTH // 2 - death_text2.get_width() // 2, HEIGHT // 2)
                    )

                    screen.blit(
                        death_text3,
                        (WIDTH // 2 - death_text3.get_width() // 2, int(HEIGHT // 1.7))
                    )

                    disponibles = [
                        i for i in range(len(CHARACTERS)) if i not in used_characters
                    ]

                    if keys[pygame.K_RETURN]:
                        death_selected = disponibles[0]

                        game_state = 'death_select'

                    if keys[pygame.K_ESCAPE]:
                        selected = 0
                        death_selected = 0

                        return_to_menu(gs, used_characters)

                        game_state = 'menu'

                        play_music('assets/musica2.mp3')

            apply_boss_shake(gs)

            if gs.is_boss and gs.boss_dying:
                draw_boss_death_overlay(gs, pygame.time.get_ticks())

            draw_fade_in()

            pygame.display.flip()

        clock.tick(60)

    delete_save_on_exit()
    pygame.quit()


asyncio.run(main())
