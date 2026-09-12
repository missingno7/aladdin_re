"""pygame presents completed frames/PCM; it never owns simulated time."""
from datetime import datetime, timezone
from pathlib import Path
import time

from . import artifacts
from .audio import AudioOutput, FramePacer
from .machine import Machine
from .profile import FRAME_TICKS, MASTER_HZ


def play(rom, *, frames=0, mute=False, origin="user", record_from_start=False, snapshot=None, audio_report=None):
    import pygame
    pygame.display.init()
    pygame.font.init()
    window = pygame.display.set_mode((960, 736))
    font = pygame.font.Font(None, 22)
    keys = {pygame.K_UP: 1, pygame.K_DOWN: 2, pygame.K_LEFT: 4, pygame.K_RIGHT: 8,
            pygame.K_x: 16, pygame.K_c: 32, pygame.K_z: 64, pygame.K_RETURN: 128}
    held = set()
    recording = None
    paused = False
    running = True
    step = False
    count = 0
    message = "Original mode | Ready"
    audio = None
    pacer = FramePacer(time.perf_counter(), FRAME_TICKS / MASTER_HZ)

    def filename(extension):
        return Path("recordings") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + extension)

    with Machine(rom) as machine:
        try:
            if snapshot is not None:
                artifacts.restore_snapshot(machine, artifacts.read_bounded(snapshot))
                message = f"Resumed {Path(snapshot).name}"
            if record_from_start:
                recording = artifacts.Recorder(machine, origin=origin, reset_provenance="snapshot-resume" if snapshot is not None else "cold-boot")
                message = "Recording from snapshot | F5: stop and save" if snapshot is not None else "Recording from reset | F5: stop and save"
                pygame.display.set_caption("Aladdin RE | RUNNING | REC")
            # Release any keys held in the saved state through the same input path.
            # The snapshot remains intact; a new recording includes this takeover event.
            if snapshot is not None:
                if recording:
                    recording.apply_pad(machine, 0)
                else:
                    machine.pad(0)
            audio = AudioOutput() if not mute else None
            pacer.reset(time.perf_counter())
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.WINDOWFOCUSLOST:
                        held.clear()
                        if recording:
                            recording.apply_pad(machine, 0)
                        else:
                            machine.pad(0)
                    elif event.type in {pygame.KEYDOWN, pygame.KEYUP}:
                        if event.key in keys:
                            if event.type == pygame.KEYDOWN:
                                held.add(event.key)
                            else:
                                held.discard(event.key)
                            mask = sum(keys[key] for key in held)
                            if recording:
                                recording.apply_pad(machine, mask)
                            else:
                                machine.pad(mask)
                        elif event.type == pygame.KEYDOWN and not getattr(event, "repeat", False):
                            if event.key == pygame.K_F5:
                                if recording:
                                    path = filename(".alreplay")
                                    artifacts.write_new(path, recording.finish(machine))
                                    message = f"Saved {path} ({(machine.info['tick']-recording.start)/MASTER_HZ:.2f}s)"
                                    print(message, flush=True)
                                    recording = None
                                else:
                                    recording = artifacts.Recorder(machine, origin=origin, reset_provenance="cold-boot" if machine.info["tick"] == 0 else "mid-session")
                                    message = "Recording original input"
                            elif event.key == pygame.K_F6:
                                path = filename(".alsnap")
                                artifacts.write_new(path, artifacts.snapshot_bytes(machine))
                                message = f"Saved {path}"
                                print(message, flush=True)
                            elif event.key == pygame.K_F7:
                                paused = not paused
                                if audio:
                                    audio.clear()
                                pacer.reset(time.perf_counter())
                            elif event.key == pygame.K_F8 and paused:
                                step = True
                            elif event.key == pygame.K_F9 and recording:
                                recording.bookmarks.append({"tick": machine.info["tick"], "label": f"Bookmark {len(recording.bookmarks)+1}"})
                                message = "Bookmark added"
                if not running:
                    break
                if not paused or step:
                    target = (machine.info["tick"] // FRAME_TICKS + 1) * FRAME_TICKS
                    machine.run(target=target)
                    pcm = machine.audio()
                    if audio and not paused:
                        audio.push(pcm)
                    step = False
                    count += 1
                width, height, rgb = machine.frame()
                picture = pygame.image.frombuffer(rgb, (width, height), "RGB")
                window.fill((15, 18, 24))
                window.blit(pygame.transform.scale(picture, (960, 672)), (0, 0))
                state = "PAUSED" if paused else "RUNNING"
                pygame.display.set_caption(f"Aladdin RE | {state}" + (" | REC" if recording else ""))
                window.blit(font.render("Arrows: move | Z/X/C: A/B/C | Enter: Start | F5: record | F6: snapshot | F7: pause | F8: step | F9: bookmark", True, (230, 230, 235)), (12, 682))
                window.blit(font.render(message, True, (255, 195, 85)), (12, 710))
                pygame.display.flip()
                if frames and count >= frames:
                    running = False
                time.sleep(pacer.delay(time.perf_counter()))
        finally:
            if recording:
                path = filename(".alreplay")
                artifacts.write_new(path, recording.finish(machine))
                print(f"Saved {path}", flush=True)
            if audio:
                audio.close()
                if audio_report:
                    import json
                    path = Path(audio_report)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(audio.buffer.stats, indent=2) + "\n")
            pygame.quit()
