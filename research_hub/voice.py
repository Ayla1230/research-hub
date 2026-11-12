"""Text to speech with the voices already installed on this computer (no cloud, no extra packages).

macOS uses ``say``, Windows uses System.Speech through PowerShell, Linux uses espeak-ng. The text is always
handed over through a temporary file, never on a command line. Output is a WAV file.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_CHARS = 30000
TIMEOUT = 300


class VoiceError(Exception):
    pass


def engine() -> str:
    if sys.platform == "darwin" and shutil.which("say"):
        return "say"
    if sys.platform == "win32" and shutil.which("powershell"):
        return "sapi"
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"
    return ""


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=kw.pop("timeout", 30), **kw)


def voices() -> list[dict]:
    """Installed voices as [{name, lang}]."""
    eng = engine()
    out: list[dict] = []
    try:
        if eng == "say":
            for line in _run(["say", "-v", "?"]).stdout.decode("utf-8", "replace").splitlines():
                m = re.match(r"^(.+?)\s{2,}([a-z]{2}[_-][A-Za-z0-9]+)", line)
                if m:
                    out.append({"name": m.group(1).strip(), "lang": m.group(2).replace("_", "-")})
        elif eng == "sapi":
            ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture.Name }")
            for line in _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]).stdout.decode("utf-8", "replace").splitlines():
                if "|" in line:
                    name, lang = line.strip().split("|", 1)
                    out.append({"name": name, "lang": lang})
        elif eng == "espeak":
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            for line in _run([exe, "--voices"]).stdout.decode("utf-8", "replace").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    out.append({"name": parts[1], "lang": parts[1]})
    except (OSError, subprocess.SubprocessError):
        return []
    return out


def _clean(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text or "").strip()
    if not text:
        raise VoiceError("nothing to read")
    return text[:MAX_CHARS]


def synthesize(text: str, voice: str = "", rate: float = 1.0, pitch: float = 1.0) -> bytes:
    """Read ``text`` aloud into WAV bytes. ``rate`` and ``pitch`` are multipliers around 1.0 (0.5–2.0)."""
    eng = engine()
    if not eng:
        raise VoiceError("no speech engine found on this computer (macOS: say, Windows: built in, Linux: install espeak-ng)")
    text = _clean(text)
    rate = max(0.5, min(2.0, float(rate or 1)))
    pitch = max(0.5, min(2.0, float(pitch or 1)))
    known = {v["name"] for v in voices()}
    if voice and voice not in known:
        raise VoiceError("unknown voice")
    with tempfile.TemporaryDirectory(prefix="hub-voice-") as tmp:
        src, dst = Path(tmp) / "script.txt", Path(tmp) / "speech.wav"
        if eng == "say":
            shift = round((pitch - 1) * 24)  # semitone-ish offset on the voice's base pitch
            src.write_text((f"[[pbas {shift:+d}]] " if shift else "") + text, encoding="utf-8")
            cmd = ["say", "-r", str(round(180 * rate)), "-o", str(dst), "--file-format=WAVE", "--data-format=LEI16@22050", "-f", str(src)]
            if voice:
                cmd[1:1] = ["-v", voice]
            done = _run(cmd, timeout=TIMEOUT)
        elif eng == "sapi":
            src.write_text(text, encoding="utf-8")
            (Path(tmp) / "voice.txt").write_text(voice, encoding="utf-8")
            ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$v = Get-Content -Raw -Encoding UTF8 '{tmp}\\voice.txt'; if ($v) {{ $s.SelectVoice($v.Trim()) }}; "
                  f"$s.Rate = {round((rate - 1) * 10 if rate <= 1 else (rate - 1) * 10)}; $s.SetOutputToWaveFile('{dst}'); "
                  f"$t = [System.Security.SecurityElement]::Escape((Get-Content -Raw -Encoding UTF8 '{src}')); "
                  f"$p = New-Object System.Speech.Synthesis.PromptBuilder; "
                  f"$p.AppendSsmlMarkup('<prosody pitch=\"{round((pitch - 1) * 100):+d}%\">' + $t + '</prosody>'); $s.Speak($p); $s.Dispose()")
            done = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=TIMEOUT)
        else:
            src.write_text(text, encoding="utf-8")
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            cmd = [exe, "-s", str(round(170 * rate)), "-p", str(max(0, min(99, round(50 * pitch)))), "-w", str(dst), "-f", str(src)]
            if voice:
                cmd[1:1] = ["-v", voice]
            done = _run(cmd, timeout=TIMEOUT)
        if done.returncode != 0 or not dst.is_file() or dst.stat().st_size < 100:
            raise VoiceError("speech engine failed: " + done.stderr.decode("utf-8", "replace")[:200])
        return dst.read_bytes()
