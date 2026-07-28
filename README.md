# Photo Booth — Raspberry Pi 3B + Microsoft LifeCam VX-7000

Versão baseada no fluxo do código original, mas adaptada para:

- webcam USB via OpenCV e V4L2;
- Microsoft LifeCam VX-7000;
- Raspberry Pi 3B;
- interface em Pygame;
- botão de captura na própria tela;
- ausência de botões GPIO;
- impressão desativada até a chegada da impressora.

## Fluxo

1. Tela inicial.
2. Botão **TIRAR FOTO**.
3. Preview ao vivo.
4. Botão **FOTO**.
5. Contagem regressiva 3, 2, 1 sem congelar o preview.
6. Captura e gravação em `photos/`.
7. Tela de revisão.
8. **REPETIR** ou **FINALIZAR**.
9. Retorno automático à tela inicial.

## Estrutura

```text
photobooth_lifecam/
├── main.py
├── app.py
├── config.py
├── camera_service.py
├── printer_service.py
├── ui.py
├── camera_test.py
├── install.sh
├── images/
│   ├── attract.jpg   # opcional
│   ├── printing.jpg  # opcional
│   └── done.jpg      # opcional
└── photos/
```

## Instalação

No terminal, entre na pasta do projeto e execute:

```bash
chmod +x install.sh
./install.sh
```

Ou instale manualmente:

```bash
sudo apt update
sudo apt install python3-opencv python3-pygame v4l-utils fswebcam
```

## Conferir a câmera

```bash
v4l2-ctl -d /dev/video0 --list-formats-ext
```

A LifeCam testada apresentou MJPG em 640x480 a 30 fps, configuração já usada em `config.py`.

## Testar apenas a webcam

```bash
python3 camera_test.py
```

No teste:

- `ESPAÇO` salva uma foto;
- `ESC` ou `Q` fecha o programa.

## Executar o Photo Booth

```bash
python3 main.py
```

Também é possível usar:

- `ESPAÇO` na tela inicial para iniciar;
- `ESPAÇO` no preview para fotografar;
- `ESC` ou `Q` para fechar.

## Tela sensível ao toque

Na maioria das instalações do Raspberry Pi OS, o toque é traduzido pelo SDL para clique de mouse. O código também trata diretamente o evento `FINGERDOWN`.

## Ajustes mais importantes

Todos os ajustes ficam em `config.py`.

### Rodar em janela durante os testes

```python
FULLSCREEN = False
DISPLAY_SIZE = (1280, 720)
```

### Esconder o cursor no modo quiosque

```python
SHOW_MOUSE_CURSOR = False
```

### Trocar o dispositivo da câmera

```python
CAMERA_DEVICE = "/dev/video0"
```

Para evitar que o número mude, confira:

```bash
ls -l /dev/v4l/by-id/
```

Depois use o caminho completo retornado, por exemplo:

```python
CAMERA_DEVICE = "/dev/v4l/by-id/usb-Microsoft_...-video-index0"
```

### Preview e foto espelhados

```python
MIRROR_PREVIEW = True
MIRROR_SAVED_PHOTO = False
```

### Desempenho no Raspberry Pi 3B

Os valores iniciais foram escolhidos para reduzir carga:

```python
DISPLAY_SIZE = (1280, 720)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
TARGET_FPS = 20
```

Caso o preview fique pesado:

```python
TARGET_FPS = 15
DISPLAY_SIZE = (1024, 576)
```

## Imagens personalizadas

Coloque na pasta `images/`:

- `attract.jpg`: tela inicial;
- `printing.jpg`: tela de processamento;
- `done.jpg`: tela final.

Se os arquivos não existirem, o programa usa telas simples desenhadas em Pygame.

## Quando a impressora chegar

1. Instale e configure o CUPS.
2. Confirme que este comando imprime:

```bash
lp photos/alguma_foto.jpg
```

3. Em `config.py`, altere:

```python
PRINTER_MODE = "cups"
```

Para selecionar uma impressora específica:

```python
PRINTER_NAME = "Nome_da_Impressora"
```

A lógica de câmera e interface não precisará ser alterada.

## Solução de problemas

### A câmera está ocupada

Feche outros programas que estejam usando `/dev/video0`, como `fswebcam`, VLC ou outro teste OpenCV.

### Permissão negada

Confira os grupos do usuário:

```bash
groups
```

Caso `video` não apareça:

```bash
sudo usermod -aG video "$USER"
```

Reinicie a sessão ou o Raspberry Pi.

### Preview demora para aparecer

A câmera é aberta durante a inicialização do programa para que o botão responda mais rapidamente. Um pequeno tempo inicial é normal por causa da exposição automática e da negociação do modo MJPG.

### Sair do modo tela cheia

Use `ESC` ou `Q`.
