#!/usr/bin/env python3
"""Importa nomes de config.py e lista todos os que faltam.

Um `from config import` cru só cita o primeiro nome ausente. require()
encerra com a lista completa, sem propagar ImportError.
"""

from __future__ import annotations

import sys


def require(*names: str):
    """Devolve os valores de config na ordem pedida.

    Se config.py não existir, ou se faltar qualquer nome, escreve a lista
    em stderr e encerra com SystemExit. Não deixa ImportError estourar.
    """
    try:
        import config as cfg
    except ImportError as exc:
        if getattr(exc, "name", None) not in (None, "config"):
            raise
        sys.stderr.write(
            "config.py não encontrado. Copie config.example.py para config.py.\n"
        )
        raise SystemExit(1) from exc

    missing = [name for name in names if not hasattr(cfg, name)]
    if missing:
        sys.stderr.write(
            "config.py incompleto. Faltam: "
            + ", ".join(missing)
            + ".\nAtualize config.py a partir de config.example.py.\n"
        )
        raise SystemExit(1)
    return tuple(getattr(cfg, name) for name in names)
