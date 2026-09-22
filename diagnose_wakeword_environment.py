import importlib.util
import sys
from pathlib import Path

print("Python:", sys.executable)
print("Project:", Path.cwd())
print()

packages = (
    "sounddevice",
    "soundfile",
    "numpy",
    "webrtcvad",
    "vosk",
    "openwakeword",
    "onnxruntime",
    "faster_whisper",
    "whisper",
    "torch",
)

print("Installed packages:")
for name in packages:
    print(f"  {name:18} {'YES' if importlib.util.find_spec(name) else 'NO'}")

print()
print("Potential wake-word / speech model files:")
roots = (
    Path("models"),
    Path("data/models"),
    Path("app/speech"),
)

extensions = {".onnx", ".tflite", ".pt", ".pth"}
found = 0

for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if path.is_file() and (
            path.suffix.lower() in extensions
            or path.name.lower() in {"am", "final.mdl"}
        ):
            print(" ", path)
            found += 1
            if found >= 50:
                print("  ... output limited to 50 files")
                break
    if found >= 50:
        break

if not found:
    print("  No candidate model files in the checked directories.")

print()
try:
    import sounddevice as sd
    devices = sd.query_devices()
    if len(devices) > 1:
        device = devices[1]
        print("Device 1:", device["name"])
        print("Input channels:", device["max_input_channels"])
        print("Default sample rate:", device["default_samplerate"])
    else:
        print("Device 1 is not available.")
except Exception as exc:
    print("Audio device check failed:", repr(exc))
