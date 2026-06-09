"""Pre-launch settings menu for Spotify, display, mode, and resolution."""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass

import pygame

from display_setup import list_displays
from font_setup import default_font_name, get_font
from spotify_connect import (
    connect_spotify,
    credentials_configured,
    disconnect_spotify,
    get_authorize_url,
    get_status,
    is_logged_in,
    save_defaults_credentials,
)
from spotify_qr import make_qr_surface

BG = (2, 16, 8)
PANEL = (5, 24, 12)
BORDER = (20, 120, 70)
HEAD = (180, 255, 180)
TEXT = (110, 210, 140)
DIM = (40, 105, 70)
WARN = (255, 200, 60)
SPOTIFY_GREEN = (30, 215, 96)
BTN = (8, 38, 20)
BTN_HOVER = (14, 58, 32)
FIELD_BG = (4, 28, 14)


@dataclass
class LaunchSettings:
    display_index: int
    mode: str
    window_size: tuple[int, int]
    enable_spotify: bool = True


MODE_OPTIONS = ["borderless", "exclusive", "windowed"]
WINDOW_RESOLUTIONS = [
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
]


def _read_clipboard() -> str:
    try:
        if sys.platform == "darwin":
            return subprocess.check_output(["pbpaste"], text=True, stderr=subprocess.DEVNULL)
        if sys.platform == "win32":
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            try:
                return str(root.clipboard_get())
            finally:
                root.destroy()
        for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
            try:
                return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
    except Exception:
        pass
    return ""


class TextField:
    _MAX_LEN = 96

    def __init__(self, label: str, x: int, y: int, w: int, h: int, *, secret: bool = False) -> None:
        self.label = label
        self.rect = pygame.Rect(x, y, w, h)
        self.secret = secret
        self.text = ""
        self.active = False
        self._cursor = 0

    def _insert(self, raw: str) -> None:
        cleaned = "".join(ch for ch in raw.replace("\r", "").replace("\n", "") if ch.isprintable())
        if not cleaned:
            return
        room = self._MAX_LEN - len(self.text)
        if room <= 0:
            return
        cleaned = cleaned[:room]
        self.text = self.text[: self._cursor] + cleaned + self.text[self._cursor :]
        self._cursor += len(cleaned)

    def paste_from_clipboard(self) -> None:
        self._insert(_read_clipboard())

    def _set_active(self, active: bool) -> None:
        self.active = active
        if active:
            pygame.key.start_text_input()
            pygame.key.set_text_input_rect(self.rect)
        else:
            pygame.key.stop_text_input()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            was_active = self.active
            hit = self.rect.collidepoint(event.pos)
            if hit:
                self._set_active(True)
            elif was_active:
                self._set_active(False)
            return hit
        if not self.active:
            return False
        if event.type == pygame.TEXTINPUT:
            self._insert(event.text)
            return True
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_BACKSPACE:
            if self._cursor > 0:
                self.text = self.text[: self._cursor - 1] + self.text[self._cursor :]
                self._cursor -= 1
            return True
        if event.key == pygame.K_DELETE:
            if self._cursor < len(self.text):
                self.text = self.text[: self._cursor] + self.text[self._cursor + 1 :]
            return True
        if event.key == pygame.K_LEFT:
            self._cursor = max(0, self._cursor - 1)
            return True
        if event.key == pygame.K_RIGHT:
            self._cursor = min(len(self.text), self._cursor + 1)
            return True
        if event.key == pygame.K_HOME:
            self._cursor = 0
            return True
        if event.key == pygame.K_END:
            self._cursor = len(self.text)
            return True
        return False

    def draw(self, screen: pygame.Surface, font_sm: pygame.font.Font, font_md: pygame.font.Font) -> None:
        screen.blit(font_sm.render(self.label, True, DIM), (self.rect.x, self.rect.y - 20))
        pygame.draw.rect(screen, FIELD_BG, self.rect, border_radius=4)
        border = SPOTIFY_GREEN if self.active else BORDER
        pygame.draw.rect(screen, border, self.rect, width=2, border_radius=4)
        shown = ("*" * len(self.text)) if self.secret and self.text else self.text
        if self.active and pygame.time.get_ticks() % 1000 < 500:
            shown = shown[: self._cursor] + "|" + shown[self._cursor :]
        screen.blit(
            font_md.render(shown or " ", True, TEXT if self.text else DIM),
            (self.rect.x + 12, self.rect.y + (self.rect.height - font_md.get_height()) // 2),
        )


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


def _draw_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    active: bool = True,
    accent: tuple[int, int, int] = HEAD,
    hover: bool = False,
) -> None:
    fill = BTN_HOVER if hover and active else BTN
    if not active:
        fill = (6, 20, 10)
    pygame.draw.rect(screen, fill, rect, border_radius=4)
    pygame.draw.rect(screen, BORDER if active else DIM, rect, width=2, border_radius=4)
    color = accent if active else DIM
    text = font.render(label, True, color)
    screen.blit(
        text,
        (rect.x + (rect.width - text.get_width()) // 2, rect.y + (rect.height - text.get_height()) // 2),
    )


def _wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text[:80]]


def _draw_connect_modal(
    screen: pygame.Surface,
    font_md: pygame.font.Font,
    font_sm: pygame.font.Font,
    *,
    qr_surface: pygame.Surface | None,
    status_line: str,
) -> None:
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    box = pygame.Rect(180, 120, 560, 420)
    pygame.draw.rect(screen, PANEL, box, border_radius=6)
    pygame.draw.rect(screen, BORDER, box, width=2, border_radius=6)

    title = font_md.render("CONNECT SPOTIFY", True, SPOTIFY_GREEN)
    screen.blit(title, (box.x + 24, box.y + 20))
    screen.blit(font_sm.render("A browser tab will open on this Mac automatically.", True, TEXT), (box.x + 24, box.y + 52))

    if qr_surface:
        qr_x = box.x + 32
        qr_y = box.y + 88
        pad = pygame.Rect(qr_x - 8, qr_y - 8, qr_surface.get_width() + 16, qr_surface.get_height() + 16)
        pygame.draw.rect(screen, (240, 240, 240), pad, border_radius=4)
        screen.blit(qr_surface, (qr_x, qr_y))
        tx = qr_x + qr_surface.get_width() + 28
        for i, line in enumerate(
            _wrap_text(
                font_sm,
                "If no browser opened, scan this QR on this Mac or open the Spotify login link here.",
                250,
            )
        ):
            screen.blit(font_sm.render(line, True, TEXT), (tx, box.y + 100 + i * 22))
    else:
        screen.blit(font_sm.render("Starting Spotify login...", True, TEXT), (box.x + 24, box.y + 100))

    for i, line in enumerate(_wrap_text(font_sm, status_line, 500)):
        screen.blit(font_sm.render(line, True, WARN if "fail" in line.lower() else HEAD), (box.x + 24, box.y + 300 + i * 22))


def _start_connect_flow() -> tuple[threading.Thread, list]:
    result: list = [None]

    def worker() -> None:
        # open_browser=True: spotipy starts localhost:8888 FIRST, then opens the browser
        result[0] = connect_spotify(open_browser=True)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread, result


def open_settings_menu(
    default_display: int | None,
    default_mode: str,
    default_window_size: tuple[int, int] | None,
    *,
    default_spotify: bool = True,
) -> LaunchSettings | None:
    pygame.init()
    monitors = list_displays()
    pygame.display.set_caption("TheMatrix")
    screen = pygame.display.set_mode((920, 820))
    clock = pygame.time.Clock()

    family = default_font_name()
    font_title = get_font(40, name=family, bold=True)
    font_md = get_font(22, name=family)
    font_sm = get_font(17, name=family)

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

    dd_monitor = Dropdown("Monitor", monitor_labels, default_monitor_idx, 120, 470, 680, 42)
    dd_mode = Dropdown("Display mode", MODE_OPTIONS, _closest_index(MODE_OPTIONS, default_mode), 120, 570, 680, 42)
    dd_res = Dropdown(
        "Windowed resolution",
        res_labels,
        _closest_index(res_labels, f"{dws[0]}x{dws[1]}"),
        120,
        670,
        680,
        42,
    )

    field_client_id = TextField("Client ID", 120, 200, 560, 38)
    field_client_secret = TextField("Client Secret", 120, 248, 560, 38, secret=True)
    paste_id_btn = pygame.Rect(690, 200, 90, 38)
    paste_secret_btn = pygame.Rect(690, 248, 90, 38)

    connect_btn = pygame.Rect(120, 330, 240, 44)
    save_connect_btn = pygame.Rect(380, 330, 220, 44)
    disconnect_btn = pygame.Rect(620, 330, 180, 44)
    rain_only_btn = pygame.Rect(120, 382, 200, 40)
    launch_btn = pygame.Rect(120, 740, 280, 54)
    cancel_btn = pygame.Rect(430, 740, 180, 54)

    enable_spotify = default_spotify
    status_note = get_status().message
    mouse_pos = (0, 0)
    connect_thread: threading.Thread | None = None
    connect_result: list = []
    connect_modal = False
    connect_status = "Waiting for Spotify login..."
    qr_surface: pygame.Surface | None = None
    show_setup_fields = not credentials_configured()

    def blur_fields() -> None:
        field_client_id._set_active(False)
        field_client_secret._set_active(False)

    def paste_into(field: TextField) -> None:
        blur_fields()
        field._set_active(True)
        field.paste_from_clipboard()

    def finish() -> LaunchSettings | None:
        idx = int(dd_monitor.value.split("]", 1)[0][1:])
        mode = dd_mode.value
        blur_fields()
        pygame.quit()
        return LaunchSettings(idx, mode, _parse_res(dd_res.value), enable_spotify=enable_spotify)

    def begin_connect(*, save_first: bool = False) -> bool:
        nonlocal connect_modal, connect_thread, connect_result, connect_status, qr_surface, status_note, enable_spotify, show_setup_fields

        if save_first:
            cid = field_client_id.text.strip()
            secret = field_client_secret.text.strip()
            if not cid or not secret:
                status_note = "Enter Client ID and Client Secret first."
                return False
            save_defaults_credentials(cid, secret)
            show_setup_fields = False

        if not credentials_configured():
            status_note = "Add Spotify app credentials, then click Connect."
            show_setup_fields = True
            return False

        auth_url = get_authorize_url()
        if auth_url:
            qr_surface = make_qr_surface(auth_url)

        connect_modal = True
        connect_status = "Waiting for Spotify — approve access in the browser window on this Mac."
        connect_thread, connect_result = _start_connect_flow()
        return True

    while True:
        if connect_modal and connect_thread and not connect_thread.is_alive():
            connect_modal = False
            ok, status_note, _name = connect_result[0] or (False, "Login cancelled", "")
            if ok:
                enable_spotify = True
            connect_thread = None

        spotify_status = get_status()
        show_setup_fields = not credentials_configured()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return None
            if event.type == pygame.MOUSEMOTION:
                mouse_pos = event.pos
            if event.type == pygame.KEYDOWN:
                mods = event.mod | pygame.key.get_mods()
                if mods & pygame.KMOD_META:
                    continue
                if event.key == pygame.K_ESCAPE:
                    if connect_modal:
                        connect_modal = False
                        connect_status = "Login cancelled."
                        continue
                    pygame.quit()
                    return None
                if connect_modal:
                    continue
                if show_setup_fields and field_client_id.handle_event(event):
                    field_client_secret._set_active(False)
                    continue
                if show_setup_fields and field_client_secret.handle_event(event):
                    field_client_id._set_active(False)
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return finish()
            if event.type == pygame.TEXTINPUT and show_setup_fields and not connect_modal:
                if field_client_id.handle_event(event):
                    continue
                if field_client_secret.handle_event(event):
                    continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if connect_modal:
                    continue
                if show_setup_fields:
                    if field_client_id.handle_event(event):
                        field_client_secret._set_active(False)
                        continue
                    if field_client_secret.handle_event(event):
                        field_client_id._set_active(False)
                        continue
                    blur_fields()
                if show_setup_fields and paste_id_btn.collidepoint(pos):
                    paste_into(field_client_id)
                    continue
                if show_setup_fields and paste_secret_btn.collidepoint(pos):
                    paste_into(field_client_secret)
                    continue
                if connect_btn.collidepoint(pos):
                    begin_connect()
                    continue
                if save_connect_btn.collidepoint(pos) and show_setup_fields:
                    begin_connect(save_first=True)
                    continue
                if disconnect_btn.collidepoint(pos) and is_logged_in():
                    disconnect_spotify()
                    status_note = "Disconnected. Click Connect Spotify to log in again."
                    continue
                if rain_only_btn.collidepoint(pos):
                    enable_spotify = not enable_spotify
                    continue
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
                    return finish()
                if cancel_btn.collidepoint(pos):
                    blur_fields()
                    pygame.quit()
                    return None
                dd_monitor.open = False
                dd_mode.open = False
                dd_res.open = False

        screen.fill(BG)
        frame = pygame.Surface((760, 760), pygame.SRCALPHA)
        frame.fill((*PANEL, 220))
        pygame.draw.rect(frame, BORDER, frame.get_rect(), width=2)
        screen.blit(frame, (80, 24))

        screen.blit(font_title.render("THE MATRIX", True, HEAD), (110, 50))
        screen.blit(font_sm.render("Launch settings", True, DIM), (110, 96))

        screen.blit(font_md.render("SPOTIFY", True, SPOTIFY_GREEN), (120, 128))
        if spotify_status.logged_in:
            status_color = SPOTIFY_GREEN
            status_text = f"Connected as {spotify_status.display_name or 'Spotify user'}"
        elif show_setup_fields:
            status_color = WARN
            status_text = status_note if status_note.startswith("Enter") else (
                "One-time setup: paste keys from developer.spotify.com/dashboard"
            )
        else:
            status_color = TEXT
            status_text = status_note if status_note else spotify_status.message

        screen.blit(font_sm.render(status_text[:72], True, status_color), (120, 158))

        if show_setup_fields:
            field_client_id.draw(screen, font_sm, font_md)
            field_client_secret.draw(screen, font_sm, font_md)
            _draw_button(
                screen,
                paste_id_btn,
                "Paste",
                font_sm,
                active=not connect_modal,
                accent=TEXT,
                hover=paste_id_btn.collidepoint(mouse_pos),
            )
            _draw_button(
                screen,
                paste_secret_btn,
                "Paste",
                font_sm,
                active=not connect_modal,
                accent=TEXT,
                hover=paste_secret_btn.collidepoint(mouse_pos),
            )
            screen.blit(
                font_sm.render("Redirect URI: http://127.0.0.1:8888/callback", True, DIM),
                (120, 292),
            )
            screen.blit(
                font_sm.render("Click Paste to insert from clipboard.", True, DIM),
                (120, 314),
            )

        _draw_button(
            screen,
            connect_btn,
            "Connect Spotify",
            font_md,
            active=not connect_modal,
            accent=SPOTIFY_GREEN,
            hover=connect_btn.collidepoint(mouse_pos),
        )
        if show_setup_fields:
            _draw_button(
                screen,
                save_connect_btn,
                "Save & Connect",
                font_md,
                active=not connect_modal,
                accent=HEAD,
                hover=save_connect_btn.collidepoint(mouse_pos),
            )
        _draw_button(
            screen,
            disconnect_btn,
            "Disconnect",
            font_md,
            active=is_logged_in() and not connect_modal,
            hover=disconnect_btn.collidepoint(mouse_pos),
        )
        rain_label = "Rain only ✓" if not enable_spotify else "Rain only"
        _draw_button(
            screen,
            rain_only_btn,
            rain_label,
            font_md,
            active=not connect_modal,
            hover=rain_only_btn.collidepoint(mouse_pos),
        )

        pygame.draw.line(screen, BORDER, (120, 430), (800, 430), 1)
        screen.blit(font_md.render("DISPLAY", True, HEAD), (120, 444))

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
            hint = font_sm.render("Resolution applies to windowed mode only.", True, DIM)
            screen.blit(hint, (120, 718))

        _draw_button(screen, launch_btn, "LAUNCH", font_md, hover=launch_btn.collidepoint(mouse_pos))
        _draw_button(screen, cancel_btn, "Cancel", font_md, accent=TEXT, hover=cancel_btn.collidepoint(mouse_pos))

        if connect_modal:
            _draw_connect_modal(
                screen,
                font_md,
                font_sm,
                qr_surface=qr_surface,
                status_line=connect_status,
            )

        pygame.display.flip()
        clock.tick(60)
