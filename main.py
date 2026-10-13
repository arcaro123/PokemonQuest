# Versió preparada per al navegador (pygbag / WebAssembly) i també per a l'escriptori.
import asyncio
import json
import math
import os
import random
import sys
import time

import pygame

# True quan el joc corre dins el navegador
IS_WEB = sys.platform == 'emscripten'


def music_file(path):
    """Al navegador l'mp3 no sol funcionar: si hi ha un .ogg amb el mateix nom, el fem servir."""

    ogg = os.path.splitext(path)[0] + '.ogg'

    if os.path.exists(ogg):
        return ogg

    return path


# ---------------------------------------------------------------
# DADES DESADES (medalles i rècords)
# Al navegador es guarden al localStorage (si no, es perdrien en
# refrescar la pàgina); a l'escriptori, en un fitxer .json.
# ---------------------------------------------------------------

def _browser_storage():
    """Obté localStorage de diferents maneres segons el runtime del navegador."""
    try:
        import platform
        storage = getattr(getattr(platform, 'window', None), 'localStorage', None)
        if storage is not None:
            return storage
    except Exception:
        pass
    try:
        from js import window
        return window.localStorage
    except Exception:
        return None


def persist_load(key, filename):
    """Llegeix les dades del navegador o del fitxer local."""
    if IS_WEB:
        try:
            storage = _browser_storage()
            if storage is not None:
                raw = storage.getItem(key)
                if raw is not None:
                    raw = str(raw)
                    if raw and raw not in ('null', 'undefined'):
                        return json.loads(raw)
        except Exception as exc:
            print(f'[DESATGE] No s ha pogut llegir {key} del navegador: {exc}')

    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (OSError, ValueError, TypeError, NameError) as exc:
        print(f'[DESATGE] No s ha pogut llegir {filename}: {exc}')
    return None


def persist_save(key, filename, data):
    """Desa les dades al localStorage del navegador o en un JSON local."""
    serialized = json.dumps(data, ensure_ascii=False)

    if IS_WEB:
        try:
            storage = _browser_storage()
            if storage is not None:
                storage.setItem(key, serialized)
                # Verifica que el navegador ha acceptat realment el desatge.
                check = storage.getItem(key)
                if check is not None and str(check) == serialized:
                    return True
        except Exception as exc:
            print(f'[DESATGE] No s ha pogut guardar {key} al navegador: {exc}')

    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except (OSError, TypeError, NameError) as exc:
        print(f'[DESATGE] No s ha pogut guardar {filename}: {exc}')
        return False
