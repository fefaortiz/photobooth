from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame


@dataclass
class Button:
    rect: pygame.Rect
    text: str
    background_color: tuple[int, int, int]
    text_color: tuple[int, int, int]
    border_radius: int = 18
    enabled: bool = True

    def draw(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        pointer_position: Optional[tuple[int, int]] = None,
    ) -> None:
        color = self.background_color

        if not self.enabled:
            color = tuple(max(0, value - 45) for value in color)
        elif pointer_position and self.rect.collidepoint(pointer_position):
            color = tuple(min(255, value + 18) for value in color)

        pygame.draw.rect(
            screen,
            color,
            self.rect,
            border_radius=self.border_radius,
        )

        label = font.render(self.text, True, self.text_color)
        screen.blit(label, label.get_rect(center=self.rect.center))

    def contains(self, position: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(position)


def draw_centered_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center_y: int,
) -> pygame.Rect:
    surface = font.render(text, True, color)
    rect = surface.get_rect(
        center=(screen.get_width() // 2, center_y)
    )
    screen.blit(surface, rect)
    return rect


def draw_multiline_centered(
    screen: pygame.Surface,
    lines: list[str],
    font: pygame.font.Font,
    color: tuple[int, int, int],
    start_y: int,
    line_gap: int = 8,
) -> None:
    y = start_y

    for line in lines:
        surface = font.render(line, True, color)
        rect = surface.get_rect(
            center=(screen.get_width() // 2, y)
        )
        screen.blit(surface, rect)
        y += surface.get_height() + line_gap


def load_optional_background(
    path: Path,
    screen_size: tuple[int, int],
) -> Optional[pygame.Surface]:
    if not path.exists():
        return None

    try:
        image = pygame.image.load(str(path)).convert()
        return pygame.transform.scale(image, screen_size)
    except pygame.error as error:
        print(f"[AVISO] Não foi possível carregar {path}: {error}")
        return None


def draw_dark_overlay(
    screen: pygame.Surface,
    alpha: int = 130,
) -> None:
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, alpha))
    screen.blit(overlay, (0, 0))


def event_pointer_position(
    event: pygame.event.Event,
    screen_size: tuple[int, int],
) -> Optional[tuple[int, int]]:
    """
    Converte clique de mouse ou toque em coordenadas da tela.

    Em muitos ambientes SDL, o toque já aparece como clique de mouse.
    FINGERDOWN é tratado também para maior compatibilidade.
    """
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        return event.pos

    if event.type == pygame.FINGERDOWN:
        width, height = screen_size
        return int(event.x * width), int(event.y * height)

    return None
