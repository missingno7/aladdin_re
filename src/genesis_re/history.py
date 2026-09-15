"""Immutable cold-start input history. Machine state is never an identity input."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


# A store's root record names the game and the clock, e.g. aladdin_sega.profile.HISTORY_ROOT
# {"format": "input-history-1", "root": "aladdin-usa-new", "clock": "simulation-frame",
#  "input": "three-button-pad-1", "initial_buttons": 0}.  It enters every node id, so two
# games' histories can never share a node, and a store is refused for the wrong game.
ROOT_FIELDS = {"format", "root", "clock", "input", "initial_buttons"}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def natural(value):
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError("Expected a nonnegative simulation frame")
    return value


def object_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Invalid history ID")
    return value


def read_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate history field")
            out[key] = value
        return out
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded(value) + b"\n")
    temporary.replace(path)


class HistoryStore:
    """One game's immutable input-history DAG below ``path``.

    ``root`` is the game's root record; there is no default, so a store can only
    be opened for the game it belongs to.  An existing store whose manifest names
    another root is refused, never reinterpreted.
    """
    def __init__(self, path, root):
        if not isinstance(root, dict) or set(root) != ROOT_FIELDS or root["format"] != "input-history-1":
            raise ValueError("A history store needs its game's root record")
        self.path = Path(path)
        self.root = dict(root)
        self.root_id = digest(encoded(self.root))
        self.path.mkdir(parents=True, exist_ok=True)
        manifest = self.path / "manifest.json"
        if manifest.exists():
            found = read_json(manifest)
            if found != self.root:
                raise ValueError(f"History at {self.path} belongs to root "
                                 f"{found.get('root') if isinstance(found, dict) else found!r}, not {self.root['root']!r}")
        else:
            write_json(manifest, self.root)

    def _root(self):
        return {"parent": None, "end_frame": 0, "events": [],
                "input_digest": self.root_id, "buttons": 0}

    def ancestry(self, node_id):
        """Validate both graph structure and derived identity, from the root."""
        node_id = object_id(node_id)
        reverse, seen = [], set()
        current = node_id
        while current != self.root_id:
            if current in seen:
                raise ValueError("History ancestry contains a cycle")
            seen.add(current)
            node = read_json(self.path / "nodes" / (current + ".json"))
            if not isinstance(node, dict) or set(node) != {"parent", "end_frame", "events", "input_digest", "buttons"}:
                raise ValueError("Invalid history node fields")
            reverse.append((current, node))
            current = object_id(node["parent"])
        parent = self._root()
        result = [(self.root_id, parent)]
        for key, node in reversed(reverse):
            expected, computed = self._derive(result[-1][0], parent, node["events"], node["end_frame"])
            if key != expected or node != computed:
                raise ValueError("History content/identity mismatch")
            result.append((key, node))
            parent = node
        return result

    def node(self, node_id):
        return self.ancestry(node_id)[-1][1]

    def _derive(self, parent_id, parent, events, end_frame):
        end_frame = natural(end_frame)
        if end_frame <= parent["end_frame"]:
            raise ValueError("A child must advance canonical simulation time")
        if not isinstance(events, list):
            raise ValueError("Input segment must be a list")
        previous, buttons, chain = parent["end_frame"] - 1, parent["buttons"], parent["input_digest"]
        normalized = []
        for event in events:
            if not isinstance(event, dict) or set(event) != {"frame", "buttons"}:
                raise ValueError("Invalid canonical input event")
            frame, mask = natural(event["frame"]), event["buttons"]
            if type(mask) is not int or not 0 <= mask <= 255:
                raise ValueError("Invalid input mask")
            if not max(parent["end_frame"], previous + 1) <= frame < end_frame:
                raise ValueError("Input events must be ordered inside their segment")
            if mask == buttons:
                raise ValueError("Redundant input change")
            chain = digest(bytes.fromhex(chain) + encoded(event))
            normalized.append(dict(event))
            previous, buttons = frame, mask
        # Checkpoint placement does not alter logical path identity: only the
        # ordered input stream and elapsed frame enter this digest.
        key = digest(encoded({"root": self.root_id, "input": chain, "end_frame": end_frame}))
        return key, {"parent": parent_id, "end_frame": end_frame, "events": normalized,
                     "input_digest": chain, "buttons": buttons}

    def append(self, parent_id, events, end_frame):
        parent = self.node(parent_id)
        if end_frame == parent["end_frame"] and events == []:
            return parent_id
        key, node = self._derive(parent_id, parent, events, end_frame)
        target = self.path / "nodes" / (key + ".json")
        if target.exists():
            # The same complete path can be checkpointed at different places.
            # Reuse its first immutable ancestry representation.
            self.node(key)
        else:
            write_json(target, node)
        return key

    def flatten(self, node_id):
        path = self.ancestry(node_id)
        return {"root": self.root, "history_id": node_id,
                "end_frame": path[-1][1]["end_frame"],
                "events": [event for _, node in path for event in node["events"]]}

    def nodes(self):
        result = {self.root_id: self._root()}
        for path in sorted((self.path / "nodes").glob("*.json")):
            result[path.stem] = self.node(path.stem)
        return result

    def metadata(self, node_id):
        object_id(node_id)
        path = self.path / "presentation" / (node_id + ".json")
        return read_json(path) if path.exists() else {}

    def present(self, node_id, *, rgb, width, height, reason, label=None):
        self.node(node_id)
        if len(rgb) != width * height * 3 or width <= 0 or height <= 0:
            raise ValueError("Invalid checkpoint image")
        image = Path("screenshots") / (node_id + ".ppm")
        (self.path / image).parent.mkdir(parents=True, exist_ok=True)
        (self.path / image).write_bytes(f"P6\n{width} {height}\n255\n".encode() + rgb)
        meta = {**self.metadata(node_id), "screenshot": image.as_posix(), "reason": reason}
        if label is not None:
            meta["label"] = str(label)
        write_json(self.path / "presentation" / (node_id + ".json"), meta)

    def set_main(self, node_id):
        self.node(node_id)
        write_json(self.path / "refs" / "main.json", {"node": node_id})

    def resolve(self, ref="main"):
        """``main``, a full node id, or an unambiguous hex prefix of at least eight characters."""
        if ref == "main":
            path = self.path / "refs" / "main.json"
            ref = read_json(path)["node"] if path.exists() else self.root_id
        elif isinstance(ref, str) and 8 <= len(ref) < 64 and re.fullmatch(r"[0-9a-f]+", ref):
            matches = [key for key in [self.root_id] + [p.stem for p in (self.path / "nodes").glob("*.json")]
                       if key.startswith(ref)]
            if len(matches) != 1:
                raise ValueError(f"History prefix {ref!r} matches {len(matches)} nodes")
            ref = matches[0]
        self.node(ref)
        return ref
