"""Pre-launch settings menu for display, mode, and resolution."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from display_setup import list_displays

BG = (2, 16, 8)
PANEL = (5, 24, 12)
BORDER = (20, 120, 70)
HEAD = (180, 255, 180)
TEXT = (110, 210, 140)
DIM = (40, 105, 70)

MODE_OPTIONS = ["borderless", "exclusive", "windowed"]
WINDOW_RESOLUTIONS = [
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
]


@dataclass
class LaunchSettings:
    display_index: int
    mode: str
    window_size: tuple[int, int]


class Dropdown:
    def __init__(
        self,
        label: str,
        options: list[str],
        selected_idx: int,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> None:
        self.label = label
        self.options = options
        self.selected_idx = max(0, min(selected_idx, len(options) - 1))
        self.rect = pygame.Rect(x, y, w, h)
        self.open = False

    @property
    def value(self) -> str:
        return self.options[self.selected_idx]

    def _menu_top(self, screen_h: int) -> int:
        menu_h = len(self.options) * self.rect.height
        below = self.rect.bottom
        if below + menu_h <= screen_h - 16:
            return below
        return max(16, self.rect.y - menu_h)

    def _option_rect(self, i: int, screen_h: int) -> pygame.Rect:
        return pygame.Rect(
            self.rect.x,
            self._menu_top(screen_h) + i * self.rect.height,
            self.rect.width,
            self.rect.height,
        )

    def draw(self, screen: pygame.Surface, font_sm: pygame.font.Font, font_md: pygame.font.Font) -> None:
        screen.blit(font_sm.render(self.label, True, DIM), (self.rect.x, self.rect.y - 22))
        pygame.draw.rect(screen, PANEL, self.rect)
        pygame.draw.rect(screen, BORDER, self.rect, width=2)
        label = font_md.render(self.value, True, TEXT)
        screen.blit(label, (self.rect.x + 14, self.rect.y + (self.rect.height - label.get_height()) // 2))
        caret = font_md.render("▼" if not self.open else "▲", True, HEAD)
        screen.blit(caret, (self.rect.right - 24, self.rect.y + (self.rect.height - caret.get_height()) // 2))

        if not self.open:
            return

    def draw_menu(self, screen: pygame.Surface, font_md: pygame.font.Font) -> None:
        if not self.open:
            return
        menu_h = len(self.options) * self.rect.height
        menu_top = self._menu_top(screen.get_height())
        shadow = pygame.Surface((self.rect.width + 10, menu_h + 10), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 70))
        screen.blit(shadow, (self.rect.x + 4, menu_top + 4))
        box = pygame.Rect(self.rect.x, menu_top, self.rect.width, menu_h)
        pygame.draw.rect(screen, PANEL, box)
        pygame.draw.rect(screen, BORDER, box, width=2)
        for i, option in enumerate(self.options):
            row = self._option_rect(i, screen.get_height())
            pygame.draw.rect(screen, (12, 45, 24) if i == self.selected_idx else PANEL, row)
            pygame.draw.rect(screen, BORDER, row, width=1)
            col = HEAD if i == self.selected_idx else TEXT
            text = font_md.render(option, True, col)
            screen.blit(text, (row.x + 14, row.y + (row.height - text.get_height()) // 2))

    def click(self, pos: tuple[int, int], screen_h: int) -> bool:
        if self.rect.collidepoint(pos):
            self.open = not self.open
            return True
        if not self.open:
            return False
        for i in range(len(self.options)):
            row = self._option_rect(i, screen_h)
            if row.collidepoint(pos):
                self.selected_idx = i
                self.open = False
                return True
        self.open = False
        return False


def _closest_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def _parse_res(text: str) -> tuple[int, int]:
    left, right = text.split("x", 1)
    return int(left), int(right)


def open_settings_menu(
    default_display: int | None,
    default_mode: str,
    default_window_size: tuple[int, int] | None,
) -> LaunchSettings | None:
    pygame.init()
    monitors = list_displays()
    pygame.display.set_caption("TheMatrix Settings")
    screen = pygame.display.set_mode((920, 640))
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("consolas", 44, bold=True)
    font_md = pygame.font.SysFont("consolas", 24)
    font_sm = pygame.font.SysFont("consolas", 18)

    monitor_labels = [f"[{i}] {w}x{h} · Display {i + 1}" for i, (w, h) in monitors]
    if not monitor_labels:
        monitor_labels = ["[0] 1920x1080"]

    default_monitor_idx = 0
    if default_display is not None:
        default_monitor_idx = max(0, min(default_display, len(monitor_labels) - 1))

    res_labels = [f"{w}x{h}" for (w, h) in WINDOW_RESOLUTIONS]
    dws = default_window_size or (1280, 720)
    if f"{dws[0]}x{dws[1]}" not in res_labels:
        res_labels.append(f"{dws[0]}x{dws[1]}")

    dd_monitor = Dropdown("Monitor", monitor_labels, default_monitor_idx, 120, 190, 680, 42)
    dd_mode = Dropdown("Display mode", MODE_OPTIONS, _closest_index(MODE_OPTIONS, default_mode), 120, 290, 680, 42)
    dd_res = Dropdown(
        "Windowed resolution",
        res_labels,
        _closest_index(res_labels, f"{dws[0]}x{dws[1]}"),
        120,
        390,
        680,
        42,
    )
    launch_btn = pygame.Rect(120, 520, 280, 58)
    cancel_btn = pygame.Rect(430, 520, 180, 58)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return None
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    idx = int(dd_monitor.value.split("]", 1)[0][1:])
                    mode = dd_mode.value
                    pygame.quit()
                    return LaunchSettings(idx, mode, _parse_res(dd_res.value))
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if dd_monitor.click(pos, screen.get_height()):
                    dd_mode.open = False
                    dd_res.open = False
                    continue
                if dd_mode.click(pos, screen.get_height()):
                    dd_monitor.open = False
                    dd_res.open = False
                    continue
                if dd_res.click(pos, screen.get_height()):
                    dd_monitor.open = False
                    dd_mode.open = False
                    continue
                if launch_btn.collidepoint(pos):
                    idx = int(dd_monitor.value.split("]", 1)[0][1:])
                    mode = dd_mode.value
                    pygame.quit()
                    return LaunchSettings(idx, mode, _parse_res(dd_res.value))
                if cancel_btn.collidepoint(pos):
                    pygame.quit()
                    return None
                dd_monitor.open = False
                dd_mode.open = False
                dd_res.open = False

        screen.fill(BG)
        frame = pygame.Surface((760, 560), pygame.SRCALPHA)
        frame.fill((*PANEL, 220))
        pygame.draw.rect(frame, BORDER, frame.get_rect(), width=2)
        screen.blit(frame, (80, 40))

        screen.blit(font_title.render("THE MATRIX · DISPLAY SETTINGS", True, HEAD), (110, 78))
        tip = "Pick monitor/mode/resolution, then launch."
        screen.blit(font_sm.render(tip, True, DIM), (120, 132))

        dd_monitor.draw(screen, font_sm, font_md)
        dd_mode.draw(screen, font_sm, font_md)
        dd_res.draw(screen, font_sm, font_md)
        if dd_monitor.open:
            dd_monitor.draw_menu(screen, font_md)
        elif dd_mode.open:
            dd_mode.draw_menu(screen, font_md)
        elif dd_res.open:
            dd_res.draw_menu(screen, font_md)
        if dd_mode.value != "windowed":
            hint = font_sm.render("Resolution is used for windowed mode only.", True, DIM)
            screen.blit(hint, (120, 442))

        pygame.draw.rect(screen, PANEL, launch_btn)
        pygame.draw.rect(screen, BORDER, launch_btn, width=2)
        ltxt = font_md.render("LAUNCH", True, HEAD)
        screen.blit(ltxt, (launch_btn.x + (launch_btn.width - ltxt.get_width()) // 2, launch_btn.y + 14))

        pygame.draw.rect(screen, PANEL, cancel_btn)
        pygame.draw.rect(screen, BORDER, cancel_btn, width=2)
        ctxt = font_md.render("Cancel", True, TEXT)
        screen.blit(ctxt, (cancel_btn.x + (cancel_btn.width - ctxt.get_width()) // 2, cancel_btn.y + 14))

        pygame.display.flip()
        clock.tick(60)
