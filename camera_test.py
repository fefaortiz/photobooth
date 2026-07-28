#!/usr/bin/env python3

"""
Teste mínimo da LifeCam com OpenCV.

Teclas:
    ESC ou Q -> sair
    ESPAÇO   -> salvar uma foto de teste
"""

from pathlib import Path
import time

import cv2

import config


def main() -> None:
    camera = cv2.VideoCapture(
        config.CAMERA_DEVICE,
        cv2.CAP_V4L2,
    )

    camera.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(*config.CAMERA_FOURCC),
    )
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    camera.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not camera.isOpened():
        raise RuntimeError(
            f"Não foi possível abrir {config.CAMERA_DEVICE}"
        )

    config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    print("Câmera aberta.")
    print("Pressione ESPAÇO para salvar uma foto; ESC ou Q para sair.")

    try:
        while True:
            ok, frame = camera.read()

            if not ok:
                print("Falha ao capturar frame.")
                continue

            preview = frame
            if config.MIRROR_PREVIEW:
                preview = cv2.flip(preview, 1)

            cv2.imshow("Teste LifeCam", preview)

            key = cv2.waitKey(1) & 0xFF

            if key in (27, ord("q")):
                break

            if key == 32:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                path = config.PHOTOS_DIR / f"teste_{timestamp}.jpg"

                photo = frame
                if config.MIRROR_SAVED_PHOTO:
                    photo = cv2.flip(photo, 1)

                cv2.imwrite(
                    str(path),
                    photo,
                    [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY],
                )
                print(f"Foto salva em: {path}")

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
