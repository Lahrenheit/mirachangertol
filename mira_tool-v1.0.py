#!/usr/bin/env python3
"""
Mira Changer Tool v1.0 - Cambia la Mira Normal (mira.tex) y la Mira Telescopica
(PUNTOdeMIRA.tex) dentro del demo.vpk de Torrente Online.  Todo en un solo .py.
https://github.com/Lahrenheit/mirachangertol

 * Muestra la mira actual y, al lado, un desplegable con las miras del VPK
   (las que empiezan por "mira..." / "PUNTOdeMIRA...") con su vista previa.
 * Reemplazar: cambia la mira actual por un .tex o .dds externo (siempre DXT5).
 * Aplicar la seleccionada: copia la mira elegida sobre mira.tex / PUNTOdeMIRA.tex.
 * Exportar la mira actual o la seleccionada a .dds o .tex.
 * Idiomas: espanol, portugues e ingles (selector arriba a la derecha).
 * Siempre se crea una copia .bak del VPK antes del primer cambio.
 * Icono: pone un .ico (ideal "mira_tool.ico") junto al programa y se usa en la barra de titulo,
   la barra de tareas y Alt+Tab. En un .exe se usa el icono incrustado.
 * Si hay un error, se muestra en una ventana y se guarda en mira_tool_error.log.
"""
import os
import sys
import time
import json
import struct
import zlib
import base64
import tempfile
import threading
import contextlib
import webbrowser

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ================================================================ NUCLEO VPK / TEX
# (extraido de vpk_tool v1.1: lectura del VPK, visor de texturas, copia .bak,
#  reemplazo, reconstruccion del VPK y conversion TEX -> DDS / DDS -> TEX)
MAGIC = b"vtPack"
HEADER_SIZE = 0x22
TAG_ROOT, TAG_DIR, TAG_FILE = 0xAAAAAAAA, 0xBBBBBBBB, 0xCCCCCCCC
COPY_BUF = 4 * 1024 * 1024
_BACKED = set()   # VPK que ya tienen copia .bak en esta sesion

LANGS = [("es", "Espa\u00f1ol"), ("pt", "Portugu\u00eas"), ("en", "English")]
_LANG = {"v": "es"}
_LANG_CFG = os.path.join(os.path.expanduser("~"), ".mira_tool_lang")

I18N = {
    'e_notvpk': ("No es un archivo vtPack (falta la firma 'vtPack').", "Não é um arquivo vtPack (falta a assinatura 'vtPack').", "Not a vtPack file (missing 'vtPack' signature)."),
    'e_tocoff': ('Offset de tabla invalido: %d', 'Offset da tabela inválido: %d', 'Invalid table offset: %d'),
    'e_toctrunc': ('La tabla esta truncada o corrupta.', 'A tabela está truncada ou corrompida.', 'The table is truncated or corrupt.'),
    'c_warn_hdr': ('Aviso: la cabecera dice %d registros y la tabla tiene %d.', 'Aviso: o cabeçalho diz %d registros e a tabela tem %d.', 'Warning: the header says %d records but the table has %d.'),
    'e_vpktrunc': ('VPK truncado leyendo %s', 'VPK truncado ao ler %s', 'VPK truncated while reading %s'),
    'e_4gb_vpk': ('El VPK superaria 4 GB; el formato usa offsets de 32 bits.', 'O VPK passaria de 4 GB; o formato usa offsets de 32 bits.', 'The VPK would exceed 4 GB; the format uses 32-bit offsets.'),
    'be_backup': ('Copia de seguridad: %s', 'Cópia de segurança: %s', 'Backup copy: %s'),
    'be_modified': ('Anadidos: %d archivos nuevos, reemplazados: %d, eliminados: %d registros.', 'Adicionados: %d arquivos novos, substituídos: %d, excluídos: %d registros.', 'Added: %d new files, replaced: %d, deleted: %d records.'),
    'c_files_n': ('archivos', 'arquivos', 'files'),
}


def load_lang():
    """Idioma elegido la ultima vez."""
    try:
        with open(_LANG_CFG, encoding="utf-8") as fh:
            code = fh.read().strip()
        if code in [c for c, _ in LANGS]:
            _LANG["v"] = code
    except Exception:  # noqa
        pass


def save_lang():
    try:
        with open(_LANG_CFG, "w", encoding="utf-8") as fh:
            fh.write(_LANG["v"])
    except Exception:  # noqa
        pass


def tr(key, *args):
    t = I18N[key][[c for c, _ in LANGS].index(_LANG["v"])]
    return t % args if args else t

def console_progress(done, total, fdone, ftotal, name, final=False):
    pct = 100.0 if total == 0 else done * 100.0 / total
    if sys.stdout.isatty():
        w = 30
        k = int(w * pct / 100)
        line = "\r[%s%s] %5.1f%%  %d/%d %s  %s" % (
            "#" * k, "-" * (w - k), pct, fdone, ftotal, tr("c_files_n"), name[-35:].ljust(35))
        sys.stdout.write(line + ("\n" if final else ""))
        sys.stdout.flush()
    else:
        step = int(pct // 10)
        if final or step > console_progress.last:
            console_progress.last = step
            print("%3d%%  %d/%d %s" % (int(pct), fdone, ftotal, tr("c_files_n")))
console_progress.last = -1

progress_cb = console_progress   # la ventana lo reemplaza



class Progress:
    def __init__(self, total_bytes, total_files):
        self.total, self.ftotal = total_bytes, total_files
        self.done = self.fdone = 0
        self.name = ""
        self.last = 0.0
        console_progress.last = -1
        self._emit(False)

    def _emit(self, final):
        progress_cb(self.done, self.total, self.fdone, self.ftotal, self.name, final) \
            if progress_cb is console_progress else \
            progress_cb(self.done, self.total, self.fdone, self.ftotal, self.name)

    def add(self, nbytes, name=None):
        self.done += nbytes
        if name is not None:
            self.name = name
        now = time.time()
        if now - self.last >= 0.05:
            self.last = now
            self._emit(False)

    def file_done(self):
        self.fdone += 1

    def finish(self):
        self.done, self.fdone = self.total, self.ftotal
        self._emit(True)


def _run_safe(fn, *args):
    try:
        fn(*args)
    except SystemExit as e:
        if e.code not in (None, 0):
            print("ERROR:", e.code)
    except Exception as e:  # noqa
        print("ERROR: %s: %s" % (type(e).__name__, e))


def read_toc(f):
    f.seek(0, 2)
    total = f.tell()
    f.seek(0)
    head = f.read(HEADER_SIZE)
    if len(head) < HEADER_SIZE or head[:6] != MAGIC:
        raise SystemExit(tr("e_notvpk"))
    hdr_extra = head[6:0x16]
    data_start, count, toc_off = struct.unpack_from("<III", head, 0x16)
    if not (HEADER_SIZE <= toc_off <= total):
        raise SystemExit(tr("e_tocoff", toc_off))
    f.seek(toc_off)
    toc = f.read(total - toc_off)
    recs, p = [], 0
    try:
        while p < len(toc):
            nl, = struct.unpack_from("<I", toc, p); p += 4
            name = toc[p:p + nl]; p += nl
            dl, = struct.unpack_from("<I", toc, p); p += 4
            dr = toc[p:p + dl]; p += dl
            flag, s1, s2, off, tag, typ = struct.unpack_from("<iIIIII", toc, p); p += 24
            if name.endswith(b"\0"):
                name = name[:-1]
            if dr.endswith(b"\0"):
                dr = dr[:-1]
            recs.append(dict(name=name, dir=dr, flag=flag, size=s1, size2=s2,
                             off=off, tag=tag, type=typ))
    except struct.error:
        raise SystemExit(tr("e_toctrunc"))
    if len(recs) != count:
        print(tr("c_warn_hdr", count, len(recs)),
              file=sys.stderr)
    return dict(hdr_extra=hdr_extra, data_start=data_start, toc_off=toc_off,
                total=total, recs=recs)


def rec_display(r):
    """Ruta tal como la muestra el UnpaKer (dir + nombre, con \\)."""
    return (r["dir"] + r["name"]).decode("cp1252", errors="replace")


def _rgb565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def decode_dxt(w, h, fmt, data, step=1):
    """Decodifica DXT1 (fmt 0) o DXT5 (fmt 1) tomando 1 de cada 'step' pixeles.
    Devuelve (ancho, alto, bytearray RGBA)."""
    bw, bh = (w + 3) // 4, (h + 3) // 4
    bpb = 8 if fmt == 0 else 16
    ow, oh = (w + step - 1) // step, (h + step - 1) // step
    out = bytearray(ow * oh * 4)
    for by in range(bh):
        ys = [j for j in range(4) if (by * 4 + j) % step == 0 and by * 4 + j < h]
        if not ys:
            continue
        for bx in range(bw):
            xs = [i for i in range(4) if (bx * 4 + i) % step == 0 and bx * 4 + i < w]
            if not xs:
                continue
            o = (by * bw + bx) * bpb
            blk = data[o:o + bpb]
            if len(blk) < bpb:
                continue
            if fmt == 1:
                a0, a1 = blk[0], blk[1]
                abits = int.from_bytes(blk[2:8], "little")
                if a0 > a1:
                    al = [a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)]
                else:
                    al = [a0, a1] + [((5 - k) * a0 + k * a1) // 5 for k in range(1, 5)] + [0, 255]
                cb = blk[8:16]
            else:
                cb = blk
            c0, c1, bits = struct.unpack("<HHI", cb)
            r0, g0, b0 = _rgb565(c0)
            r1, g1, b1 = _rgb565(c1)
            if c0 > c1 or fmt == 1:
                pal = [(r0, g0, b0, 255), (r1, g1, b1, 255),
                       ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255),
                       ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255)]
            else:
                pal = [(r0, g0, b0, 255), (r1, g1, b1, 255),
                       ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255), (0, 0, 0, 0)]
            for j in ys:
                for i in xs:
                    k = j * 4 + i
                    px = pal[(bits >> (2 * k)) & 3]
                    a = px[3] if fmt == 0 else al[(abits >> (3 * k)) & 7]
                    q = (((by * 4 + j) // step) * ow + (bx * 4 + i) // step) * 4
                    out[q], out[q + 1], out[q + 2], out[q + 3] = px[0], px[1], px[2], a
    return ow, oh, out


def _png_rgb(w, h, raw):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def tex_preview(data, box=440, ignore_alpha=False):
    """Convierte un .tex (TeX2, DXT1/DXT5) en un PNG que cabe en box x box.
    Devuelve (bytes_png, texto_info). La transparencia se muestra sobre un tablero gris."""
    if data[:4] != b"TeX2":
        raise ValueError("no es un TeX2")
    fmt = data[4]
    if fmt not in (0, 1):
        raise ValueError("formato %d no soportado" % fmt)
    w, h, sz = struct.unpack("<III", data[9:21])
    if w == 0 or h == 0 or w > 8192 or h > 8192:
        raise ValueError("tamano invalido %dx%d" % (w, h))
    step = 1
    while max(w, h) // step > 1024:
        step *= 2
    ow, oh, rgba = decode_dxt(w, h, fmt, data[21:21 + sz], step)
    sc = min(box / ow, box / oh, 1.0)
    nw, nh = max(1, int(ow * sc)), max(1, int(oh * sc))
    xi = [min(ow - 1, int(x / sc)) for x in range(nw)]
    raw = bytearray()
    for y in range(nh):
        base = min(oh - 1, int(y / sc)) * ow * 4
        row = bytearray(nw * 3)
        for x in range(nw):
            q = base + xi[x] * 4
            r, g, b, a = rgba[q], rgba[q + 1], rgba[q + 2], rgba[q + 3]
            if a != 255 and not ignore_alpha:
                bg = 205 if ((x >> 3) + (y >> 3)) & 1 else 140
                r, g, b = (r * a + bg * (255 - a)) // 255, (g * a + bg * (255 - a)) // 255, \
                          (b * a + bg * (255 - a)) // 255
            row[x * 3:x * 3 + 3] = bytes((r, g, b))
        raw += b"\0" + row
    return _png_rgb(nw, nh, bytes(raw)), "%dx%d  %s" % (w, h, "DXT1" if fmt == 0 else "DXT5")


def _bak_name(vpk):
    n = vpk + ".bak"
    k = 1
    while os.path.exists(n):
        n = "%s.%d.bak" % (vpk, k)
        k += 1
    return n


def backup_copy(vpk):
    """Hace una copia .bak del VPK antes del primer cambio directo de la sesion."""
    key = os.path.realpath(vpk)
    if key in _BACKED:
        return None
    bak = _bak_name(vpk)
    pr = Progress(os.path.getsize(vpk), 1)
    label = "Copia de seguridad: " + os.path.basename(bak)
    with open(vpk, "rb") as fi, open(bak, "wb") as fo:
        while True:
            c = fi.read(COPY_BUF)
            if not c:
                break
            fo.write(c)
            pr.add(len(c), label)
    pr.file_done()
    pr.finish()
    _BACKED.add(key)
    print(tr("be_backup", bak))
    return bak


def replace_in_vpk(vpk, rec, srcfile):
    """Reemplaza el contenido de un archivo DENTRO del VPK sin mover nada mas
    (como el 'Reemplazar' del UnpaKer original):
      igual tamano -> se reemplaza
      mayor        -> se escribe solo hasta el tamano original
      menor        -> se escribe y el resto se rellena con ceros (00)
    Devuelve (bytes_escritos, tamano_original, tamano_nuevo)."""
    with open(srcfile, "rb") as fh:
        data = fh.read()
    size = rec["size"]
    chunk = data[:size] + b"\0" * max(0, size - len(data))
    with open(vpk, "r+b") as f:
        f.seek(rec["off"])
        f.write(chunk)
    return min(len(data), size), size, len(data)


def _toc_bytes(r):
    nm, dr = r["name"], r["dir"]
    b = struct.pack("<I", len(nm) + 1) + nm + b"\0"
    b += struct.pack("<I", len(dr) + 1 if dr else 0) + (dr + b"\0" if dr else b"")
    return b + struct.pack("<iIIIII", r["flag"], r["size"], r["size"], r["off"], r["tag"], r["type"])


def modify_vpk(vpk, remove_keys=(), adds=()):
    """Edita el VPK: elimina registros (clave = (dir, nombre, tipo)) y anade o reemplaza archivos
    y carpetas. Reescribe el VPK completo en un archivo temporal (datos contiguos, sin restos),
    deja el original como copia .bak (una vez por sesion) y pone el nuevo en su lugar."""
    with open(vpk, "rb") as f0:
        t = read_toc(f0)
    old = t["recs"]
    remove_keys = set(remove_keys)
    keep = [r for r in old if (r["dir"], r["name"], r["type"]) not in remove_keys]
    removed = len(old) - len(keep)
    index = {(r["dir"].upper(), r["name"].upper(), r["type"]): r for r in keep}
    new_recs, n_new, n_rep = [], 0, 0
    for a in adds:
        typ = 1 if a["kind"] == "d" else 2
        k = (a["dir"].upper(), a["name"].upper(), typ)
        if k in index:
            if typ == 2:
                index[k]["src"] = a["src"]
                n_rep += 1
            continue
        top = (a["dir"] == b"")
        r = dict(name=a["name"], dir=a["dir"], flag=-1 if (top and typ == 1) else 0, size=0,
                 size2=0, off=0, type=typ, src=a["src"],
                 tag=(TAG_ROOT if top else TAG_DIR) if typ == 1 else TAG_FILE)
        new_recs.append(r)
        index[k] = r
        if typ == 2:
            n_new += 1
    allr = keep + new_recs
    # orden de la tabla: por carpeta, sus entradas y luego cada subcarpeta (como el original)
    kids = {}
    for r in allr:
        kids.setdefault(r["dir"], []).append(r)
    out, seen_dirs = [], set()

    def emit(d):
        if d in seen_dirs:
            return
        seen_dirs.add(d)
        items = kids.get(d, [])
        out.extend(items)
        for r in items:
            if r["type"] == 1:
                emit(r["dir"] + r["name"] + b"\\")
    emit(b"")
    ids = {id(r) for r in out}
    out.extend(r for r in allr if id(r) not in ids)   # huerfanos (por si acaso)

    files = [r for r in out if r["type"] == 2]
    sizes = [os.path.getsize(r["src"]) if r.get("src") else r["size"] for r in files]
    pr = Progress(sum(sizes), len(files))
    tmp = vpk + ".tmp"
    bak = None
    try:
        with open(vpk, "rb") as fi, open(tmp, "wb") as o:
            o.write(b"\0" * HEADER_SIZE)
            toc = bytearray()
            for r in out:
                if r["type"] == 2:
                    off = o.tell()
                    label = rec_display(r)
                    if r.get("src"):
                        with open(r["src"], "rb") as fs_:
                            while True:
                                c = fs_.read(COPY_BUF)
                                if not c:
                                    break
                                o.write(c)
                                pr.add(len(c), label)
                    else:
                        fi.seek(r["off"])
                        left = r["size"]
                        while left:
                            c = fi.read(min(COPY_BUF, left))
                            if not c:
                                raise SystemExit(tr("e_vpktrunc", label))
                            o.write(c)
                            left -= len(c)
                            pr.add(len(c), label)
                    if o.tell() >= 0xFFFFFFFF:
                        raise SystemExit(tr("e_4gb_vpk"))
                    r["off"], r["size"] = off, o.tell() - off
                    pr.file_done()
                toc += _toc_bytes(r)
            toc_off = o.tell()
            o.write(toc)
            o.seek(0)
            o.write(MAGIC + t["hdr_extra"] + struct.pack("<III", HEADER_SIZE, len(out), toc_off))
        pr.finish()
        key = os.path.realpath(vpk)
        if key not in _BACKED:
            bak = _bak_name(vpk)
            os.replace(vpk, bak)
            _BACKED.add(key)
        try:
            os.replace(tmp, vpk)
        except Exception:
            if bak:
                os.replace(bak, vpk)
                _BACKED.discard(key)
                bak = None
            raise
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    if bak:
        print(tr("be_backup", bak))
    print(tr("be_modified", n_new, n_rep, removed))


def mips(w, h, bpb, size):
    n, tot = 0, 0
    while tot < size:
        tot += max(w // 4, 1) * max(h // 4, 1) * bpb
        w, h, n = max(w // 2, 1), max(h // 2, 1), n + 1
    return n


def tex2dds(b):
    if b[:4] != b'TeX2':
        raise ValueError('no es un TeX2')
    fmt = b[4]
    w, h, sz = struct.unpack('<III', b[9:21])
    fourcc = {0: b'DXT1', 1: b'DXT5'}[fmt]
    bpb = 8 if fmt == 0 else 16
    n = mips(w, h, bpb, sz)
    flags = 0x81007 | (0x20000 if n > 1 else 0)
    caps = 0x1000 | (0x400008 if n > 1 else 0)
    hdr = (b'DDS ' + struct.pack('<7I', 124, flags, h, w, sz, 0, n) + b'\0' * 44 +
           struct.pack('<II4s5I', 32, 4, fourcc, 0, 0, 0, 0, 0) +
           struct.pack('<5I', caps, 0, 0, 0, 0))
    return hdr + b[21:21 + sz]


def dds2tex(b):
    """Acepta DXT1/DXT5 (tambien BC1/BC3 con cabecera DX10). Se queda SOLO con el nivel
    principal: los .tex originales casi nunca llevan mipmaps y el juego se cuelga si
    el tamano de datos no coincide con lo que espera."""
    if b[:4] != b'DDS ':
        raise ValueError('no es un DDS')
    h, w = struct.unpack('<II', b[12:20])
    fc = b[84:88]
    off = 128
    if fc == b'DX10':
        dxgi = struct.unpack('<I', b[128:132])[0]
        off = 148
        fc = {70: b'DXT1', 71: b'DXT1', 72: b'DXT1', 76: b'DXT5', 77: b'DXT5',
              78: b'DXT5'}.get(dxgi, b'DX10/%d' % dxgi)
    fmt = {b'DXT1': 0, b'DXT5': 1}.get(fc)
    if fmt is None:
        raise ValueError('formato %r no soportado: guardalo como DXT1 (sin alfa) o DXT5 (con alfa)' % fc)
    bpb = 8 if fmt == 0 else 16
    sz = max(w // 4, 1) * max(h // 4, 1) * bpb
    data = b[off:off + sz]
    if len(data) != sz:
        raise ValueError('el DDS esta incompleto')
    return b'TeX2' + bytes([fmt]) + struct.pack('<I', 1) + struct.pack('<III', w, h, sz) + data


# ================================================================ TEXTOS DE LA APP (es, pt, en)
I18N.update({
    "lang_lbl": ("Idioma:", "Idioma:", "Language:"),
    "btn_open": ("Leer", "Ler", "Read"),
    "chk_alpha": ("Ignorar transparencia (alfa)", "Ignorar transparência (alfa)",
                  "Ignore transparency (alpha)"),
    "status_init": ("Pulsa 'Leer' y elige tu demo.vpk.",
                    "Clique em 'Ler' e escolha seu demo.vpk.",
                    "Press 'Read' and choose your demo.vpk."),
    "t_normal": ("Mira Normal (mira.tex)", "Mira Normal (mira.tex)", "Normal Crosshair (mira.tex)"),
    "t_scope": ("Mira Telescópica (PUNTOdeMIRA.tex)", "Mira Telescópica (PUNTOdeMIRA.tex)",
                "Scope Crosshair (PUNTOdeMIRA.tex)"),
    "lbl_current": ("Actual", "Atual", "Current"),
    "lbl_avail": ("Miras disponibles:", "Miras disponíveis:", "Available crosshairs:"),
    "btn_replace": ("Reemplazar...", "Substituir...", "Replace..."),
    "btn_export_cur": ("Exportar actual...", "Exportar atual...", "Export current..."),
    "btn_export_sel": ("Exportar seleccionada...", "Exportar selecionada...", "Export selected..."),
    "btn_apply": ("Aplicar la seleccionada", "Aplicar a selecionada", "Apply selected"),
    "not_found": ("No se encontró %s en el VPK", "%s não foi encontrado no VPK",
                  "%s was not found in the VPK"),
    "no_miras": ("(sin miras)", "(sem miras)", "(no crosshairs)"),
    "cant_show": ("No se puede mostrar:\n%s", "Não é possível mostrar:\n%s",
                  "Cannot display:\n%s"),
    "unsupported_tex": ("Formato de textura no compatible (solo DXT1/DXT5).",
                        "Formato de textura incompatível (apenas DXT1/DXT5).",
                        "Unsupported texture format (only DXT1/DXT5)."),
    "ext_prefix": ("Externa: %s", "Externa: %s", "External: %s"),
    "read_ok": ("Leído: %s", "Lido: %s", "Read: %s"),
    "progress": ("%.1f%%  -  %d/%d archivos  -  %s", "%.1f%%  -  %d/%d arquivos  -  %s",
                 "%.1f%%  -  %d/%d files  -  %s"),
    "dlg_pick_vpk": ("Elegir VPK", "Escolher VPK", "Choose VPK"),
    "ft_all": ("Todos", "Todos", "All"),
    "ft_tex": ("Texturas", "Texturas", "Textures"),
    "need_vpk": ("Primero pulsa 'Leer' y elige un VPK.", "Primeiro clique em 'Ler' e escolha um VPK.",
                 "First press 'Read' and choose a VPK."),
    "no_target": ("No existe %s en este VPK.", "%s não existe neste VPK.",
                  "%s does not exist in this VPK."),
    "already_current": ("Esa ya es la mira actual.", "Essa já é a mira atual.",
                        "That is already the current crosshair."),
    "pick_ext": ("Textura externa (.tex o .dds) - debe ser DXT5",
                 "Textura externa (.tex ou .dds) - deve ser DXT5",
                 "External texture (.tex or .dds) - must be DXT5"),
    "dxt5_required": (
        "La textura tiene que ser DXT5 para que el juego la lea correctamente "
        "(las miras siempre son DXT5).\nFormato detectado: %s\n\n"
        "Guardala como DXT5 y vuelve a intentarlo.",
        "A textura precisa ser DXT5 para que o jogo a leia corretamente "
        "(as miras são sempre DXT5).\nFormato detectado: %s\n\n"
        "Salve-a como DXT5 e tente novamente.",
        "The texture must be DXT5 for the game to read it correctly "
        "(crosshairs are always DXT5).\nDetected format: %s\n\n"
        "Save it as DXT5 and try again."),
    "bad_texture": (
        "No es un .tex (TeX2) o un .dds valido, o su formato no es compatible.\n"
        "Recuerda: el formato tiene que ser DXT5 para que el juego lo lea correctamente.",
        "Não é um .tex (TeX2) ou .dds válido, ou o formato é incompatível.\n"
        "Lembre-se: o formato precisa ser DXT5 para que o jogo o leia corretamente.",
        "Not a valid .tex (TeX2) or .dds file, or its format is unsupported.\n"
        "Remember: the format must be DXT5 for the game to read it correctly."),
    "warn_internal_fmt": (
        "Aviso: esta mira es %s. Las miras tienen que ser DXT5 para que el juego las lea "
        "correctamente.\n\n",
        "Aviso: esta mira é %s. As miras precisam ser DXT5 para que o jogo as leia "
        "corretamente.\n\n",
        "Warning: this crosshair is %s. Crosshairs must be DXT5 for the game to read them "
        "correctly.\n\n"),
    "warn_export_fmt": (
        "Aviso: esta mira es %s. Para volver a importarla debe ser DXT5 "
        "(las miras siempre son DXT5 para que el juego las lea correctamente).",
        "Aviso: esta mira é %s. Para importá-la novamente ela deve ser DXT5 "
        "(as miras são sempre DXT5 para que o jogo as leia corretamente).",
        "Warning: this crosshair is %s. To import it again it must be DXT5 "
        "(crosshairs are always DXT5 for the game to read them correctly)."),
    "the_ext_file": ("el archivo externo %s", "o arquivo externo %s", "the external file %s"),
    "confirm_title": ("Confirmar", "Confirmar", "Confirm"),
    "confirm_body": (
        "Reemplazar %s\npor %s\n\n%s\n\nSe crea una copia .bak del VPK.\n\n¿Continuar?",
        "Substituir %s\npor %s\n\n%s\n\nUma cópia .bak do VPK é criada.\n\nContinuar?",
        "Replace %s\nwith %s\n\n%s\n\nA .bak copy of the VPK is created.\n\nContinue?"),
    "same_size": ("Mismo tamaño: se escribe en el sitio.",
                  "Mesmo tamanho: é gravado no lugar.", "Same size: written in place."),
    "diff_size": ("Distinto tamaño: se reconstruye el VPK completo (puede tardar).",
                  "Tamanho diferente: o VPK inteiro é reconstruído (pode demorar).",
                  "Different size: the whole VPK is rebuilt (may take a while)."),
    "be_inplace": ("Reemplazado en el sitio (mismo tamaño).",
                   "Substituído no lugar (mesmo tamanho).", "Replaced in place (same size)."),
    "done_ok": ("Listo.", "Pronto.", "Done."),
    "title_apply": ("Aplicar", "Aplicar", "Apply"),
    "title_replace": ("Reemplazar", "Substituir", "Replace"),
    "title_export": ("Exportar", "Exportar", "Export"),
    "save_as": ("Guardar mira como", "Salvar mira como", "Save crosshair as"),
    "exported": ("Exportado: %s", "Exportado: %s", "Exported: %s"),
    "link_title": ("Enlace", "Link", "Link"),
    "link_fail": ("No se pudo abrir el navegador.", "Não foi possível abrir o navegador.",
                  "Could not open the browser."),
})

# ================================================================ INTERFAZ
APP_TITLE = "Mira Changer Tool v1.0"
REPO_URL = "https://github.com/Lahrenheit/mirachangertol"
BOX_DEF = 128                   # lado del visor mientras no hay VPK
MAXBOX = 256                    # lado maximo del visor (las texturas se ven a tamano real)
TARGETS = (                     # (clave del titulo, archivo destino, prefijo del desplegable)
    ("t_normal", b"mira.tex", b"mira"),
    ("t_scope", b"puntodemira.tex", b"puntodemira"),
)
CFG = os.path.join(os.path.expanduser("~"), ".mira_tool_cfg")
HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else HERE
BOLD9 = ("MS Sans Serif", 9, "bold")


def rec_bytes(vpk, rec):
    with open(vpk, "rb") as f:
        f.seek(rec["off"])
        return f.read(rec["size"])


def rec_label(r):
    return rec_display(r)


def tex_format(data):
    """'DXT1' / 'DXT5' / '?' segun la cabecera TeX2."""
    if len(data) < 5 or data[:4] != b"TeX2":
        return "?"
    return {0: "DXT1", 1: "DXT5"}.get(data[4], "?")


def tex_dims(data):
    """(ancho, alto) de un TeX2, o None."""
    if len(data) < 17 or data[:4] != b"TeX2":
        return None
    w, h = struct.unpack("<II", data[9:17])
    return (w, h) if 0 < w <= 8192 and 0 < h <= 8192 else None


def open_url(url):
    try:
        if webbrowser.open(url):
            return True
    except Exception:  # noqa
        pass
    try:                       # respaldo en Windows
        os.startfile(url)      # noqa
        return True
    except Exception:  # noqa
        return False


# ---------------------------------------------------------------- icono de la aplicacion
APP_ID = "Lahrenheit.MiraChangerTool.1"   # identidad propia en la barra de tareas de Windows
_ICON_KEEP = []                            # referencias a los iconos (que no se pierdan)


def find_icon(exts, bases):
    """Busca un icono en las carpetas dadas. Prefiere mira_tool.ico / icon.ico / icono.ico /
    app.ico; si no, el primero por orden alfabetico."""
    pref = ("mira_tool", "mira", "icon", "icono", "app", "main")
    seen = []
    for b in bases:
        if not b or b in seen or not os.path.isdir(b):
            continue
        seen.append(b)
        try:
            files = [f for f in os.listdir(b) if f.lower().endswith(exts)]
        except OSError:
            continue
        if files:
            def key(f):
                stem = os.path.splitext(f)[0].lower()
                return (pref.index(stem) if stem in pref else 99, f.lower())
            return os.path.join(b, sorted(files, key=key)[0])
    return None


def exe_icon_bytes(path):
    """Reconstruye un .ico a partir del icono incrustado en un .exe (recursos RT_GROUP_ICON y
    RT_ICON del formato PE). Es el icono que elegiste en auto-py-to-exe. Devuelve bytes o None."""
    u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
    u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
    with open(path, "rb") as f:
        def rd(off, n):
            f.seek(off)
            return f.read(n)
        head = rd(0, 65536)
        if head[:2] != b"MZ":
            return None
        pe = u32(head, 0x3C)
        if head[pe:pe + 4] != b"PE\0\0":
            return None
        nsec, optsz = u16(head, pe + 6), u16(head, pe + 20)
        opt = pe + 24
        dd = opt + (112 if u16(head, opt) == 0x20B else 96)       # PE32+ / PE32
        rsrc_rva = u32(head, dd + 16)
        if not rsrc_rva:
            return None
        secs = []
        for i in range(nsec):
            o = opt + optsz + 40 * i
            secs.append((u32(head, o + 12), max(u32(head, o + 8), u32(head, o + 16)),
                         u32(head, o + 20)))                       # (rva, tamano, offset en disco)

        def off_of(rva):
            for va, size, raw in secs:
                if va <= rva < va + size:
                    return rva - va + raw
            return None
        base = off_of(rsrc_rva)
        if base is None:
            return None

        def entries(off):
            h = rd(off, 16)
            n = u16(h, 12) + u16(h, 14)
            out = []
            for i in range(n):
                e = rd(off + 16 + 8 * i, 8)
                nid, ptr = u32(e, 0), u32(e, 4)
                out.append((nid, bool(ptr & 0x80000000), ptr & 0x7FFFFFFF))
            return out

        def first_leaf(ptr, is_dir):
            """Baja por los niveles (nombre / idioma) hasta los datos del primer recurso."""
            while is_dir:
                sub = entries(base + ptr)
                if not sub:
                    return None
                _, is_dir, ptr = sub[0]
            d = rd(base + ptr, 16)
            o = off_of(u32(d, 0))
            return None if o is None else rd(o, u32(d, 4))

        groups, icons = None, {}
        for tid, is_dir, ptr in entries(base):
            if tid == 14 and is_dir:                                # RT_GROUP_ICON
                sub = entries(base + ptr)
                if sub:
                    groups = first_leaf(sub[0][2], sub[0][1])
            elif tid == 3 and is_dir:                               # RT_ICON
                for iid, d2, p2 in entries(base + ptr):
                    if not iid & 0x80000000:
                        data = first_leaf(p2, d2)
                        if data:
                            icons[iid] = data
    if not groups or len(groups) < 6 or not icons:
        return None
    count = u16(groups, 4)
    items = []
    for i in range(count):
        w, h, cc, _r, planes, bits, _sz, iid = struct.unpack_from("<BBBBHHIH", groups, 6 + 14 * i)
        if iid in icons:
            items.append((w, h, cc, planes, bits, icons[iid]))
    if not items:
        return None
    out = bytearray(struct.pack("<HHH", 0, 1, len(items)))
    pos = 6 + 16 * len(items)
    for w, h, cc, planes, bits, data in items:
        out += struct.pack("<BBBBHHII", w, h, cc, 0, planes, bits, len(data), pos)
        pos += len(data)
    for item in items:
        out += item[5]
    return bytes(out)


def exe_icon_file():
    """Guarda el icono incrustado del .exe en un .ico temporal (para que Tk lo use)."""
    try:
        data = exe_icon_bytes(sys.executable)
        if not data:
            return None
        import atexit
        path = os.path.join(tempfile.gettempdir(), "mira_changer_tool_%d.ico" % os.getpid())
        with open(path, "wb") as fh:
            fh.write(data)

        def rm():
            try:
                os.remove(path)
            except OSError:
                pass
        atexit.register(rm)
        return path
    except Exception:  # noqa
        return None


def resolve_icon():
    """Ruta de un .ico a usar, o None. Como .exe: primero un .ico incluido en el paquete,
    luego el icono incrustado en el .exe y por ultimo un .ico junto al .exe.
    Como .py: un .ico junto al programa."""
    argdir = os.path.dirname(os.path.abspath(sys.argv[0] or "."))
    if getattr(sys, "frozen", False):
        return (find_icon((".ico",), [getattr(sys, "_MEIPASS", None)])
                or exe_icon_file()
                or find_icon((".ico",), [APP_DIR, argdir]))
    return find_icon((".ico",), [HERE, argdir])


def win_set_app_id():
    """Windows: sin esto la barra de tareas agrupa la ventana bajo Python (o muestra otro icono)
    en vez del tuyo. Hay que llamarlo antes de crear la ventana."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:  # noqa
        pass


def _win_load_ico(path):
    """Carga el .ico en tamano grande (barra de tareas, Alt+Tab) y pequeno (barra de titulo)."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.LoadImageW.restype = wintypes.HANDLE
    u.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                             ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u.GetSystemMetrics.argtypes = [ctypes.c_int]

    def load(cx, cy):   # IMAGE_ICON = 1, LR_LOADFROMFILE = 0x10
        return u.LoadImageW(None, path, 1, u.GetSystemMetrics(cx), u.GetSystemMetrics(cy), 0x10)
    return load(11, 12), load(49, 50)      # SM_CXICON/CYICON, SM_CXSMICON/CYSMICON


def _win_exe_icons():
    """Ultimo recurso: icono del .exe via la API de Windows."""
    import ctypes
    from ctypes import wintypes
    large, small = wintypes.HICON(), wintypes.HICON()
    sh = ctypes.windll.shell32
    sh.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON),
                                  ctypes.POINTER(wintypes.HICON), wintypes.UINT]
    if sh.ExtractIconExW(sys.executable, 0, ctypes.byref(large), ctypes.byref(small), 1) < 1:
        return None, None
    return large.value, small.value


def _win_apply(root, big, small):
    """Pone el icono a la ventana (barra de titulo, barra de tareas, Alt+Tab) y a su clase,
    para que tambien lo hereden las ventanas secundarias."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    root.update_idletasks()
    u.GetParent.restype = wintypes.HWND
    u.GetParent.argtypes = [wintypes.HWND]
    u.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
    setcls = getattr(u, "SetClassLongPtrW", None) or u.SetClassLongW
    setcls.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    setcls.restype = ctypes.c_void_p
    if big:
        u.SendMessageW(hwnd, 0x80, 1, big)       # WM_SETICON, ICON_BIG
        setcls(hwnd, -14, big)                   # GCLP_HICON
    if small:
        u.SendMessageW(hwnd, 0x80, 0, small)     # WM_SETICON, ICON_SMALL
        setcls(hwnd, -34, small)                 # GCLP_HICONSM


def set_app_icon(root):
    """Pone el icono de la aplicacion (en lugar de la pluma de Tk) en TODOS lados: barra de titulo,
    barra de tareas, Alt+Tab y ventanas secundarias. Nunca falla: si no puede, deja el de Tk."""
    if os.name == "nt":
        ico = resolve_icon()
        ok = False
        if ico:
            try:
                root.iconbitmap(default=ico)       # el metodo de Tk: tambien ventanas futuras
                ok = True
            except Exception:  # noqa
                pass
        big = small = None
        try:
            if ico:
                big, small = _win_load_ico(ico)
            if not (big or small) and getattr(sys, "frozen", False):
                big, small = _win_exe_icons()
        except Exception:  # noqa
            pass
        if big or small:
            _ICON_KEEP.append((big, small))

            def again(ev=None):
                if ev is not None and ev.widget is not root:
                    return                       # solo la ventana principal, no sus widgets
                try:
                    _win_apply(root, big, small)
                except Exception:  # noqa
                    pass
            again()
            # Tk vuelve a poner su icono al mostrar la ventana por primera vez: se reaplica despues
            root.after(150, again)
            root.after(600, again)
            root.after(1500, again)
            root.bind("<Map>", again, add="+")
            ok = True
        return ok
    argdir = os.path.dirname(os.path.abspath(sys.argv[0] or "."))
    png = find_icon((".png",), [HERE, argdir])     # Linux / macOS
    if png:
        try:
            img = tk.PhotoImage(file=png)
            root.iconphoto(True, img)
            _ICON_KEEP.append(img)
            return True
        except Exception:  # noqa
            pass
    return False


# ---------------------------------------------------------------- panel de una mira
class MiraPanel:
    def __init__(self, app, parent, title_key, target_name, prefix):
        self.app, self.target_name, self.prefix = app, target_name, prefix
        self.target = None
        self.cands = []
        self.ext = None            # (bytes TeX2, nombre) mientras se confirma una textura externa
        self.bw = self.bh = BOX_DEF   # tamano de los visores = tamano de la textura a reemplazar

        f = self.frame = app.reg(tk.LabelFrame(parent, font=("MS Sans Serif", 10, "bold"),
                                               padx=8, pady=6), title_key)
        PAD = (14, 0)
        # fila 0: titulos
        app.reg(tk.Label(f, font=BOLD9), "lbl_current").grid(row=0, column=0, sticky="s", pady=(0, 2))
        row = tk.Frame(f)
        row.grid(row=0, column=1, sticky="w", padx=PAD, pady=(0, 2))
        app.reg(tk.Label(row, font=BOLD9), "lbl_avail").pack(side="left")
        self.cb = ttk.Combobox(row, state="readonly", width=34)
        self.cb.pack(side="left", padx=6)
        self.cb.bind("<<ComboboxSelected>>", self.on_combo)
        # fila 1: visores
        self.cur_box, self.cur_img = self._viewer(f)
        self.cur_box.grid(row=1, column=0, pady=4)
        self.opt_box, self.opt_img = self._viewer(f)
        self.opt_box.grid(row=1, column=1, padx=PAD, pady=4)
        # fila 2: informacion
        self.cur_info = tk.Label(f, text="", anchor="w")
        self.cur_info.grid(row=2, column=0, sticky="w")
        self.opt_info = tk.Label(f, text="", anchor="w")
        self.opt_info.grid(row=2, column=1, sticky="w", padx=PAD)
        # filas 3 y 4: botones (Exportar debajo de Reemplazar / Aplicar)
        self.b_rep = app.reg(tk.Button(f, command=self.replace_current, font=BOLD9), "btn_replace")
        self.b_rep.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self.b_exp_cur = app.reg(tk.Button(f, command=self.export_current), "btn_export_cur")
        self.b_exp_cur.grid(row=4, column=0, sticky="ew", pady=(2, 0))
        self.b_apply = app.reg(tk.Button(f, command=self.apply_selected, font=BOLD9), "btn_apply")
        self.b_apply.grid(row=3, column=1, sticky="ew", padx=PAD, pady=(4, 0))
        self.b_exp_sel = app.reg(tk.Button(f, command=self.export_selected), "btn_export_sel")
        self.b_exp_sel.grid(row=4, column=1, sticky="ew", padx=PAD, pady=(2, 0))
        app.buttons += [self.b_rep, self.b_exp_cur, self.b_apply, self.b_exp_sel]

    def _viewer(self, parent):
        box = tk.Frame(parent, width=self.bw, height=self.bh, bg="#2b2b2b")
        box.pack_propagate(False)
        img = tk.Label(box, bg="#2b2b2b", fg="white", wraplength=max(60, self.bw - 8))
        img.pack(expand=True)
        return box, img

    def set_box(self, w, h):
        """Los visores miden lo mismo que la textura que se reemplaza (sin ampliar)."""
        self.bw, self.bh = max(32, min(w, MAXBOX)), max(32, min(h, MAXBOX))
        for fr, im in ((self.cur_box, self.cur_img), (self.opt_box, self.opt_img)):
            fr.config(width=self.bw, height=self.bh)
            im.config(wraplength=max(60, self.bw - 8))

    # --- vista previa
    def _show(self, img_lbl, info_lbl, data, name=""):
        try:
            png, info = tex_preview(data, max(self.bw, self.bh), self.app.ign.get())
            im = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
            img_lbl.image = im
            img_lbl.config(image=im, text="")
            info_lbl.config(text="%s   %s" % (name, info))
        except Exception as e:  # noqa
            msg = tr("unsupported_tex") if isinstance(e, ValueError) else (str(e) or type(e).__name__)
            img_lbl.image = None
            img_lbl.config(image="", text=tr("cant_show", msg))
            info_lbl.config(text=name)

    def _clear(self, img_lbl, info_lbl, text):
        img_lbl.image = None
        img_lbl.config(image="", text=text)
        info_lbl.config(text="")

    def render_current(self):
        if self.target is None:
            self._clear(self.cur_img, self.cur_info,
                        tr("not_found", self.target_name.decode()) if self.app.vpk else "")
        else:
            self._show(self.cur_img, self.cur_info, rec_bytes(self.app.vpk, self.target),
                       rec_label(self.target))

    def render_opt(self):
        if self.ext:
            self._show(self.opt_img, self.opt_info, self.ext[0], tr("ext_prefix", self.ext[1]))
            return
        r = self.selected_rec()
        if r is None:
            self._clear(self.opt_img, self.opt_info, tr("no_miras") if self.app.vpk else "")
        else:
            self._show(self.opt_img, self.opt_info, rec_bytes(self.app.vpk, r), rec_label(r))

    def render_all(self):
        self.render_current()
        self.render_opt()

    # --- datos del VPK
    def refresh(self):
        recs = self.app.recs
        self.target = next((r for r in recs if r["type"] == 2
                            and r["name"].lower() == self.target_name), None)
        self.cands = [r for r in recs if r["type"] == 2 and r["name"].lower().startswith(self.prefix)
                      and r["name"].lower().endswith(b".tex")]
        self.cands.sort(key=lambda r: r["name"].lower())
        names = [r["name"].decode("cp1252", "replace") for r in self.cands]
        labels = [rec_label(r) if names.count(n) > 1 else n for r, n in zip(self.cands, names)]
        self.cb.config(values=labels)
        self.ext = None
        if self.target is not None and self.target in self.cands:
            self.cb.current(self.cands.index(self.target))
        elif self.cands:
            self.cb.current(0)
        else:
            self.cb.set("")
        dims = tex_dims(rec_bytes(self.app.vpk, self.target)) if self.target is not None else None
        self.set_box(*(dims or (BOX_DEF, BOX_DEF)))
        self.render_all()

    def selected_rec(self):
        i = self.cb.current()
        return self.cands[i] if 0 <= i < len(self.cands) else None

    def on_combo(self, *_):
        self.ext = None
        self.render_opt()

    # --- exportar
    def export_rec(self, rec):
        if not self.app.vpk:
            messagebox.showinfo(tr("title_export"), tr("need_vpk"))
            return
        if rec is None:
            messagebox.showinfo(tr("title_export"), tr("no_target", self.target_name.decode()))
            return
        data = rec_bytes(self.app.vpk, rec)
        fmt = tex_format(data)
        if fmt != "DXT5":
            messagebox.showwarning(tr("title_export"), tr("warn_export_fmt", fmt))
        base = os.path.splitext(rec["name"].decode("cp1252", "replace"))[0]
        o = filedialog.asksaveasfilename(
            title=tr("save_as"), defaultextension=".dds", initialfile=base + ".dds",
            filetypes=[("DDS", "*.dds"), ("TeX2 (.tex)", "*.tex")])
        if not o:
            return
        try:
            out = tex2dds(data) if o.lower().endswith(".dds") else data
            with open(o, "wb") as fh:
                fh.write(out)
            self.app.say(tr("exported", o))
        except Exception as e:  # noqa
            messagebox.showerror(tr("title_export"), "%s: %s" % (type(e).__name__, e))

    def export_current(self):
        self.export_rec(self.target)

    def export_selected(self):
        self.export_rec(self.selected_rec())

    # --- aplicar / reemplazar
    def apply_selected(self):
        if not self.app.vpk:
            messagebox.showinfo(tr("title_apply"), tr("need_vpk"))
            return
        if self.target is None:
            messagebox.showinfo(tr("title_apply"), tr("no_target", self.target_name.decode()))
            return
        r = self.selected_rec()
        if r is None:
            return
        if r is self.target:
            messagebox.showinfo(tr("title_apply"), tr("already_current"))
            return
        data = rec_bytes(self.app.vpk, r)
        fmt = tex_format(data)
        warn = tr("warn_internal_fmt", fmt) if fmt != "DXT5" else ""
        self.apply_data(data, rec_label(r), warn)

    def read_external(self, p):
        """Devuelve (TeX2 en bytes, None) o (None, mensaje de error). Tiene que ser DXT5."""
        try:
            with open(p, "rb") as fh:
                data = fh.read()
            if p.lower().endswith(".dds"):
                data = dds2tex(data)
            if data[:4] != b"TeX2":
                return None, tr("bad_texture")
            fmt = tex_format(data)
            if fmt != "DXT5":
                return None, tr("dxt5_required", fmt)
            tex_preview(data, 16)   # valida que se pueda decodificar
        except ValueError:
            return None, tr("bad_texture")
        except Exception as e:  # noqa
            return None, "%s: %s" % (type(e).__name__, e)
        return data, None

    def replace_current(self):
        if not self.app.vpk:
            messagebox.showinfo(tr("title_replace"), tr("need_vpk"))
            return
        if self.target is None:
            messagebox.showinfo(tr("title_replace"), tr("no_target", self.target_name.decode()))
            return
        p = filedialog.askopenfilename(
            title=tr("pick_ext"),
            filetypes=[(tr("ft_tex"), "*.tex *.dds"), ("TeX2", "*.tex"), ("DDS", "*.dds"),
                       (tr("ft_all"), "*.*")])
        if not p:
            return
        data, err = self.read_external(p)
        if err:
            messagebox.showerror(tr("title_replace"), err)
            return
        name = os.path.basename(p)
        self.ext = (data, name)
        self.render_opt()
        if not self.apply_data(data, tr("the_ext_file", name)):
            self.ext = None
            self.render_opt()

    def apply_data(self, data, desc, warn=""):
        """Pide confirmacion y reemplaza la mira actual. Devuelve True si se lanzo el cambio."""
        igual = len(data) == self.target["size"]
        if not messagebox.askyesno(
                tr("confirm_title"),
                warn + tr("confirm_body", rec_label(self.target), desc,
                          tr("same_size") if igual else tr("diff_size"))):
            return False
        fd, tmp = tempfile.mkstemp(suffix=".tex")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        rec = self.target

        def work(vpk):
            if os.path.getsize(tmp) == rec["size"]:
                backup_copy(vpk)
                replace_in_vpk(vpk, rec, tmp)
                print(tr("be_inplace"))
            else:
                modify_vpk(vpk, [], [dict(kind="f", dir=rec["dir"], name=rec["name"], src=tmp)])

        def done(text):
            try:
                os.remove(tmp)
            except OSError:
                pass
            self.app.reload()
            if "ERROR" in text:
                messagebox.showerror(tr("title_apply"), text)
            else:
                messagebox.showinfo(tr("title_apply"), tr("done_ok") + "\n\n" + text)
        self.app.run(work, self.app.vpk, on_done=done)
        return True


# ---------------------------------------------------------------- aplicacion
class App:
    def __init__(self):
        load_lang()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.vpk, self.recs, self.busy = None, [], False
        self.buttons = []
        self.labels = []   # (widget, opcion, clave): se retraducen al cambiar de idioma
        self._sizes = None
        try:
            set_app_icon(self.root)
        except Exception:  # noqa
            pass

        # fila superior: Leer, transparencia, ruta del VPK e idioma
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=(8, 2))
        b = self.reg(tk.Button(top, width=10, command=self.open_vpk, font=BOLD9), "btn_open")
        b.pack(side="left")
        self.buttons.append(b)
        self.ign = tk.BooleanVar(value=False)
        self.reg(tk.Checkbutton(top, variable=self.ign, command=self.redraw),
                 "chk_alpha").pack(side="left", padx=8)
        self.lang_cb = ttk.Combobox(top, state="readonly", width=11, values=[n for _, n in LANGS])
        self.lang_cb.current([c for c, _ in LANGS].index(_LANG["v"]))
        self.lang_cb.pack(side="right")
        self.lang_cb.bind("<<ComboboxSelected>>", self.apply_lang)
        self.reg(tk.Label(top, font=BOLD9), "lang_lbl").pack(side="right", padx=(8, 4))
        self.path_lbl = tk.Label(top, text="", anchor="w", fg="#444")
        self.path_lbl.pack(side="left", fill="x", expand=True)

        # justo debajo: barra de progreso, estado y enlace a GitHub
        bf = tk.Frame(self.root)
        bf.pack(fill="x", padx=8, pady=(2, 2))
        self.bar = ttk.Progressbar(bf, maximum=100)
        self.bar.pack(fill="x")
        brow = tk.Frame(bf)
        brow.pack(fill="x")
        link = tk.Label(brow, text=REPO_URL, fg="#0645ad", cursor="hand2",
                        font=("MS Sans Serif", 8, "underline"))
        link.pack(side="right", padx=(8, 0))
        link.bind("<Button-1>", lambda e: open_url(REPO_URL) or messagebox.showinfo(
            tr("link_title"), tr("link_fail") + "\n\n" + REPO_URL))
        self.status = tk.Label(brow, text=tr("status_init"), anchor="w")
        self.status.pack(side="left", fill="x", expand=True)

        self.panels = []
        for key, tname, prefix in TARGETS:
            p = MiraPanel(self, self.root, key, tname, prefix)
            p.frame.pack(fill="x", padx=8, pady=(2, 6))
            self.panels.append(p)

        globals()["progress_cb"] = self.progress
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())
        self.root.after(100, self.autoload)

    def fit_window(self):
        """Ajusta la ventana al contenido cuando cambia el tamano de los visores."""
        sizes = tuple((p.bw, p.bh) for p in self.panels)
        if sizes == self._sizes:
            return
        self._sizes = sizes
        try:
            self.root.update_idletasks()
            self.root.geometry("")
            self.root.update_idletasks()
            self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())
        except Exception:  # noqa
            pass

    def reg(self, w, key, opt="text"):
        w.config(**{opt: tr(key)})
        self.labels.append((w, opt, key))
        return w

    def apply_lang(self, *_):
        _LANG["v"] = LANGS[self.lang_cb.current()][0]
        for w, opt, key in self.labels:
            w.config(**{opt: tr(key)})
        for p in self.panels:
            p.render_all()
        if not self.busy:
            self.say(tr("read_ok", self.vpk) if self.vpk else tr("status_init"))
        save_lang()

    def say(self, t):
        self.status.config(text=t)

    def progress(self, done, total, fdone, ftotal, name):
        pct = 100.0 if total == 0 else done * 100.0 / total

        def u():
            self.bar["value"] = pct
            self.status.config(text=tr("progress", pct, fdone, ftotal, name))
        self.root.after(0, u)

    def run(self, fn, *args, on_done=None):
        if self.busy:
            return
        self.busy = True
        self.bar["value"] = 0
        for b in self.buttons:
            b.config(state="disabled")
        buf = []

        class W:
            def write(self, t):
                buf.append(t)
                return len(t)

            def flush(self):
                pass

        def work():
            w = W()
            with contextlib.redirect_stdout(w), contextlib.redirect_stderr(w):
                _run_safe(fn, *args)
            text = "".join(buf).strip()

            def fin():
                self.busy = False
                for b in self.buttons:
                    b.config(state="normal")
                if on_done:
                    on_done(text)
            self.root.after(0, fin)
        threading.Thread(target=work, daemon=True).start()

    # --- VPK
    def autoload(self):
        try:
            with open(CFG, encoding="utf-8") as fh:
                p = fh.read().strip()
            if p and os.path.isfile(p):
                self.load(p)
        except Exception:  # noqa
            pass

    def open_vpk(self):
        p = filedialog.askopenfilename(title=tr("dlg_pick_vpk"),
                                       filetypes=[("VPK", "*.vpk"), (tr("ft_all"), "*.*")])
        if p:
            self.load(p)

    def load(self, path):
        try:
            with open(path, "rb") as f:
                t = read_toc(f)
        except SystemExit as e:
            messagebox.showerror(tr("dlg_pick_vpk"), str(e))
            return
        except Exception as e:  # noqa
            messagebox.showerror(tr("dlg_pick_vpk"), "%s: %s" % (type(e).__name__, e))
            return
        self.vpk, self.recs = path, t["recs"]
        self.path_lbl.config(text=path)
        self.root.title("%s - %s" % (APP_TITLE, os.path.basename(path)))
        try:
            with open(CFG, "w", encoding="utf-8") as fh:
                fh.write(path)
        except Exception:  # noqa
            pass
        for p in self.panels:
            p.refresh()
        self.fit_window()
        self.say(tr("read_ok", path))

    def reload(self):
        if self.vpk:
            self.load(self.vpk)

    def redraw(self):
        for p in self.panels:
            p.render_all()


def main():
    win_set_app_id()
    try:
        App().root.mainloop()
    except SystemExit as e:
        if e.code not in (None, 0):
            _fatal(str(e.code))
    except BaseException:  # noqa
        import traceback
        _fatal(traceback.format_exc())


def _fatal(text):
    """Muestra el error en una ventana y lo guarda en mira_tool_error.log (nada de cierres mudos)."""
    try:
        with open(os.path.join(APP_DIR, "mira_tool_error.log"), "w", encoding="utf-8") as fh:
            fh.write(text)
    except Exception:  # noqa
        pass
    print(text)
    try:
        r = tk.Tk()
        r.withdraw()
        try:
            set_app_icon(r)
        except Exception:  # noqa
            pass
        messagebox.showerror(APP_TITLE + " - error", text[-1500:])
        r.destroy()
    except Exception:  # noqa
        try:
            input("\nPress Enter...")
        except Exception:  # noqa
            pass


if __name__ == "__main__":
    main()
