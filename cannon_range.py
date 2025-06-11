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
BARREL_MAX_ANGLE = 70
BARREL_LENGTH = 1.5

# Reload settings
RELOAD_TIME = 0.5  # seconds

# Target settings
NUM_TARGETS = 20
TARGET_MIN_DIST = 50
TARGET_MAX_DIST = 100
TARGET_HORIZON_Y = 0

# Colors
COLOR_CANNON = (0.2, 0.2, 0.7)
COLOR_BARREL = (0.1, 0.1, 0.5)
COLOR_PROJECTILE = (1, 0, 0)
COLOR_TANK = (0.5, 0.5, 0)
COLOR_AV = (0.5, 0, 0.5)
COLOR_EXPLOSION = (1, 0.5, 0)
COLOR_DIRT = (0.4, 0.3, 0.1)

# Utility clamp function
def clamp(x, minimum, maximum):
    return max(minimum, min(x, maximum))

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
    pygame.init()
    pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | OPENGL)
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.5, 0.8, 1.0, 1)  # Sky blue

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
    draw_cube(2.0, COLOR_TANK)

# Draw an AV (simple smaller cube)
def draw_av():
    draw_cube(1.2, COLOR_AV)

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

def move_camera(camera_x):
    glLoadIdentity()
    gluPerspective(45, (WIDTH / HEIGHT), 0.1, 5000.0)
    gluLookAt(camera_x, 2, -4, camera_x, 0, 50, 0, 1, 0)

# Main function
def main():
    init()
    clock = pygame.time.Clock()

    # Cannon state
    cannon_x = 0.0
    barrel_angle = 45.0  # degrees
    reload_timer = 0.0

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
            move_camera(cannon_x)
        if keys[K_RIGHT]:
            cannon_x -= CANNON_MOVE_SPEED
            cannon_x = clamp(cannon_x, -100, 100)
            move_camera(cannon_x)
        # Adjust barrel angle
        if keys[K_UP]:
            barrel_angle += 30 * dt
            barrel_angle = clamp(barrel_angle, BARREL_MIN_ANGLE, BARREL_MAX_ANGLE)
        if keys[K_DOWN]:
            barrel_angle -= 30 * dt
            barrel_angle = clamp(barrel_angle, BARREL_MIN_ANGLE, BARREL_MAX_ANGLE)

        # Fire projectile
        if keys[K_SPACE] and reload_timer <= 0:
            # Calculate initial velocity vector of projectile
            angle_rad = math.radians(barrel_angle)
            vel_y = math.sin(angle_rad) * 50  # speed scale
            vel_z = math.cos(angle_rad) * 50
            proj_pos = np.array([cannon_x, CANNON_Y + 1.0, 0])
            proj_vel = np.array([0, vel_y, vel_z])
            projectiles.append({"pos": proj_pos, "vel": proj_vel, "active": True})
            reload_timer = RELOAD_TIME

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

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()

