#!/usr/bin/env bash
set -e

sudo apt update
sudo apt install -y \
  python3-opencv \
  python3-pygame \
  v4l-utils \
  fswebcam

echo
echo "Dependências instaladas."
echo "Teste a câmera com:"
echo "  python3 camera_test.py"
echo
echo "Execute o photobooth com:"
echo "  python3 main.py"
