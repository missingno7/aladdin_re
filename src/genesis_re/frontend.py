"""pygame presents history-backed frames and PCM; it never owns simulated time."""
from pathlib import Path
import time

from .audio import AudioOutput, FramePacer


_WINDOW = (960, 736)
_GAME_HEIGHT = 672


def _button_mask(held, keys):
    return sum(keys[key] for key in held)


def _history_layout(nodes, root_id, *, width, height):
    """Return a small stable branch layout from immutable node metadata."""
    children = {node_id: [] for node_id in nodes}
    for node_id, value in nodes.items():
        parent = value.get("parent")
        if parent in children:
            children[parent].append(node_id)
    for ids in children.values():
        ids.sort(key=lambda value: (int(nodes[value].get("end_frame", 0)), value))

    leaves = sorted((node_id for node_id, ids in children.items() if not ids),
                    key=lambda value: (int(nodes[value].get("end_frame", 0)), value))
    if not leaves:
        leaves = [root_id]
    leaf_lanes = {node_id: index for index, node_id in enumerate(leaves)}

    def lane(node_id):
        if node_id in leaf_lanes:
            return leaf_lanes[node_id]
        return min(lane(child) for child in children[node_id])

    longest = max(1, *(int(value.get("end_frame", 0)) for value in nodes.values()))
    left, right = 44, width - 44
    # Keep checkpoint previews in the header clear of the branch graph.
    top, bottom = 208, height - 114
    spacing = 0 if len(leaves) == 1 else (bottom - top) / (len(leaves) - 1)
    return {
        node_id: (int(left + (right - left) * int(value.get("end_frame", 0)) / longest),
                  int(top + lane(node_id) * spacing))
        for node_id, value in nodes.items()
    }


def _inside(position, rect):
    x, y = position
    left, top, width, height = rect
    return left <= x < left + width and top <= y < top + height


def _checkpoint_preview(pygame, store, node_id):
    """Load presentation data only; it never affects history identity or simulation."""
    relative = store.metadata(node_id).get("screenshot")
    if not relative:
        return None
    candidate = (store.path / relative).resolve()
    try:
        candidate.relative_to(store.path.resolve())
    except ValueError:
        return None
    if not candidate.is_file() or not hasattr(pygame.image, "load"):
        return None
    try:
        return pygame.image.load(str(candidate))
    except Exception:
        return None


def _game_layout(games, *, width):
    """One button per registered game, centred; the order is the registry's."""
    button = (260, 56)
    top = 236
    return {game_id: ((width - button[0]) // 2, top + index * (button[1] + 24), *button)
            for index, game_id in enumerate(games)}


def _choose_game(pygame, window, font, games):
    """Return the chosen game profile, or ``None`` when the window is closed."""
    layout = _game_layout(games, width=_WINDOW[0])
    hovered = None
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == getattr(pygame, "MOUSEMOTION", object()):
                hovered = next((game_id for game_id, rect in layout.items() if _inside(event.pos, rect)), None)
            elif event.type == getattr(pygame, "MOUSEBUTTONDOWN", object()) and getattr(event, "button", 1) == 1:
                chosen = next((game_id for game_id, rect in layout.items() if _inside(event.pos, rect)), None)
                if chosen is not None:
                    return games[chosen]
        window.fill((15, 18, 24))
        draw = getattr(pygame, "draw", None)
        window.blit(font.render("Choose game", True, (235, 239, 245)), (16, 23))
        window.blit(font.render("Each game keeps its own immutable input history.", True, (184, 194, 206)), (16, 62))
        for game_id, rect in layout.items():
            if draw:
                draw.rect(window, (84, 110, 138) if game_id == hovered else (58, 78, 99), rect, border_radius=6)
            title = games[game_id].title
            missing = "" if games[game_id].rom_path.is_file() else "   (ROM missing)"
            window.blit(font.render(title + missing, True, (240, 244, 248)), (rect[0] + 16, rect[1] + 18))
        pygame.display.set_caption("Genesis RE | Choose game")
        pygame.display.flip()
        time.sleep(1 / 60)


def _choose_history(pygame, window, font, store, game):
    """Return ``(node, new)`` before a simulation session is opened."""
    nodes = store.nodes()
    selected = store.resolve("main")
    hovered = None
    new_rect, main_rect = (16, 16, 104, 34), (128, 16, 104, 34)
    clock = game.board.frame_ticks / game.board.master_hz
    while True:
        layout = _history_layout(nodes, store.root_id, width=_WINDOW[0], height=_WINDOW[1])
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, False
            if event.type == getattr(pygame, "MOUSEMOTION", object()):
                hovered = next((node_id for node_id, point in layout.items()
                                if (event.pos[0] - point[0]) ** 2 + (event.pos[1] - point[1]) ** 2 <= 100), None)
            elif event.type == getattr(pygame, "MOUSEBUTTONDOWN", object()) and getattr(event, "button", 1) == 1:
                if _inside(event.pos, new_rect):
                    return None, True
                if _inside(event.pos, main_rect):
                    return store.resolve("main"), False
                else:
                    chosen = next((node_id for node_id, point in layout.items()
                                   if (event.pos[0] - point[0]) ** 2 + (event.pos[1] - point[1]) ** 2 <= 144), None)
                    if chosen is not None:
                        return chosen, False

        window.fill((15, 18, 24))
        draw = getattr(pygame, "draw", None)
        if draw:
            for node_id, value in nodes.items():
                parent = value.get("parent")
                if parent in layout:
                    draw.line(window, (92, 117, 143), layout[parent], layout[node_id], 2)
            for node_id, point in layout.items():
                color = (255, 195, 85) if node_id == selected else (175, 206, 232)
                draw.circle(window, color, point, 7 if node_id == selected else 5)
            for rect, label in ((new_rect, "New"), (main_rect, "Main")):
                draw.rect(window, (58, 78, 99), rect, border_radius=4)
                window.blit(font.render(label, True, (240, 244, 248)), (rect[0] + 8, rect[1] + 8))
        window.blit(font.render(f"{game.title}: immutable input history", True, (235, 239, 245)), (252, 23))
        window.blit(font.render("Click a checkpoint to start; branches share their input prefix.", True, (184, 194, 206)), (16, 62))
        target = hovered or selected
        if target:
            value = nodes[target]
            metadata = store.metadata(target)
            seconds = int(value.get("end_frame", 0)) * clock
            label = metadata.get("label") or metadata.get("reason") or target[:12]
            window.blit(font.render(f"{label}  |  frame {value.get('end_frame', 0)}  |  {seconds:.2f}s", True, (255, 215, 130)), (250, 685))
            preview = _checkpoint_preview(pygame, store, target)
            if preview:
                window.blit(pygame.transform.scale(preview, (240, 168)), (704, 16))
        pygame.display.set_caption(f"{game.title} | History")
        pygame.display.flip()
        time.sleep(1 / 60)


def play(game=None, rom=None, *, frames=0, mute=False, history_path=None, node=None, new=False, audio_report=None):
    """Play a cold-start input-history branch, checkpointing only immutable inputs.

    Without ``game`` the window first asks which registered game to play; the
    ROM is read after that choice.  ``history_path`` defaults to ``history/<game>``.
    """
    import pygame
    from .games import GAMES
    from .history import HistoryStore
    from .history_runtime import Session

    primary_error = None
    cleanup_errors = []
    audio = None

    def cleanup(label, operation):
        try:
            operation()
        except BaseException as error:
            cleanup_errors.append((label, error))

    def save_audio_report():
        import json
        path = Path(audio_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(audio.buffer.stats, indent=2) + "\n")

    try:
        pygame.display.init()
        pygame.font.init()
        window = pygame.display.set_mode(_WINDOW)
        font = pygame.font.Font(None, 22)
        if game is None:
            if frames or new or node is not None or rom is not None or history_path is not None:
                raise ValueError("Automated play needs an explicit game")
            game = _choose_game(pygame, window, font, GAMES)
            if game is None:
                return
        if rom is None:
            rom = game.read_rom()
        store = HistoryStore(game.history_path() if history_path is None else Path(history_path), game.history_root)
        # Frame-limited runs are deterministic automation: they never wait for the panel.
        if frames:
            selected, cold_start = (node, new) if node is not None else (None, True)
        elif new:
            selected, cold_start = None, True
        elif node is not None:
            selected, cold_start = store.resolve(node), False
        else:
            selected, cold_start = _choose_history(pygame, window, font, store, game)
            if selected is None and not cold_start:
                return

        keys = {pygame.K_UP: 1, pygame.K_DOWN: 2, pygame.K_LEFT: 4, pygame.K_RIGHT: 8,
                pygame.K_x: 16, pygame.K_c: 32, pygame.K_z: 64, pygame.K_RETURN: 128}
        held = set()
        paused = False
        running = True
        one_step = False
        count = 0
        message = "Cold start" if cold_start else f"Resumed {selected[:12]}"
        pacer = FramePacer(time.perf_counter(), game.board.frame_ticks / game.board.master_hz)

        with Session(game, store, rom, node=None if cold_start else selected) as session:
            try:
                audio = AudioOutput() if not mute else None
                pacer.reset(time.perf_counter())
                while running:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        elif event.type == pygame.WINDOWFOCUSLOST:
                            held.clear()
                        elif event.type in {pygame.KEYDOWN, pygame.KEYUP}:
                            if event.key in keys:
                                if event.type == pygame.KEYDOWN:
                                    held.add(event.key)
                                else:
                                    held.discard(event.key)
                            elif event.type == pygame.KEYDOWN and not getattr(event, "repeat", False):
                                if event.key in {pygame.K_F5, pygame.K_F6}:
                                    saved = session.checkpoint(reason="manual", label="F5" if event.key == pygame.K_F5 else "F6")
                                    message = f"Checkpoint {saved[:12]}"
                                elif event.key == pygame.K_F7:
                                    paused = not paused
                                    if audio:
                                        audio.clear()
                                    pacer.reset(time.perf_counter())
                                elif event.key == pygame.K_F8 and paused:
                                    one_step = True
                    if not running:
                        break
                    if not paused or one_step:
                        # A resumed node can carry a pressed pad. This first zero-mask step is
                        # journaled by Session, so hand-off does not mutate an existing node.
                        pcm = session.step(_button_mask(held, keys))
                        if audio and not paused:
                            audio.push(pcm)
                        one_step = False
                        count += 1
                    # Pause/checkpoint can happen before the ROM configures
                    # video. Power-on has a black presentation, not a VDP frame.
                    width, height, rgb = (session.machine.frame() if session.frame
                                          else (320, 224, bytes(320 * 224 * 3)))
                    picture = pygame.image.frombuffer(rgb, (width, height), "RGB")
                    window.fill((15, 18, 24))
                    window.blit(pygame.transform.scale(picture, (960, _GAME_HEIGHT)), (0, 0))
                    state = "PAUSED" if paused else "RUNNING"
                    pygame.display.set_caption(f"{game.title} | {state} | history")
                    window.blit(font.render("Arrows: move | Z/X/C: A/B/C | Enter: Start | F5/F6: checkpoint | F7: pause | F8: step", True, (230, 230, 235)), (12, 682))
                    window.blit(font.render(message, True, (255, 195, 85)), (12, 710))
                    pygame.display.flip()
                    if frames and count >= frames:
                        running = False
                    time.sleep(pacer.delay(time.perf_counter()))
            except BaseException as error:
                primary_error = error
                raise
            finally:
                if audio_report and audio:
                    cleanup("audio report", save_audio_report)
                if audio:
                    cleanup("audio output", audio.close)
    except BaseException as error:
        if primary_error is None:
            primary_error = error
        raise
    finally:
        cleanup("pygame", pygame.quit)
        if primary_error is not None:
            for label, error in cleanup_errors:
                try:
                    primary_error.add_note(f"Cleanup failed ({label}): {type(error).__name__}: {error}")
                except AttributeError:
                    pass
        elif cleanup_errors:
            cleanup_error = cleanup_errors[0][1]
            for label, error in cleanup_errors[1:]:
                try:
                    cleanup_error.add_note(f"Additional cleanup failure ({label}): {type(error).__name__}: {error}")
                except AttributeError:
                    pass
            raise cleanup_error
