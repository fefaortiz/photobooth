from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Optional


@dataclass(frozen=True)
class PrintResult:
    success: bool
    message: str


class PrinterService:
    """
    Serviço isolado de impressão.

    Enquanto PRINTER_MODE estiver como "disabled", nenhuma impressão é feita.
    Quando a impressora chegar, basta configurar CUPS e usar o modo "cups".
    """

    def __init__(
        self,
        mode: str = "disabled",
        printer_name: Optional[str] = None,
    ) -> None:
        normalized_mode = mode.strip().lower()

        if normalized_mode not in {"disabled", "cups"}:
            raise ValueError(
                'Modo de impressão inválido. Use "disabled" ou "cups".'
            )

        self.mode = normalized_mode
        self.printer_name = printer_name

    @property
    def enabled(self) -> bool:
        return self.mode == "cups"

    def process_photo(self, photo_path: Path) -> PrintResult:
        if not photo_path.exists():
            return PrintResult(
                False,
                f"Arquivo não encontrado: {photo_path}",
            )

        if self.mode == "disabled":
            return PrintResult(
                True,
                f"Foto salva em {photo_path.name}. Impressão desativada.",
            )

        command = ["lp"]

        if self.printer_name:
            command.extend(["-d", self.printer_name])

        command.append(str(photo_path))

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            return PrintResult(
                False,
                "O comando lp não foi encontrado. Instale e configure o CUPS.",
            )
        except subprocess.TimeoutExpired:
            return PrintResult(
                False,
                "A impressão excedeu o tempo limite.",
            )

        if completed.returncode != 0:
            error_message = completed.stderr.strip() or "Falha desconhecida no CUPS."
            return PrintResult(False, error_message)

        output_message = completed.stdout.strip() or "Foto enviada para impressão."
        return PrintResult(True, output_message)
