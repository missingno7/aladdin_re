"""Bounded encoding helpers for disposable execution caches and diagnostics."""
import hashlib
import io
import json
from pathlib import Path
import zipfile


LIMIT = 16 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def decode_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")))


def uint(value, bits=64):
    if type(value) is not int or not 0 <= value < 2**bits:
        raise ValueError(f"Expected uint{bits}")
    return value


def pack(parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return stream.getvalue()


def unpack(data, allowed, required):
    if len(data) > LIMIT:
        raise ValueError("Archive exceeds size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [entry.filename for entry in infos]
            if len(names) != len(set(names)) or not set(names) <= allowed or not required <= set(names):
                raise ValueError("Unexpected, duplicate or missing archive member")
            if sum(entry.file_size for entry in infos) > LIMIT:
                raise ValueError("Archive expands beyond size limit")
            if any(entry.flag_bits & 1 for entry in infos):
                raise ValueError("Encrypted archives are unsupported")
            return {name: archive.read(name) for name in names}
    except zipfile.BadZipFile as e:
        raise ValueError("Corrupt archive") from e


def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves existing recordings, including on name collision.
    with path.open("xb") as out:
        out.write(data)


def read_bounded(path):
    with Path(path).open("rb") as source:
        data = source.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("Artifact exceeds size limit")
    return data


