#!/usr/bin/env python3
"""
EMU HUB v3
 - Detecta emuladores instalados no PC automaticamente
 - Detecta o console de cada jogo automaticamente
 - Pastas de ROMs fixas, reescaneadas toda vez que o Hub abre
 - Capas automáticas para vários consoles (por serial e por nome)

Requisitos: Python 3.8+ e Pillow (pip install pillow)
Uso: python emu_hub.py
"""
import difflib
import html
import json
import os
import queue
import re
import shlex
import shutil
import string
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

IS_WIN = sys.platform.startswith("win")
CORE_SUFFIX = "_libretro.dll" if IS_WIN else ("_libretro.dylib" if sys.platform == "darwin" else "_libretro.so")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "hub_config.json"
COVERS_DIR = BASE_DIR / "covers"

THUMB = (44, 60)
PREVIEW = (210, 290)
ALL = "Todos"
META_VERSION = 3
IGNORE = "__ignore__"
UA = {"User-Agent": "EmuHub/3.0"}

# --------------------------------------------------------------------------
# Plataformas: código -> (nome amigável, nome do sistema no thumbnails.libretro.com)
# --------------------------------------------------------------------------
PLATFORMS = {
    "PS1": ("PlayStation", "Sony - PlayStation"),
    "PS2": ("PlayStation 2", "Sony - PlayStation 2"),
    "PS3": ("PlayStation 3", "Sony - PlayStation 3"),
    "PSP": ("PSP", "Sony - PlayStation Portable"),
    "GC": ("GameCube", "Nintendo - GameCube"),
    "WII": ("Wii", "Nintendo - Wii"),
    "WIIU": ("Wii U", "Nintendo - Wii U"),
    "SWITCH": ("Switch", "Nintendo - Switch"),
    "3DS": ("Nintendo 3DS", "Nintendo - Nintendo 3DS"),
    "DS": ("Nintendo DS", "Nintendo - Nintendo DS"),
    "GB": ("Game Boy", "Nintendo - Game Boy"),
    "GBC": ("Game Boy Color", "Nintendo - Game Boy Color"),
    "GBA": ("Game Boy Advance", "Nintendo - Game Boy Advance"),
    "NES": ("NES", "Nintendo - Nintendo Entertainment System"),
    "SNES": ("Super Nintendo", "Nintendo - Super Nintendo Entertainment System"),
    "N64": ("Nintendo 64", "Nintendo - Nintendo 64"),
    "GENESIS": ("Mega Drive / Genesis", "Sega - Mega Drive - Genesis"),
    "SMS": ("Master System", "Sega - Master System - Mark III"),
    "SATURN": ("Saturn", "Sega - Saturn"),
    "DC": ("Dreamcast", "Sega - Dreamcast"),
}

# --------------------------------------------------------------------------
# Emuladores conhecidos. "exe" são regex aplicadas ao nome do arquivo SEM extensão.
# {rom} nos argumentos = caminho do jogo.
# --------------------------------------------------------------------------
KNOWN_EMULATORS = {
    "pcsx2": {
        "label": "PS2 (PCSX2)", "exe": [r"^pcsx2.*"],
        "args": '-batch -fullscreen -- "{rom}"',
        "exts": [".iso", ".bin", ".chd", ".cso", ".gz"], "platforms": ["PS2"],
    },
    "duckstation": {
        "label": "PS1 (DuckStation)", "exe": [r"^duckstation-qt.*"],
        "args": '-batch -fullscreen -- "{rom}"',
        "exts": [".cue", ".chd", ".bin", ".iso", ".pbp"], "platforms": ["PS1"],
    },
    "dolphin": {
        "label": "GameCube/Wii (Dolphin)", "exe": [r"^dolphin$"],
        "args": '-b -e "{rom}"',
        "exts": [".iso", ".gcm", ".rvz", ".wbfs", ".gcz", ".wad"], "platforms": ["GC", "WII"],
    },
    "ppsspp": {
        "label": "PSP (PPSSPP)", "exe": [r"^ppsspp(windows)?(64)?$"],
        "args": '"{rom}"', "exts": [".iso", ".cso", ".pbp"], "platforms": ["PSP"],
    },
    "rpcs3": {
        "label": "PS3 (RPCS3)", "exe": [r"^rpcs3$"],
        "args": '"{rom}"', "exts": [".iso", ".bin", ".self", ".elf"], "platforms": ["PS3"],
    },
    "ryujinx": {
        "label": "Switch (Ryujinx)", "exe": [r"^ryujinx(\.ava)?$"],
        "args": '"{rom}"', "exts": [".nsp", ".xci"], "platforms": ["SWITCH"],
    },
    "cemu": {
        "label": "Wii U (Cemu)", "exe": [r"^cemu$"],
        "args": '-g "{rom}" -f', "exts": [".wua", ".wud", ".wux", ".rpx"], "platforms": ["WIIU"],
    },
    "azahar": {
        "label": "3DS (Azahar/Lime3DS)", "exe": [r"^(azahar|lime3ds-gui|citra-qt)$"],
        "aliases": ["3DS (Lime3DS/Citra)"],
        "args": '"{rom}"', "exts": [".3ds", ".cci", ".cxi", ".cia"], "platforms": ["3DS"],
    },
    "melonds": {
        "label": "DS (melonDS)", "exe": [r"^melonds$"],
        "args": '"{rom}"', "exts": [".nds", ".dsi"], "platforms": ["DS"],
    },
    "mgba": {
        "label": "GB/GBC/GBA (mGBA)", "exe": [r"^mgba$"],
        "aliases": ["GBA (mGBA)"],
        "args": '-f "{rom}"', "exts": [".gba", ".gb", ".gbc"], "platforms": ["GBA", "GB", "GBC"],
    },
    "project64": {
        "label": "N64 (Project64)", "exe": [r"^project64(\s*\d+)?$"],
        "args": '"{rom}"', "exts": [".z64", ".n64", ".v64", ".ndd"], "platforms": ["N64"],
    },
    "simple64": {
        "label": "N64 (simple64)", "exe": [r"^simple64-gui$"],
        "args": '"{rom}"', "exts": [".z64", ".n64", ".v64"], "platforms": ["N64"],
    },
    "mupen64plus": {
        "label": "N64 (Mupen64Plus)", "exe": [r"^mupen64plus-ui-console$"],
        "args": '--fullscreen "{rom}"', "exts": [".z64", ".n64", ".v64"], "platforms": ["N64"],
    },
    "snes9x": {
        "label": "SNES (Snes9x)", "exe": [r"^snes9x(-x64)?$"],
        "args": '"{rom}"', "exts": [".sfc", ".smc"], "platforms": ["SNES"],
    },
    "mesen": {
        "label": "NES (Mesen)", "exe": [r"^mesen$"],
        "args": '"{rom}"', "exts": [".nes"], "platforms": ["NES"],
    },
    "flycast": {
        "label": "Dreamcast (Flycast)", "exe": [r"^flycast$"],
        "args": '"{rom}"', "exts": [".gdi", ".cdi", ".chd", ".cue"], "platforms": ["DC"],
    },
    "blastem": {
        "label": "Mega Drive (BlastEm)", "exe": [r"^blastem$"],
        "args": '"{rom}"', "exts": [".md", ".gen", ".smd"], "platforms": ["GENESIS"],
    },
}
RETROARCH_EXE = [r"^retroarch$"]

# Cores do RetroArch por grupo: (nome do grupo, plataformas, cores em ordem de preferência, extensões)
RETROARCH_GROUPS = [
    ("Nintendo 64", ["N64"], ["mupen64plus_next", "parallel_n64"], [".z64", ".n64", ".v64", ".ndd"]),
    ("NES", ["NES"], ["mesen", "nestopia", "fceumm", "quicknes"], [".nes"]),
    ("Super Nintendo", ["SNES"], ["snes9x", "bsnes", "mesen-s", "snes9x2010"], [".sfc", ".smc"]),
    ("Game Boy / Color", ["GB", "GBC"], ["gambatte", "sameboy", "mgba"], [".gb", ".gbc"]),
    ("Game Boy Advance", ["GBA"], ["mgba", "vba_next", "vbam"], [".gba"]),
    ("Mega Drive / Genesis", ["GENESIS"], ["genesis_plus_gx", "picodrive", "blastem"], [".md", ".gen", ".smd"]),
    ("Master System", ["SMS"], ["genesis_plus_gx", "picodrive", "smsplus", "gearsystem"], [".sms"]),
    ("Saturn", ["SATURN"], ["mednafen_saturn", "kronos", "yabasanshiro", "yabause"], [".cue", ".chd"]),
    ("Dreamcast", ["DC"], ["flycast"], [".gdi", ".cdi", ".chd"]),
    ("PlayStation", ["PS1"], ["swanstation", "mednafen_psx_hw", "mednafen_psx", "pcsx_rearmed"], [".cue", ".chd", ".pbp"]),
]

# Fontes de capa por SERIAL (PS1/PS2). ${serial} -> ex.: SLUS-00771
DEFAULT_COVER_SOURCES = {
    "PS2": [
        "https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/default/${serial}.jpg",
        "https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/3d/${serial}.png",
    ],
    "PS1": [
        "https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/default/${serial}.jpg",
        "https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/3d/${serial}.png",
    ],
}
LIBRETRO_BASE = "https://thumbnails.libretro.com/"

# Extensões que identificam o console sem ambiguidade
EXT_PLATFORM = {
    ".nds": "DS", ".dsi": "DS",
    ".gba": "GBA", ".gb": "GB", ".gbc": "GBC",
    ".3ds": "3DS", ".cci": "3DS", ".cxi": "3DS", ".cia": "3DS",
    ".nsp": "SWITCH", ".xci": "SWITCH",
    ".wua": "WIIU", ".wud": "WIIU", ".wux": "WIIU", ".rpx": "WIIU",
    ".rvz": "GC", ".gcm": "GC", ".gcz": "GC",
    ".wbfs": "WII", ".wad": "WII",
    ".sfc": "SNES", ".smc": "SNES",
    ".z64": "N64", ".n64": "N64", ".v64": "N64", ".ndd": "N64",
    ".nes": "NES",
    ".md": "GENESIS", ".gen": "GENESIS", ".smd": "GENESIS",
    ".sms": "SMS",
    ".gdi": "DC", ".cdi": "DC",
    ".pbp": "PSP",
    ".cue": "PS1",
    ".self": "PS3", ".elf": "PS3",
}
AMBIGUOUS_EXTS = {".iso", ".bin", ".img", ".chd", ".cso"}
ARCHIVE_EXTS = {".zip", ".gz"}  # só aceitos quando a pasta indica o console

# Nome de pasta -> plataforma (ajuda com .chd/.zip, que não dá pra ler por dentro)
FOLDER_HINTS = {
    "ps1": "PS1", "psx": "PS1", "playstation": "PS1", "playstation 1": "PS1", "sony playstation": "PS1",
    "ps2": "PS2", "playstation 2": "PS2", "sony playstation 2": "PS2",
    "ps3": "PS3", "playstation 3": "PS3",
    "psp": "PSP", "playstation portable": "PSP",
    "gc": "GC", "gamecube": "GC", "game cube": "GC", "nintendo gamecube": "GC",
    "wii": "WII", "nintendo wii": "WII",
    "wiiu": "WIIU", "wii u": "WIIU", "nintendo wii u": "WIIU",
    "switch": "SWITCH", "nintendo switch": "SWITCH",
    "3ds": "3DS", "nintendo 3ds": "3DS",
    "ds": "DS", "nds": "DS", "nintendo ds": "DS",
    "gb": "GB", "game boy": "GB", "gameboy": "GB",
    "gbc": "GBC", "game boy color": "GBC", "gameboy color": "GBC",
    "gba": "GBA", "game boy advance": "GBA", "gameboy advance": "GBA",
    "nes": "NES", "famicom": "NES", "nintendo entertainment system": "NES",
    "snes": "SNES", "sfc": "SNES", "super nintendo": "SNES", "super famicom": "SNES",
    "n64": "N64", "nintendo 64": "N64",
    "genesis": "GENESIS", "mega drive": "GENESIS", "megadrive": "GENESIS", "sega genesis": "GENESIS",
    "master system": "SMS", "sms": "SMS", "sega master system": "SMS",
    "saturn": "SATURN", "sega saturn": "SATURN",
    "dreamcast": "DC", "dc": "DC", "sega dreamcast": "DC",
}


# --------------------------------------------------------------------------
# Detecção de console / serial
# --------------------------------------------------------------------------
SERIAL_RE = re.compile(r"([A-Z]{4})[_\-]?(\d{3})[\._]?(\d{2})")


def normalize_serial(text):
    """'SLUS_207.15' / 'SLUS-20715' / 'slus20715' -> 'SLUS-20715'"""
    m = SERIAL_RE.search((text or "").upper())
    return f"{m.group(1)}-{m.group(2)}{m.group(3)}" if m else None


def norm_folder(s):
    return re.sub(r"[\s_\-]+", " ", s.lower()).strip()


def hint_platform(path):
    for part in reversed(Path(path).parts[:-1]):
        p = FOLDER_HINTS.get(norm_folder(part))
        if p:
            return p
    return None


class IsoImage:
    """Leitor mínimo de ISO9660 (setores de 2048 ou raw 2352)."""

    def __init__(self, f):
        self.f = f
        self.ss = self.off = None
        for ss, off in ((2048, 0), (2352, 16), (2352, 24)):
            f.seek(16 * ss + off + 1)
            if f.read(5) == b"CD001":
                self.ss, self.off = ss, off
                break
        self.ok = self.ss is not None

    def sector(self, n, count=1):
        out = b""
        for i in range(count):
            self.f.seek((n + i) * self.ss + self.off)
            out += self.f.read(2048)
        return out

    def read_dir(self, lba, size):
        size = min(size, 1 << 20)
        data = self.sector(lba, (size + 2047) // 2048)
        entries, pos = {}, 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = (pos // 2048 + 1) * 2048
                continue
            rec = data[pos:pos + ln]
            if len(rec) < 34:
                break
            extent = struct.unpack_from("<I", rec, 2)[0]
            dsize = struct.unpack_from("<I", rec, 10)[0]
            flags, nlen = rec[25], rec[32]
            name = rec[33:33 + nlen].decode("latin-1").split(";")[0].upper()
            if name not in ("\x00", "\x01"):
                entries[name] = (extent, dsize, bool(flags & 2))
            pos += ln
        return entries

    def root(self):
        pvd = self.sector(16)
        return self.read_dir(struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0])

    def read_file(self, entry, limit=2048):
        lba, size, _ = entry
        n = min(size, limit)
        return self.sector(lba, (n + 2047) // 2048)[:n]


def sniff_disc(path):
    """Espia o conteúdo. Retorna (plataforma, serial) ou (None, None)."""
    try:
        with open(path, "rb") as f:
            head = f.read(0x20)
            if head[:4] == b"CISO":
                return "PSP", None
            if head[0x1C:0x20] == b"\xC2\x33\x9F\x3D":
                return "GC", None
            if head[0x18:0x1C] == b"\x5D\x1C\x9E\xA3":
                return "WII", None
            iso = IsoImage(f)
            if not iso.ok:
                return None, None
            root = iso.root()
            if "PSP_GAME" in root:
                return "PSP", None
            if "PS3_GAME" in root or "PS3_DISC.SFB" in root:
                return "PS3", None
            cnf = root.get("SYSTEM.CNF")
            if cnf:
                text = iso.read_file(cnf).decode("latin-1", "ignore").upper()
                if "BOOT2" in text:
                    return "PS2", normalize_serial(text.split("BOOT2", 1)[1])
                m = re.search(r"^\s*BOOT\s*=\s*(\S+)", text, re.M)
                if m:
                    return "PS1", normalize_serial(m.group(1))
    except Exception:
        pass
    return None, None


def cue_first_track(cue_path):
    try:
        with open(cue_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read(4096)
        m = re.search(r'FILE\s+"([^"]+)"', text, re.I) or re.search(r"FILE\s+(\S+)", text, re.I)
        if m:
            p = os.path.join(os.path.dirname(cue_path), m.group(1))
            if os.path.isfile(p):
                return p
    except Exception:
        pass
    return None


def detect(path):
    """(plataforma, serial). Plataforma None = não reconhecido."""
    ext = Path(path).suffix.lower()
    plat, serial = None, None
    if ext == ".cue":
        plat = hint_platform(path) or "PS1"
        track = cue_first_track(path)
        if track and plat == "PS1":
            p2, serial = sniff_disc(track)
            if p2 and p2 != "PS1":
                plat, serial = p2, None
    elif ext in EXT_PLATFORM:
        plat = EXT_PLATFORM[ext]
    else:
        plat, serial = sniff_disc(path)
        if not plat:
            plat = hint_platform(path)
    if plat in ("PS1", "PS2") and not serial:
        serial = normalize_serial(Path(path).stem)
    return plat, serial


# --------------------------------------------------------------------------
# Busca de emuladores instalados
# --------------------------------------------------------------------------
SKIP_DIRS = {
    "windows", "$recycle.bin", "system volume information", "programdata", "users", "recovery",
    "msocache", "perflogs", "node_modules", ".git", "appdata", "windowsapps", "winsxs",
    "program files", "program files (x86)",
}
EXCLUDE_EXE = re.compile(r"(unins|uninstall|setup|install|updater|crash|headless|redist|vc_redist)")
_EMU_PATTERNS = {eid: [re.compile(p) for p in spec["exe"]] for eid, spec in KNOWN_EMULATORS.items()}
_EMU_PATTERNS["retroarch"] = [re.compile(p) for p in RETROARCH_EXE]


def candidate_roots():
    roots = []
    home = Path.home()
    env = os.environ
    if IS_WIN:
        for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            if env.get(k):
                roots.append((env[k], 3))
        if env.get("LOCALAPPDATA"):
            roots += [(os.path.join(env["LOCALAPPDATA"], "Programs"), 3), (env["LOCALAPPDATA"], 2)]
        if env.get("APPDATA"):
            roots.append((env["APPDATA"], 2))
        for sub in ("Desktop", "Downloads", "Documents", "Games", "Emulators", "Emuladores", "OneDrive"):
            roots.append((str(home / sub), 5))
        for letter in string.ascii_uppercase:
            d = f"{letter}:\\"
            if os.path.isdir(d):
                roots.append((d, 4))
    else:
        roots += [(str(home / ".local" / "share"), 3), (str(home / "Applications"), 3),
                  (str(home / "Games"), 4), (str(home / "Downloads"), 4), ("/opt", 3), ("/Applications", 2)]
    return roots


def is_executable_name(fn, full):
    if IS_WIN:
        return fn.lower().endswith(".exe")
    return os.access(full, os.X_OK) or fn.lower().endswith(".appimage")


def scan_for_emulators(roots):
    """Retorna {id_do_emulador: caminho} (o mais recente de cada)."""
    best = {}
    seen = set()
    for root, maxdepth in roots:
        root = str(root)
        if not os.path.isdir(root):
            continue
        base = root.rstrip("\\/").count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            key = os.path.normcase(dirpath)
            if key in seen:
                dirnames[:] = []
                continue
            seen.add(key)
            depth = dirpath.rstrip("\\/").count(os.sep) - base
            if depth >= maxdepth:
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith("$")]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if not is_executable_name(fn, full):
                    continue
                stem = os.path.splitext(fn)[0].lower()
                if EXCLUDE_EXE.search(stem):
                    continue
                for eid, pats in _EMU_PATTERNS.items():
                    if any(p.match(stem) for p in pats):
                        try:
                            mt = os.path.getmtime(full)
                        except OSError:
                            mt = 0
                        if eid not in best or mt > best[eid][0]:
                            best[eid] = (mt, full)
    return {eid: v[1] for eid, v in best.items()}


def create_console(cfg, eid, exe=""):
    spec = KNOWN_EMULATORS[eid]
    name, i = spec["label"], 2
    while name in cfg["consoles"]:
        name = f'{spec["label"]} ({i})'
        i += 1
    cfg["consoles"][name] = {
        "exe": exe, "args": spec["args"], "exts": list(spec["exts"]),
        "platforms": list(spec["platforms"]), "emu": eid,
    }
    return name


# --------------------------------------------------------------------------
# Capas
# --------------------------------------------------------------------------
def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:90] or "x"


def http_get(url, timeout=20):
    """Retorna (bytes|None, código). código 0 = erro de rede."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), 200
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, 0


_index_lock = threading.Lock()
_index_maps = {}  # sistema -> {chave_normalizada: [nomes]}


def norm_title(s):
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(t for t in s.split() if t != "the")


def libretro_index(system):
    """Lista de nomes disponíveis no Named_Boxarts. Retorna (mapa|None, status).
    status: ok | 404 | noindex | error"""
    with _index_lock:
        if system in _index_maps:
            return _index_maps[system], "ok"
        cache_dir = COVERS_DIR / "_index"
        cache = cache_dir / (slug(system) + ".json")
        names = None
        if cache.exists() and time.time() - cache.stat().st_mtime < 30 * 86400:
            try:
                names = json.loads(cache.read_text(encoding="utf-8"))
            except Exception:
                names = None
        if names is None:
            url = LIBRETRO_BASE + urllib.parse.quote(system) + "/Named_Boxarts/"
            data, code = http_get(url, timeout=60)
            if data is None:
                if cache.exists():  # usa cache velho se a rede falhar
                    try:
                        names = json.loads(cache.read_text(encoding="utf-8"))
                    except Exception:
                        names = None
                if names is None:
                    return None, ("404" if code == 404 else "error")
            else:
                text = data.decode("utf-8", "ignore")
                names = []
                for href in re.findall(r'href="([^"]+?)\.png"', text, re.I):
                    n = urllib.parse.unquote(html.unescape(href))
                    if "/" not in n and "?" not in n:
                        names.append(n)
                if not names:
                    return None, "noindex"
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    cache.write_text(json.dumps(names), encoding="utf-8")
                except Exception:
                    pass
        m = {}
        for n in names:
            m.setdefault(norm_title(n), []).append(n)
        _index_maps[system] = m
        return m, "ok"


REGION_WORDS = {"usa", "europe", "japan", "world", "brazil", "korea", "germany", "france", "spain",
                "italy", "australia", "asia", "china", "taiwan", "netherlands", "sweden", "russia"}


def regions_of(name):
    out = set()
    for tag in re.findall(r"\(([^)]*)\)", name):
        for w in tag.split(","):
            if w.strip().lower() in REGION_WORDS:
                out.add(w.strip().lower())
    return out


def score_candidate(cand, wanted):
    low = cand.lower()
    s = 0
    regs = regions_of(cand)
    if wanted and regs & wanted:
        s -= 30
    if "usa" in regs:
        s -= 20
    if "world" in regs:
        s -= 15
    if "europe" in regs:
        s -= 10
    if re.search(r"\((beta|demo|proto|sample|unl|virtual console)", low):
        s += 30
    if re.search(r"disc [2-9]", low):
        s += 15
    if "(rev" in low:
        s += 3
    return s


def libretro_match(system, stem):
    """Escolhe o melhor nome do índice para um jogo. Retorna (nome|None, status)."""
    m, status = libretro_index(system)
    if m is None:
        return None, status
    key = norm_title(stem)
    if not key:
        return None, "ok"
    cands = m.get(key)
    if not cands:
        toks = key.split()
        longest = max(toks, key=len)
        pool = [k for k in m if longest in k.split()]
        close = difflib.get_close_matches(key, pool, n=1, cutoff=0.84)
        if close:
            cands = m[close[0]]
    if not cands:
        return None, "ok"
    wanted = regions_of(stem)
    return min(cands, key=lambda c: score_candidate(c, wanted)), "ok"


def fetch_cover(platform, serial, stems, serial_sources):
    """Baixa a capa. Retorna (arquivo|'', erro_definitivo)."""
    COVERS_DIR.mkdir(exist_ok=True)
    definitive = True

    # 1) fontes por serial (PS1/PS2)
    if serial:
        for tmpl in serial_sources.get(platform, []):
            url = tmpl.replace("${serial}", serial).replace("{serial}", serial)
            ext = os.path.splitext(url)[1] or ".jpg"
            dest = COVERS_DIR / f"{platform}_{serial}{ext}"
            if dest.exists() and dest.stat().st_size > 0:
                return dest.name, False
            data, code = http_get(url)
            if data:
                dest.write_bytes(data)
                return dest.name, False
            if code != 404:
                definitive = False

    # 2) thumbnails.libretro.com por nome do jogo
    system = PLATFORMS.get(platform, (None, None))[1]
    if system:
        for stem in stems:
            chosen, status = libretro_match(system, stem)
            if status == "error":
                definitive = False
            if chosen:
                dest = COVERS_DIR / f"{platform}_{slug(chosen)}.png"
                if dest.exists() and dest.stat().st_size > 0:
                    return dest.name, False
                url = LIBRETRO_BASE + urllib.parse.quote(system) + "/Named_Boxarts/" + urllib.parse.quote(chosen) + ".png"
                data, code = http_get(url)
                if data:
                    dest.write_bytes(data)
                    return dest.name, False
                if code != 404:
                    definitive = False
            elif status in ("noindex", "error"):
                # sem índice: tenta o nome exato do arquivo (funciona com ROMs nomeadas pelo padrão No-Intro/Redump)
                exact = re.sub(r'[&*/:`<>?\\|"]', "_", stem)
                dest = COVERS_DIR / f"{platform}_{slug(exact)}.png"
                if dest.exists() and dest.stat().st_size > 0:
                    return dest.name, False
                url = LIBRETRO_BASE + urllib.parse.quote(system) + "/Named_Boxarts/" + urllib.parse.quote(exact) + ".png"
                data, code = http_get(url)
                if data:
                    dest.write_bytes(data)
                    return dest.name, False
    return "", definitive


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
def load_config():
    cfg = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            messagebox.showwarning("Config", f"Não consegui ler a config ({e}). Usando padrão.")
    cfg.setdefault("consoles", {})
    cfg.setdefault("games", [])
    cfg.setdefault("rom_folders", [])
    cfg.setdefault("ignored", [])
    cfg.setdefault("last_emu_scan", 0)
    cfg.setdefault("cover_sources", {})
    for k, v in DEFAULT_COVER_SOURCES.items():
        cfg["cover_sources"].setdefault(k, deepcopy(v))
    # migração de configs antigas: liga cada console ao emulador conhecido
    for name, c in cfg["consoles"].items():
        if "emu" not in c:
            for eid, spec in KNOWN_EMULATORS.items():
                if name == spec["label"] or name in spec.get("aliases", []):
                    c["emu"] = eid
                    break
        if "platforms" not in c:
            spec = KNOWN_EMULATORS.get(c.get("emu", ""), {})
            c["platforms"] = list(spec.get("platforms", []))
    if cfg.get("meta_v", 1) < META_VERSION:
        for g in cfg["games"]:
            g["scanned"] = False
            g["cover_tried"] = False
        cfg["meta_v"] = META_VERSION
    return cfg


def save_config(cfg):
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)


def clean_name(path):
    return Path(path).stem.replace("_", " ").replace(".", " ").strip()


def exe_ok(c):
    exe = (c or {}).get("exe", "")
    return bool(exe) and os.path.isfile(exe)


def build_command(console_cfg, rom):
    exe = console_cfg.get("exe", "").strip()
    if not exe:
        raise ValueError("Emulador não configurado para este console.")
    if not os.path.exists(exe):
        raise ValueError(f"Executável não encontrado:\n{exe}")
    tokens = shlex.split(console_cfg.get("args", ""), posix=False)
    tokens = [t.strip('"').replace("{rom}", rom) for t in tokens]
    return [exe] + tokens


def scan_roms(folders, known, ignored, exts):
    """Varre pastas e identifica cada arquivo novo. Retorna [(path, plataforma, serial)]."""
    found = []
    for folder in folders:
        for root, _d, files in os.walk(folder):
            has_cue = any(f.lower().endswith(".cue") for f in files)
            for f in files:
                e = Path(f).suffix.lower()
                p = os.path.abspath(os.path.join(root, f))
                if p in known or p in ignored:
                    continue
                if e in ARCHIVE_EXTS:
                    plat = hint_platform(p)
                    if plat:
                        found.append((p, plat, None))
                    continue
                if e not in exts:
                    continue
                if e == ".bin" and has_cue:
                    continue  # faixas do .cue
                plat, serial = detect(p)
                found.append((p, plat, serial))
    return found


# --------------------------------------------------------------------------
# Diálogos
# --------------------------------------------------------------------------
def pick_choice(parent, title, msg, options, ok_text="OK", extra=None):
    """Janela modal. Retorna a opção escolhida, `extra[1]` se clicou no botão extra, ou None se fechou."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    ttk.Label(win, text=msg, padding=10, wraplength=420, justify="center").pack()
    v = tk.StringVar(value=options[0] if options else "")
    ttk.Combobox(win, textvariable=v, values=options, state="readonly", width=44).pack(padx=14)
    res = {"v": None}

    def ok():
        res["v"] = v.get()
        win.destroy()

    def ex():
        res["v"] = extra[1]
        win.destroy()

    bf = ttk.Frame(win)
    bf.pack(pady=12)
    ttk.Button(bf, text=ok_text, command=ok).pack(side="left", padx=4)
    if extra:
        ttk.Button(bf, text=extra[0], command=ex).pack(side="left", padx=4)
    parent.wait_window(win)
    return res["v"]


class EmulatorsDialog(tk.Toplevel):
    def __init__(self, hub):
        super().__init__(hub)
        self.hub = hub
        self.cfg = hub.cfg
        self.title("Emuladores")
        self.geometry("860x560")
        self.transient(hub)
        self.current = None
        self.names = []

        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")
        self.lb = tk.Listbox(left, width=30, exportselection=False)
        self.lb.pack(fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", self.select)
        ttk.Button(left, text="🔍 Detectar emuladores no PC", command=self.detect).pack(fill="x", pady=(8, 2))
        ttk.Button(left, text="＋ Adicionar (modelo)…", command=self.new_template).pack(fill="x", pady=2)
        row = ttk.Frame(left)
        row.pack(fill="x", pady=2)
        ttk.Button(row, text="＋ Vazio", command=self.new_blank).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Remover", command=self.remove).pack(side="left", expand=True, fill="x")
        ttk.Label(left, text="✔ pronto   ✖ falta o .exe", foreground="#777").pack(pady=(6, 0))

        right = ttk.Frame(self, padding=8)
        right.pack(side="left", fill="both", expand=True)
        self.name_v, self.exe_v = tk.StringVar(), tk.StringVar()
        self.args_v, self.exts_v, self.plat_v = tk.StringVar(), tk.StringVar(), tk.StringVar()

        ttk.Label(right, text="Nome").pack(anchor="w")
        ttk.Entry(right, textvariable=self.name_v).pack(fill="x", pady=(0, 8))
        ttk.Label(right, text="Executável do emulador").pack(anchor="w")
        r2 = ttk.Frame(right)
        r2.pack(fill="x", pady=(0, 8))
        ttk.Entry(r2, textvariable=self.exe_v).pack(side="left", fill="x", expand=True)
        ttk.Button(r2, text="Procurar…", command=self.browse).pack(side="left", padx=(6, 0))
        ttk.Label(right, text="Argumentos  ({rom} = caminho do jogo)").pack(anchor="w")
        ttk.Entry(right, textvariable=self.args_v).pack(fill="x", pady=(0, 8))
        ttk.Label(right, text="Extensões das ROMs (vírgula)").pack(anchor="w")
        ttk.Entry(right, textvariable=self.exts_v).pack(fill="x", pady=(0, 8))
        ttk.Label(right, text="Plataformas que este emulador atende (vírgula)").pack(anchor="w")
        ttk.Entry(right, textvariable=self.plat_v).pack(fill="x", pady=(0, 2))
        ttk.Label(
            right, foreground="#777", wraplength=520, justify="left",
            text="Códigos: " + ", ".join(PLATFORMS),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            right, foreground="#777", wraplength=520, justify="left",
            text=("O Hub usa as plataformas daqui para escolher o emulador de cada jogo. "
                  "Para adicionar um emulador que não está nos modelos, use '＋ Vazio', "
                  "escolha o .exe, coloque os argumentos e as plataformas."),
        ).pack(anchor="w", pady=(4, 8))
        ttk.Button(right, text="Salvar", command=self.save).pack(anchor="e")
        self.refresh()

    # ---- lista
    def refresh(self, select=None):
        self.names = list(self.cfg["consoles"])
        self.lb.delete(0, "end")
        for n in self.names:
            self.lb.insert("end", ("✔ " if exe_ok(self.cfg["consoles"][n]) else "✖ ") + n)
        target = select or self.current
        if target in self.names:
            self.lb.selection_set(self.names.index(target))
            self.select()

    def select(self, _e=None):
        sel = self.lb.curselection()
        if not sel:
            return
        name = self.names[sel[0]]
        c = self.cfg["consoles"][name]
        self.current = name
        self.name_v.set(name)
        self.exe_v.set(c.get("exe", ""))
        self.args_v.set(c.get("args", ""))
        self.exts_v.set(", ".join(c.get("exts", [])))
        self.plat_v.set(", ".join(c.get("platforms", [])))

    def browse(self):
        p = filedialog.askopenfilename(title="Escolha o executável do emulador")
        if p:
            self.exe_v.set(p)

    def detect(self):
        self.hub.start_emu_detect(manual=True)

    def new_template(self):
        labels = {s["label"]: eid for eid, s in KNOWN_EMULATORS.items()}
        choice = pick_choice(self, "Adicionar emulador", "Escolha o emulador (modelo):", list(labels))
        if choice:
            name = create_console(self.cfg, labels[choice])
            self.hub.on_consoles_changed()
            self.refresh(select=name)

    def new_blank(self):
        name = simpledialog.askstring("Novo", "Nome do emulador/console:", parent=self)
        if name and name not in self.cfg["consoles"]:
            self.cfg["consoles"][name] = {"exe": "", "args": '"{rom}"', "exts": [], "platforms": []}
            self.hub.on_consoles_changed()
            self.refresh(select=name)

    def remove(self):
        if self.current and messagebox.askyesno("Remover", f"Remover '{self.current}'?", parent=self):
            self.cfg["consoles"].pop(self.current, None)
            self.current = None
            self.hub.on_consoles_changed()
            self.refresh()

    def save(self):
        if not self.current:
            return
        old = self.cfg["consoles"][self.current]
        new_name = self.name_v.get().strip() or self.current
        data = {
            "exe": self.exe_v.get().strip(),
            "args": self.args_v.get().strip(),
            "exts": [("." + e.strip().lstrip(".").lower()) for e in self.exts_v.get().split(",") if e.strip()],
            "platforms": [p.strip().upper() for p in self.plat_v.get().split(",") if p.strip()],
        }
        if old.get("emu"):
            data["emu"] = old["emu"]
        if new_name != self.current:
            self.cfg["consoles"] = {
                (new_name if k == self.current else k): (data if k == self.current else v)
                for k, v in self.cfg["consoles"].items()
            }
            for g in self.cfg["games"]:
                if g["console"] == self.current:
                    g["console"] = new_name
        else:
            self.cfg["consoles"][new_name] = data
        self.current = new_name
        self.hub.on_consoles_changed()
        self.refresh(select=new_name)


class RomFoldersDialog(tk.Toplevel):
    def __init__(self, hub):
        super().__init__(hub)
        self.hub = hub
        self.cfg = hub.cfg
        self.title("Pastas de ROMs")
        self.geometry("620x360")
        self.transient(hub)
        ttk.Label(
            self, padding=10, wraplength=580, justify="left",
            text=("Estas pastas são lidas toda vez que o EMU HUB abre. Jogos novos entram na biblioteca "
                  "sozinhos, com console e capa detectados automaticamente (subpastas incluídas).\n"
                  "Dica: se você separar por pastas com o nome do console (PS2, N64, GBA…), arquivos "
                  ".chd e .zip também são reconhecidos."),
        ).pack(fill="x")
        self.lb = tk.Listbox(self, exportselection=False)
        self.lb.pack(fill="both", expand=True, padx=10)
        bf = ttk.Frame(self, padding=10)
        bf.pack(fill="x")
        ttk.Button(bf, text="＋ Adicionar pasta…", command=self.add).pack(side="left")
        ttk.Button(bf, text="Remover", command=self.remove).pack(side="left", padx=6)
        ttk.Button(bf, text="⟳ Escanear agora", command=self.scan).pack(side="left")
        ttk.Button(bf, text="Fechar", command=self.destroy).pack(side="right")
        self.refresh()

    def refresh(self):
        self.lb.delete(0, "end")
        for f in self.cfg["rom_folders"]:
            self.lb.insert("end", f)

    def add(self):
        d = filedialog.askdirectory(title="Escolha a pasta de ROMs", parent=self)
        if d:
            d = os.path.abspath(d)
            if d not in self.cfg["rom_folders"]:
                self.cfg["rom_folders"].append(d)
                save_config(self.cfg)
                self.refresh()
                self.hub.start_scan(manual=True)

    def remove(self):
        sel = self.lb.curselection()
        if sel:
            self.cfg["rom_folders"].pop(sel[0])
            save_config(self.cfg)
            self.refresh()

    def scan(self):
        self.hub.start_scan(manual=True)


# --------------------------------------------------------------------------
# App principal
# --------------------------------------------------------------------------
class Hub(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EMU HUB")
        self.geometry("1100x640")
        self.minsize(860, 460)
        self.cfg = load_config()
        self.running = {}
        self.img_cache = {}
        self.pool = ThreadPoolExecutor(max_workers=4)  # capas
        self.bg = ThreadPoolExecutor(max_workers=2)    # varredura de pastas / emuladores
        self.results = queue.Queue()
        self.pending = set()
        self.scanning = self.detecting = False
        self.scan_manual = self.detect_manual = False
        self.emu_dialog = None
        self.pv_photo = None

        self.build_ui()
        self.reload_filters()
        self.migrate_games()
        self.reassign_unconfigured()
        self.refresh_list()
        self.queue_all_covers()
        self.after(300, self.poll_results)
        self.after(600, self.startup_tasks)
        if not HAS_PIL:
            self.status.set("Pillow não instalado: capas .jpg não aparecem. Rode: pip install pillow")

    # ---------- UI
    def build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=THUMB[1] + 6)
        style.configure("Big.TButton", padding=8)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="＋ Adicionar ROMs", command=self.add_roms).pack(side="left")
        ttk.Button(top, text="📂 Pastas de ROMs", command=self.open_folders).pack(side="left", padx=6)
        ttk.Button(top, text="🔍 Detectar emuladores", command=lambda: self.start_emu_detect(True)).pack(side="left")
        ttk.Button(top, text="⚙ Emuladores", command=self.open_emulators).pack(side="left", padx=6)
        ttk.Button(top, text="🖼 Buscar capas", command=self.refetch_missing).pack(side="left")

        self.search_v = tk.StringVar()
        self.search_v.trace_add("write", lambda *a: self.refresh_list())
        ttk.Entry(top, textvariable=self.search_v, width=22).pack(side="right")
        ttk.Label(top, text="Buscar:").pack(side="right", padx=4)

        filt = ttk.Frame(self, padding=(8, 0, 8, 6))
        filt.pack(fill="x")
        ttk.Label(filt, text="Console:").pack(side="left", padx=(0, 4))
        self.filter_v = tk.StringVar(value=ALL)
        self.filter_cb = ttk.Combobox(filt, textvariable=self.filter_v, state="readonly", width=28)
        self.filter_cb.pack(side="left")
        self.filter_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())
        self.fav_v = tk.BooleanVar()
        ttk.Checkbutton(filt, text="★ Favoritos", variable=self.fav_v, command=self.refresh_list).pack(side="left", padx=10)

        mid = ttk.Frame(self, padding=(8, 0))
        mid.pack(fill="both", expand=True)
        side = ttk.Frame(mid, padding=(10, 0, 0, 0), width=240)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)
        self.pv_img = ttk.Label(side, anchor="center")
        self.pv_img.pack(pady=(0, 8))
        self.pv_name = ttk.Label(side, wraplength=220, justify="center", font=("TkDefaultFont", 11, "bold"))
        self.pv_name.pack()
        self.pv_info = ttk.Label(side, wraplength=220, justify="center", foreground="#777")
        self.pv_info.pack(pady=4)

        cols = ("fav", "name", "console", "plays", "last")
        self.tree = ttk.Treeview(mid, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Capa")
        self.tree.column("#0", width=THUMB[0] + 20, stretch=False, anchor="center")
        for c, t, w, a in [("fav", "★", 34, "center"), ("name", "Jogo", 320, "w"),
                           ("console", "Console", 180, "w"), ("plays", "Jogadas", 66, "center"),
                           ("last", "Última vez", 100, "center")]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a, stretch=(c == "name"))
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", lambda e: self.play())
        self.tree.bind("<Return>", lambda e: self.play())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_preview())
        self.tree.bind("<Button-3>", self.popup)
        self.tree.bind("<Button-2>", self.popup)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="▶ Jogar", command=self.play)
        self.menu.add_command(label="★ Favoritar / desfavoritar", command=self.toggle_fav)
        self.menu.add_separator()
        self.menu.add_command(label="🖼 Buscar capa de novo", command=self.refetch_selected)
        self.menu.add_command(label="🖼 Escolher imagem de capa…", command=self.pick_cover)
        self.menu.add_command(label="Definir serial…", command=self.set_serial)
        self.menu.add_separator()
        self.menu.add_command(label="✎ Renomear", command=self.rename)
        self.menu.add_command(label="Trocar console", command=self.change_console)
        self.menu.add_command(label="Abrir pasta da ROM", command=self.open_folder)
        self.menu.add_separator()
        self.menu.add_command(label="Remover da biblioteca", command=self.remove_game)

        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="▶  JOGAR", style="Big.TButton", command=self.play).pack(side="right")
        self.status = tk.StringVar(value="Pronto.")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")

    def busy(self):
        return bool(self.pending or self.scanning or self.detecting)

    # ---------- imagens
    def placeholder(self, size):
        key = ("", size)
        if key not in self.img_cache:
            img = tk.PhotoImage(width=size[0], height=size[1])
            img.put("#2b2b2b", to=(0, 0, size[0], size[1]))
            self.img_cache[key] = img
        return self.img_cache[key]

    def load_image(self, filename, size):
        if not filename:
            return self.placeholder(size)
        key = (filename, size)
        if key in self.img_cache:
            return self.img_cache[key]
        p = COVERS_DIR / filename
        photo = None
        try:
            if HAS_PIL:
                im = Image.open(p).convert("RGBA")
                im.thumbnail(size, Image.LANCZOS)
                photo = ImageTk.PhotoImage(im)
            elif p.suffix.lower() == ".png":
                photo = tk.PhotoImage(file=str(p))
        except Exception:
            photo = None
        if photo is None:
            return self.placeholder(size)
        self.img_cache[key] = photo
        return photo

    def drop_cached(self, filename):
        self.img_cache = {k: v for k, v in self.img_cache.items() if k[0] != filename}

    def update_preview(self):
        g = self.selected_game()
        if not g:
            self.pv_photo = self.placeholder(PREVIEW)
            self.pv_img.configure(image=self.pv_photo)
            self.pv_name.configure(text="")
            self.pv_info.configure(text="")
            return
        self.pv_photo = self.load_image(g.get("cover"), PREVIEW)
        self.pv_img.configure(image=self.pv_photo)
        self.pv_name.configure(text=g["name"])
        info = [g["console"]]
        if g.get("platform"):
            info.append(PLATFORMS.get(g["platform"], (g["platform"],))[0])
        if g.get("serial"):
            info.append(f"Serial: {g['serial']}")
        self.pv_info.configure(text="\n".join(info))

    # ---------- biblioteca
    def reload_filters(self):
        self.filter_cb["values"] = [ALL] + list(self.cfg["consoles"])
        if self.filter_v.get() not in self.filter_cb["values"]:
            self.filter_v.set(ALL)

    def refresh_list(self):
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        q = self.search_v.get().lower().strip()
        flt = self.filter_v.get()
        shown = 0
        for g in sorted(self.cfg["games"], key=lambda g: g["name"].lower()):
            if flt != ALL and g["console"] != flt:
                continue
            if self.fav_v.get() and not g.get("fav"):
                continue
            if q and q not in g["name"].lower():
                continue
            last = time.strftime("%d/%m/%Y", time.localtime(g["last"])) if g.get("last") else "—"
            self.tree.insert(
                "", "end", iid=g["path"], image=self.load_image(g.get("cover"), THUMB),
                values=("★" if g.get("fav") else "", g["name"], g["console"], g.get("plays", 0), last),
            )
            shown += 1
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])
        self.update_preview()
        if not self.busy():
            self.status.set(f"{shown} jogo(s) exibido(s) • {len(self.cfg['games'])} na biblioteca")

    def selected_game(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return next((g for g in self.cfg["games"] if g["path"] == sel[0]), None)

    # ---------- consoles
    def console_for_platform(self, platform, create=False):
        consoles = self.cfg["consoles"]
        cands = [n for n, c in consoles.items() if platform in c.get("platforms", [])]
        good = [n for n in cands if exe_ok(consoles[n])]
        if good:
            return good[0]
        if cands:
            return cands[0]
        if create:
            for eid, spec in KNOWN_EMULATORS.items():
                if platform in spec["platforms"]:
                    for n, c in consoles.items():
                        if c.get("emu") == eid:
                            c.setdefault("platforms", []).append(platform)
                            return n
                    name = create_console(self.cfg, eid)
                    self.reload_filters()
                    return name
        return None

    def reassign_unconfigured(self):
        """Jogos ligados a um console sem .exe passam para outro que já esteja pronto."""
        consoles = self.cfg["consoles"]
        changed = False
        for g in self.cfg["games"]:
            if exe_ok(consoles.get(g["console"])):
                continue
            plat = g.get("platform")
            if not plat:
                continue
            n = self.console_for_platform(plat)
            if n and n != g["console"] and exe_ok(consoles[n]):
                g["console"] = n
                changed = True
        if changed:
            save_config(self.cfg)

    def on_consoles_changed(self):
        save_config(self.cfg)
        self.reload_filters()
        self.reassign_unconfigured()
        self.refresh_list()

    def console_choices(self):
        """Opções para o usuário escolher um console (existentes + modelos ainda não criados)."""
        used = {c.get("emu") for c in self.cfg["consoles"].values()}
        opts = {n: ("console", n) for n in self.cfg["consoles"]}
        for eid, spec in KNOWN_EMULATORS.items():
            if eid not in used:
                opts[f"＋ Novo: {spec['label']}"] = ("template", eid)
        return opts

    def ask_console(self, title, msg, can_ignore=False):
        opts = self.console_choices()
        choice = pick_choice(self, title, msg, list(opts),
                             extra=("Ignorar estes arquivos", IGNORE) if can_ignore else None)
        if choice is None or choice == IGNORE:
            return choice
        kind, ref = opts[choice]
        if kind == "template":
            name = create_console(self.cfg, ref)
            self.reload_filters()
            return name
        return ref

    # ---------- detecção de emuladores (em segundo plano)
    def start_emu_detect(self, manual=False):
        if self.detecting:
            return
        self.detecting, self.detect_manual = True, manual
        self.status.set("Procurando emuladores instalados no PC… (pode levar alguns segundos)")
        roots = candidate_roots() + [(f, 5) for f in self.cfg.get("emulator_folders", [])]
        self.bg.submit(self._detect_job, roots)

    def _detect_job(self, roots):
        try:
            found = scan_for_emulators(roots)
        except Exception:
            found = {}
        self.results.put(("emus", found))

    def apply_emulators(self, found):
        consoles = self.cfg["consoles"]
        report = []
        for eid, path in found.items():
            if eid == "retroarch":
                continue
            name = next((n for n, c in consoles.items() if c.get("emu") == eid), None)
            if name is None:
                name = create_console(self.cfg, eid, path)
                report.append(KNOWN_EMULATORS[eid]["label"])
            elif not exe_ok(consoles[name]):
                consoles[name]["exe"] = path
                report.append(KNOWN_EMULATORS[eid]["label"])
        if "retroarch" in found:
            report += self.setup_retroarch(found["retroarch"])
        self.cfg["last_emu_scan"] = int(time.time())
        self.reload_filters()
        self.reassign_unconfigured()
        save_config(self.cfg)
        self.refresh_list()
        if self.emu_dialog is not None and self.emu_dialog.winfo_exists():
            self.emu_dialog.refresh()
        if report:
            self.status.set("Emuladores configurados: " + ", ".join(report))
        elif self.detect_manual:
            self.status.set("Nenhum emulador novo encontrado. Use ⚙ Emuladores para escolher o .exe manualmente.")

    def setup_retroarch(self, exe):
        consoles = self.cfg["consoles"]
        cores_dir = Path(exe).parent / "cores"
        if not cores_dir.is_dir():
            return []
        available = {p.name[: -len(CORE_SUFFIX)] for p in cores_dir.iterdir() if p.name.endswith(CORE_SUFFIX)}
        report = []
        for label, plats, cores, exts in RETROARCH_GROUPS:
            key = "retroarch:" + label
            existing = next((n for n, c in consoles.items() if c.get("emu") == key), None)
            if existing and exe_ok(consoles[existing]):
                continue
            core = next((c for c in cores if c in available), None)
            if not core:
                continue
            args = '-L "' + str(cores_dir / (core + CORE_SUFFIX)) + '" "{rom}" -f'
            if existing:
                consoles[existing]["exe"], consoles[existing]["args"] = exe, args
            else:
                consoles[f"{label} (RetroArch)"] = {
                    "exe": exe, "args": args, "exts": list(exts), "platforms": list(plats), "emu": key,
                }
            report.append(f"{label} (RetroArch)")
        return report

    # ---------- pastas de ROMs (em segundo plano)
    def known_exts(self):
        exts = set(EXT_PLATFORM) | AMBIGUOUS_EXTS
        for c in self.cfg["consoles"].values():
            exts |= set(c.get("exts", []))
        return exts - ARCHIVE_EXTS

    def start_scan(self, manual=False):
        if self.scanning:
            return
        folders = [f for f in self.cfg["rom_folders"] if os.path.isdir(f)]
        if not folders:
            if manual:
                self.status.set("Nenhuma pasta de ROMs configurada.")
                self.open_folders()
            return
        self.scanning, self.scan_manual = True, manual
        self.status.set("Procurando jogos novos nas pastas de ROMs…")
        known = {g["path"] for g in self.cfg["games"]}
        self.bg.submit(self._scan_job, folders, known, set(self.cfg["ignored"]), self.known_exts())

    def _scan_job(self, folders, known, ignored, exts):
        try:
            found = scan_roms(folders, known, ignored, exts)
        except Exception:
            found = []
        self.results.put(("scan", found))

    def make_game(self, path, console, meta=None):
        g = {"path": path, "name": clean_name(path), "console": console,
             "fav": False, "plays": 0, "last": 0}
        if meta and meta[0]:
            g["platform"], g["serial"], g["scanned"] = meta[0], meta[1], True
        else:
            self.analyze(g)
        self.cfg["games"].append(g)
        return g

    def apply_scan(self, found, persist_ignore=True, notify=True):
        existing = {g["path"] for g in self.cfg["games"]}
        ignored = set(self.cfg["ignored"])
        new, unknown = [], []
        for p, plat, serial in found:
            if p in existing or p in ignored:
                continue
            existing.add(p)
            console = self.console_for_platform(plat, create=True) if plat else None
            if console:
                new.append(self.make_game(p, console, (plat, serial)))
            else:
                unknown.append((p, plat, serial))
        skipped = 0
        if unknown:
            ex = os.path.basename(unknown[0][0])
            choice = self.ask_console(
                "Console não reconhecido",
                f"Não consegui identificar o console de {len(unknown)} arquivo(s) (ex.: {ex}).\n"
                "Escolha o console para eles:",
                can_ignore=persist_ignore,
            )
            if choice == IGNORE:
                self.cfg["ignored"] += [u[0] for u in unknown]
                skipped = len(unknown)
            elif choice:
                for p, plat, serial in unknown:
                    new.append(self.make_game(p, choice, (plat, serial) if plat else None))
            else:
                skipped = len(unknown)
        self.reassign_unconfigured()
        save_config(self.cfg)
        self.reload_filters()
        self.refresh_list()
        for g in new:
            self.queue_cover(g)
        if notify and not self.busy():
            msg = f"{len(new)} jogo(s) novo(s) adicionado(s)." if new else "Nenhum jogo novo."
            if skipped:
                msg += f" {skipped} ignorado(s)."
            self.status.set(msg)

    def add_roms(self):
        pats = " ".join("*" + e for e in sorted(self.known_exts() | ARCHIVE_EXTS))
        files = filedialog.askopenfilenames(title="Escolha as ROMs", filetypes=[("ROMs", pats), ("Todos", "*.*")])
        if files:
            found = [(os.path.abspath(p),) + detect(p) for p in files]
            self.apply_scan(found, persist_ignore=False)

    # ---------- análise / migração
    def analyze(self, g):
        plat, serial = (None, None)
        if os.path.exists(g["path"]):
            plat, serial = detect(g["path"])
        if not plat:
            pl = self.cfg["consoles"].get(g["console"], {}).get("platforms", [])
            if len(pl) == 1:
                plat = pl[0]
        if plat in ("PS1", "PS2") and not serial:
            serial = normalize_serial(Path(g["path"]).stem)
        g["platform"], g["serial"], g["scanned"] = plat, serial, True

    def migrate_games(self):
        changed = False
        for g in self.cfg["games"]:
            if not g.get("scanned"):
                self.analyze(g)
                changed = True
        if changed:
            save_config(self.cfg)

    # ---------- inicialização
    def startup_tasks(self):
        due = time.time() - self.cfg.get("last_emu_scan", 0) > 86400
        if due:
            self.start_emu_detect(manual=False)
        if self.cfg["rom_folders"]:
            self.start_scan(manual=False)
        elif not self.cfg["games"]:
            self.open_folders()

    # ---------- capas
    def can_cover(self, g):
        plat = g.get("platform")
        if not plat:
            return False
        if g.get("serial") and plat in self.cfg["cover_sources"]:
            return True
        return bool(PLATFORMS.get(plat, (None, None))[1])

    def queue_cover(self, g, force=False):
        if not self.can_cover(g):
            return
        if g.get("cover") and (COVERS_DIR / g["cover"]).exists() and not force:
            return
        if g.get("cover_tried") and not force:
            return
        if g["path"] in self.pending:
            return
        self.pending.add(g["path"])
        self.status.set(f"Baixando capas… ({len(self.pending)})")
        stems = [Path(g["path"]).stem]
        if g["name"] not in stems:
            stems.append(g["name"])
        self.pool.submit(self._cover_job, g["path"], g["platform"], g.get("serial"), stems,
                         deepcopy(self.cfg["cover_sources"]))

    def _cover_job(self, path, platform, serial, stems, sources):
        try:
            name, miss = fetch_cover(platform, serial, stems, sources)
        except Exception:
            name, miss = "", False
        self.results.put(("cover", (path, name, miss)))

    def queue_all_covers(self):
        for g in self.cfg["games"]:
            self.queue_cover(g)

    def refetch_missing(self):
        n = 0
        for g in self.cfg["games"]:
            if not (g.get("cover") and (COVERS_DIR / g["cover"]).exists()):
                g["cover_tried"] = False
                if self.can_cover(g):
                    self.queue_cover(g)
                    n += 1
        if not n:
            self.status.set("Todos os jogos já têm capa (ou não há fonte de capa para o console).")

    def refetch_selected(self):
        g = self.selected_game()
        if g:
            g["cover_tried"] = False
            if self.can_cover(g):
                self.queue_cover(g, force=True)
            else:
                messagebox.showinfo("Capa", "Sem fonte de capa para este jogo. Tente 'Definir serial…' ou 'Escolher imagem'.")

    def set_serial(self):
        g = self.selected_game()
        if not g:
            return
        s = simpledialog.askstring("Serial", "Serial do jogo (ex.: SCUS-97102):",
                                   initialvalue=g.get("serial") or "", parent=self)
        if not s:
            return
        g["serial"] = normalize_serial(s) or s.strip().upper()
        if not g.get("platform"):
            pl = self.cfg["consoles"].get(g["console"], {}).get("platforms", [])
            g["platform"] = pl[0] if pl else None
        g["cover_tried"] = False
        save_config(self.cfg)
        self.queue_cover(g, force=True)
        self.update_preview()

    def pick_cover(self):
        g = self.selected_game()
        if not g:
            return
        p = filedialog.askopenfilename(title="Escolha a imagem da capa",
                                       filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Todos", "*.*")])
        if not p:
            return
        COVERS_DIR.mkdir(exist_ok=True)
        name = f"custom_{abs(hash(g['path'])) % 10**8}{Path(p).suffix.lower()}"
        shutil.copyfile(p, COVERS_DIR / name)
        self.drop_cached(name)
        g["cover"] = name
        save_config(self.cfg)
        self.refresh_list()

    # ---------- fila de resultados (threads -> interface)
    def poll_results(self):
        covers_changed = False
        try:
            while True:
                kind, payload = self.results.get_nowait()
                if kind == "cover":
                    path, name, miss = payload
                    self.pending.discard(path)
                    g = next((x for x in self.cfg["games"] if x["path"] == path), None)
                    if g:
                        if name:
                            self.drop_cached(name)
                            g["cover"], g["cover_tried"] = name, False
                        elif miss:
                            g["cover_tried"] = True
                        covers_changed = True
                elif kind == "scan":
                    self.scanning = False
                    self.after(0, lambda f=payload: self.apply_scan(f, persist_ignore=True))
                elif kind == "emus":
                    self.detecting = False
                    self.after(0, lambda f=payload: self.apply_emulators(f))
        except queue.Empty:
            pass
        if covers_changed:
            save_config(self.cfg)
            self.refresh_list()
            if not self.busy():
                self.status.set("Capas atualizadas.")
        if self.pending and not self.scanning and not self.detecting:
            self.status.set(f"Baixando capas… ({len(self.pending)})")
        self.after(300, self.poll_results)

    # ---------- ações
    def play(self):
        g = self.selected_game()
        if not g:
            messagebox.showinfo("Jogar", "Selecione um jogo primeiro.")
            return
        if not os.path.exists(g["path"]):
            messagebox.showerror("Jogar", f"Arquivo não encontrado:\n{g['path']}")
            return
        console_cfg = self.cfg["consoles"].get(g["console"])
        if not console_cfg:
            messagebox.showerror("Jogar", "Console deste jogo não existe mais. Use 'Trocar console'.")
            return
        if not exe_ok(console_cfg):
            if messagebox.askyesno(
                "Emulador não configurado",
                f"O emulador de '{g['console']}' ainda não foi encontrado.\nQuer escolher o executável agora?",
            ):
                p = filedialog.askopenfilename(title=f"Executável do emulador - {g['console']}")
                if not p:
                    return
                console_cfg["exe"] = p
                save_config(self.cfg)
            else:
                return
        try:
            cmd = build_command(console_cfg, g["path"])
        except ValueError as e:
            messagebox.showwarning("Emulador", str(e))
            return
        try:
            proc = subprocess.Popen(cmd, cwd=os.path.dirname(console_cfg["exe"]) or None)
        except Exception as e:
            messagebox.showerror("Erro ao abrir", f"{e}\n\nComando:\n{' '.join(cmd)}")
            return
        g["plays"] = g.get("plays", 0) + 1
        g["last"] = int(time.time())
        save_config(self.cfg)
        self.running[proc.pid] = proc
        self.refresh_list()
        self.tree.selection_set(g["path"])
        self.status.set(f"Rodando: {g['name']}  ({g['console']})")

    def toggle_fav(self):
        g = self.selected_game()
        if g:
            g["fav"] = not g.get("fav")
            save_config(self.cfg)
            self.refresh_list()

    def rename(self):
        g = self.selected_game()
        if g:
            n = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=g["name"], parent=self)
            if n:
                g["name"] = n.strip()
                save_config(self.cfg)
                self.refresh_list()

    def change_console(self):
        g = self.selected_game()
        if not g:
            return
        c = self.ask_console("Trocar console", "Novo console para este jogo:")
        if c and c != IGNORE:
            g["console"] = c
            pl = self.cfg["consoles"][c].get("platforms", [])
            if len(pl) == 1 or (g.get("platform") not in pl and pl):
                g["platform"] = g.get("platform") if g.get("platform") in pl else pl[0]
            g["cover_tried"] = False
            save_config(self.cfg)
            self.reload_filters()
            self.refresh_list()
            self.queue_cover(g)

    def remove_game(self):
        g = self.selected_game()
        if g and messagebox.askyesno("Remover", f"Remover '{g['name']}' da biblioteca?\n(o arquivo não é apagado)"):
            self.cfg["games"].remove(g)
            # evita que a próxima varredura recoloque o jogo
            if g["path"] not in self.cfg["ignored"]:
                self.cfg["ignored"].append(g["path"])
            save_config(self.cfg)
            self.refresh_list()

    def open_folder(self):
        g = self.selected_game()
        if not g:
            return
        folder = os.path.dirname(g["path"])
        if IS_WIN:
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def popup(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.menu.tk_popup(event.x_root, event.y_root)

    def open_emulators(self):
        self.emu_dialog = EmulatorsDialog(self)

    def open_folders(self):
        RomFoldersDialog(self)


if __name__ == "__main__":
    Hub().mainloop()
