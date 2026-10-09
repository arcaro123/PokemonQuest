import asyncio
import json
import math
import os
import random
import time

import sys

import pygame

# Fa que els recursos ('assets/...') es trobin sempre, es llanci el joc des d'on
# es llanci, i també quan està empaquetat amb PyInstaller.
try:
    os.chdir(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))))
except (NameError, OSError):
    pass


def music_file(name):
    """Prefereix .ogg: els navegadors (versió web) no llegeixen bé els .mp3."""

    for ext in ('ogg', 'mp3'):
        path = f'assets/{name}.{ext}'
        if os.path.exists(path):
            return path

    return f'assets/{name}.mp3'


pygame.init()

try:
    pygame.mixer.music.load(music_file('musica2'))
    pygame.mixer.music.play(-1)
except pygame.error as e:
    print('Música no disponible:', e)

WIDTH, HEIGHT = 1024, 720
AMPLADA, ALTURA = WIDTH, HEIGHT

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pantalla = screen

pygame.display.set_caption("Pokémon Platformer: Poké Ball Quest")

_cache_fons = {}


def imprimir_pantalla_fons(image):
    if image not in _cache_fons:
        original = pygame.image.load(image).convert()
        _cache_fons[image] = pygame.transform.scale(original, (AMPLADA, ALTURA))
    pantalla.blit(_cache_fons[image], (0, 0))


# ---------------------------------------------------------------
# FONTS AMB CACHE (s'usen a tot el joc)
# ---------------------------------------------------------------

_boss_fonts = {}


def _font(size, bold=False):
    key = (size, bold)
    if key not in _boss_fonts:
        if sys.platform == 'emscripten':
            # Al navegador no hi ha fonts del sistema (SysFont és lent o falla)
            f = pygame.font.Font(None, int(size * 1.3))
            f.set_bold(bold)
            _boss_fonts[key] = f
        else:
            try:
                _boss_fonts[key] = pygame.font.SysFont('Arial', size, bold=bold)
            except Exception:
                _boss_fonts[key] = pygame.font.Font(None, int(size * 1.3))
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

ATTACK_COOLDOWN_MS = 450
ATTACK_SPEED = 11
ATTACK_LIFE_FRAMES = 45          # ~0,75 s de vol

ENEMY_HP_BY_KIND = {0: 2, 1: 3, 2: 4, 3: 2}  # 0 = abella, 1 = volador gran, 2 = llop, 3 = abella perseguidora

# ---------------------------------------------------------------
# [NOU4] ENEMIC TERRESTRE (llop, assets/terra.png)
# Només als nivells GROUND_ENEMY_LEVELS, n'hi ha UN, i només camina
# per terra, sense sortir dels límits de la plataforma on neix.
# Fotogrames de caminar: assets/terra_corre1.png ... terra_corre4.png
# (es generen amb genera_frames_terra.py). Si no hi són, simula el caminar.
# ---------------------------------------------------------------

GROUND_ENEMY_LEVELS = {4, 5, 6}
GROUND_ENEMY_KIND = 2
GROUND_ENEMY_SPEED = 2
GROUND_ENEMY_HEIGHT = 84          # alçada en píxels (la hitbox fa la mida de la imatge)
GROUND_ENEMY_FACES_LEFT = True    # a terra.png el llop mira cap a l'ESQUERRA
GROUND_ENEMY_FRAME_MS = 120       # temps de cada fotograma de caminar

# ---------------------------------------------------------------
# [NOU6] COMPORTAMENTS DELS ENEMICS
#   patrol        -> camina d'una vora a l'altra de la SEVA plataforma
#   chaser        -> patrulla la seva plataforma i, si el jugador és a prop,
#                    el persegueix (sense sortir de la plataforma)
#   ground_chaser -> igual que chaser, però pel terra (el llop)
#   sine          -> vola amb moviment sinusoïdal; rebota amb les plataformes
# Els enemics s'assignen a les plataformes en aquest ordre (ENEMY_AI_CYCLE).
# Saltar a sobre d'un enemic el mata (ENEMY_STOMP_DAMAGE).
# ---------------------------------------------------------------

ENEMY_AI = {
    'patrol':        {'speed': 2.0},
    'chaser':        {'speed': 1.5, 'chase': 3.4, 'range': 380, 'y_range': 200},
    'ground_chaser': {'speed': GROUND_ENEMY_SPEED, 'chase': 2.8, 'range': 380, 'y_range': 160},
    'sine':          {'speed': 2.5, 'amp': 45, 'freq': 0.0035},
}

ENEMY_AI_CYCLE = ['patrol', 'sine', 'chaser']

AI_KIND = {'patrol': 1, 'sine': 0, 'chaser': 3}   # quin sprite i vida fa servir cada tipus

ENEMY_STOMP_DAMAGE = {0: 99, 1: 99, 2: 2, 3: 99}  # el llop aguanta 2 trepitjades

ATTACK_COLORS = {
    'Pikachu': (255, 230, 40),
    'Jolteon': (120, 200, 255),
    'Flareon': (255, 120, 30),
}

# Quina habilitat és l'atac especial de cada personatge
SPECIAL_BY_CHAR = {
    'Pikachu': 'cua',
    'Jolteon': 'plasma',
    'Flareon': 'foc',
}

MIN_POKEBALL_DISTANCE = 60

# Mida (en píxels) de les pokeballs: la textura i la hitbox són iguals
POKEBALL_SIZE = 40

# Els atacs (X/J i C/K) es desbloquegen en comprar el nivell 1
# de l'habilitat especial del personatge. Posa-ho a False per
# tornar a tenir l'atac bàsic des del principi.
BASIC_ATTACK_REQUIRES_SPECIAL = True

# Personatges els sprites dels quals miren cap a l'ESQUERRA al PNG original.
# Es giren en carregar-los perquè mirin cap on es mouen.
# (Buit = no es gira cap personatge. Si Jolteon es veu al revés, posa {'Jolteon'}.)
SPRITE_FACES_LEFT = set()

START_LEVEL = 1

# ---------------------------------------------------------------
# [NOU5] PROGRÉS DE LA PARTIDA (només mentre el joc està obert)
# Si tornes al menú sense haver mort amb tots els personatges, en
# prémer CONTINUAR tornes al nivell on eres i es mantenen els
# personatges que ja han mort. Amb R al menú comences de zero.
# ---------------------------------------------------------------

RESUME_AT_NEXT_LEVEL = False   # False = últim nivell COMPLETAT; True = el següent

PROGRESS = {'level': None}     # últim nivell completat (None = cap)


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

BOSS_MAX_HP = 11

# FASE 2 quan arriba al 50%
BOSS_PHASE2_HP = BOSS_MAX_HP / 2

# ---------------------------------------------------------------
# POKEBALLS I PUNTS
# Nivells 1..SIMPLE_POKEBALL_MAX_LEVEL -> pokeball petita (1 punt)
# Resta de nivells                     -> ultraball (2 punts)
# ---------------------------------------------------------------

SIMPLE_POKEBALL_MAX_LEVEL = 5
POINTS_SIMPLE_POKEBALL = 1
POINTS_ULTRABALL = 2


def pokeball_points_for_level(level):
    if level <= SIMPLE_POKEBALL_MAX_LEVEL:
        return POINTS_SIMPLE_POKEBALL
    return POINTS_ULTRABALL


# ---------------------------------------------------------------
# CARES DELS PERSONATGES (HUD)
# Si no hi ha 'assets/cara_<nom>.png' (ex: cara_pikachu.png),
# es retalla automàticament la part de dalt de l'sprite.
# ---------------------------------------------------------------

FACE_CROP_HEIGHT = 0.5   # fracció de l'alçada de l'sprite que es considera "cara"

# ---------------------------------------------------------------
# PLATAFORMES DEL BOSS
# ---------------------------------------------------------------

BOSS_PLATFORM_DAMAGE_HP = BOSS_MAX_HP * 0.75
BOSS_PLATFORM_DAMAGE_SCALE = 0.55

BOSS_PLATFORM_PRE_ROAR_MIN = 2000
BOSS_PLATFORM_PRE_ROAR_MAX = 3000

BOSS_PLATFORM_ROAR_TIME = 1200

BOSS_PLATFORM_SPECIAL_MIN = 5000
BOSS_PLATFORM_SPECIAL_MAX = 7000

BOSS_PLATFORM_RETURN_WARNING = 2000

BOSS_PHASE2_ROAR_TIME = 1600

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
# PARTIDA GUARDADA (punts + habilitats comprades)
# Es guarda a savegame.json, al costat del joc.
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
    """Esborra tota la partida guardada en tancar el joc."""
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
# Fitxer a part (records.json): NO s'esborra en tancar el joc.
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
    """Retorna (és_nou_rècord, millor_temps)."""

    key = str(key)

    best = RECORDS.get(key)

    if best is None or t < best:
        RECORDS[key] = round(t, 2)
        save_records()
        return True, RECORDS[key]

    return False, best


# ---------------------------------------------------------------
# HABILITATS (5 per personatge)
#
#   'id'    -> identificador (no el canviïs un cop publicat)
#   'nom'   -> nom que es veu a la botiga
#   'desc'  -> descripció (màx ~48 caràcters perquè càpiga)
#   'costs' -> preu de cada nivell (el nombre d'elements = nivell màxim)
#
# Per saber el nivell d'una habilitat dins el joc:
#   ability_level('Pikachu', 'triple_salt')   # 0 = no comprada
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
         'desc': 'Fa +1 de mal al boss per nivell', 'costs': [12, 22]},
        {'id': 'enemics_lents', 'nom': 'Enemics lents',
         'desc': 'Els enemics volen més lents', 'costs': [5, 10]},
        {'id': 'foc', 'nom': 'Cometa de foc',
         'desc': 'Desbloqueja atacs. Especial C/K: cometa explosiu', 'costs': [10, 18, 28]},
    ],
}

# Personatge que s'està fent servir (per a get_player_hitbox, etc.)
ACTIVE = {'nom': 'Pikachu'}


def get_abilities(nom):
    return ABILITIES.get(nom, DEFAULT_ABILITIES)


def ability_level(nom, ab_id):
    return int(SAVE['upgrades'].get(nom, {}).get(ab_id, 0))


def buy_ability(nom, ab):
    """Intenta comprar el següent nivell d'una habilitat. Retorna (ok, missatge)."""

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
# EFECTES DE SO (opcionals: si el fitxer no existeix, no sona)
# Fitxers esperats a assets/: salt, pokeball, hit, atac  (.wav o .ogg)
# ---------------------------------------------------------------

sfx = {}

# Silenci (tecla N)
MUTED = {'on': False}


def apply_volume():
    pygame.mixer.music.set_volume(0.0 if MUTED['on'] else 1.0)


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
# ONES EXPANSIVES (explosions d'atacs)
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
# TEXTOS FLOTANTS (+punts, -mal, COMBO...)
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
# AMBIENT AMB PARALLAX: núvols de dia, estrelles de nit
# Es dibuixa sobre el fons i es mou lleugerament amb el jugador.
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
# TRANSICIONS (fade)
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

        # jump buffering
        self.jump_buffer_until = 0

        self.alive = True
        self.death_music_played = False
        self.death_fx = False                # explosió en morir

        # Vida extra (habilitat de Pikachu) i invulnerabilitat en reviure
        self.extra_lives = ability_level(ACTIVE['nom'], 'vida_extra')
        self.player_invuln_until = 0

        # Valors que main() actualitza cada frame segons les habilitats
        self.boss_damage = 1
        self.stomp_bounce = 0

        self.collected_pokeballs = 0

        # punts guanyats en aquest nivell (es guarden en completar-lo)
        self.level_points = 0

        # combo de pokeballs
        self.combo = 0
        self.last_pickup_at = 0

        self.start_time = time.time()

        particles.clear()
        popups.clear()
        rings.clear()

        self.platforms = build_platforms(level)

        self.enemy_size = (30, 30)

        # [NOU6] Enemics amb comportaments variats (vegeu ENEMY_AI i move_enemy)
        self.enemies = []
        self.enemy_speeds = []       # només s'usa el signe: cap on mira
        self.enemy_kind = []
        self.enemy_hp = []
        self.enemy_hp_max = []
        self.enemy_base_y = []
        self.enemy_phase = []
        self.enemy_ai = {}           # dades de comportament (clau = id del rect)

        self._spawn_enemies()
        self._spawn_ground_enemy()

        # Atacs del jugador
        self.attacks = []
        self.attack_ready_at = 0
        self.special_ready_at = 0
        self.special_cd_total = 1            # per a la barra de recàrrega

        if self.is_boss:
            self.pokeballs = []
        else:
            self.pokeballs = self.generate_pokeballs(8)

        # valor en punts de cada pokeball (mateix ordre que self.pokeballs)
        self.pokeball_values = [
            pokeball_points_for_level(level) for _ in self.pokeballs
        ]

        self.total_pokeballs = len(self.pokeballs)

        # -------------------------------------------------------
        # BOSS
        # -------------------------------------------------------

        self.boss_hp = BOSS_MAX_HP

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

        # -------------------------------------------------------
        # PLATAFORMES DEL BOSS
        # -------------------------------------------------------

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

    def _add_enemy(self, rect, kind, ai, **extra):
        """Afegeix un enemic a totes les llistes i guarda les seves dades d'IA."""

        hp = ENEMY_HP_BY_KIND[kind]

        direction = random.choice([-1, 1])

        self.enemies.append(rect)
        self.enemy_speeds.append(direction * 3)   # només el signe importa
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
        """Volador sinusoïdal: busca una zona de l'aire lliure de plataformes."""

        amp = ENEMY_AI['sine']['amp']

        rect = None

        for attempt in range(100):

            x = random.randint(150, WIDTH - 150 - w)
            y = random.randint(200, HEIGHT - 230)

            r = pygame.Rect(x, y, w, h)

            # primer exigim espai lliure per a tota l'ona; després, només per a l'enemic
            zone = r.inflate(0, 2 * amp) if attempt < 60 else r

            if zone.collidelist(self.platforms) == -1 and abs(x - 120) > 200:
                rect = r
                break

        if rect is None:
            rect = pygame.Rect(WIDTH // 2, 120, w, h)

        self._add_enemy(rect, kind, 'sine')

    def _spawn_enemies(self):
        """Reparteix els comportaments entre les plataformes del nivell."""

        if self.is_boss:
            return

        for i, p in enumerate(self.platforms[1:]):

            ai = ENEMY_AI_CYCLE[i % len(ENEMY_AI_CYCLE)]

            kind = AI_KIND[ai]

            w, h = enemy_hitbox_size(kind)

            left = max(p.left, 0)
            right = min(p.right, WIDTH)

            # Si la plataforma és massa estreta (o fora de pantalla), vola
            if ai in ('patrol', 'chaser') and right - left < w + 20:
                ai = 'sine'
                kind = AI_KIND[ai]
                w, h = enemy_hitbox_size(kind)

            if ai == 'sine':
                self._spawn_flyer(kind, w, h)
                continue

            # camina per la plataforma (planeja 6 px per sobre) sense néixer a sobre del jugador
            x = random.randint(left, right - w)

            for _ in range(30):
                x = random.randint(left, right - w)
                if abs(x + w // 2 - 120) > 200:
                    break

            rect = pygame.Rect(x, p.top - h - 6, w, h)

            self._add_enemy(rect, kind, ai, bounds=(left, right))

    def _spawn_ground_enemy(self):
        """Llop terrestre: només als nivells GROUND_ENEMY_LEVELS, i només un."""

        if self.level not in GROUND_ENEMY_LEVELS or not ground_frames[0]:
            return

        w, h = ground_info['size']

        # Plataformes del terra (la seva part de dalt és el terra)
        floor = [p for p in self.platforms if p.top == HEIGHT - 50]

        if not floor:
            return

        def visible(p):
            return min(p.right, WIDTH) - max(p.left, 0)

        # Agafa el tros de terra més ample (així té espai per caminar)
        best = max(visible(p) for p in floor)

        plat = random.choice([p for p in floor if visible(p) == best])

        left = max(plat.left, 0)
        right = min(plat.right, WIDTH)

        if right - left < w + 10:
            return

        # Si es pot, no neix a sobre del jugador
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

                # [NOU3] flota sempre 12 px per sobre de la plataforma,
                # sigui quina sigui la mida de la bola
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

    # ===========================================================
    # RESET
    # ===========================================================

    def reset(self, level=None, keep_boss_hp=False):

        if level is None:
            level = self.level

        old_boss_hp = self.boss_hp
        old_boss_phase = getattr(self, 'boss_phase', 1)
        old_platforms_deteriorated = getattr(
            self, 'boss_platforms_deteriorated', False
        )

        self.__init__(level)

        if keep_boss_hp and level == BOSS_LEVEL:

            self.boss_hp = old_boss_hp
            self.boss_hp = max(0, min(self.boss_hp, BOSS_MAX_HP))

            # la barra fantasma comença igual que la vida
            self.boss_hp_ghost = float(self.boss_hp)

            if old_boss_phase == 2 or self.boss_hp <= BOSS_PHASE2_HP:
                self.boss_phase = 2
            else:
                self.boss_phase = 1

            if (
                old_platforms_deteriorated
                or self.boss_hp <= BOSS_PLATFORM_DAMAGE_HP
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
pokeball_texture = None          # ultraball (2 punts)
pokeball_small_texture = None    # pokeball petita (1 punt)
enemy_texture1 = None
enemy_texture2 = None
enemy_chaser_texture = None      # [NOU6] abella vermella (perseguidora)

# [NOU4] fotogrames del llop: 0 = mira a la dreta, 1 = mira a l'esquerra
ground_frames = {0: [], 1: []}
ground_bob = []                   # desplaçament vertical de cada fotograma
ground_info = {'size': None}      # mida de la hitbox

boss_frames = []

shot_texture = None
logo_texture = None


def remove_logo_background(surf):

    w, h = surf.get_size()

    stack = []
    visited = set()

    for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))

    for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))

    def es_fons(color):
        r, g, b, a = color
        if a == 0:
            return True
        blau_clar = (b >= r + 12 and g >= r - 5 and b > 145)
        blanc_fons = (r > 238 and g > 238 and b > 238)
        return blau_clar or blanc_fons

    while stack:

        x, y = stack.pop()

        if x < 0 or y < 0 or x >= w or y >= h or (x, y) in visited:
            continue

        visited.add((x, y))

        if not es_fons(surf.get_at((x, y))):
            continue

        surf.set_at((x, y), (255, 255, 255, 0))

        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    return surf


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
    """Retalla amb un rectangle comú, escala amb el mateix factor i deixa'l mirant a la DRETA."""

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

    # Mateixa escala per a tots els fotogrames (surt de la imatge de repòs)
    k = GROUND_ENEMY_HEIGHT / base_bb.height

    # Hitbox = mida de la imatge de repòs escalada
    ground_info['size'] = (
        max(1, int(base_bb.width * k)), max(1, int(base_bb.height * k))
    )

    # Fotogrames propis (terra_corre1..4.png), opcionals
    raw_frames = []

    for n in range(1, 5):
        ruta = f'assets/terra_corre{n}.png'
        if os.path.exists(ruta):
            raw_frames.append(pygame.image.load(ruta).convert_alpha())

    if raw_frames:

        # Tots els fotogrames es retallen amb el MATEIX rectangle (la unió),
        # així no canvien de mida ni "salten" quan es mouen les potes.
        crop = base_bb.copy()

        for img in raw_frames:
            bb = img.get_bounding_rect()
            if bb.width > 0 and bb.height > 0:
                crop.union_ip(bb)

        frames = [_scale_ground(img, crop, k) for img in raw_frames]

        # Petit rebot als fotogrames "de pas" (els parells), com un trot
        bob = [(-1 if i % 2 else 0) for i in range(len(frames))]

    else:

        # Sense fotogrames: caminar simulat amb l'única imatge
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

    CHARACTERS.append(make_pikachu())

    if os.path.exists('assets/jolteon.png'):
        CHARACTERS.append(make_eevee_evolution('Jolteon', 'assets/jolteon.png'))

    if os.path.exists('assets/flareon.png'):
        CHARACTERS.append(make_eevee_evolution('Flareon', 'assets/flareon.png'))

    platform_texture = pygame.image.load('assets/plataforma1.png')
    float_platform_texture = pygame.image.load('assets/plataforma1.png')

    enemy_texture1 = pygame.image.load('assets/volador1.png')

    # [NOU6] Perseguidora: la mateixa abella tenyida de vermell
    enemy_chaser_texture = enemy_texture1.copy()
    enemy_chaser_texture.fill((90, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
    enemy_chaser_texture.fill((255, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
    enemy_texture2 = pygame.image.load('assets/volador2.png')

    load_ground_enemy()

    # Les dues boles es retallen i s'escalen a POKEBALL_SIZE, que és
    # també la mida de la hitbox: així la imatge i la hitbox coincideixen.
    ultra_raw = pygame.image.load('assets/ultraball2.png').convert_alpha()

    ub = ultra_raw.get_bounding_rect()

    if ub.width > 0 and ub.height > 0:
        ultra_raw = ultra_raw.subsurface(ub).copy()

    pokeball_texture = pygame.transform.smoothscale(
        ultra_raw, (POKEBALL_SIZE, POKEBALL_SIZE)
    )

    # Pokeball petita: el PNG té la bola a un racó i la resta
    # transparent, així que es retalla i s'escala a la mida de l'ultraball.
    if os.path.exists('assets/pokeball.png'):

        raw = pygame.image.load('assets/pokeball.png').convert_alpha()

        bbox = raw.get_bounding_rect()

        if bbox.width > 0 and bbox.height > 0:
            raw = raw.subsurface(bbox).copy()

        pokeball_small_texture = pygame.transform.smoothscale(
            raw, (POKEBALL_SIZE, POKEBALL_SIZE)
        )

    else:

        # Si falta el fitxer, fem servir l'ultraball
        pokeball_small_texture = pokeball_texture

    load_boss_frames()

    shot_texture = pygame.Surface((28, 28), pygame.SRCALPHA)

    pygame.draw.circle(shot_texture, (70, 10, 120), (14, 14), 14)
    pygame.draw.circle(shot_texture, (170, 80, 230), (14, 14), 10)
    pygame.draw.circle(shot_texture, (255, 255, 255), (14, 14), 5)

    if os.path.exists('assets/logo_transparent.png'):

        # Logo ja amb el fons tret (recomanat per a la versió web: no cal processar-lo)
        logo_raw = pygame.image.load('assets/logo_transparent.png').convert_alpha()

    else:

        logo_raw = pygame.image.load('assets/logo.png').convert_alpha()

        # Es redueix ABANS de treure el fons: el recorregut píxel a píxel és
        # molt lent amb imatges grans (sobretot al navegador).
        biggest = max(logo_raw.get_size())

        if biggest > 400:
            k = 400 / biggest
            logo_raw = pygame.transform.smoothscale(
                logo_raw,
                (max(1, int(logo_raw.get_width() * k)),
                 max(1, int(logo_raw.get_height() * k)))
            )

        logo_raw = remove_logo_background(logo_raw)

    bbox = logo_raw.get_bounding_rect()

    if bbox.width > 0 and bbox.height > 0:
        logo_raw = logo_raw.subsurface(bbox).copy()

    logo_texture = pygame.transform.smoothscale(logo_raw, (280, 280))


load_textures()
load_sfx()
load_save()
load_records()


def enemy_hitbox_size(kind):
    """[NOU3] Mida de la hitbox: el volador gran (kind 1) fa la mida de la seva imatge."""

    if kind == 1:
        return enemy_texture2.get_size()

    return (30, 30)


def get_player_hitbox(x, y, ducking):

    if ducking:
        return pygame.Rect(x + 10, y + 10, 20, 10)

    # Cos àgil: la hitbox s'encongeix per dalt i pels costats,
    # però els peus es queden al mateix lloc (si no, el jugador
    # deixaria de detectar el terra).
    s = ability_level(ACTIVE['nom'], 'cos_agil') * 2

    return pygame.Rect(x + 5 + s, y + 5 + 2 * s, 30 - 2 * s, 30 - 2 * s)


def try_revive(gs, now):
    """Vida extra: si ha mort i li queden vides, reviu amb invulnerabilitat."""

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

    # Més fosc perquè es noti bé que no està disponible
    g.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)

    return g


def get_face(index, size, gray=False):
    """Icona quadrada amb la cara d'un personatge (en color o en gris amb una X)."""

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
    """Fila de cares: color = disponible, gris + X = ja ha mort amb ell."""

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
    """Els atacs es desbloquegen en comprar el nivell 1 de l'especial."""

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
    """
    Atac bàsic (X / J). Cada personatge té el seu:
      Pikachu -> espurna elèctrica en ziga-zaga
      Jolteon -> agulla ràpida i fina
      Flareon -> brasa ardent amb cua de flama
    """

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
    """
    Atac especial (C / K). Retorna el cooldown en ms, o 0 si el
    personatge encara no ha comprat l'habilitat.
      Pikachu -> llamp llarg que toca tot el que té al davant
      Jolteon -> ona de plasma (anell) que travessa els enemics
      Flareon -> cometa de foc que explota amb una ona expansiva
    """

    sid = SPECIAL_BY_CHAR.get(nom)

    if not sid:
        return 0

    lvl = ability_level(nom, sid)

    if lvl <= 0:
        return 0

    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    color = ATTACK_COLORS.get(nom, WHITE)

    # Pikachu: llamp molt llarg (220 / 280 / 340 px).
    if sid == 'cua':

        reach = 220 + 60 * (lvl - 1)

        _add_attack(
            gs, 'bolt', px + d * (10 + reach // 2), py, d, 0, 0, 16, color,
            dmg=lvl + 1, pierce=True, follow=True, w=reach, h=54
        )

        return 800 - 100 * (lvl - 1)

    # Jolteon: anell elèctric alt que travessa tots els enemics.
    if sid == 'plasma':

        _add_attack(
            gs, 'ring', px + d * 24, py, d, 0, 14 + lvl, 70, color,
            dmg=1 + (lvl >= 2) + (lvl >= 3), pierce=True, w=34, h=72
        )

        return 700 - 100 * (lvl - 1)

    # Flareon: cometa de foc que explota i fa mal als enemics del voltant.
    if sid == 'foc':

        _add_attack(
            gs, 'fire', px + d * 24, py, d, 26 + 4 * lvl, 9, 80, color,
            dmg=2 if lvl == 1 else 3,
            splash=(0, 0, 70, 110)[lvl]
        )

        return 900 - 100 * (lvl - 1)

    return 0


def move_enemy(gs, i, enemy, player_hitbox, slow, now):
    """Mou un enemic segons el seu comportament (patrol / chaser / ground_chaser / sine)."""

    d = gs.enemy_ai.get(id(enemy))

    if d is None:
        return

    ai = d['ai']

    cfg = ENEMY_AI[ai]

    reduce = min(slow, 2)               # habilitat Enemics lents (Flareon)

    # ------------------------------------------------------------
    # Volador sinusoïdal: rebota amb els costats de la pantalla i de les plataformes
    # ------------------------------------------------------------
    if ai == 'sine':

        speed = max(1.0, cfg['speed'] - reduce)

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

    # ------------------------------------------------------------
    # Caminadors: només dins els límits de la seva plataforma
    # ------------------------------------------------------------
    else:

        left, right = d['bounds']

        speed = cfg['speed']

        chasing = False

        dx = player_hitbox.centerx - enemy.centerx

        if ai in ('chaser', 'ground_chaser'):

            near_y = abs(player_hitbox.bottom - enemy.bottom) <= cfg['y_range']

            if abs(dx) <= cfg['range'] and near_y:
                chasing = True

        if chasing:
            speed = cfg['chase']
            d['dir'] = 1 if dx > 0 else -1

        if chasing and abs(dx) < 6:
            move = 0.0                      # ja és sota el jugador: no tremola
        else:
            move = max(1.0, speed - reduce)

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

            # petit balanceig vertical (només cap amunt, mai dins la plataforma)
            enemy.y = d['base_y'] - int((1 + math.sin(now / 350 + d['phase'])) * 3)

        # avís "!" quan comença a perseguir
        if chasing and not d['alert']:
            add_popup(enemy.centerx, enemy.top - 20, '!', (255, 70, 70), 28)

        d['alert'] = chasing

    gs.enemy_speeds[i] = d['dir'] * 3       # cap on mira


def hit_enemy(gs, i, dmg, color):
    """Resta vida a l'enemic i, si arriba a 0, l'elimina."""

    e = gs.enemies[i]

    shown = min(dmg, max(gs.enemy_hp[i], 0))

    gs.enemy_hp[i] -= dmg

    spawn_particles(
        e.centerx, e.centery, color, 8, speed=3, life=300, size=4, gravity=0.1
    )

    # número de mal
    add_popup(e.centerx, e.top - 6, f'-{shown}', (255, 230, 120), 20)

    if gs.enemy_hp[i] <= 0:

        spawn_particles(
            e.centerx, e.centery, WHITE, 16, speed=4, life=450, size=5,
            gravity=0.1
        )
        play_sfx('hit')

        gs.enemy_ai.pop(id(e), None)

        del gs.enemies[i]
        del gs.enemy_speeds[i]
        del gs.enemy_hp[i]
        del gs.enemy_hp_max[i]
        del gs.enemy_kind[i]
        del gs.enemy_base_y[i]
        del gs.enemy_phase[i]


def damage_boss(gs, now):
    """Mal al boss per atac (mateix mal que trepitjar-lo)."""

    dmg = getattr(gs, 'boss_damage', 1)

    gs.boss_hp -= dmg
    gs.boss_invuln_until = now + 1500
    gs.boss_flash_until = now + 250

    spawn_particles(
        gs.boss_rect.centerx, gs.boss_rect.centery,
        (200, 90, 255), 22, speed=6, life=600, size=6, gravity=0.18
    )
    add_popup(gs.boss_rect.centerx, gs.boss_rect.top - 10, f'-{dmg}', WHITE, 34)
    play_sfx('hit')

    if gs.boss_hp <= 0:
        gs.boss_dead = True
    elif gs.boss_phase == 1 and gs.boss_hp <= BOSS_PHASE2_HP:
        _enter_phase2(gs, now)


def update_attacks(gs, now):

    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    for a in gs.attacks[:]:

        r = a['rect']

        if a['follow']:
            # El llamp es queda enganxat al jugador
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

        # ---------------- Efectes visuals per tipus ----------------
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

        # ---------------- Enemics ----------------
        consumed = False

        for i in range(len(gs.enemies) - 1, -1, -1):

            e = gs.enemies[i]

            if id(e) in a['hit'] or not r.colliderect(e):
                continue

            a['hit'].add(id(e))

            hit_id = id(e)
            ex, ey = e.centerx, e.centery

            hit_enemy(gs, i, a['dmg'], a['color'])

            if a['splash']:

                spawn_particles(
                    ex, ey, a['color'], 24, speed=5, life=450, size=6,
                    gravity=0.05
                )

                # ona expansiva
                spawn_ring(ex, ey, a['color'], a['splash'])

                for j in range(len(gs.enemies) - 1, -1, -1):
                    e2 = gs.enemies[j]
                    if id(e2) == hit_id:
                        continue
                    if math.hypot(e2.centerx - ex, e2.centery - ey) <= a['splash']:
                        hit_enemy(gs, j, a['dmg'], a['color'])

                consumed = True
                break

            if not a['pierce']:
                consumed = True
                break

        if consumed:
            gs.attacks.remove(a)
            continue

        # ---------------- Boss ----------------
        if gs.is_boss and 'boss' not in a['hit'] and r.colliderect(gs.boss_rect):

            a['hit'].add('boss')

            if now >= gs.boss_invuln_until:
                damage_boss(gs, now)

            if kind == 'fire':
                spawn_ring(r.centerx, r.centery, a['color'], 80)

            # el llamp es manté uns frames, la resta es gasten
            if not a['follow']:
                gs.attacks.remove(a)


def _zigzag(x0, x1, cy, amp, n):
    """Punts d'una línia en ziga-zaga (per als llamps)."""

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

        # ---- Pikachu: llamp llarg amb brillantor i ramificació ----
        if kind == 'bolt':

            x0, x1 = (r.left, r.right) if d > 0 else (r.right, r.left)

            n = max(6, r.width // 20)

            main = _zigzag(x0, x1, cy, r.height // 2 - 4, n)

            pygame.draw.lines(screen, (190, 140, 0), False, main, 11)
            pygame.draw.lines(screen, col, False, main, 6)
            pygame.draw.lines(screen, WHITE, False, main, 2)

            branch = _zigzag(x0, x1, cy, 14, n)

            pygame.draw.lines(screen, col, False, branch, 2)

        # ---- Pikachu: espurna en ziga-zaga ----
        elif kind == 'spark':

            pts = []

            for k in range(5):
                x = cx + d * (-13 + k * 6.5)
                y = cy if k in (0, 4) else cy + (6 if k % 2 else -6) + random.randint(-2, 2)
                pts.append((x, y))

            pygame.draw.lines(screen, col, False, pts, 5)
            pygame.draw.lines(screen, WHITE, False, pts, 2)

        # ---- Jolteon: agulla fina amb rastre ----
        elif kind == 'needle':

            tip = (cx + d * 17, cy)
            t1 = (cx - d * 14, cy - 4)
            t2 = (cx - d * 14, cy + 4)

            pygame.draw.line(
                screen, (200, 230, 255), (cx - d * 14, cy), (cx - d * 32, cy), 1
            )
            pygame.draw.polygon(screen, col, [tip, t1, t2])
            pygame.draw.line(screen, WHITE, (cx - d * 14, cy), tip, 2)

        # ---- Jolteon: anell elèctric alt amb punts que giren ----
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

        # ---- Flareon: brasa amb cua de flama ----
        elif kind == 'ember':

            fl = random.randint(-2, 2)

            pygame.draw.polygon(
                screen, (230, 80, 10),
                [(cx - d * 24, cy + fl), (cx - d * 2, cy - 10), (cx - d * 2, cy + 10)]
            )
            pygame.draw.circle(screen, (200, 50, 10), (cx, cy), 11 + fl)
            pygame.draw.circle(screen, col, (cx, cy), 8)
            pygame.draw.circle(screen, (255, 230, 120), (cx, cy), 4)

        # ---- Flareon: cometa de foc ----
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

    gs.boss_pending = None
    gs.boss_windup_until = 0
    gs.boss_last_attack = None

    gs.boss_meteors = []
    gs.boss_waves = []

    gs.boss_static_frame = 0

    gs.boss_platform_event = "active"
    gs.boss_platform_event_until = 0
    gs.boss_platform_roar_until = 0
    gs.boss_edge_choice_done = False
    gs.boss_platform_pre_roar = False

    # barra fantasma i flaix de cop
    gs.boss_hp_ghost = float(gs.boss_hp)
    gs.boss_flash_until = 0


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


def _choose_attack(gs):

    if gs.boss_phase == 1:
        pool = {'orb': 3, 'fan': 2, 'meteors': 1, 'wave': 2}
    else:
        pool = {'orb': 1, 'fan': 2, 'meteors': 2, 'wave': 2, 'homing': 2}

    pool.pop(gs.boss_last_attack, None)

    names = list(pool)

    return random.choices(names, weights=[pool[n] for n in names])[0]


# Quan es reprèn de la pausa, desplaça tots els temporitzadors
_BOSS_TIMERS = (
    'boss_next_action', 'boss_invuln_until', 'boss_next_shot',
    'boss_phase_until', 'boss_shake_until', 'boss_windup_until',
    'boss_platform_event_until', 'boss_platform_roar_until',
    'boss_flash_until',
    'player_invuln_until', 'attack_ready_at', 'special_ready_at',
    'last_pickup_at'
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

        # MATEIX GRUIX
        new_height = platform.height

        platform.width = new_width
        platform.height = new_height

        platform.centerx = old_centerx
        platform.bottom = old_bottom

        gs.boss_platform_damaged_rects.append(platform.copy())

        # Trossos visuals
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

    # 2-3 segons quiet abans del crit
    gs.boss_platform_event_until = now + random.randint(
        BOSS_PLATFORM_PRE_ROAR_MIN,
        BOSS_PLATFORM_PRE_ROAR_MAX
    )

    gs.boss_platform_roar_until = 0
    gs.boss_static_frame = 0


def update_boss_platform_attack(gs, now):

    if not gs.is_boss:
        return

    # -----------------------------------------------------------
    # PREPARACIÓ ABANS DEL CRIT
    # -----------------------------------------------------------

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

    # -----------------------------------------------------------
    # ATAC ESPECIAL
    # -----------------------------------------------------------

    elif gs.boss_platform_event == "special_attack":

        hide_boss_platforms(gs)

        gs.boss_walking = False
        gs.boss_static_frame = 0

        if now >= gs.boss_platform_event_until:

            gs.boss_platform_event = "return_warning"
            gs.boss_platform_event_until = now + BOSS_PLATFORM_RETURN_WARNING

            gs.boss_walking = False

            hide_boss_platforms(gs)

    # -----------------------------------------------------------
    # PARPELLEIG DE RETORN
    # -----------------------------------------------------------

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
# FASE 2
# ===============================================================

def _enter_phase2(gs, now):

    gs.boss_phase = 2

    gs.boss_shots.clear()
    gs.boss_meteors.clear()
    gs.boss_waves.clear()

    # Primer crit
    gs.boss_phase_until = now + BOSS_PHASE2_ROAR_TIME
    gs.boss_shake_until = now + BOSS_PHASE2_ROAR_TIME

    # Boss quiet
    gs.boss_walking = False
    gs.boss_static_frame = 0
    gs.boss_pending = None

    gs.boss_next_shot = now + BOSS_PHASE2_ROAR_TIME + 800

    gs.boss_walk_time = 1100
    gs.boss_stop_time = 250


# ===============================================================
# ATACS DEL BOSS
# ===============================================================

def _launch_attack(gs, kind, rage, now):

    fase2 = (gs.boss_phase == 2)

    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    ox = gs.boss_rect.centerx
    oy = gs.boss_rect.top + 70

    # -----------------------------------------------------------
    # ORB
    # -----------------------------------------------------------

    if kind == 'orb':

        direction = -1 if px < gs.boss_rect.centerx else 1

        sx = gs.boss_rect.left - 28 if direction == -1 else gs.boss_rect.right

        vx = direction * (5 + rage * 0.5 + (1.5 if fase2 else 0))

        alçades = [HEIGHT - 50 - 26, HEIGHT - 50 - 110]

        if not fase2:
            alçades = [random.choice(alçades)]

        for y in alçades:
            _new_shot(gs, sx, y, vx, 0)

    # -----------------------------------------------------------
    # FAN DE BOLES
    # -----------------------------------------------------------

    elif kind == 'fan':

        # FASE 1 = 3 boles, FASE 2 = 6 boles
        n = 6 if fase2 else 3

        # MÉS SEPARADES EN FASE 2
        spread = 0.48 if fase2 else 0.28

        speed = 5 + rage * 0.3 + (1 if fase2 else 0)

        base = math.atan2(py - oy, px - ox)

        for i in range(n):
            ang = base + (i - (n - 1) / 2) * spread
            _new_shot(
                gs,
                ox - 14,
                oy - 14,
                math.cos(ang) * speed,
                math.sin(ang) * speed
            )

    # -----------------------------------------------------------
    # HOMING
    # -----------------------------------------------------------

    elif kind == 'homing':

        speed = 3.8 + rage * 0.1

        dx = px - ox
        dy = py - oy

        d = math.hypot(dx, dy) or 1

        _new_shot(
            gs,
            ox - 14,
            oy - 14,
            dx / d * speed,
            dy / d * speed,
            homing_until=now + 1800,
            speed=speed
        )

    # -----------------------------------------------------------
    # METEORS
    # -----------------------------------------------------------

    elif kind == 'meteors':

        n = 7 if fase2 else 4
        warn = 650 if fase2 else 900
        vy = 12 if fase2 else 9

        for i in range(n):

            x = px - 14 if i == 0 else random.randint(40, WIDTH - 70)

            gs.boss_meteors.append({
                'x': x,
                'y': -40.0,
                'vy': vy,
                'falling': False,
                'warn_until': now + warn + i * 120,
                'rect': pygame.Rect(int(x), -40, 28, 28)
            })

    # -----------------------------------------------------------
    # WAVE
    # -----------------------------------------------------------

    elif kind == 'wave':

        gs.boss_shake_until = now + 350

        speed = 8 if fase2 else 6

        wy = HEIGHT - 50 - 30

        direccions = (
            [-1, 1] if fase2
            else [-1 if px < gs.boss_rect.centerx else 1]
        )

        for d in direccions:

            wx = gs.boss_rect.left - 40 if d == -1 else gs.boss_rect.right

            gs.boss_waves.append({
                'x': float(wx),
                'vx': d * speed,
                'rect': pygame.Rect(int(wx), wy, 40, 30)
            })


# ===============================================================
# UPDATE BOSS
# ===============================================================

def update_boss(gs, player_hitbox):

    now = pygame.time.get_ticks()

    update_boss_platform_debris(gs)

    rage = BOSS_MAX_HP - gs.boss_hp

    fase2 = (gs.boss_phase == 2)

    in_roar = (now < gs.boss_phase_until)

    charging = (gs.boss_pending is not None)

    # -----------------------------------------------------------
    # DETERIORAMENT AL 75%
    # -----------------------------------------------------------

    if (
        gs.boss_phase == 1
        and not gs.boss_platforms_deteriorated
        and gs.boss_hp <= BOSS_PLATFORM_DAMAGE_HP
    ):
        deteriorate_boss_platforms(gs)

    # -----------------------------------------------------------
    # ATAC ESPECIAL DE PLATAFORMES
    # -----------------------------------------------------------

    update_boss_platform_attack(gs, now)

    platform_special = gs.boss_platform_event in (
        "pre_roar", "special_attack", "return_warning"
    )

    px = gs.player_x + PLAYER_SIZE[0] // 2
    py = gs.player_y + PLAYER_SIZE[1] // 2

    # -----------------------------------------------------------
    # DESPRÉS DEL PRIMER CRIT, TORNA A MOURE'S
    # -----------------------------------------------------------

    if (
        gs.boss_phase == 2
        and gs.boss_phase_until > 0
        and now >= gs.boss_phase_until
        and not platform_special
    ):
        gs.boss_walking = True

    # -----------------------------------------------------------
    # MOVIMENT
    # -----------------------------------------------------------

    if not platform_special:

        if now >= gs.boss_next_action:

            gs.boss_walking = not gs.boss_walking

            gs.boss_next_action = now + (
                gs.boss_walk_time if gs.boss_walking else gs.boss_stop_time
            )

        if gs.boss_walking and not in_roar and not charging:

            speed = gs.boss_speed + rage * 0.15

            if fase2:
                speed *= 1.6

            gs.boss_x += gs.boss_dir * speed

    # -----------------------------------------------------------
    # PUNTS
    # -----------------------------------------------------------

    at_left = (gs.boss_x <= 20)
    at_right = (gs.boss_x >= WIDTH - 20 - gs.boss_w)

    if at_left:
        gs.boss_x = 20
    elif at_right:
        gs.boss_x = WIDTH - 20 - gs.boss_w

    # -----------------------------------------------------------
    # QUAN S'ALLUNYA D'UNA PUNTA
    # -----------------------------------------------------------

    if not at_left and not at_right:
        gs.boss_edge_choice_done = False

    # -----------------------------------------------------------
    # FASE 2: RANDOM 1 / 2 / 3
    # -----------------------------------------------------------

    if (
        fase2
        and not platform_special
        and (at_left or at_right)
        and not gs.boss_edge_choice_done
    ):

        gs.boss_edge_choice_done = True

        eleccio = random.randint(1, 3)

        if eleccio == 1:
            start_boss_platform_attack(gs, now)
        else:
            gs.boss_walking = True
            gs.boss_static_frame = 0
            gs.boss_dir = 1 if at_left else -1

    # -----------------------------------------------------------
    # FRAME FIX
    # -----------------------------------------------------------

    if gs.boss_walking:
        gs.boss_static_frame = 0

    gs.boss_rect.x = int(gs.boss_x)

    # -----------------------------------------------------------
    # ATACS
    # -----------------------------------------------------------

    if not in_roar:

        if gs.boss_pending is None and now >= gs.boss_next_shot:

            gs.boss_pending = _choose_attack(gs)
            gs.boss_last_attack = gs.boss_pending

            gs.boss_windup_until = now + (300 if fase2 else 500)

        elif gs.boss_pending is not None and now >= gs.boss_windup_until:

            _launch_attack(gs, gs.boss_pending, rage, now)

            gs.boss_pending = None

            # FASE 2: UNA MICA MÉS SEPARAT EN EL TEMPS
            if fase2:
                cooldown = max(1000, 1700 - rage * 100)
            else:
                cooldown = max(1100, 2200 - rage * 250)

            gs.boss_next_shot = now + cooldown

    # -----------------------------------------------------------
    # ESFERES
    # -----------------------------------------------------------

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

        # rastre lluminós darrere dels projectils
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

    # -----------------------------------------------------------
    # METEORS
    # -----------------------------------------------------------

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

    # -----------------------------------------------------------
    # ONES
    # -----------------------------------------------------------

    for w in gs.boss_waves[:]:

        w['x'] += w['vx']

        w['rect'].x = int(w['x'])

        if w['rect'].right < -50 or w['rect'].left > WIDTH + 50:
            gs.boss_waves.remove(w)
        elif player_hitbox.colliderect(w['rect']):
            gs.alive = False

    # -----------------------------------------------------------
    # COL·LISIÓ AMB EL BOSS
    # -----------------------------------------------------------

    if player_hitbox.colliderect(gs.boss_rect) and now >= gs.boss_invuln_until:

        if (
            gs.velocity_y > 0
            and player_hitbox.bottom <= gs.boss_rect.top + 35
        ):

            dmg = getattr(gs, 'boss_damage', 1)

            gs.boss_hp -= dmg

            gs.boss_invuln_until = now + 1500

            # flaix blanc, partícules, número de mal i so
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
            elif gs.boss_phase == 1 and gs.boss_hp <= BOSS_PHASE2_HP:
                _enter_phase2(gs, now)

        else:
            gs.alive = False


# ===============================================================
# DIBUIX BOSS
# ===============================================================

def _boss_tinted(idx, d, img):

    key = (idx, d)

    if key not in _boss_tint_cache:
        t = img.copy()
        t.fill((70, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        _boss_tint_cache[key] = t

    return _boss_tint_cache[key]


def draw_boss(gs):

    now = pygame.time.get_ticks()

    # -----------------------------------------------------------
    # METEORS
    # -----------------------------------------------------------

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

    # -----------------------------------------------------------
    # ONES
    # -----------------------------------------------------------

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

    # -----------------------------------------------------------
    # ESFERES
    # -----------------------------------------------------------

    for shot in gs.boss_shots:

        screen.blit(shot_texture, shot['rect'])

        if shot['homing_until'] > 0:
            pygame.draw.circle(
                screen, (255, 60, 60), shot['rect'].center, 18, 3
            )

    # -----------------------------------------------------------
    # BOSS
    # -----------------------------------------------------------

    in_roar = (now < gs.boss_phase_until)

    charging = (gs.boss_pending is not None)

    # -----------------------------------------------------------
    # ANIMACIÓ
    # -----------------------------------------------------------

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

    # ombra del boss
    blit_shadow(gs.boss_rect.centerx, HEIGHT - 50, 230, 18, 100)

    # resplendor vermell en fase 2
    if gs.boss_phase == 2:
        pulse = 0.5 + 0.5 * math.sin(now / 200)
        aura = pygame.Surface((gs.boss_w + 120, gs.boss_h + 60), pygame.SRCALPHA)
        pygame.draw.ellipse(
            aura,
            (255, 60, 20, int(30 + 30 * pulse)),
            aura.get_rect()
        )
        screen.blit(
            aura,
            (gs.boss_rect.centerx - aura.get_width() // 2,
             gs.boss_rect.centery - aura.get_height() // 2)
        )

    # -----------------------------------------------------------
    # DIBUIX
    # -----------------------------------------------------------

    if not (
        now < gs.boss_invuln_until
        and not in_roar
        and (now // 100) % 2 == 0
    ):

        d = 1 if gs.boss_dir > 0 else 0

        img, bb = boss_frames[idx][d]

        if gs.boss_phase == 2:
            img = _boss_tinted(idx, d, img)

        # flaix blanc quan rep un cop
        if now < gs.boss_flash_until:
            img = img.copy()
            img.fill((140, 140, 140), special_flags=pygame.BLEND_RGB_ADD)

        shake = 8 if in_roar else (4 if charging else 0)

        ox = random.randint(-shake, shake) if shake else 0
        oy = random.randint(-shake, shake) if shake else 0

        bx = gs.boss_rect.centerx - img.get_width() // 2 + ox

        by = gs.boss_rect.bottom - bb.bottom + oy

        screen.blit(img, (bx, by))

    # -----------------------------------------------------------
    # ! ATAC
    # -----------------------------------------------------------

    if charging:

        mark = _font(60, True).render('!', True, (255, 60, 60))

        screen.blit(
            mark,
            (gs.boss_rect.centerx - mark.get_width() // 2,
             gs.boss_rect.top - 70)
        )

    # -----------------------------------------------------------
    # CRIT
    # -----------------------------------------------------------

    if now < gs.boss_platform_roar_until:

        roar_text = _font(72, True).render('RUGIT!', True, (255, 50, 50))

        roar_x = WIDTH // 2 - roar_text.get_width() // 2 + random.randint(-5, 5)
        roar_y = 140 + random.randint(-5, 5)

        screen.blit(roar_text, (roar_x, roar_y))


def draw_boss_bar(gs):

    now = pygame.time.get_ticks()

    fase2 = (gs.boss_phase == 2)

    bar_w = 300
    bar_h = 18

    x = WIDTH // 2 - bar_w // 2
    y = 20

    # la barra fantasma baixa suaument cap a la vida real
    gs.boss_hp_ghost = max(float(gs.boss_hp), gs.boss_hp_ghost - 0.03)

    pygame.draw.rect(screen, BLACK, (x - 3, y - 3, bar_w + 6, bar_h + 6))

    pygame.draw.rect(screen, (90, 0, 0), (x, y, bar_w, bar_h))

    ghost = max(0, gs.boss_hp_ghost) / BOSS_MAX_HP

    pygame.draw.rect(
        screen, (255, 225, 190), (x, y, int(bar_w * ghost), bar_h)
    )

    vida = max(0, gs.boss_hp) / BOSS_MAX_HP

    pygame.draw.rect(
        screen,
        (255, 110, 0) if fase2 else (230, 40, 60),
        (x, y, int(bar_w * vida), bar_h)
    )

    pygame.draw.line(
        screen,
        WHITE,
        (x + bar_w // 2, y - 3),
        (x + bar_w // 2, y + bar_h + 3),
        2
    )

    label = _font(24).render(
        'BOSS FINAL - FASE 2' if fase2 else 'BOSS FINAL',
        True,
        (255, 140, 40) if fase2 else WHITE
    )

    screen.blit(label, (WIDTH // 2 - label.get_width() // 2, y + bar_h + 6))

    if now < gs.boss_phase_until:

        txt = _font(72, True).render('ENFURISMAT!', True, (255, 50, 50))

        screen.blit(
            txt,
            (WIDTH // 2 - txt.get_width() // 2 + random.randint(-4, 4),
             190 + random.randint(-4, 4))
        )


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
    """Text del primer botó i si hi ha una partida començada."""

    has_run = PROGRESS['level'] is not None or bool(used_characters)

    if not has_run:
        return 'JUGAR', False

    lvl = resume_level()

    where = 'BOSS' if lvl == BOSS_LEVEL else f'NIVELL {lvl}'

    return f'CONTINUAR ({where})', True


def return_to_menu(gs, used_characters):
    """
    Torna al menú. Si encara queden personatges vius es manté el progrés
    (nivell i personatges morts); si han mort tots, es comença de zero.
    """

    if len(used_characters) >= len(CHARACTERS):
        used_characters.clear()
        reset_progress()

    gs.reset(resume_level())

    gs.start_time = time.time()


def show_start_menu(play_label='JUGAR', has_run=False):

    screen.blit(
        pygame.transform.scale(pygame.image.load('assets/menu.png'), (WIDTH, HEIGHT)),
        (0, 0)
    )

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 35))
    screen.blit(overlay, (0, 0))

    if logo_texture:
        logo_rect = logo_texture.get_rect()
        logo_rect.centerx = WIDTH // 2
        logo_rect.top = 25
        screen.blit(logo_texture, logo_rect)

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

    # [NOU5] avís per començar de zero
    if has_run:
        rh = _font(20, True).render('R = començar una partida nova', True, YELLOW)
        screen.blit(rh, (WIDTH // 2 - rh.get_width() // 2, HEIGHT - 52))

    # punts guanyats fins ara
    pts = _font(26, True).render(f'Punts: {SAVE["points"]}', True, GOLD)

    screen.blit(pts, (WIDTH - pts.get_width() - 20, 20))

    # indicador de silenci
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
# BOTIGA D'HABILITATS (5 habilitats per personatge)
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

    # ---------------- Personatges ----------------

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

    # ---------------- Habilitats ----------------

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

        # Nivell (punts plens / buits)
        for k in range(max_level):

            cx = row_x + row_w - 290 + k * 30
            cy = y + 20

            pygame.draw.circle(
                screen,
                GOLD if k < level else (70, 70, 70),
                (cx, cy), 10
            )

            pygame.draw.circle(screen, WHITE, (cx, cy), 10, 2)

        # Preu / màxim
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

    # ---------------- Missatge i ajuda ----------------

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

    n = len(CHARACTERS)

    card_w = 240
    card_h = 330
    gap = 40

    total = n * card_w + (n - 1) * gap

    start_x = (WIDTH - total) // 2

    card_y = 190

    for i, ch in enumerate(CHARACTERS):

        x = start_x + i * (card_w + gap)

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
        'A/D o fletxes = triar    ENTER = començar    ESC = enrere',
        True,
        WHITE
    )

    screen.blit(help_text, (WIDTH // 2 - help_text.get_width() // 2, HEIGHT - 70))

    pygame.display.flip()


# ===============================================================
# SELECCIÓ DESPRÉS DE MORIR
# ===============================================================

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

    card_w = 250
    card_h = 330
    gap = 30

    total = len(disponibles) * card_w + (len(disponibles) - 1) * gap

    start_x = (WIDTH - total) // 2

    card_y = 190

    now = pygame.time.get_ticks()

    for pos, character_index in enumerate(disponibles):

        ch = CHARACTERS[character_index]

        x = start_x + pos * (card_w + gap)

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
        'A/D o fletxes = triar     ENTER = continuar     ESC = menú',
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
        'M = tornar al menú',
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
            ('Hi ha doble salt', WHITE),
            ('Tocar un enemic de costat = mort', WHITE),
            ('Pokeball petita = 1 punt, Ultraball = 2 punts', WHITE),
            ('Gasta els punts a la BOTIGA del menú', WHITE),
        ],
        font,
        25,
        38
    )

    pygame.display.flip()


def show_victory_screen(time_taken, collected_pokeballs, total_pokeballs,
                        level, points_gained=0, points_total=0,
                        best_time=None, is_record=False):

    screen.fill(BLACK)

    font = _font(50)

    next_text = (
        '1 - Lluitar contra el BOSS'
        if level + 1 == BOSS_LEVEL
        else '1 - Següent Nivell'
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
            ('2 - Tornar al Nivell', WHITE),
            ('ESC - Sortir', WHITE),
        ],
        font,
        HEIGHT // 6,
        62
    )

    pygame.display.flip()


def show_final_screen(time_taken, best_time=None, is_record=False):

    screen.fill(BLACK)

    font = _font(50)

    if best_time is None:
        record_line = ('', WHITE)
    elif is_record:
        record_line = (f'NOU RÈCORD! {best_time:.2f} s', GREEN)
    else:
        record_line = (f'Rècord: {best_time:.2f} s', (200, 200, 200))

    draw_centered_lines(
        [
            ('HAS GUANYAT!', GOLD),
            ('Has derrotat el boss final', WHITE),
            (f'Time: {time_taken:.2f} seconds', WHITE),
            record_line,
            ('2 - Tornar a lluitar contra el boss', WHITE),
            ('ESC - Menu', WHITE),
        ],
        font,
        HEIGHT // 5,
        70
    )

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

        pygame.mixer.music.load(path)

        # en carregar música nova el volum es reinicia: el tornem a aplicar
        apply_volume()

        pygame.mixer.music.play(-1 if loop else 0)

    except pygame.error as e:

        print('Música no disponible:', e)


JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)


# ===============================================================
# MAIN
# ===============================================================

async def main():

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

    # pausa i detecció d'aterratge
    pause_snapshot = None
    pause_started = 0
    prev_on_ground = True

    # botiga
    shop_char = 0
    shop_ability = 0
    shop_msg = ''
    shop_msg_ok = True
    shop_msg_until = 0

    while running:

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

                # [NOU5] R = partida nova (esborra el progrés)
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

                        selected = 0
                        death_selected = 0

                        game_state = 'select'

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

                        game_state = 'menu'

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

                            play_music(music_file('musica1'))

                    if event.key == pygame.K_ESCAPE:

                        game_state = 'menu'

        # =====================================================
        # DEATH SELECT
        # =====================================================

        elif game_state == 'death_select':

            disponibles = [
                i for i in range(len(CHARACTERS)) if i not in used_characters
            ]

            if not disponibles:

                used_characters.clear()
                reset_progress()

                selected = 0
                death_selected = 0

                gs.reset(START_LEVEL)

                gs.start_time = time.time()

                game_state = 'menu'

                play_music(music_file('musica2'))

                continue

            if death_selected not in disponibles:
                death_selected = disponibles[0]

            show_death_character_select(death_selected, used_characters)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

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

                        # Conserva la vida del boss
                        gs.reset(gs.level, keep_boss_hp=True)

                        gs.start_time = time.time()

                        game_state = 'playing'

                        prev_on_ground = True

                        start_fade_in()

                        play_music(music_file('musica1'))

                    if event.key == pygame.K_ESCAPE:

                        selected = 0
                        death_selected = 0

                        return_to_menu(gs, used_characters)

                        game_state = 'menu'

                        play_music(music_file('musica2'))

        # =====================================================
        # CREDITS
        # =====================================================

        elif game_state == 'credits':

            show_credits()

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:

                    game_state = 'menu'

                    gs.start_time = time.time()

        # =====================================================
        # AJUDA
        # =====================================================

        elif game_state == 'ajuda':

            show_A()

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:

                    game_state = 'menu'

                    gs.start_time = time.time()

        # =====================================================
        # FINAL
        # =====================================================

        elif game_state == 'final':

            show_final_screen(final_time, final_best, final_is_record)

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:

                    if event.key == pygame.K_2:

                        gs.reset(BOSS_LEVEL)

                        gs.start_time = time.time()

                        game_state = 'playing'

                        prev_on_ground = True

                        start_fade_in()

                        play_music(music_file('musica1'))

                    if event.key == pygame.K_ESCAPE:

                        used_characters.clear()
                        reset_progress()

                        gs.reset(START_LEVEL)

                        gs.start_time = time.time()

                        game_state = 'menu'

                        play_music(music_file('musica2'))

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

                        # El temps de pausa no compta
                        gs.start_time += dt / 1000
                        shift_boss_timers(gs, dt)

                        pygame.mixer.music.unpause()

                        game_state = 'playing'

                    elif event.key == pygame.K_m:

                        selected = 0
                        death_selected = 0

                        return_to_menu(gs, used_characters)

                        pygame.mixer.music.unpause()

                        game_state = 'menu'

                        play_music(music_file('musica2'))

        # =====================================================
        # JUGANT
        # =====================================================

        elif game_state == 'playing':

            pause_requested = False

            # ---- Valors segons les habilitats del personatge actiu ----
            nom = player_char.nom

            def lv(ab_id, _nom=nom):
                return ability_level(_nom, ab_id)

            speed = PLAYER_SPEED + lv('velocitat')
            max_jumps = 3 if lv('triple_salt') else 2
            jump_str = JUMP_STRENGTH - lv('salt_alt')
            dbl_str = DOUBLE_JUMP_STRENGTH - 1.5 * lv('doble_fort')
            max_fall = MAX_FALL_SPEED - 1.5 * lv('planeig')

            gs.boss_damage = 1 + lv('mal_boss')
            gs.stomp_bounce = 2 * lv('rebot')

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:

                    # Silenci
                    if event.key == pygame.K_n:
                        toggle_mute()

                    # Pausa
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
                            # Jump buffering: recorda el salt
                            gs.jump_buffer_until = current_time + JUMP_BUFFER_MS

                    # Atac bàsic (X / J)
                    if (
                        event.key in ATTACK_KEYS
                        and gs.alive
                        and attacks_unlocked(nom)
                        and current_time >= gs.attack_ready_at
                    ):
                        fire_basic(gs, nom, -1 if direccio == 1 else 1)

                        gs.attack_ready_at = current_time + ATTACK_COOLDOWN_MS

                        play_sfx('atac')

                    # Atac especial (C / K): només si l'has comprat
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

                # Salt variable: si deixes anar la tecla, saltes menys
                if event.type == pygame.KEYUP and event.key in JUMP_KEYS:
                    if gs.velocity_y < -5:
                        gs.velocity_y *= JUMP_CUT_FACTOR

            if pause_requested:

                pause_snapshot = screen.copy()
                pause_started = pygame.time.get_ticks()
                pygame.mixer.music.pause()
                game_state = 'paused'

                continue

            if gs.alive:

                # ------------------------------------------------
                # MOVIMENT
                # ------------------------------------------------

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

                gs.is_ducking = keys[pygame.K_DOWN]

                if keys[pygame.K_a] and gs.player_x > 0:

                    pokemon_state = "camina"
                    direccio = 1

                    gs.player_x -= speed

                if keys[pygame.K_d] and gs.player_x < WIDTH - PLAYER_SIZE[0]:

                    pokemon_state = "camina"
                    direccio = 0

                    gs.player_x += speed

                # ------------------------------------------------
                # GRAVETAT
                # ------------------------------------------------

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

                # pols en aterrar i en córrer
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

                # Jump buffering: salta just en aterrar
                if on_ground and gs.jump_buffer_until > current_time:

                    gs.velocity_y = jump_str
                    gs.jump_count = 1
                    gs.jump_buffer_until = 0

                    play_sfx('salt')

                # ------------------------------------------------
                # CAIGUDA
                # ------------------------------------------------

                if gs.player_y > HEIGHT:
                    gs.alive = False

                player_hitbox = get_player_hitbox(
                    gs.player_x, gs.player_y, gs.is_ducking
                )

                # ------------------------------------------------
                # POKEBALLS (cada una té el seu valor en punts)
                # L'imant fa més gran la zona on les recollim.
                # Combo: pokeballs seguides donen punts extra.
                # ------------------------------------------------

                magnet = player_hitbox.inflate(
                    30 * lv('imant'), 30 * lv('imant')
                )

                for idx in range(len(gs.pokeballs) - 1, -1, -1):

                    pokeball = gs.pokeballs[idx]

                    if magnet.colliderect(pokeball):

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

                        # espurnes i so (daurades = 2 punts, vermelles = 1 punt)
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

                # ------------------------------------------------
                # ENEMICS
                # Cada tipus té el seu comportament; trepitjar-los els mata.
                # Es recorre al revés perquè hit_enemy pot esborrar-ne.
                # ------------------------------------------------

                for i in range(len(gs.enemies) - 1, -1, -1):

                    enemy = gs.enemies[i]

                    # [NOU6] moviment segons el comportament de cada enemic
                    move_enemy(
                        gs, i, enemy, player_hitbox, lv('enemics_lents'), current_time
                    )

                    if player_hitbox.colliderect(enemy):

                        # Trepitjar: caient i amb els peus per la part de dalt de l'enemic
                        if (
                            gs.velocity_y > 0
                            and not on_ground
                            and player_hitbox.bottom <= enemy.top + enemy.height * 0.6
                        ):

                            ex, etop = enemy.centerx, enemy.top

                            hit_enemy(
                                gs, i, ENEMY_STOMP_DAMAGE.get(gs.enemy_kind[i], 99), YELLOW
                            )

                            # efecte d'aixafament
                            spawn_ring(ex, etop, YELLOW, 40, 250)

                            gs.velocity_y = jump_str * 0.8
                            gs.jump_count = 1

                        else:

                            gs.alive = False

                # ------------------------------------------------
                # ATACS DEL JUGADOR
                # (abans del boss: si un atac el mata, es detecta aquest frame)
                # ------------------------------------------------

                update_attacks(gs, pygame.time.get_ticks())

                # ------------------------------------------------
                # BOSS
                # ------------------------------------------------

                if gs.is_boss:

                    if gs.alive:
                        update_boss(gs, player_hitbox)

                    if gs.boss_dead:

                        final_time = time.time() - gs.start_time

                        final_is_record, final_best = submit_record(
                            'boss', final_time
                        )

                        game_state = 'final'

                        play_music(music_file('musica2'))

                # ------------------------------------------------
                # NIVELL COMPLETAT
                # ------------------------------------------------

                if not gs.pokeballs and not gs.is_boss:

                    time_taken = time.time() - gs.start_time

                    # Ara es guarden els punts del nivell
                    points_gained = gs.level_points

                    add_points(points_gained)

                    # [NOU5] recorda l'últim nivell completat
                    PROGRESS['level'] = max(PROGRESS['level'] or 0, gs.level)

                    # rècord de temps del nivell
                    is_record, best_time = submit_record(gs.level, time_taken)

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

                    waiting = True

                    while waiting:

                        await asyncio.sleep(0)

                        for event in pygame.event.get():

                            if event.type == pygame.QUIT:
                                delete_save_on_exit()
                                return

                            if event.type == pygame.KEYDOWN:

                                if event.key == pygame.K_1:

                                    gs.reset(gs.level + 1)

                                    gs.start_time = time.time()

                                    waiting = False

                                    prev_on_ground = True

                                    start_fade_in()

                                    pygame.mixer.music.play()

                                if event.key == pygame.K_2:

                                    gs.reset(gs.level)

                                    gs.start_time = time.time()

                                    waiting = False

                                    prev_on_ground = True

                                    start_fade_in()

                                    pygame.mixer.music.play()

                                if event.key == pygame.K_ESCAPE:

                                    game_state = 'menu'

                                    return_to_menu(gs, used_characters)

                                    play_music(music_file('musica2'))

                                    waiting = False

            # Vida extra: si ha mort i li queden vides, reviu
            try_revive(gs, pygame.time.get_ticks())

            # =====================================================
            # DIBUIX
            # =====================================================

            screen.fill(BLACK)

            if gs.level in LEVEL_BACKGROUNDS:
                imprimir_pantalla_fons(LEVEL_BACKGROUNDS[gs.level])

            # -----------------------------------------------------
            # PLATAFORMES
            # -----------------------------------------------------

            now = pygame.time.get_ticks()

            # núvols / estrelles amb parallax
            draw_ambient(gs.level, now, gs.player_x)

            for platform_index, platform in enumerate(gs.platforms):

                is_upper_boss_platform = gs.is_boss and platform_index > 0

                # Fora durant l'atac especial
                if (
                    is_upper_boss_platform
                    and gs.boss_platform_event == "special_attack"
                ):
                    continue

                # Parpellegen abans de tornar
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

            # -----------------------------------------------------
            # PEDRES
            # -----------------------------------------------------

            draw_boss_platform_debris(gs)

            # -----------------------------------------------------
            # POKEBALLS (textura segons el valor)
            # -----------------------------------------------------

            for pokeball, value in zip(gs.pokeballs, gs.pokeball_values):

                tex = (
                    pokeball_small_texture
                    if value <= POINTS_SIMPLE_POKEBALL
                    else pokeball_texture
                )

                screen.blit(tex, (pokeball.x, pokeball.y))

            # -----------------------------------------------------
            # ENEMICS (amb barreta de vida si ja han rebut algun cop)
            # -----------------------------------------------------

            for i, enemy in enumerate(gs.enemies):

                flip = gs.enemy_speeds[i] < 0

                if gs.enemy_kind[i] == GROUND_ENEMY_KIND:

                    # [NOU4] Llop: animació de caminar, alineat pels peus
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

                    # [NOU3] la barra s'adapta a l'amplada de l'enemic
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

            # -----------------------------------------------------
            # BOSS
            # -----------------------------------------------------

            if gs.is_boss:
                draw_boss(gs)

            # -----------------------------------------------------
            # PERSONATGE
            # -----------------------------------------------------

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

            # ombra del jugador
            draw_player_shadow(
                gs.player_x + PLAYER_SIZE[0] // 2,
                gs.player_y + PLAYER_SIZE[1],
                gs.platforms
            )

            # Parpelleja mentre és invulnerable (després de reviure)
            if not (
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

            # Atacs del jugador
            draw_attacks(gs)

            # partícules i textos flotants (damunt del món, sota el HUD)
            update_particles()
            draw_particles()

            update_rings()
            draw_rings()

            update_popups()
            draw_popups()

            # -----------------------------------------------------
            # HUD
            # -----------------------------------------------------

            font = _font(30)

            time_text = font.render(
                f'Time: {time.time() - gs.start_time:.2f}s', True, WHITE
            )

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

                # punts totals (+ els d'aquest nivell, pendents de guardar)
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

            # cares dels personatges sota el nivell:
            # color = es pot utilitzar, gris amb X = ja ha mort
            draw_character_faces(selected, used_characters, 20, 62)

            # Barra de recàrrega de l'atac bàsic
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

            # Indicador de l'atac especial (només si l'has comprat)
            special_id = SPECIAL_BY_CHAR.get(nom)

            if special_id and lv(special_id) > 0:

                ready = current_time >= gs.special_ready_at

                sp_text = _font(20, True).render(
                    'Especial (C/K): ' + ('LLEST' if ready else '...'),
                    True,
                    GOLD if ready else (170, 170, 170)
                )

                screen.blit(sp_text, (20, 114))

                # barra de recàrrega de l'especial
                special_left = max(0, gs.special_ready_at - current_time)

                draw_cd_bar(
                    20, 138, 130, 6,
                    1 - special_left / max(1, gs.special_cd_total),
                    GOLD if ready else (200, 140, 40)
                )

            # Vides extra que queden
            if gs.extra_lives > 0:

                life_text = _font(20, True).render(
                    f'Vides extra: {gs.extra_lives}', True, (255, 120, 160)
                )

                screen.blit(life_text, (20, 150))

            # Combo actiu
            if (
                gs.combo >= 2
                and gs.last_pickup_at > 0
                and current_time - gs.last_pickup_at <= COMBO_WINDOW_MS
            ):

                combo_text = _font(24, True).render(
                    f'COMBO x{gs.combo}', True, (255, 160, 40)
                )

                screen.blit(combo_text, (20, 176))

            # Silenci
            if MUTED['on']:

                mute_text = _font(20, True).render(
                    'MUT (N)', True, (255, 120, 120)
                )

                screen.blit(mute_text, (20, HEIGHT - 30))

            # -----------------------------------------------------
            # BOSS BAR
            # -----------------------------------------------------

            if gs.is_boss:

                draw_boss_bar(gs)

                if time.time() - gs.start_time < 5:

                    hint = font.render(
                        f'Salta-li al cap {BOSS_MAX_HP} cops! Esquiva els atacs!',
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

                # explosió de partícules una sola vegada
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

                if not gs.death_music_played:

                    play_music(music_file('musica_mort'))

                    gs.death_music_played = True

                disponibles = [
                    i for i in range(len(CHARACTERS)) if i not in used_characters
                ]

                if keys[pygame.K_RETURN]:

                    if disponibles:

                        death_selected = disponibles[0]

                        game_state = 'death_select'

                    else:

                        used_characters.clear()
                        reset_progress()

                        selected = 0
                        death_selected = 0

                        gs.reset(START_LEVEL)

                        gs.start_time = time.time()

                        game_state = 'menu'

                        play_music(music_file('musica2'))

                if keys[pygame.K_ESCAPE]:

                    selected = 0
                    death_selected = 0

                    return_to_menu(gs, used_characters)

                    game_state = 'menu'

                    play_music(music_file('musica2'))

            apply_boss_shake(gs)

            # fade in en començar el nivell
            draw_fade_in()

            pygame.display.flip()

        clock.tick(60)

        # cedeix el control al navegador (obligatori a la versió web)
        await asyncio.sleep(0)

    delete_save_on_exit()
    pygame.quit()


asyncio.run(main())
