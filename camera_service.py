from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2
import pygame


class CameraError(RuntimeError):
    """Erro relacionado à inicialização ou leitura da câmera."""


class CameraService:
    def __init__(
        self,
        device: str,
        width: int,
        height: int,
        fps: int,
        fourcc: str = "MJPG",
        warmup_frames: int = 10,
    ) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.fourcc = fourcc
        self.warmup_frames = warmup_frames
        self._capture: Optional[cv2.VideoCapture] = None

    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def open(self) -> None:
        if self.is_open:
            return

        capture = cv2.VideoCapture(self.device, cv2.CAP_V4L2)

        if not capture.isOpened():
            capture.release()
            raise CameraError(
                f"Não foi possível abrir a câmera em {self.device}. "
                "Verifique se ela está conectada e se nenhum outro programa está usando-a."
            )

        capture.set(
            cv2.CAP_PROP_FOURCC,
            cv2.VideoWriter_fourcc(*self.fourcc),
        )
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)

        # Mantém apenas um frame pendente para reduzir atraso acumulado.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._capture = capture
        self.flush(self.warmup_frames)

    def flush(self, frame_count: int = 4) -> None:
        """Descarta frames antigos para reduzir atraso antes do preview."""
        if not self.is_open:
            return

        for _ in range(max(0, frame_count)):
            self._capture.grab()

    def read(self) -> Tuple[bool, Optional[object]]:
        if not self.is_open:
            raise CameraError("A câmera não está aberta.")

        ok, frame = self._capture.read()
        if not ok or frame is None:
            return False, None

        return True, frame

    def save_frame(
        self,
        frame,
        output_path: Path,
        jpeg_quality: int = 95,
        mirror: bool = False,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        image = frame
        if mirror:
            image = cv2.flip(image, 1)

        success = cv2.imwrite(
            str(output_path),
            image,
            [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)],
        )

        if not success:
            raise CameraError(f"Não foi possível salvar a foto em {output_path}.")

        return output_path

    def actual_settings(self) -> dict:
        if not self.is_open:
            return {}

        return {
            "width": int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": float(self._capture.get(cv2.CAP_PROP_FPS)),
        }

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


def frame_to_surface(
    frame,
    target_size: tuple[int, int],
    mirror: bool = False,
    cover: bool = True,
) -> pygame.Surface:
    """
    Converte um frame BGR do OpenCV em uma Surface do Pygame.

    cover=True:
        preenche a área inteira, cortando pequenas sobras nas bordas.

    cover=False:
        preserva toda a imagem e pode deixar barras vazias.
    """
    if mirror:
        frame = cv2.flip(frame, 1)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    source_height, source_width = rgb.shape[:2]

    surface = pygame.image.frombuffer(
        rgb.tobytes(),
        (source_width, source_height),
        "RGB",
    ).copy()

    target_width, target_height = target_size

    if cover:
        scale = max(
            target_width / source_width,
            target_height / source_height,
        )
    else:
        scale = min(
            target_width / source_width,
            target_height / source_height,
        )

    scaled_size = (
        max(1, int(source_width * scale)),
        max(1, int(source_height * scale)),
    )

    # transform.scale é mais leve que smoothscale no Raspberry Pi 3B.
    scaled = pygame.transform.scale(surface, scaled_size)

    if not cover:
        return scaled

    crop_x = max(0, (scaled.get_width() - target_width) // 2)
    crop_y = max(0, (scaled.get_height() - target_height) // 2)
    crop_rect = pygame.Rect(crop_x, crop_y, target_width, target_height)

    return scaled.subsurface(crop_rect).copy()
