from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
import threading
import time

import cv2
import pygame

import config
from camera_service import CameraError, CameraService, frame_to_surface
from printer_service import PrintResult, PrinterService
from ui import (
    Button,
    draw_centered_text,
    draw_dark_overlay,
    draw_multiline_centered,
    event_pointer_position,
    load_optional_background,
)


class AppState(Enum):
    IDLE = auto()
    PREVIEW = auto()
    COUNTDOWN = auto()
    REVIEW = auto()
    PROCESSING = auto()
    DONE = auto()
    ERROR = auto()


class PhotoboothApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(config.APP_TITLE)
        pygame.mouse.set_visible(config.SHOW_MOUSE_CURSOR)

        flags = pygame.FULLSCREEN if config.FULLSCREEN else 0
        self.screen = pygame.display.set_mode(config.DISPLAY_SIZE, flags)
        self.screen_size = self.screen.get_size()
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont(None, 78, bold=True)
        self.font_subtitle = pygame.font.SysFont(None, 38)
        self.font_button = pygame.font.SysFont(None, 42, bold=True)
        self.font_countdown = pygame.font.SysFont(None, 300, bold=True)
        self.font_small = pygame.font.SysFont(None, 30)

        self.camera = CameraService(
            device=config.CAMERA_DEVICE,
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
            fps=config.CAMERA_FPS,
            fourcc=config.CAMERA_FOURCC,
            warmup_frames=config.CAMERA_WARMUP_FRAMES,
        )

        self.printer = PrinterService(
            mode=config.PRINTER_MODE,
            printer_name=config.PRINTER_NAME,
        )

        self.backgrounds = {
            "attract": load_optional_background(
                config.ATTRACT_IMAGE,
                self.screen_size,
            ),
            "printing": load_optional_background(
                config.PRINTING_IMAGE,
                self.screen_size,
            ),
            "done": load_optional_background(
                config.DONE_IMAGE,
                self.screen_size,
            ),
        }

        self.state = AppState.IDLE
        self.running = True

        self.latest_frame = None
        self.captured_frame = None
        self.captured_surface = None
        self.photo_path: Path | None = None

        self.countdown_started_at = 0.0
        self.processing_started_at = 0.0
        self.done_started_at = 0.0

        self.processing_thread: threading.Thread | None = None
        self.processing_result: PrintResult | None = None

        self.error_message = ""
        self.camera_failure_count = 0

        self._build_buttons()

    def _build_buttons(self) -> None:
        width, height = self.screen_size

        main_button_width = min(430, width - 80)
        main_button_height = 92
        main_x = (width - main_button_width) // 2
        main_y = height - 150

        self.start_button = Button(
            pygame.Rect(
                main_x,
                main_y,
                main_button_width,
                main_button_height,
            ),
            "TIRAR FOTO",
            config.PRIMARY_BUTTON_COLOR,
            config.PRIMARY_BUTTON_TEXT_COLOR,
        )

        bottom_button_width = min(330, (width - 120) // 2)
        bottom_button_height = 82
        gap = 30
        total_width = bottom_button_width * 2 + gap
        left_x = (width - total_width) // 2
        buttons_y = height - 125

        self.cancel_button = Button(
            pygame.Rect(40, 35, 190, 70),
            "CANCELAR",
            config.SECONDARY_BUTTON_COLOR,
            config.SECONDARY_BUTTON_TEXT_COLOR,
        )

        self.capture_button = Button(
            pygame.Rect(
                width - 250,
                height - 120,
                210,
                80,
            ),
            "FOTO",
            config.PRIMARY_BUTTON_COLOR,
            config.PRIMARY_BUTTON_TEXT_COLOR,
        )

        self.repeat_button = Button(
            pygame.Rect(
                left_x,
                buttons_y,
                bottom_button_width,
                bottom_button_height,
            ),
            "REPETIR",
            config.SECONDARY_BUTTON_COLOR,
            config.SECONDARY_BUTTON_TEXT_COLOR,
        )

        finish_label = "IMPRIMIR" if self.printer.enabled else "FINALIZAR"
        self.finish_button = Button(
            pygame.Rect(
                left_x + bottom_button_width + gap,
                buttons_y,
                bottom_button_width,
                bottom_button_height,
            ),
            finish_label,
            config.PRIMARY_BUTTON_COLOR,
            config.PRIMARY_BUTTON_TEXT_COLOR,
        )

        self.done_button = Button(
            pygame.Rect(
                main_x,
                main_y,
                main_button_width,
                main_button_height,
            ),
            "NOVA FOTO",
            config.PRIMARY_BUTTON_COLOR,
            config.PRIMARY_BUTTON_TEXT_COLOR,
        )

        self.retry_button = Button(
            pygame.Rect(
                main_x,
                main_y,
                main_button_width,
                main_button_height,
            ),
            "TENTAR NOVAMENTE",
            config.PRIMARY_BUTTON_COLOR,
            config.PRIMARY_BUTTON_TEXT_COLOR,
        )

    def initialize_camera(self) -> None:
        try:
            self.camera.open()
            settings = self.camera.actual_settings()
            print(
                "Câmera aberta: "
                f"{settings.get('width')}x{settings.get('height')} "
                f"a {settings.get('fps'):.1f} fps"
            )
        except CameraError as error:
            self._set_error(str(error))

    def _set_error(self, message: str) -> None:
        print(f"[ERRO] {message}")
        self.error_message = message
        self.state = AppState.ERROR

    def _go_to_idle(self) -> None:
        self.latest_frame = None
        self.captured_frame = None
        self.captured_surface = None
        self.photo_path = None
        self.processing_result = None
        self.camera_failure_count = 0
        self.state = AppState.IDLE

    def _go_to_preview(self) -> None:
        try:
            if not self.camera.is_open:
                self.camera.open()

            self.camera.flush(5)
            self.camera_failure_count = 0
            self.state = AppState.PREVIEW
        except CameraError as error:
            self._set_error(str(error))

    def _start_countdown(self) -> None:
        if self.latest_frame is None:
            return

        self.countdown_started_at = time.monotonic()
        self.state = AppState.COUNTDOWN

    def _capture_photo(self) -> None:
        if self.latest_frame is None:
            self._set_error("Nenhum frame da câmera estava disponível para salvar.")
            return

        self.captured_frame = self.latest_frame.copy()

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.photo_path = config.PHOTOS_DIR / f"foto_{timestamp}.jpg"

        try:
            self.camera.save_frame(
                self.captured_frame,
                self.photo_path,
                jpeg_quality=config.JPEG_QUALITY,
                mirror=config.MIRROR_SAVED_PHOTO,
            )
        except CameraError as error:
            self._set_error(str(error))
            return

        review_frame = self.captured_frame
        if config.MIRROR_SAVED_PHOTO:
            review_frame = cv2.flip(review_frame, 1)

        self.captured_surface = frame_to_surface(
            review_frame,
            self.screen_size,
            mirror=False,
            cover=True,
        )

        print(f"Foto salva: {self.photo_path}")
        self.state = AppState.REVIEW

    def _discard_photo(self) -> None:
        if self.photo_path and self.photo_path.exists():
            try:
                self.photo_path.unlink()
            except OSError as error:
                print(f"[AVISO] Não foi possível excluir {self.photo_path}: {error}")

        self.photo_path = None
        self.captured_frame = None
        self.captured_surface = None
        self._go_to_preview()

    def _start_processing(self) -> None:
        if self.photo_path is None:
            self._set_error("Não há uma foto salva para processar.")
            return

        self.processing_started_at = time.monotonic()
        self.processing_result = None
        self.state = AppState.PROCESSING

        self.processing_thread = threading.Thread(
            target=self._processing_worker,
            daemon=True,
        )
        self.processing_thread.start()

    def _processing_worker(self) -> None:
        try:
            self.processing_result = self.printer.process_photo(self.photo_path)
        except Exception as error:
            self.processing_result = PrintResult(
                False,
                f"Falha inesperada durante o processamento: {error}",
            )

    def _finish_processing_if_ready(self) -> None:
        if self.processing_thread is None:
            return

        if self.processing_thread.is_alive():
            return

        elapsed = time.monotonic() - self.processing_started_at
        if elapsed < config.MIN_PROCESSING_SCREEN_SECONDS:
            return

        if self.processing_result is None:
            self._set_error("O processamento terminou sem resultado.")
            return

        if not self.processing_result.success:
            self._set_error(self.processing_result.message)
            return

        self.done_started_at = time.monotonic()
        self.state = AppState.DONE

    def _read_camera(self) -> None:
        try:
            ok, frame = self.camera.read()
        except CameraError as error:
            self._set_error(str(error))
            return

        if not ok:
            self.camera_failure_count += 1

            if self.camera_failure_count >= 20:
                self._set_error(
                    "A câmera parou de fornecer imagens. "
                    "Verifique a conexão USB."
                )
            return

        self.camera_failure_count = 0
        self.latest_frame = frame

    def _handle_global_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            self.running = False
            return True

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.running = False
                return True

            if event.key == pygame.K_SPACE:
                if self.state == AppState.IDLE:
                    self._go_to_preview()
                elif self.state == AppState.PREVIEW:
                    self._start_countdown()
                return True

        return False

    def _handle_pointer(self, position: tuple[int, int]) -> None:
        if self.state == AppState.IDLE:
            if self.start_button.contains(position):
                self._go_to_preview()

        elif self.state == AppState.PREVIEW:
            if self.cancel_button.contains(position):
                self._go_to_idle()
            elif self.capture_button.contains(position):
                self._start_countdown()

        elif self.state == AppState.REVIEW:
            if self.repeat_button.contains(position):
                self._discard_photo()
            elif self.finish_button.contains(position):
                self._start_processing()

        elif self.state == AppState.DONE:
            if self.done_button.contains(position):
                self._go_to_idle()

        elif self.state == AppState.ERROR:
            if self.retry_button.contains(position):
                self.camera.release()
                self.error_message = ""
                self.initialize_camera()
                if self.state != AppState.ERROR:
                    self._go_to_idle()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if self._handle_global_event(event):
                continue

            position = event_pointer_position(event, self.screen_size)
            if position is not None:
                self._handle_pointer(position)

    def _draw_background_or_color(
        self,
        key: str,
        fallback_color: tuple[int, int, int],
    ) -> None:
        background = self.backgrounds.get(key)

        if background is not None:
            self.screen.blit(background, (0, 0))
        else:
            self.screen.fill(fallback_color)

    def _draw_idle(self) -> None:
        self._draw_background_or_color(
            "attract",
            config.BACKGROUND_COLOR,
        )

        if self.backgrounds["attract"] is not None:
            draw_dark_overlay(self.screen, 90)

        draw_centered_text(
            self.screen,
            "PHOTO BOOTH",
            self.font_title,
            config.TEXT_COLOR,
            190,
        )
        draw_centered_text(
            self.screen,
            "Toque no botão para começar",
            self.font_subtitle,
            config.SECONDARY_TEXT_COLOR,
            265,
        )

        pointer = pygame.mouse.get_pos()
        self.start_button.draw(
            self.screen,
            self.font_button,
            pointer,
        )

    def _draw_preview(self, countdown_number: int | None = None) -> None:
        if self.latest_frame is not None:
            preview = frame_to_surface(
                self.latest_frame,
                self.screen_size,
                mirror=config.MIRROR_PREVIEW,
                cover=True,
            )
            self.screen.blit(preview, (0, 0))
        else:
            self.screen.fill(config.BACKGROUND_COLOR)
            draw_centered_text(
                self.screen,
                "Inicializando câmera...",
                self.font_subtitle,
                config.TEXT_COLOR,
                self.screen_size[1] // 2,
            )

        pointer = pygame.mouse.get_pos()

        if countdown_number is None:
            self.cancel_button.draw(
                self.screen,
                self.font_small,
                pointer,
            )
            self.capture_button.draw(
                self.screen,
                self.font_button,
                pointer,
            )
        else:
            draw_dark_overlay(self.screen, 45)

            shadow = self.font_countdown.render(
                str(countdown_number),
                True,
                config.COUNTDOWN_SHADOW_COLOR,
            )
            shadow_rect = shadow.get_rect(
                center=(
                    self.screen_size[0] // 2 + 8,
                    self.screen_size[1] // 2 + 8,
                )
            )
            self.screen.blit(shadow, shadow_rect)

            number = self.font_countdown.render(
                str(countdown_number),
                True,
                config.COUNTDOWN_COLOR,
            )
            number_rect = number.get_rect(
                center=(
                    self.screen_size[0] // 2,
                    self.screen_size[1] // 2,
                )
            )
            self.screen.blit(number, number_rect)

    def _draw_review(self) -> None:
        if self.captured_surface is not None:
            self.screen.blit(self.captured_surface, (0, 0))
        else:
            self.screen.fill(config.BACKGROUND_COLOR)

        draw_dark_overlay(self.screen, 35)

        draw_centered_text(
            self.screen,
            "Gostou da foto?",
            self.font_title,
            config.TEXT_COLOR,
            85,
        )

        pointer = pygame.mouse.get_pos()
        self.repeat_button.draw(
            self.screen,
            self.font_button,
            pointer,
        )
        self.finish_button.draw(
            self.screen,
            self.font_button,
            pointer,
        )

    def _draw_processing(self) -> None:
        self._draw_background_or_color(
            "printing",
            config.PANEL_COLOR,
        )

        if self.backgrounds["printing"] is not None:
            draw_dark_overlay(self.screen, 110)

        title = "Enviando para impressão..." if self.printer.enabled else "Salvando sua foto..."

        draw_centered_text(
            self.screen,
            title,
            self.font_title,
            config.TEXT_COLOR,
            self.screen_size[1] // 2 - 25,
        )
        draw_centered_text(
            self.screen,
            "Aguarde um instante",
            self.font_subtitle,
            config.SECONDARY_TEXT_COLOR,
            self.screen_size[1] // 2 + 55,
        )

    def _draw_done(self) -> None:
        self._draw_background_or_color(
            "done",
            config.BACKGROUND_COLOR,
        )

        if self.backgrounds["done"] is not None:
            draw_dark_overlay(self.screen, 100)

        title = "Foto enviada!" if self.printer.enabled else "Foto salva!"

        draw_centered_text(
            self.screen,
            title,
            self.font_title,
            config.TEXT_COLOR,
            210,
        )

        message = (
            self.processing_result.message
            if self.processing_result
            else "Processo concluído."
        )

        draw_multiline_centered(
            self.screen,
            [message],
            self.font_subtitle,
            config.SECONDARY_TEXT_COLOR,
            285,
        )

        pointer = pygame.mouse.get_pos()
        self.done_button.draw(
            self.screen,
            self.font_button,
            pointer,
        )

    def _draw_error(self) -> None:
        self.screen.fill(config.BACKGROUND_COLOR)

        draw_centered_text(
            self.screen,
            "Ocorreu um erro",
            self.font_title,
            config.TEXT_COLOR,
            180,
        )

        # Divide a mensagem em linhas simples para caber melhor na tela.
        words = self.error_message.split()
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > 58 and current:
                lines.append(current)
                current = word
            else:
                current = candidate

        if current:
            lines.append(current)

        draw_multiline_centered(
            self.screen,
            lines or ["Erro desconhecido."],
            self.font_subtitle,
            config.SECONDARY_TEXT_COLOR,
            270,
            line_gap=12,
        )

        pointer = pygame.mouse.get_pos()
        self.retry_button.draw(
            self.screen,
            self.font_button,
            pointer,
        )

    def _update(self) -> None:
        if self.state in {AppState.PREVIEW, AppState.COUNTDOWN}:
            self._read_camera()

        if self.state == AppState.COUNTDOWN:
            elapsed = time.monotonic() - self.countdown_started_at

            if elapsed >= config.COUNTDOWN_SECONDS:
                self._capture_photo()

        elif self.state == AppState.PROCESSING:
            self._finish_processing_if_ready()

        elif self.state == AppState.DONE:
            elapsed = time.monotonic() - self.done_started_at

            if elapsed >= config.DONE_SCREEN_SECONDS:
                self._go_to_idle()

    def _draw(self) -> None:
        if self.state == AppState.IDLE:
            self._draw_idle()

        elif self.state == AppState.PREVIEW:
            self._draw_preview()

        elif self.state == AppState.COUNTDOWN:
            elapsed = time.monotonic() - self.countdown_started_at
            number = config.COUNTDOWN_SECONDS - int(elapsed)
            number = max(1, number)
            self._draw_preview(number)

        elif self.state == AppState.REVIEW:
            self._draw_review()

        elif self.state == AppState.PROCESSING:
            self._draw_processing()

        elif self.state == AppState.DONE:
            self._draw_done()

        elif self.state == AppState.ERROR:
            self._draw_error()

        pygame.display.flip()

    def run(self) -> None:
        config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        self.initialize_camera()

        try:
            while self.running:
                self._handle_events()
                self._update()
                self._draw()
                self.clock.tick(config.TARGET_FPS)
        finally:
            self.camera.release()
            pygame.quit()
