import pygame
import random
import time

# Initialize Pygame
pygame.init()
pygame.mixer.music.load('assets/musica2.mp3')
pygame.mixer.music.play()
pygame.mixer.music.play(-1)

AMPLADA = 1024
ALTURA = 720
pantalla = pygame.display.set_mode((AMPLADA, ALTURA))
def imprimir_pantalla_fons(image):
    # Imprimeixo imatge de fons:
    background = pygame.image.load(image).convert()
    pantalla.blit(background, (0, 0))

# Screen setup
WIDTH, HEIGHT = 1024, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pokémon Platformer: Poké Ball Quest")

# Colors
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

# Player properties
PLAYER_SIZE = (40, 40)
PLAYER_SIZE_DUCKING = (40, 40)  # Reduced height when ducking
PLAYER_SPEED = 6
GRAVITY = 0.6
JUMP_STRENGTH = -14
DOUBLE_JUMP_STRENGTH = -12  # Slightly weaker second jump for balance
MAX_FALL_SPEED = 10
MIN_POKEBALL_DISTANCE = 60
pokemon_state = "peu" #peu, ajupit, camina

# Game state class
class GameState:
    def __init__(self, level=1):
        self.level = level
        self.player_x = 100
        self.player_y = HEIGHT - PLAYER_SIZE[1] - 10
        self.velocity_y = 0
        self.jump_count = 0
        self.is_ducking = False
        self.alive = True
        self.collected_pokeballs = 0
        self.start_time = time.time()


        # Platforms for each level imprimir_pantalla_fons('assets/dia.png')
        if self.level == 1:
            self.platforms = [
                pygame.Rect(0, HEIGHT - 50, 2000, 50),  # Groun
            ]

        if self.level == 2:
            self.platforms = [
                pygame.Rect(0, HEIGHT - 50, 2000, 50),  # Ground
                pygame.Rect(350, HEIGHT - 200, 400, 30),

            ]
        if self.level == 3:
            self.platforms = [
                pygame.Rect(0, HEIGHT - 50, 2000, 50),  # Ground
                pygame.Rect(600, HEIGHT - 250, 350, 30),
                pygame.Rect(1400, HEIGHT - 350, 350, 30),
                pygame.Rect(200, HEIGHT - 150, 300, 30),

            ]
        elif self.level == 4:
            self.platforms = [
                pygame.Rect(0, HEIGHT - 50, 2500, 50),  # Ground
                pygame.Rect(150, HEIGHT - 200, 400, 30),
                pygame.Rect(1100, HEIGHT - 400, 400, 30),
                pygame.Rect(650, HEIGHT - 300, 350, 30),
                pygame.Rect(1600, HEIGHT - 500, 350, 30),
            ]
        elif self.level == 5:
            self.platforms = [
                pygame.Rect(100, HEIGHT - 50, 250, 50),  # Ground
                pygame.Rect(500, HEIGHT - 50, 700, 50),
                pygame.Rect(300, HEIGHT - 250, 400, 30),
                pygame.Rect(450, HEIGHT - 450, 330, 30),
                pygame.Rect(100, HEIGHT - 500, 200, 30),
                pygame.Rect(900, HEIGHT - 500, 400, 30),
            ]
        elif self.level == 6:
            self.platforms = [
                pygame.Rect(100, HEIGHT - 50, 100, 50),  # Ground
                pygame.Rect(850, HEIGHT - 50, 150, 50),
                pygame.Rect(500, HEIGHT - 50, 150, 50),
                pygame.Rect(150, HEIGHT - 250, 400, 30),
                pygame.Rect(500, HEIGHT - 350, 350, 30),
                pygame.Rect(900, HEIGHT - 300, 400, 30),
                pygame.Rect(100, HEIGHT - 500, 400, 30),
            ]
        elif self.level == 7:
            self.platforms = [
                pygame.Rect(100, HEIGHT - 50, 100, 50),  # Ground
                pygame.Rect(850, HEIGHT - 50, 150, 50),
                pygame.Rect(250, HEIGHT - 200, 250, 30),
                pygame.Rect(600, HEIGHT - 350, 200, 30),
                pygame.Rect(800, HEIGHT - 600, 400, 30),
                pygame.Rect(50, HEIGHT - 500, 200, 30),
            ]
        elif self.level == 8:
            self.platforms = [
                pygame.Rect(100, HEIGHT - 50, 100, 50),  # Ground
                pygame.Rect(850, HEIGHT - 50, 150, 50),
                pygame.Rect(70, HEIGHT - 680, 150, 30),
                pygame.Rect(270, HEIGHT - 150, 150, 30),
                pygame.Rect(800, HEIGHT - 530, 400, 30),
                pygame.Rect(100, HEIGHT - 500, 50, 30),
                pygame.Rect(550, HEIGHT - 350, 100, 30),
                pygame.Rect(1950, HEIGHT - 350, 200, 30),
            ]
        elif self.level == 9:
            self.platforms = [
                pygame.Rect(100, HEIGHT - 50, 50, 50),
                pygame.Rect(870, HEIGHT - 50, 50, 50),
                pygame.Rect(1950, HEIGHT - 200, 50, 50),
                pygame.Rect(570, HEIGHT - 100, 50, 50),
                pygame.Rect(190, HEIGHT - 420, 30, 30),
                pygame.Rect(800, HEIGHT - 330, 100, 30),
                pygame.Rect(380, HEIGHT - 650, 170, 30),
            ]
        elif self.level == 10:
            self.platforms = [
                pygame.Rect(1600, HEIGHT - 500, 50, 50),
                pygame.Rect(100, HEIGHT - 50, 50, 50),
                pygame.Rect(1950, HEIGHT - 200, 50, 50),
                pygame.Rect(300, HEIGHT - 250, 50, 50),
                pygame.Rect(750, HEIGHT - 300, 50, 50),
                pygame.Rect(1600, HEIGHT - 400, 50, 50),


            ]

        # Enemies (wild Pokémon)
        self.enemy_size = (30, 30)
        self.enemies = [
            pygame.Rect(random.randint(400, WIDTH - 400), p.top - self.enemy_size[1], *self.enemy_size)
            for p in self.platforms[1:]
        ]
        self.enemy_speeds = [random.choice([-3, 3]) for _ in self.enemies]

        # Poké Balls (collectibles)
        self.pokeballs = self.generate_pokeballs(8)
        self.total_pokeballs = len(self.pokeballs)

    def generate_pokeballs(self, num_pokeballs):
        pokeballs = []
        for _ in range(num_pokeballs):
            attempts = 0
            while attempts < 100:
                pokeball_x = random.randint(100, WIDTH - 100)
                pokeball_y = random.choice([p.top - 40 for p in self.platforms])
                new_pokeball = pygame.Rect(pokeball_x, pokeball_y, 20, 20)
                too_close = False
                for existing_pokeball in pokeballs:
                    distance = ((new_pokeball.x - existing_pokeball.x) ** 2 + (new_pokeball.y - existing_pokeball.y) ** 2) ** 0.5
                    if distance < MIN_POKEBALL_DISTANCE:
                        too_close = True
                        break
                if too_close:
                    attempts += 1
                    continue
                if all(not new_pokeball.colliderect(p) for p in self.platforms) and \
                   all(not new_pokeball.colliderect(e) for e in self.enemies):
                    pokeballs.append(new_pokeball)
                    break
                attempts += 1
        return pokeballs

    def reset(self, level=None):
        if level is None:
            level = self.level
        self.__init__(level)

# Textures
player_texture = None
player_ducking_texture = None
platform_texture = None
float_platform_texture = None
pokeball_texture = None
player_texture_run1 = None
player_texture_run2 = None
enemy_texture1 = None
enemy_texture2 = None

def load_textures():
    global player_texture, player_ducking_texture, platform_texture, float_platform_texture, pokeball_texture, player_texture_run1, player_texture_run2, enemy_texture1, enemy_texture2

    player_texture = pygame.image.load('assets/pikachu.png')
    player_texture_run1 = pygame.image.load('assets/pikachu_corre13.png')
    player_texture_run2 = pygame.image.load('assets/pikachu_corre23.png')
    player_ducking_texture = pygame.image.load('assets/pikachu_baix2.png')

    platform_texture = pygame.image.load('assets/plataforma1.png')
    float_platform_texture = pygame.image.load('assets/plataforma1.png')

    dia = pygame.image.load('assets/dia.png')
    nit = pygame.image.load('assets/nit.png')

    # Enemy texture (wild Pokémon)
    enemy_texture1 = pygame.image.load('assets/volador1.png')
    enemy_texture2 = pygame.image.load('assets/volador2.png')

    # Poké Ball texture
    pokeball_texture = pygame.image.load('assets/ultraball2.png')

# Load textures
load_textures()

# Player hitbox
def get_player_hitbox(x, y, ducking):
    if ducking:
        return pygame.Rect(x + 10, y + 10, 20, 10)
    return pygame.Rect(x + 5, y + 5, 30, 30)

# Menu functions
def show_start_menu():
    screen.fill(C4)
    imprimir_pantalla_fons('assets/fonsmenu.png')
    font = pygame.font.SysFont('Arial', 50)
    texts = [
        font.render(' ', True, WHITE)
    ]
    for i, text in enumerate(texts):
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 4 + i * 100))
    pygame.display.flip()

def show_credits():
    screen.fill(C4)
    imprimir_pantalla_fons('assets/fondocredits.png')
    font = pygame.font.SysFont('Arial', 50)
    texts = [
        font.render('CREDITS', True, WHITE),
        font.render('Creadors del joc:   Arnau, Moha i Sergio', True, WHITE),
        font.render('Diseny: Arnau i Moha', True, WHITE),
        font.render('Codi: Chatgpt, Arnau, Sergio, Xavi', True, WHITE),
        font.render('Musica: tiktok i musiques sense copyright', True, WHITE),
        font.render('ENTER - Menu', True, WHITE)
    ]
    for i, text in enumerate(texts):
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 4 + i * 80))
    pygame.display.flip()

def show_A():
    screen.fill(C4)
    imprimir_pantalla_fons('assets/fondo12.png')
    font = pygame.font.SysFont('Arial', 40)
    texts = [
        font.render('Ajuda', True, WHITE),
        font.render('Objectiu del joc: aconsegir les 8', True, WHITE),
        font.render('pokeballs de tots els nivells', True, WHITE),
        font.render('Moviment = a,d i fletxes esquerra/dreta', True, WHITE),
        font.render('Saltar = w, espai i fletxa dalt', True, WHITE),
        font.render('Ajupir = fletxa baix', True, WHITE),
        font.render('Hi ha doble salt', True, WHITE),
        font.render('Tocar un enemic = mort', True, WHITE)
    ]
    for i, text in enumerate(texts):
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 4 + i * 70))
    pygame.display.flip()

def show_victory_screen(time_taken, collected_pokeballs, total_pokeballs, level):
    screen.fill(BLACK)
    font = pygame.font.SysFont('Arial', 50)
    texts = [
        font.render(f'Level {level} Completed!', True, WHITE),
        font.render(f'Poké Balls: {collected_pokeballs}/{total_pokeballs}', True, WHITE),
        font.render(f'Time: {time_taken:.2f} seconds', True, WHITE),
        font.render('1 - Seguent Nivell', True, WHITE),
        font.render('2 - Tornar al Nivell', True, WHITE),
        font.render('ESC - Sortir', True, WHITE)
    ]
    for i, text in enumerate(texts):
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 4 + i * 60))
    pygame.display.flip()

# Main game loop
def main():
    clock = pygame.time.Clock()
    running = True
    game_state = 'menu'
    gs = GameState(level=1)
    sprite_index = 1
    animation_protagonist_speed = 100
    sprite_frame_number = 2
    last_change_frame_time = 0
    direccio = 0

    while running:
        pokemon_state = "peu"
        keys = pygame.key.get_pressed()
        current_time = pygame.time.get_ticks()

        if game_state == 'menu':
            show_start_menu()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game_state = 'playing'
                        gs.start_time = time.time()
                        pygame.mixer.music.load('assets/musica1.mp3')
                        pygame.mixer.music.play()
                    if event.key == pygame.K_SPACE:
                        game_state = 'credits'
                        gs.start_time = time.time()
                    if event.key == pygame.K_a:
                        game_state = 'ajuda'
                        gs.start_time = time.time()
                    if event.key == pygame.K_ESCAPE:
                        return

        if game_state == 'credits':
            show_credits()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game_state = 'menu'
                        gs.start_time = time.time()

        if game_state == 'ajuda':
            show_A()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game_state = 'menu'
                        gs.start_time = time.time()

        elif game_state == 'playing':
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE and gs.jump_count < 2 and not gs.is_ducking:
                        pokemon_state = "peu"
                        if gs.jump_count == 0:
                            gs.velocity_y = JUMP_STRENGTH
                        else:
                            gs.velocity_y = DOUBLE_JUMP_STRENGTH  # Double jump
                        gs.jump_count += 1
                    if event.key == pygame.K_SPACE:
                        pokemon_state = "ajupit"
                        player_ducking_texture = pygame.image.load('assets/baix.png')
                    if event.key == pygame.K_UP and gs.jump_count < 2 and not gs.is_ducking:
                        pokemon_state = "peu"
                        if gs.jump_count == 0:
                            gs.velocity_y = JUMP_STRENGTH
                        else:
                            gs.velocity_y = DOUBLE_JUMP_STRENGTH  # Double jump
                        gs.jump_count += 1
                    if event.key == pygame.K_UP:
                        pokemon_state = "ajupit"
                        player_ducking_texture = pygame.image.load('assets/baix.png')

                    if event.key == pygame.K_w and gs.jump_count < 2 and not gs.is_ducking:
                        pokemon_state = "peu"
                        if gs.jump_count == 0:
                            gs.velocity_y = JUMP_STRENGTH
                        else:
                            gs.velocity_y = DOUBLE_JUMP_STRENGTH  # Double jump
                        gs.jump_count += 1
                    if event.key == pygame.K_w:
                        pokemon_state = "ajupit"
                        player_ducking_texture = pygame.image.load('assets/baix.png')


            if gs.alive:
                # Player input
                if keys[pygame.K_LEFT] and gs.player_x > 0:
                    pokemon_state = "camina"
                    direccio = 1
                    player_texture_run1 = pygame.image.load('assets/pikachu_corre13.png')
                    gs.player_x -= PLAYER_SPEED
                if keys[pygame.K_RIGHT] and gs.player_x < WIDTH - PLAYER_SIZE[0]:
                    gs.player_x += PLAYER_SPEED
                    direccio = 0
                    pokemon_state = "camina"
                    player_texture_run1 = pygame.image.load('assets/pikachu_corre13.png')
                if keys[pygame.K_DOWN]:
                    pokemon_state = "ajupit"
                    player_ducking_texture = pygame.image.load('assets/baix.png')
                gs.is_ducking = keys[pygame.K_DOWN]

                if keys[pygame.K_a] and gs.player_x > 0:
                    pokemon_state = "camina"
                    direccio = 1
                    player_texture_run1 = pygame.image.load('assets/pikachu_corre13.png')
                    gs.player_x -= PLAYER_SPEED
                if keys[pygame.K_d] and gs.player_x < WIDTH - PLAYER_SIZE[0]:
                    gs.player_x += PLAYER_SPEED
                    direccio = 0
                    pokemon_state = "camina"
                    player_texture_run1 = pygame.image.load('assets/pikachu_corre13.png')
                # if keys[pygame.K_s]:
                #     pokemon_state = "ajupit"
                #     player_ducking_texture = pygame.image.load('assets/pikachu_baix2.png')
                # gs.is_ducking = keys[pygame.K_s]

                # Physics
                next_y = gs.player_y + gs.velocity_y
                player_hitbox = get_player_hitbox(gs.player_x, next_y, gs.is_ducking)

                # Check platform collisions (skip if ducking and falling)
                on_ground = False
                if not (gs.is_ducking and gs.velocity_y > 0):  # Allow passing through platforms while ducking and falling
                    for platform in gs.platforms:
                        if player_hitbox.colliderect(platform):
                            if gs.velocity_y > 0:  # Falling
                                gs.player_y = platform.top - (PLAYER_SIZE_DUCKING[1] if gs.is_ducking else PLAYER_SIZE[1])
                                gs.velocity_y = 6
                                gs.jump_count = 0
                                on_ground = True
                            elif gs.velocity_y < 0:  # Hitting platform from below
                                gs.player_y = platform.midbottom
                                gs.velocity_y = 0
                            break

                # Apply gravity only if not on ground
                if not on_ground:
                    gs.velocity_y = min(gs.velocity_y + GRAVITY, MAX_FALL_SPEED)
                    gs.player_y = next_y

                # Prevent falling through bottom
                if gs.player_y > HEIGHT:
                    gs.alive = False

                # Poké Ball collection
                player_hitbox = get_player_hitbox(gs.player_x, gs.player_y, gs.is_ducking)
                for pokeball in gs.pokeballs[:]:
                    if player_hitbox.colliderect(pokeball):
                        gs.pokeballs.remove(pokeball)
                        gs.collected_pokeballs += 1

                # Enemy movement and collision
                for i, enemy in enumerate(gs.enemies):
                    enemy.x += gs.enemy_speeds[i]
                    if enemy.left <= 0 or enemy.right >= WIDTH:
                        gs.enemy_speeds[i] *= -1
                        sprite1 = enemy_texture1
                        sprite2 = enemy_texture2


                        aux = True
                        if gs.enemy_speeds[i] < 0:
                            aux = False
                    if player_hitbox.colliderect(enemy):
                        gs.alive = False

                # Victory condition
                if not gs.pokeballs:
                    time_taken = time.time() - gs.start_time
                    show_victory_screen(time_taken, gs.collected_pokeballs, gs.total_pokeballs, gs.level)
                    waiting = True
                    while waiting:
                        for event in pygame.event.get():
                            if event.type == pygame.QUIT:
                                return
                            if event.type == pygame.KEYDOWN:
                                if event.key == pygame.K_1:
                                    gs.reset(gs.level+1)
                                    gs.start_time = time.time()
                                    waiting = False
                                    pygame.mixer.music.play()
                                if event.key == pygame.K_2:
                                    # gs.level = 1;
                                    gs.reset(gs.level)
                                    gs.start_time = time.time()
                                    waiting = False
                                    pygame.mixer.music.play()
                                if event.key == pygame.K_ESCAPE:
                                    game_state = 'menu'
                                    show_start_menu()
                                    gs.reset(gs.level)
                                    gs.start_time = time.time()
                                    pygame.mixer.music.load('assets/musica2.mp3')
                                    pygame.mixer.music.play()


            # Drawing
            screen.fill(BLACK)
            imprimir_pantalla_fons('assets/dia.png')
            if gs.level == 3:
                imprimir_pantalla_fons('assets/nit.png')
            if gs.level == 6:
                imprimir_pantalla_fons('assets/nit.png')
            if gs.level == 9:
                imprimir_pantalla_fons('assets/nit.png')
            for platform in gs.platforms:
                texture = platform_texture if platform.height == 50 else float_platform_texture
                #
                for x in range(0, platform.width, 50):
                    screen.blit(texture, (platform.x + x, platform.y))
            #   scaled_texture = pygame.transform.scale(texture, (platform.width, platform.height))
            #   screen.blit(scaled_texture, (platform.x, platform.y))
            for pokeball in gs.pokeballs:
                screen.blit(pokeball_texture, (pokeball.x, pokeball.y))
            for i, enemy in enumerate(gs.enemies):
                aux = False
                if gs.enemy_speeds[i] < 0:
                    aux = True
                if i%2==0:
                    sprite3 = pygame.transform.flip(enemy_texture1, aux, 0)
                else:
                    sprite3 = pygame.transform.flip(enemy_texture2, aux, 0)
                screen.blit(sprite3, (enemy.x, enemy.y))

            # Draw player with appropriate texture based on ducking state
            if pokemon_state == "peu":
                screen.blit(player_texture, (gs.player_x, gs.player_y - 5))  # Adjust position for ducking
            elif pokemon_state == "camina":
                if current_time - last_change_frame_time >= animation_protagonist_speed:
                    last_change_frame_time = current_time
                    if sprite_index == 1:
                        sprite0 = player_texture_run1
                        sprite_index = 2
                        if direccio == 1:
                            sprite0 = pygame.transform.flip(sprite0,1,0)
                    else:
                        sprite0 = player_texture_run2
                        sprite_index = 1
                        if direccio == 1:
                            sprite0 = pygame.transform.flip(sprite0, 1, 0)
                screen.blit(sprite0, (gs.player_x, gs.player_y - 5))  # Adjust position for ducking
            elif pokemon_state == "ajupit":
                screen.blit(player_ducking_texture, (gs.player_x, gs.player_y - 5))  # Adjust position for ducking

            font = pygame.font.SysFont('Arial', 30)
            time_text = font.render(f'Time: {time.time() - gs.start_time:.2f}s', True, WHITE)
            pokeball_text = font.render(f'Poké Balls: {gs.collected_pokeballs}/{gs.total_pokeballs}', True, WHITE)
            level_text = font.render(f'Level: {gs.level}', True, WHITE)
            screen.blit(time_text, (850, 20))
            screen.blit(pokeball_text, (810, 60))
            screen.blit(level_text, (20, 20))
            if not gs.alive:
                death_text1 = font.render('GAME OVER', True, RED)
                death_text2 = font.render('Presiona R por Reintentar', True, RED)
                death_text3 = font.render('Presiona ESC per Sortir', True, RED)
                screen.blit(death_text1, (WIDTH // 2 - death_text1.get_width() // 2, HEIGHT // 2.3))
                screen.blit(death_text2, (WIDTH // 2 - death_text2.get_width() // 2, HEIGHT // 2))
                screen.blit(death_text3, (WIDTH // 2 - death_text3.get_width() // 2, HEIGHT // 1.7))
                gs.start_time = time.time()
                pygame.mixer.music.load('assets/musica_mort.mp3')

                if keys[pygame.K_ESCAPE]:
                    game_state = 'menu'
                    gs.reset(gs.level)
                    gs.start_time = time.time()
                    pygame.mixer.music.load('assets/musica2.mp3')
                    pygame.mixer.music.play()
                if keys[pygame.K_r]:
                    gs.reset(gs.level)
                    pygame.mixer.music.load('assets/musica1.mp3')
                    gs.start_time = time.time()
                    pygame.mixer.music.play()

            pygame.display.flip()
            clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
