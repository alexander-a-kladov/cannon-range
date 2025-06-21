#!/usr/bin/python3

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import random
import time
import math

# Screen settings
WIDTH, HEIGHT = 1200, 800

# Cannon settings
CANNON_Y = 0
CANNON_MOVE_SPEED = 0.25
BARREL_MIN_ANGLE = 0
BARREL_MAX_ANGLE = 80
BARREL_LENGTH = 1.5

CAMERA_MOVE_SPEED = 0.5

# Reload settings
RELOAD_TIME = 0.5  # seconds

# Target settings
NUM_TARGETS = 20
TARGET_MIN_DIST = 50
TARGET_MAX_DIST = 250
TARGET_HORIZON_Y = 0

# Colors
COLOR_CANNON = (0.2, 0.2, 0.7)
COLOR_BARREL = (0.1, 0.1, 0.5)
COLOR_PROJECTILE = (1, 0, 0)
COLOR_TANK = (0.5, 0.5, 0)
COLOR_AV = (0.5, 0, 0.5)
COLOR_EXPLOSION = (1, 0.5, 0)
COLOR_DIRT = (0.4, 0.3, 0.1)

# Objects
OBJ_TANK = None
OBJ_AV = None

# Fonts
FONT = None

# Sounds
CANNON_SOUND = None
EXPLOSION_SOUND = None

# Utility clamp function
def clamp(x, minimum, maximum):
    return max(minimum, min(x, maximum))

# --- OBJ and MTL Loader ---
def MTL(filename):
    contents = {}
    mtl = None
    for line in open(filename, "r"):
        if line.startswith('#'): continue
        values = line.strip().split()
        if not values: continue
        if values[0] == 'newmtl':
            mtl = contents[values[1]] = {}
        elif mtl is None:
            raise ValueError("mtl file doesn't start with newmtl stmt")
        elif values[0] == 'map_Kd':
            mtl['map_Kd'] = values[1]
            surf = pygame.image.load(mtl['map_Kd'])
            image = pygame.image.tostring(surf, 'RGBA', 1)
            ix, iy = surf.get_rect().size
            texid = mtl['texture_Kd'] = glGenTextures(1)
            print(texid, filename)
            glBindTexture(GL_TEXTURE_2D, texid)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, ix, iy, 0, GL_RGBA, GL_UNSIGNED_BYTE, image)
        else:
            mtl[values[0]] = list(map(float, values[1:]))
    return contents

class OBJ:
    def __init__(self, filename, swapyz=False):
        self.vertices = []
        self.normals = []
        self.texcoords = []
        self.faces = []
        self.mtl = None
        material = None
        for line in open(filename, "r"):
            if line.startswith('#'): continue
            values = line.strip().split()
            if not values: continue
            if values[0] == 'v':
                v = list(map(float, values[1:4]))
                if swapyz: v = [v[0], v[2], v[1]]
                self.vertices.append(v)
            elif values[0] == 'vn':
                v = list(map(float, values[1:4]))
                if swapyz: v = [v[0], v[2], v[1]]
                self.normals.append(v)
            elif values[0] == 'vt':
                self.texcoords.append(list(map(float, values[1:3])))
            elif values[0] in ('usemtl', 'usemat'):
                material = values[1]
            elif values[0] == 'mtllib':
                self.mtl = MTL(values[1])
            elif values[0] == 'f':
                face = []
                texcoords = []
                norms = []
                for v in values[1:]:
                    w = v.split('/')
                    face.append(int(w[0]))
                    texcoords.append(int(w[1]) if len(w) > 1 and w[1] else 0)
                    norms.append(int(w[2]) if len(w) > 2 and w[2] else 0)
                self.faces.append((face, norms, texcoords, material))
        self.gl_list = glGenLists(1)
        glNewList(self.gl_list, GL_COMPILE)
        glEnable(GL_TEXTURE_2D)
        glFrontFace(GL_CCW)
        for face in self.faces:
            vertices, normals, texture_coords, material = face
            mtl = self.mtl[material] if self.mtl and material else None
            if mtl and 'texture_Kd' in mtl:
                glBindTexture(GL_TEXTURE_2D, mtl['texture_Kd'])
            elif mtl and 'Kd' in mtl:
                glColor(*mtl['Kd'])
            glBegin(GL_POLYGON)
            for i in range(len(vertices)):
                if normals[i] > 0:
                    glNormal3fv(self.normals[normals[i] - 1])
                if texture_coords[i] > 0:
                    glTexCoord2fv(self.texcoords[texture_coords[i] - 1])
                glVertex3fv(self.vertices[vertices[i] - 1])
            glEnd()
        glDisable(GL_TEXTURE_2D)
        glEndList()

# Draw a simple cube at origin with given size and color
def draw_cube(size=1.0, color=(1,1,1)):
    glColor3f(*color)
    glBegin(GL_QUADS)
    s = size / 2.0
    # Front face
    glVertex3f(-s, -s, s)
    glVertex3f(s, -s, s)
    glVertex3f(s, s, s)
    glVertex3f(-s, s, s)
    # Back face
    glVertex3f(-s, -s, -s)
    glVertex3f(-s, s, -s)
    glVertex3f(s, s, -s)
    glVertex3f(s, -s, -s)
    # Left face
    glVertex3f(-s, -s, -s)
    glVertex3f(-s, -s, s)
    glVertex3f(-s, s, s)
    glVertex3f(-s, s, -s)
    # Right face
    glVertex3f(s, -s, -s)
    glVertex3f(s, s, -s)
    glVertex3f(s, s, s)
    glVertex3f(s, -s, s)
    # Top face
    glVertex3f(-s, s, -s)
    glVertex3f(-s, s, s)
    glVertex3f(s, s, s)
    glVertex3f(s, s, -s)
    # Bottom face
    glVertex3f(-s, -s, -s)
    glVertex3f(s, -s, -s)
    glVertex3f(s, -s, s)
    glVertex3f(-s, -s, s)
    glEnd()

# Draw a cylinder (barrel) along positive Y axis
def draw_cylinder(radius=0.15, length=1.5, slices=16, color=(1,1,1)):
    glColor3f(*color)
    quad = gluNewQuadric()
    gluCylinder(quad, radius, radius, length, slices, 1)
    gluDeleteQuadric(quad)

# Explosion particle effect (simple expanding sphere)
class Explosion:
    def __init__(self, pos):
        self.pos = pos
        self.start_time = time.time()
        self.duration = 1.0  # seconds
        self.radius = 1.0

    def update(self):
        elapsed = time.time() - self.start_time
        self.radius = 1.0 + elapsed * 2.5

    def draw(self):
        elapsed = time.time() - self.start_time
        if elapsed > self.duration:
            return False
        glPushMatrix()
        glTranslatef(*self.pos)
        glColor4f(1, 0.5, 0, 1 - elapsed/self.duration)
        draw_cylinder(radius=5*self.radius, length=10*self.radius)
        glPopMatrix()
        return True

# Dirt mark decal on ground (simple flat quad)
class DirtMark:
    def __init__(self, pos):
        self.pos = pos
        self.size = 1.0

    def draw(self):
        glPushMatrix()
        glTranslatef(self.pos[0], TARGET_HORIZON_Y + 0.01, self.pos[2])
        glColor3f(*COLOR_DIRT)
        glBegin(GL_QUADS)
        s = self.size / 2
        glVertex3f(-s, 0, -s)
        glVertex3f(s, 0, -s)
        glVertex3f(s, 0, s)
        glVertex3f(-s, 0, s)
        glEnd()
        glPopMatrix()

# Initialize pygame and OpenGL
def init():
    global FONT, CANNON_SOUND, EXPLOSION_SOUND, OBJ_TANK, OBJ_AV
    pygame.init()
    pygame.mixer.init()
    pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | OPENGL)
    FONT = pygame.font.SysFont("Arial", 32)
    CANNON_SOUND = pygame.mixer.Sound("sounds/cannon.wav")
    EXPLOSION_SOUND = pygame.mixer.Sound("sounds/explosion.wav")
    OBJ_TANK = OBJ("tank.obj", swapyz=True)
    OBJ_AV = OBJ("av.obj", swapyz=True)
    glLightfv(GL_LIGHT0, GL_POSITION, (-40, 200, 100, 0.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.5, 0.5, 0.5, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.8, 0.8, 0.8, 1.0))
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHTING)
    glEnable(GL_COLOR_MATERIAL)
    glShadeModel(GL_SMOOTH)
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.5, 0.8, 1.0, 1)  # Sky blue
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    # Perspective projection
    gluPerspective(45, (WIDTH / HEIGHT), 0.1, 5000.0)
    gluLookAt(0, 2, -4, 0, 0, 50, 0, 1, 0)


# Create targets randomly positioned
def create_targets():
    targets = []
    for _ in range(NUM_TARGETS):
        x = random.uniform(-100, 100)
        z = random.uniform(TARGET_MIN_DIST, TARGET_MAX_DIST)
        ttype = random.choice(["tank", "av"])
        targets.append({
            "pos": np.array([x, TARGET_HORIZON_Y, z]),
            "type": ttype,
            "active": True,
        })
    return targets

# Draw a tank (simple cube)
def draw_tank():
    glPushMatrix()
    glRotatef(-90,1,0,0)
    glRotatef(90,0,0,1)
    glScalef(0.3,0.3,0.3)
    glCallList(OBJ_TANK.gl_list)
    glPopMatrix()

# Draw an AV (simple smaller cube)
def draw_av():
    glPushMatrix()
    glRotatef(-90,1,0,0)
    glRotatef(90,0,0,1)
    glScalef(0.2,0.2,0.2)
    glCallList(OBJ_AV.gl_list)
    glPopMatrix()

# Draw cannon base
def draw_cannon_base():
    glPushMatrix()
    glColor3f(*COLOR_CANNON)
    glScalef(3, 1, 2)
    draw_cube()
    glPopMatrix()

# Draw cannon barrel
def draw_cannon_barrel():
    draw_cylinder(radius=0.2, length=BARREL_LENGTH, color=COLOR_BARREL)

# Draw projectile as small red sphere
def draw_projectile():
    draw_cylinder(radius=0.1, length=2, color=COLOR_PROJECTILE)

def move_camera(camera_x, camera_y):
    glLoadIdentity()
    gluPerspective(45, (WIDTH / HEIGHT), 0.1, 5000.0)
    gluLookAt(camera_x, 2+camera_y, -4, camera_x, 0, 50, 0, 1, 0)

def draw_text(x, y, text):                                                
    textSurface = FONT.render(text, True, (255, 255, 66, 255)).convert_alpha()
    textData = pygame.image.tostring(textSurface, "RGBA", True)
    glWindowPos2d(x, y)
    glDrawPixels(textSurface.get_width(), textSurface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, textData)


# Main function
def main():
    init()
    clock = pygame.time.Clock()

    # Cannon state
    cannon_x = 0.0
    barrel_angle = 45.0  # degrees
    reload_timer = 0.0
    camera_y = 0
    shell_spent = 0

    # Projectiles list
    projectiles = []

    # Targets
    targets = create_targets()

    # Effects
    explosions = []
    dirt_marks = []

    running = True
    while running:
        dt = clock.tick(60) / 1000.0  # Delta time in seconds

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False

        keys = pygame.key.get_pressed()
        # Move cannon left/right
        if keys[K_LEFT]:
            cannon_x += CANNON_MOVE_SPEED
            cannon_x = clamp(cannon_x, -100, 100)
            # Perspective projection
            move_camera(cannon_x, camera_y)
        if keys[K_RIGHT]:
            cannon_x -= CANNON_MOVE_SPEED
            cannon_x = clamp(cannon_x, -100, 100)
            move_camera(cannon_x, camera_y)
        # Adjust barrel angle
        if keys[K_UP]:
            barrel_angle += 30 * dt
            barrel_angle = clamp(barrel_angle, BARREL_MIN_ANGLE, BARREL_MAX_ANGLE)
        if keys[K_DOWN]:
            barrel_angle -= 30 * dt
            barrel_angle = clamp(barrel_angle, BARREL_MIN_ANGLE, BARREL_MAX_ANGLE)
        if keys[K_q]:
            camera_y += CAMERA_MOVE_SPEED
            camera_y =  clamp(camera_y, 0, 50)
            move_camera(cannon_x, camera_y)
        if keys[K_a]:
            camera_y -= CAMERA_MOVE_SPEED
            camera_y =  clamp(camera_y, 0, 50)
            move_camera(cannon_x, camera_y)

        # Fire projectile
        if keys[K_SPACE] and reload_timer <= 0:
            # Calculate initial velocity vector of projectile
            CANNON_SOUND.play()
            angle_rad = math.radians(barrel_angle)
            vel_y = math.sin(angle_rad) * 50  # speed scale
            vel_z = math.cos(angle_rad) * 50
            proj_pos = np.array([cannon_x, CANNON_Y + 1.0, 0])
            proj_vel = np.array([0, vel_y, vel_z])
            projectiles.append({"pos": proj_pos, "vel": proj_vel, "active": True})
            reload_timer = RELOAD_TIME
            shell_spent += 1

        if reload_timer > 0:
            reload_timer -= dt

        # Update projectiles
        gravity = -9.81
        for proj in projectiles:
            if not proj["active"]:
                continue
            # Simple physics update
            proj["vel"][1] += gravity * dt
            proj["pos"] += proj["vel"] * dt
            # Check if projectile hit ground (y <= horizon)
            if proj["pos"][1] <= TARGET_HORIZON_Y:
                proj["active"] = False
                # Check for hits or near hits
                hit_any = False
                for target in targets:
                    if not target["active"]:
                        continue
                    dist = np.linalg.norm(proj["pos"] - target["pos"])
                    if dist < 3.0:
                        # Direct hit
                        EXPLOSION_SOUND.play()
                        target["active"] = False
                        explosions.append(Explosion(target["pos"]))
                        hit_any = True
                        break
                if not hit_any:
                    # Near miss, create dirt mark
                    dirt_marks.append(DirtMark(proj["pos"]))

        # Remove inactive projectiles
        projectiles = [p for p in projectiles if p["active"]]

        # Update explosions
        explosions = [e for e in explosions if e.draw() or e.update()]

        # Clear screen and depth buffer
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Draw horizon plane (field)
        glColor3f(0.3, 0.7, 0.3)
        glBegin(GL_QUADS)
        size = 200
        glVertex3f(-size, TARGET_HORIZON_Y, 0)
        glVertex3f(size, TARGET_HORIZON_Y, 0)
        glVertex3f(size, TARGET_HORIZON_Y, 15000)
        glVertex3f(-size, TARGET_HORIZON_Y, 15000)
        glEnd()

        # Draw cannon base
        glPushMatrix()
        glTranslatef(cannon_x, CANNON_Y, 0)
        draw_cannon_base()

        # Draw barrel
        glPushMatrix()
        glTranslatef(0, 0.5, 0)
        glRotatef(-barrel_angle, 1, 0, 0)
        draw_cannon_barrel()
        glPopMatrix()
        glPopMatrix()

        # Draw targets
        for target in targets:
            if not target["active"]:
                continue
            glPushMatrix()
            glTranslatef(*target["pos"])
            if target["type"] == "tank":
                draw_tank()
            else:
                draw_av()
            glPopMatrix()

        # Draw projectiles
        for proj in projectiles:
            glPushMatrix()
            glTranslatef(*proj["pos"])
            draw_projectile()
            glPopMatrix()

        # Draw dirt marks
        for dirt in dirt_marks:
            dirt.draw()

        # Draw explosions
        for explosion in explosions:
            explosion.draw()

        shell_spent_t = f"Shells: {shell_spent}"
        barrel_angle_t = f"Angle: {barrel_angle:.2f}"
        draw_text(5,HEIGHT-40,shell_spent_t)
        draw_text(WIDTH-180,HEIGHT-40,barrel_angle_t)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()

