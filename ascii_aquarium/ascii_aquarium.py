import time
import random

# aquarium size
WIDTH = 160
HEIGHT = 40

class Fish:

    def __init__(self, right, left):
        self.right = right 
        self.left = left 
        self.x = random.randint(1, WIDTH - len(right) - 1)  # x coordinate on grid picked randomly between the width bounds with a little buffer
        self.y = random.randint(len(waves) + 2, HEIGHT - 2)  # y coordinate on grid same as x, although between waves and bottom with some buffer
        self.dx = random.choice([1, -1])  # x direction right: 1 left: -1
        self.dy = 0

    def update(self):
        self.x += self.dx
        if self.x == 0 or self.x == WIDTH-len(self.right):  # if the fish hits the width boundary, turn it around
            self.dx *= -1

        if random.random() < 0.05:  # chance that the fish changes its vertical direction
            self.dy = random.choice([-1, 0, 0, 1])  # 50% chance of moving straight, and 25% for up and down

        if not len(waves) < self.y + self.dy < HEIGHT:  # if the fish is about to hit a boundary, reverse their direction
            self.dy *= -1
        
        self.y += self.dy

    def draw(self, frame):
        if self.dx > 0: 
            fish_to_draw = self.right
        else:
            fish_to_draw = self.left

        for i in range(len(fish_to_draw)):
            frame[self.y][self.x+i] = fish_to_draw[i]
    

grid = [[' '] * WIDTH for _ in range(HEIGHT)]
grid[0] = ['_'] * WIDTH

waves = [
    "~~~^~~~~^^~~~~~~^~~", 
    " ~~  ~~~   ~~ ~~~  ",   
    "   ~      ~~     ~ ",   
]
for i in range(len(waves)):
    grid[i+1] = list((waves[i] * WIDTH)[:WIDTH])

school = (
    [Fish('><>', '<><') for _ in range(4)] +
    [Fish('><_>', '<_><') for _ in range(3)] +
    [Fish('><=>', '<=><') for _ in range(3)] +
    [Fish(">))'>", "<'((<") for _ in range(3)] +
    [Fish('><{{{o>', '<o}}}><') for _ in range(2)] +
    [Fish("><((('>", "<')))><") for _ in range(2)] +
    [Fish("><(((('>", "<'))))><") for _ in range(2)] +
    [Fish("><|||||>", "<|||||><") for _ in range(1)]
)

print('\033[2J', end='')  # clear screen
print('\033[?25l', end='')  # hide cursor

try:
    while True:
        for row in grid[1:len(waves)+1]:
            row.insert(0,row.pop())  # moving the waves

        frame = [row[:] for row in grid]

        for fish in school:
            fish.update()
            fish.draw(frame)

        print('\033[H' + '\n'.join(''.join(row) for row in frame), end='', flush=True)  # move cursor to top-left and print new frame

        time.sleep(0.1)

except KeyboardInterrupt:
    print('\033[?25h', end='')  # show cursor again
