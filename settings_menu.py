"""Pre-launch settings menu for Spotify, display, mode, and resolution."""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass

import pygame

from display_setup import list_displays
from font_setup import default_font_name, get_font
from matrix_ui import draw_keybind_table, draw_settings_frame, keybind_rows
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
from youtube_source import load_youtube_config, save_youtube_config, youtube_configured

# Colors
BG = (2, 16, 8)
PANEL = (5, 24, 12)
CARD = (8, 32, 16)
BORDER = (20, 120, 70)
HEAD = (185, 255, 185)
TEXT = (130, 220, 150)
HINT = (70, 150, 95)
WARN = (255, 200, 60)
SPOTIFY_GREEN = (30, 215, 96)
BTN = (10, 42, 22)
BTN_HOVER = (16, 62, 34)
BTN_PRIMARY = (14, 72, 36)
FIELD_BG = (4, 28, 14)

WIN_W, WIN_H = 1000, 900
FRAME_X, FRAME_Y = 50, 36
FRAME_W, FRAME_H = 900, 828
PAD = 24


@dataclass
class LaunchSettings:
    display_index: int
    mode: str
    window_size: tuple[int, int]
    enable_spotify: bool = True


MODE_CHOICES: list[tuple[str, str]] = [
    ("borderless", "Fullscreen on monitor (recommended)"),
    ("windowed", "Windowed"),
    ("exclusive", "Exclusive fullscreen (advanced)"),
]
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
            hit = self.rect.collidepoint(event.pos)
            if hit:
                self._set_active(True)
            elif self.active:
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
        return False

    def draw(self, screen: pygame.Surface, font_sm: pygame.font.Font, font_md: pygame.font.Font) -> None:
        screen.blit(font_sm.render(self.label, True, HINT), (self.rect.x, self.rect.y - 22))
        pygame.draw.rect(screen, FIELD_BG, self.rect, border_radius=6)
        border = SPOTIFY_GREEN if self.active else BORDER
        pygame.draw.rect(screen, border, self.rect, width=2, border_radius=6)
        shown = ("•" * len(self.text)) if self.secret and self.text else self.text
        if self.active and pygame.time.get_ticks() % 1000 < 500:
            shown = shown[: self._cursor] + "|" + shown[self._cursor :]
        screen.blit(
            font_md.render(shown or " ", True, TEXT if self.text else HINT),
            (self.rect.x + 14, self.rect.y + (self.rect.height - font_md.get_height()) // 2),
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
        *,
        values: list[str] | None = None,
        enabled: bool = True,
    ) -> None:
        self.label = label
        self.options = options
        self.values = values or options
        self.selected_idx = max(0, min(selected_idx, len(options) - 1))
        self.rect = pygame.Rect(x, y, w, h)
        self.open = False
        self.enabled = enabled

    @property
    def value(self) -> str:
        return self.values[self.selected_idx]

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
        label_col = HINT if self.enabled else (40, 70, 50)
        screen.blit(font_sm.render(self.label, True, label_col), (self.rect.x, self.rect.y - 24))
        fill = PANEL if self.enabled else (6, 18, 10)
        pygame.draw.rect(screen, fill, self.rect, border_radius=6)
        pygame.draw.rect(screen, BORDER if self.enabled else (30, 60, 40), self.rect, width=2, border_radius=6)
        col = TEXT if self.enabled else (50, 90, 60)
        text = font_md.render(self.options[self.selected_idx], True, col)
        screen.blit(text, (self.rect.x + 14, self.rect.y + (self.rect.height - text.get_height()) // 2))
        if self.enabled:
            caret = font_md.render("▼" if not self.open else "▲", True, HEAD)
            screen.blit(caret, (self.rect.right - 28, self.rect.y + (self.rect.height - caret.get_height()) // 2))

    def draw_menu(self, screen: pygame.Surface, font_md: pygame.font.Font) -> None:
        if not self.open or not self.enabled:
            return
        menu_h = len(self.options) * self.rect.height
        menu_top = self._menu_top(screen.get_height())
        shadow = pygame.Surface((self.rect.width + 10, menu_h + 10), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 80))
        screen.blit(shadow, (self.rect.x + 4, menu_top + 4))
        box = pygame.Rect(self.rect.x, menu_top, self.rect.width, menu_h)
        pygame.draw.rect(screen, PANEL, box, border_radius=6)
        pygame.draw.rect(screen, BORDER, box, width=2, border_radius=6)
        for i, option in enumerate(self.options):
            row = self._option_rect(i, screen.get_height())
            pygame.draw.rect(screen, (14, 50, 28) if i == self.selected_idx else PANEL, row)
            col = HEAD if i == self.selected_idx else TEXT
            text = font_md.render(option, True, col)
            screen.blit(text, (row.x + 14, row.y + (row.height - text.get_height()) // 2))

    def click(self, pos: tuple[int, int], screen_h: int) -> bool:
        if not self.enabled:
            return False
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
    primary: bool = False,
) -> None:
    if not active:
        fill = (6, 20, 10)
        border = (30, 60, 40)
        color = (50, 90, 60)
    elif primary:
        fill = BTN_PRIMARY if not hover else (22, 95, 48)
        border = SPOTIFY_GREEN
        color = HEAD
    elif hover:
        fill = BTN_HOVER
        border = BORDER
        color = accent
    else:
        fill = BTN
        border = BORDER
        color = accent
    pygame.draw.rect(screen, fill, rect, border_radius=8)
    pygame.draw.rect(screen, border, rect, width=2, border_radius=8)
    text = font.render(label, True, color)
    screen.blit(
        text,
        (rect.x + (rect.width - text.get_width()) // 2, rect.y + (rect.height - text.get_height()) // 2),
    )


def _draw_card(screen: pygame.Surface, rect: pygame.Rect, pulse: float = 0.0) -> None:
    from matrix_ui import draw_panel_frame

    draw_panel_frame(screen, rect, 1.0, pulse, fill_alpha=225, brackets=False)
    pygame.draw.rect(screen, BORDER, rect, width=1, border_radius=10)


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
    return lines or [text[:96]]


def _draw_connect_modal(
    screen: pygame.Surface,
    font_lg: pygame.font.Font,
    font_md: pygame.font.Font,
    font_sm: pygame.font.Font,
    *,
    qr_surface: pygame.Surface | None,
    status_line: str,
) -> None:
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    box = pygame.Rect(140, 140, 720, 460)
    from matrix_ui import draw_panel_frame

    draw_panel_frame(screen, box, 1.0, pygame.time.get_ticks() * 0.001, fill_alpha=240)

    screen.blit(font_lg.render("Connect Spotify", True, SPOTIFY_GREEN), (box.x + 32, box.y + 28))
    screen.blit(
        font_sm.render("A browser window will open on this Mac. Approve access, then return here.", True, TEXT),
        (box.x + 32, box.y + 68),
    )

    if qr_surface:
        qr_x = box.x + 40
        qr_y = box.y + 110
        pad = pygame.Rect(qr_x - 10, qr_y - 10, qr_surface.get_width() + 20, qr_surface.get_height() + 20)
        pygame.draw.rect(screen, (235, 235, 235), pad, border_radius=8)
        screen.blit(qr_surface, (qr_x, qr_y))
        tx = qr_x + qr_surface.get_width() + 32
        for i, line in enumerate(_wrap_text(font_sm, "Backup: scan this code on this Mac if the browser did not open.", 280)):
            screen.blit(font_sm.render(line, True, HINT), (tx, box.y + 120 + i * 22))
    else:
        screen.blit(font_sm.render("Starting login...", True, HINT), (box.x + 40, box.y + 120))

    for i, line in enumerate(_wrap_text(font_sm, status_line, 620)):
        screen.blit(font_sm.render(line, True, WARN if "fail" in line.lower() else HEAD), (box.x + 32, box.y + 340 + i * 22))
    screen.blit(font_sm.render("Press Esc to cancel", True, HINT), (box.x + 32, box.y + 400))


def _start_connect_flow() -> tuple[threading.Thread, list]:
    result: list = [None]

    def worker() -> None:
        result[0] = connect_spotify(open_browser=True)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread, result


def _spotify_status_line(logged_in: bool, display_name: str, setup: bool, note: str) -> tuple[str, tuple[int, int, int]]:
    if logged_in:
        return f"Connected as {display_name or 'Spotify user'}", SPOTIFY_GREEN
    if setup:
        return note or "Developer setup: add Spotify app keys below", WARN
    if note:
        return note, TEXT
    return "Not connected — click Connect Spotify before launching", WARN


def open_settings_menu(
    default_display: int | None,
    default_mode: str,
    default_window_size: tuple[int, int] | None,
    *,
    default_spotify: bool = True,
) -> LaunchSettings | None:
    pygame.init()
    monitors = list_displays()
    pygame.display.set_caption("TheMatrix — Setup")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()

    family = default_font_name()
    font_title = get_font(44, name=family, bold=True)
    font_lg = get_font(26, name=family, bold=True)
    font_md = get_font(20, name=family)
    font_sm = get_font(16, name=family)

    cx = FRAME_X + PAD
    content_w = FRAME_W - PAD * 2

    monitor_labels = [f"Display {i + 1}  ·  {w} × {h}" for i, (w, h) in monitors] or ["Display 1  ·  1920 × 1080"]
    mode_labels = [label for _val, label in MODE_CHOICES]
    mode_values = [val for val, _label in MODE_CHOICES]

    default_monitor_idx = max(0, min(default_display or 0, len(monitor_labels) - 1))
    res_labels = [f"{w} × {h}" for (w, h) in WINDOW_RESOLUTIONS]
    dws = default_window_size or (1920, 1080)
    res_key = f"{dws[0]} × {dws[1]}"
    if res_key not in res_labels:
        res_labels.append(res_key)

    # Layout regions (y offsets inside frame)
    spotify_card = pygame.Rect(FRAME_X + 12, FRAME_Y + 88, FRAME_W - 24, 0)  # height set dynamically
    youtube_card = pygame.Rect(FRAME_X + 12, 0, FRAME_W - 24, 0)
    display_card = pygame.Rect(FRAME_X + 12, 0, FRAME_W - 24, 0)

    field_client_id = TextField("Client ID", cx, 0, content_w - 110, 40)
    field_client_secret = TextField("Client Secret", cx, 0, content_w - 110, 40)
    field_youtube_key = TextField("YouTube Data API Key", cx, 0, content_w - 110, 40, secret=True)
    paste_id_btn = pygame.Rect(0, 0, 96, 40)
    paste_secret_btn = pygame.Rect(0, 0, 96, 40)
    paste_youtube_btn = pygame.Rect(0, 0, 96, 40)

    connect_btn = pygame.Rect(0, 0, 220, 46)
    save_connect_btn = pygame.Rect(0, 0, 200, 46)
    disconnect_btn = pygame.Rect(0, 0, 150, 46)
    save_youtube_btn = pygame.Rect(0, 0, 190, 46)
    rain_toggle = pygame.Rect(0, 0, 200, 40)
    launch_btn = pygame.Rect(0, 0, 320, 58)
    cancel_btn = pygame.Rect(0, 0, 140, 58)

    dd_monitor = Dropdown("Which screen?", monitor_labels, default_monitor_idx, cx, 0, content_w, 46)
    dd_mode = Dropdown(
        "How should it appear?",
        mode_labels,
        _closest_index(mode_values, default_mode),
        cx,
        0,
        content_w,
        46,
        values=mode_values,
    )
    dd_res = Dropdown(
        "Window size",
        res_labels,
        _closest_index(res_labels, res_key),
        cx,
        0,
        content_w,
        46,
        enabled=False,
    )

    enable_spotify = default_spotify
    status_note = get_status().message
    youtube_saved = load_youtube_config() or {}
    field_youtube_key.text = str(youtube_saved.get("api_key") or "")
    field_youtube_key._cursor = len(field_youtube_key.text)
    youtube_note = "YouTube search ready." if youtube_configured() else "Add a YouTube API key to enable song search."
    mouse_pos = (0, 0)
    pulse = 0.0
    connect_thread: threading.Thread | None = None
    connect_result: list = []
    connect_modal = False
    connect_status = "Waiting for Spotify login..."
    qr_surface: pygame.Surface | None = None

    def blur_fields() -> None:
        field_client_id._set_active(False)
        field_client_secret._set_active(False)
        field_youtube_key._set_active(False)

    def paste_into(field: TextField) -> None:
        blur_fields()
        field._set_active(True)
        field.paste_from_clipboard()

    def finish() -> LaunchSettings | None:
        idx = monitor_labels.index(dd_monitor.options[dd_monitor.selected_idx])
        blur_fields()
        pygame.quit()
        res_text = dd_res.value.replace(" ", "").replace("×", "x")
        return LaunchSettings(idx, dd_mode.value, _parse_res(res_text), enable_spotify=enable_spotify)

    def begin_connect(*, save_first: bool = False) -> bool:
        nonlocal connect_modal, connect_thread, connect_result, connect_status, qr_surface, status_note, enable_spotify

        if save_first:
            cid = field_client_id.text.strip()
            secret = field_client_secret.text.strip()
            if not cid or not secret:
                status_note = "Enter Client ID and Client Secret first."
                return False
            save_defaults_credentials(cid, secret)

        if not credentials_configured():
            status_note = "Add Spotify credentials below, then click Save & Connect."
            return False

        auth_url = get_authorize_url()
        if auth_url:
            qr_surface = make_qr_surface(auth_url)
        connect_modal = True
        connect_status = "Approve Spotify in your browser, then return to this window."
        connect_thread, connect_result = _start_connect_flow()
        return True

    def _layout() -> None:
        show_setup = not credentials_configured()
        spotify_h = 230 if show_setup else 160
        youtube_h = 150
        spotify_card.height = spotify_h
        youtube_card.y = spotify_card.bottom + 20
        youtube_card.height = youtube_h
        display_card.y = youtube_card.bottom + 20
        display_card.height = 250 if dd_mode.value == "windowed" else 190

        inner_y = spotify_card.y + 52
        if show_setup:
            field_client_id.rect.topleft = (cx, inner_y)
            paste_id_btn.topleft = (field_client_id.rect.right + 12, inner_y)
            field_client_secret.rect.topleft = (cx, inner_y + 58)
            paste_secret_btn.topleft = (field_client_secret.rect.right + 12, inner_y + 58)
            btn_y = inner_y + 130
        else:
            btn_y = inner_y + 10

        connect_btn.topleft = (cx, btn_y)
        save_connect_btn.topleft = (connect_btn.right + 14, btn_y) if show_setup else (0, 0)
        disconnect_btn.topleft = (cx + 240, btn_y) if not show_setup else (save_connect_btn.right + 14, btn_y)
        rain_toggle.topleft = (cx, btn_y + 56)

        youtube_y = youtube_card.y + 56
        field_youtube_key.rect.topleft = (cx, youtube_y)
        paste_youtube_btn.topleft = (field_youtube_key.rect.right + 12, youtube_y)
        save_youtube_btn.topleft = (cx, youtube_y + 56)

        disp_y = display_card.y + 52
        dd_monitor.rect.topleft = (cx, disp_y)
        dd_mode.rect.topleft = (cx, disp_y + 78)
        dd_res.rect.topleft = (cx, disp_y + 156)
        dd_res.enabled = dd_mode.value == "windowed"

        footer_y = FRAME_Y + FRAME_H - 88
        launch_btn.topleft = (FRAME_X + FRAME_W // 2 - 240, footer_y)
        cancel_btn.topleft = (launch_btn.right + 16, footer_y)

    while True:
        if connect_modal and connect_thread and not connect_thread.is_alive():
            connect_modal = False
            ok, status_note, _name = connect_result[0] or (False, "Login cancelled", "")
            if ok:
                enable_spotify = True
            connect_thread = None

        spotify_status = get_status()
        show_setup = not credentials_configured()
        _layout()
        pulse = pygame.time.get_ticks() * 0.001

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return None
            if event.type == pygame.MOUSEMOTION:
                mouse_pos = event.pos
            if event.type == pygame.KEYDOWN:
                if event.mod & pygame.KMOD_META:
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
                if show_setup and field_client_id.handle_event(event):
                    field_youtube_key._set_active(False)
                    field_client_secret._set_active(False)
                    continue
                if show_setup and field_client_secret.handle_event(event):
                    field_youtube_key._set_active(False)
                    field_client_id._set_active(False)
                    continue
                if field_youtube_key.handle_event(event):
                    field_client_id._set_active(False)
                    field_client_secret._set_active(False)
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return finish()
            if event.type == pygame.TEXTINPUT and show_setup and not connect_modal:
                if field_client_id.handle_event(event) or field_client_secret.handle_event(event):
                    continue
            if event.type == pygame.TEXTINPUT and not connect_modal:
                if field_youtube_key.handle_event(event):
                    continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if connect_modal:
                    continue
                if show_setup:
                    if field_client_id.handle_event(event):
                        field_youtube_key._set_active(False)
                        field_client_secret._set_active(False)
                        continue
                    if field_client_secret.handle_event(event):
                        field_youtube_key._set_active(False)
                        field_client_id._set_active(False)
                        continue
                if field_youtube_key.handle_event(event):
                    field_client_id._set_active(False)
                    field_client_secret._set_active(False)
                    continue
                blur_fields()
                if show_setup and paste_id_btn.collidepoint(pos):
                    paste_into(field_client_id)
                    continue
                if show_setup and paste_secret_btn.collidepoint(pos):
                    paste_into(field_client_secret)
                    continue
                if paste_youtube_btn.collidepoint(pos):
                    paste_into(field_youtube_key)
                    continue
                if connect_btn.collidepoint(pos):
                    begin_connect()
                    continue
                if show_setup and save_connect_btn.collidepoint(pos):
                    begin_connect(save_first=True)
                    continue
                if save_youtube_btn.collidepoint(pos):
                    api_key = field_youtube_key.text.strip()
                    if not api_key:
                        youtube_note = "Enter a YouTube API key first."
                    else:
                        save_youtube_config(api_key)
                        youtube_note = "YouTube API key saved."
                    continue
                if disconnect_btn.collidepoint(pos) and is_logged_in():
                    disconnect_spotify()
                    status_note = "Disconnected. Click Connect Spotify to sign in again."
                    continue
                if rain_toggle.collidepoint(pos):
                    enable_spotify = not enable_spotify
                    continue
                if dd_monitor.click(pos, screen.get_height()):
                    dd_mode.open = dd_res.open = False
                    continue
                if dd_mode.click(pos, screen.get_height()):
                    dd_monitor.open = dd_res.open = False
                    continue
                if dd_res.enabled and dd_res.click(pos, screen.get_height()):
                    dd_monitor.open = dd_mode.open = False
                    continue
                if launch_btn.collidepoint(pos):
                    return finish()
                if cancel_btn.collidepoint(pos):
                    blur_fields()
                    pygame.quit()
                    return None
                dd_monitor.open = dd_mode.open = dd_res.open = False

        # --- Draw ---
        screen.fill(BG)
        frame_rect = pygame.Rect(FRAME_X, FRAME_Y, FRAME_W, FRAME_H)
        draw_settings_frame(screen, frame_rect, pulse)

        screen.blit(font_title.render("THE MATRIX", True, HEAD), (FRAME_X + PAD, FRAME_Y + 16))
        screen.blit(
            font_sm.render("Set up Spotify, YouTube search, and your display, then launch.", True, HINT),
            (FRAME_X + PAD, FRAME_Y + 58),
        )

        keymap_rows = keybind_rows(include_spotify=True)
        keymap_w = int(14 * 2 + 52 + 14 + max(font_sm.size(a)[0] for _, a in keymap_rows))
        keymap_rect = draw_keybind_table(
            screen,
            FRAME_X + FRAME_W - keymap_w - PAD,
            FRAME_Y + 14,
            font_sm,
            font_md,
            keymap_rows,
            1.0,
            pulse,
            title="KEYMAP",
            compact=True,
        )
        pygame.draw.line(
            screen,
            (*BORDER, 120),
            (FRAME_X + PAD, keymap_rect.bottom + 10),
            (FRAME_X + FRAME_W - PAD - keymap_rect.width - 20, keymap_rect.bottom + 10),
            1,
        )

        _draw_card(screen, spotify_card, pulse)
        screen.blit(font_lg.render("① Spotify", True, SPOTIFY_GREEN), (spotify_card.x + 20, spotify_card.y + 16))

        status_text, status_color = _spotify_status_line(
            spotify_status.logged_in,
            spotify_status.display_name,
            show_setup,
            status_note,
        )
        status_y = spotify_card.y + 48 if show_setup else spotify_card.y + 44
        if not show_setup:
            for i, line in enumerate(_wrap_text(font_sm, status_text, content_w - 40)):
                screen.blit(font_sm.render(line, True, status_color), (cx, status_y + i * 20))

        if show_setup:
            screen.blit(font_sm.render("Developer setup (one time)", True, HINT), (cx, spotify_card.y + 44))
            for i, line in enumerate(_wrap_text(font_sm, status_text, content_w - 40)):
                screen.blit(font_sm.render(line, True, status_color), (cx, spotify_card.y + 66 + i * 18))
            field_client_id.draw(screen, font_sm, font_md)
            field_client_secret.draw(screen, font_sm, font_md)
            _draw_button(screen, paste_id_btn, "Paste", font_sm, hover=paste_id_btn.collidepoint(mouse_pos))
            _draw_button(screen, paste_secret_btn, "Paste", font_sm, hover=paste_secret_btn.collidepoint(mouse_pos))
            screen.blit(font_sm.render("Redirect URI: http://127.0.0.1:8888/callback", True, HINT), (cx, field_client_secret.rect.bottom + 8))

        _draw_button(
            screen, connect_btn, "Connect Spotify", font_md,
            accent=SPOTIFY_GREEN, hover=connect_btn.collidepoint(mouse_pos), active=not connect_modal,
        )
        if show_setup:
            _draw_button(
                screen, save_connect_btn, "Save & Connect", font_md,
                hover=save_connect_btn.collidepoint(mouse_pos), active=not connect_modal,
            )
        if is_logged_in():
            _draw_button(
                screen, disconnect_btn, "Sign out", font_md,
                hover=disconnect_btn.collidepoint(mouse_pos), active=not connect_modal, accent=TEXT,
            )

        toggle_label = "☑ Skip Spotify (rain only)" if not enable_spotify else "☐ Skip Spotify (rain only)"
        _draw_button(screen, rain_toggle, toggle_label, font_sm, hover=rain_toggle.collidepoint(mouse_pos), active=not connect_modal)

        _draw_card(screen, youtube_card, pulse)
        screen.blit(font_lg.render("② YouTube Search", True, HEAD), (youtube_card.x + 20, youtube_card.y + 16))
        youtube_color = SPOTIFY_GREEN if youtube_configured() else WARN
        for i, line in enumerate(_wrap_text(font_sm, youtube_note, content_w - 40)):
            screen.blit(font_sm.render(line, True, youtube_color), (cx, youtube_card.y + 36 + i * 18))
        field_youtube_key.draw(screen, font_sm, font_md)
        _draw_button(
            screen, paste_youtube_btn, "Paste", font_sm, hover=paste_youtube_btn.collidepoint(mouse_pos)
        )
        _draw_button(
            screen, save_youtube_btn, "Save API Key", font_md, hover=save_youtube_btn.collidepoint(mouse_pos)
        )

        _draw_card(screen, display_card, pulse)
        screen.blit(font_lg.render("③ Display", True, HEAD), (display_card.x + 20, display_card.y + 16))
        screen.blit(font_sm.render("Pick your monitor and how the Matrix should fill the screen.", True, HINT), (cx, display_card.y + 46))

        dd_monitor.draw(screen, font_sm, font_md)
        dd_mode.draw(screen, font_sm, font_md)
        if dd_mode.value == "windowed":
            dd_res.draw(screen, font_sm, font_md)
        if dd_monitor.open:
            dd_monitor.draw_menu(screen, font_md)
        elif dd_mode.open:
            dd_mode.draw_menu(screen, font_md)
        elif dd_res.open:
            dd_res.draw_menu(screen, font_md)

        footer_y = FRAME_Y + FRAME_H - 88
        pygame.draw.line(screen, BORDER, (FRAME_X + PAD, footer_y - 16), (FRAME_X + FRAME_W - PAD, footer_y - 16), 1)
        screen.blit(
            font_sm.render("Enter = Launch   ·   Esc = Cancel", True, HINT),
            (FRAME_X + PAD, footer_y - 38),
        )

        _draw_button(screen, launch_btn, "▶  LAUNCH", font_lg, primary=True, hover=launch_btn.collidepoint(mouse_pos))
        _draw_button(screen, cancel_btn, "Cancel", font_md, accent=TEXT, hover=cancel_btn.collidepoint(mouse_pos))

        if connect_modal:
            _draw_connect_modal(screen, font_lg, font_md, font_sm, qr_surface=qr_surface, status_line=connect_status)

        pygame.display.flip()
        clock.tick(60)
