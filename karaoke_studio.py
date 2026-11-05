import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "PS2 Karaoke Studio"
TASKS = queue.Queue()

def run_command(command, log):
    log("$ " + " ".join(map(str, command)))
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace"
    )
    for line in proc.stdout:
        log(line.rstrip())
    code = proc.wait()
    if code:
        raise RuntimeError(f"Kommandot misslyckades (kod {code}). Se loggen ovan.")



class PreviewWindow:
    """Simple synchronized preview/editor for a generated song package."""
    def __init__(self, parent, song_dir):
        self.parent = parent
        self.song_dir = Path(song_dir)
        self.data = json.loads((self.song_dir / "lyrics.json").read_text(encoding="utf-8"))
        self.pitch = json.loads((self.song_dir / "pitch.json").read_text(encoding="utf-8"))
        self.words = self.data.get("words", [])
        self.events = self.pitch.get("events", [])
        self.duration = max(
            [float(w.get("end", 0)) for w in self.words] +
            [float(e.get("time", 0)) for e in self.events] + [1.0]
        )

        self.win = tk.Toplevel(parent)
        self.win.title(f"Förhandsgranskning – {self.song_dir.name}")
        self.win.geometry("900x680")
        self.win.minsize(720, 560)
        self.position = 0.0
        self.playing = False
        self.audio_ready = False
        self.audio_mode = tk.StringVar(value="instrumental.wav")
        self._build()
        self._init_audio()
        self.win.after(100, self._tick)

    def _build(self):
        outer = ttk.Frame(self.win, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=self.song_dir.name, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Lyssna på bakgrundsmusiken eller sångreferensen och kontrollera textens timing.",
            foreground="#555"
        ).pack(anchor="w", pady=(0, 12))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=4)
        ttk.Button(controls, text="▶ Spela", command=self.play).pack(side="left")
        ttk.Button(controls, text="Ⅱ Pausa", command=self.pause).pack(side="left", padx=5)
        ttk.Button(controls, text="■ Stoppa", command=self.stop).pack(side="left")
        ttk.Label(controls, text="Ljud:").pack(side="left", padx=(18, 5))
        mode = ttk.Combobox(
            controls, textvariable=self.audio_mode, state="readonly", width=20,
            values=["instrumental.wav", "vocals.wav"]
        )
        mode.pack(side="left")
        mode.bind("<<ComboboxSelected>>", self.change_audio)

        self.time_label = ttk.Label(outer, text="00:00.0 / 00:00.0")
        self.time_label.pack(anchor="w", pady=(10, 2))
        self.seek = ttk.Scale(outer, from_=0, to=self.duration, command=self.seek_to)
        self.seek.pack(fill="x")

        lyric_box = ttk.LabelFrame(outer, text="Text – synkroniserad förhandsgranskning", padding=12)
        lyric_box.pack(fill="both", expand=True, pady=(12, 10))
        self.current_lyric = ttk.Label(
            lyric_box, text="Tryck på Spela för att förhandsgranska texten.",
            font=("Segoe UI", 20, "bold"), anchor="center", justify="center",
            wraplength=800
        )
        self.current_lyric.pack(fill="both", expand=True)

        pitch_box = ttk.LabelFrame(outer, text="Uppskattad tonhöjd (MIDI-notnummer)", padding=8)
        pitch_box.pack(fill="x")
        self.pitch_canvas = tk.Canvas(pitch_box, height=130, background="#101820",
                                      highlightthickness=0)
        self.pitch_canvas.pack(fill="x", expand=True)
        self.pitch_canvas.bind("<Configure>", lambda _e: self._draw_pitch())

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Label(bottom, text="Automatisk text- och tonanalys kan innehålla fel.").pack(side="left")
        ttk.Button(bottom, text="Öppna låtmapp", command=self.open_folder).pack(side="right")

    def _init_audio(self):
        try:
            import pygame
            pygame.mixer.init()
            self.pygame = pygame
            self.audio_ready = True
            self._load_audio()
        except Exception as exc:
            self.audio_ready = False
            self.current_lyric.configure(
                text=f"Ljuduppspelning kunde inte startas: {exc}\n"
                     "Kontrollera Windows ljudenhet och installera om pygame."
            )

    def _load_audio(self):
        if not self.audio_ready:
            return
        self.pygame.mixer.music.stop()
        audio_file = self.song_dir / self.audio_mode.get()
        self.pygame.mixer.music.load(str(audio_file))
        self.position = 0.0
        self.seek.set(0)

    def play(self):
        if not self.audio_ready:
            return
        try:
            if self.pygame.mixer.music.get_busy():
                self.pygame.mixer.music.unpause()
            else:
                self._play_base = self.position
                self.pygame.mixer.music.play(start=max(0, self.position))
            self.playing = True
        except Exception as exc:
            messagebox.showerror("Uppspelning", str(exc), parent=self.win)

    def pause(self):
        if self.audio_ready:
            self.pygame.mixer.music.pause()
        self.playing = False

    def stop(self):
        if self.audio_ready:
            self.pygame.mixer.music.stop()
        self.playing = False
        self.position = 0.0
        self.seek.set(0)
        self._update_preview()

    def change_audio(self, _event=None):
        was_playing = self.playing
        self.pause()
        try:
            self._load_audio()
            if was_playing:
                self.play()
        except Exception as exc:
            messagebox.showerror("Ljudfil", str(exc), parent=self.win)

    def seek_to(self, value):
        if not self.audio_ready:
            return
        new_pos = float(value)
        if abs(new_pos - self.position) > 0.8:
            was_playing = self.playing
            self.position = new_pos
            self._play_base = self.position
            self.pygame.mixer.music.stop()
            try:
                self.pygame.mixer.music.play(start=max(0, self.position))
                if not was_playing:
                    self.pygame.mixer.music.pause()
            except Exception:
                pass

    def _tick(self):
        if not self.win.winfo_exists():
            return
        if self.audio_ready and self.playing:
            pos_ms = self.pygame.mixer.music.get_pos()
            if pos_ms >= 0:
                # get_pos is time since the current play() call.
                self.position = min(self.duration, self.position if pos_ms == 0 else self.position)
                # pygame's get_pos resets after a seek; maintain a base offset.
                base = getattr(self, "_play_base", 0.0)
                self.position = min(self.duration, base + pos_ms / 1000.0)
                if not self.pygame.mixer.music.get_busy():
                    self.playing = False
        self._update_preview()
        self.win.after(100, self._tick)

    def _update_preview(self):
        t = max(0.0, min(self.duration, self.position))
        if not getattr(self, "_dragging", False):
            self.seek.set(t)
        self.time_label.configure(text=f"{self._fmt(t)} / {self._fmt(self.duration)}")
        active = None
        for w in self.words:
            if float(w.get("start", 0)) <= t <= float(w.get("end", 0)):
                active = w
                break
        if active:
            # Show a short phrase around the active word.
            idx = self.words.index(active)
            phrase = self.words[max(0, idx-3):min(len(self.words), idx+4)]
            self.current_lyric.configure(text=" ".join(x.get("text", "") for x in phrase))
        elif self.words:
            next_word = next((w for w in self.words if float(w.get("start", 0)) > t), None)
            self.current_lyric.configure(
                text=("♪  " + next_word.get("text", "") + "  ♪") if next_word else "♪"
            )
        self._draw_pitch()

    @staticmethod
    def _fmt(seconds):
        m, s = divmod(max(0, seconds), 60)
        return f"{int(m):02}:{s:04.1f}"

    def _draw_pitch(self):
        c = self.pitch_canvas
        c.delete("all")
        width = max(10, c.winfo_width())
        height = max(10, c.winfo_height())
        c.create_text(8, 8, anchor="nw", fill="#aab7c4",
                      text="Tonhöjdskurva – uppskattad från sångspåret")
        for midi in range(36, 85, 12):
            y = height - 15 - (midi - 36) / 48 * (height - 35)
            c.create_line(0, y, width, y, fill="#293744")
            c.create_text(5, y-2, anchor="sw", fill="#aab7c4", text=str(midi))
        if self.duration <= 0:
            return
        points = []
        for event in self.events:
            t = float(event.get("time", 0))
            midi = float(event.get("midi", 60))
            if t < 0 or t > self.duration:
                continue
            x = 12 + (t / self.duration) * (width - 24)
            y = height - 15 - (midi - 36) / 48 * (height - 35)
            if 0 <= y <= height:
                points.append((x, y))
        for x, y in points:
            c.create_oval(x-2, y-2, x+2, y+2, fill="#65c7a5", outline="")
        cursor_x = 12 + (self.position / self.duration) * (width - 24)
        c.create_line(cursor_x, 18, cursor_x, height-8, fill="#ffcc66", width=2)

    def open_folder(self):
        try:
            os.startfile(str(self.song_dir))
        except Exception:
            messagebox.showinfo("Låtmapp", str(self.song_dir), parent=self.win)


def process_song(mp3_path, output_root, log, status):
    mp3 = Path(mp3_path)
    song_dir = Path(output_root) / mp3.stem
    song_dir.mkdir(parents=True, exist_ok=True)
    work_dir = song_dir / "_work"
    work_dir.mkdir(exist_ok=True)

    status("1/4 – Separerar sång och musik…")
    log("Detta steg kan ta flera minuter och kräver en fungerande PyTorch-installation.")
    run_command([
        sys.executable, "-m", "demucs", "--two-stems=vocals",
        "-n", "htdemucs", "-o", str(work_dir), str(mp3)
    ], log)

    # Demucs writes: _work/htdemucs/<song name>/vocals.wav and no_vocals.wav
    separated = work_dir / "htdemucs" / mp3.stem
    vocals_src = separated / "vocals.wav"
    instrumental_src = separated / "no_vocals.wav"
    if not vocals_src.exists() or not instrumental_src.exists():
        raise FileNotFoundError("Demucs skapade inte de förväntade ljudfilerna.")

    import soundfile as sf
    import numpy as np

    status("2/4 – Förbereder ljudfiler…")
    # Preserve the separated stems as WAV; they are useful for quality checks.
    vocals_out = song_dir / "vocals.wav"
    instrumental_out = song_dir / "instrumental.wav"
    shutil.copy2(vocals_src, vocals_out)
    shutil.copy2(instrumental_src, instrumental_out)

    status("3/4 – Transkriberar sångtext…")
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(vocals_out), word_timestamps=True, vad_filter=True
    )

    words = []
    srt_blocks = []
    for seg in segments:
        seg_words = []
        if seg.words:
            for w in seg.words:
                token = (w.word or "").strip()
                if token:
                    item = {
                        "start": round(float(w.start), 3),
                        "end": round(float(w.end), 3),
                        "text": token
                    }
                    words.append(item)
                    seg_words.append(item)
        if not seg_words and (seg.text or "").strip():
            words.append({
                "start": round(float(seg.start), 3),
                "end": round(float(seg.end), 3),
                "text": seg.text.strip()
            })

    def stamp(seconds):
        ms = max(0, int(round(seconds * 1000)))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, milli = divmod(rem, 1000)
        return f"{h:02}:{m:02}:{s:02},{milli:03}"

    # Group words into readable subtitle lines, roughly 6 seconds / 7 words.
    chunks = []
    current = []
    chunk_start = None
    for word in words:
        if chunk_start is None:
            chunk_start = word["start"]
        if current and (word["start"] - chunk_start > 5.5 or len(current) >= 7):
            chunks.append(current)
            current = []
            chunk_start = word["start"]
        current.append(word)
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks, 1):
        start = chunk[0]["start"]
        end = chunk[-1]["end"]
        text = " ".join(w["text"] for w in chunk)
        srt_blocks.append(f"{i}\n{stamp(start)} --> {stamp(end)}\n{text}\n")
    (song_dir / "lyrics.srt").write_text("\n".join(srt_blocks), encoding="utf-8")
    (song_dir / "lyrics.json").write_text(
        json.dumps({"language": info.language, "words": words}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    status("4/4 – Analyserar tonhöjd…")
    # pYIN gives an estimated vocal fundamental frequency. This is an aid for
    # later note-lane generation, not a finished SingStar scoring chart.
    import librosa
    y, sr = librosa.load(str(vocals_out), sr=22050, mono=True)
    if len(y) > 0:
        f0, voiced_flag, voiced_prob = librosa.pyin(
            y, fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"), sr=sr,
            frame_length=2048, hop_length=256
        )
        times = librosa.times_like(f0, sr=sr, hop_length=256)
        note_events = []
        for t, hz, voiced, prob in zip(times, f0, voiced_flag, voiced_prob):
            if voiced and np.isfinite(hz) and prob >= 0.55:
                midi = int(round(float(librosa.hz_to_midi(hz))))
                note_events.append({
                    "time": round(float(t), 3),
                    "midi": midi,
                    "confidence": round(float(prob), 3)
                })
    else:
        note_events = []

    package = {
        "format": "ps2-karaoke-song",
        "format_version": 1,
        "title": mp3.stem,
        "source_file": mp3.name,
        "language": getattr(info, "language", None),
        "audio": {
            "instrumental": "instrumental.wav",
            "vocals_reference": "vocals.wav"
        },
        "lyrics": "lyrics.json",
        "pitch_reference": "pitch.json",
        "notes": "NOTES.txt"
    }
    (song_dir / "pitch.json").write_text(
        json.dumps({"events": note_events, "meaning": "estimated vocal pitch samples; not yet quantized into scoring notes"},
                   ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (song_dir / "song.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (song_dir / "NOTES.txt").write_text(
        "PS2 Karaoke Studio – song package\n\n"
        "instrumental.wav = backing track without separated lead vocals\n"
        "vocals.wav = separated vocal reference\n"
        "lyrics.srt / lyrics.json = automatically recognized lyrics and timing\n"
        "pitch.json = estimated vocal pitch samples\n\n"
        "IMPORTANT: automatic speech recognition and source separation can make mistakes.\n"
        "Review lyrics/timing and pitch before using this song in a game.\n"
        "This is an intermediate PC export, not yet a burnable PS2 DVD image.\n",
        encoding="utf-8"
    )

    shutil.rmtree(work_dir, ignore_errors=True)
    status("Klart!")
    log(f"Färdigt! Låtpaket: {song_dir}")
    return song_dir


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.geometry("760x540")
        root.minsize(650, 450)
        self.mp3 = tk.StringVar()
        self.out = tk.StringVar(value=str(Path.home() / "PS2_Karaoke_Library"))
        self.status = tk.StringVar(value="Välj en MP3-fil för att börja.")
        self.build()
        self.root.after(100, self.poll_queue)

    def build(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="PS2 Karaoke Studio", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Skapa ett karaokelåtpaket från en MP3-fil", foreground="#555").pack(anchor="w", pady=(0, 16))

        row = ttk.Frame(outer)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="MP3-fil", width=12).pack(side="left")
        ttk.Entry(row, textvariable=self.mp3).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Bläddra…", command=self.pick_mp3).pack(side="left", padx=(8, 0))

        row2 = ttk.Frame(outer)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Spara i", width=12).pack(side="left")
        ttk.Entry(row2, textvariable=self.out).pack(side="left", fill="x", expand=True)
        ttk.Button(row2, text="Välj mapp…", command=self.pick_out).pack(side="left", padx=(8, 0))

        self.start_btn = ttk.Button(outer, text="Skapa karaokelåt", command=self.start)
        self.start_btn.pack(anchor="w", pady=12)
        ttk.Label(outer, textvariable=self.status, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        self.log = tk.Text(outer, height=17, wrap="word", state="disabled", bg="#111820", fg="#e6edf3")
        self.log.pack(fill="both", expand=True)
        ttk.Label(outer, text="Obs: första körningen laddar ned AI-modeller. Internet krävs då. En kraftfull dator rekommenderas.",
                  foreground="#555", wraplength=700).pack(anchor="w", pady=(10, 0))

    def write_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def pick_mp3(self):
        p = filedialog.askopenfilename(filetypes=[("MP3 ljudfiler", "*.mp3"), ("Alla filer", "*.*")])
        if p:
            self.mp3.set(p)

    def pick_out(self):
        p = filedialog.askdirectory()
        if p:
            self.out.set(p)

    def start(self):
        mp3 = self.mp3.get().strip()
        if not mp3 or not Path(mp3).is_file():
            messagebox.showerror("Ingen MP3 vald", "Välj en giltig MP3-fil först.")
            return
        if Path(mp3).suffix.lower() != ".mp3":
            messagebox.showerror("Fel filtyp", "Välj en MP3-fil.")
            return
        self.start_btn.configure(state="disabled")
        self.status.set("Startar…")
        self.write_log("=== Ny låt ===")
        def worker():
            try:
                result = process_song(mp3, self.out.get(), lambda s: TASKS.put(("log", s)),
                                      lambda s: TASKS.put(("status", s)))
                TASKS.put(("done", str(result)))
            except Exception:
                TASKS.put(("error", traceback.format_exc()))
        threading.Thread(target=worker, daemon=True).start()

    def poll_queue(self):
        try:
            while True:
                kind, value = TASKS.get_nowait()
                if kind == "log":
                    self.write_log(value)
                elif kind == "status":
                    self.status.set(value)
                elif kind == "done":
                    self.start_btn.configure(state="normal")
                    self.status.set("Klart!")
                    messagebox.showinfo("Färdig", f"Karaokelåten skapades:\n{value}")
                    PreviewWindow(self.root, value)
                elif kind == "error":
                    self.start_btn.configure(state="normal")
                    self.status.set("Ett fel uppstod.")
                    self.write_log(value)
                    messagebox.showerror("Bearbetningen misslyckades", value[-1800:])
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    App(root)
    root.mainloop()
