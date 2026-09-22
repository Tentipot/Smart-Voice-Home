import time
from pathlib import Path

import torch
import nemo.collections.asr as nemo_asr


MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v3"

AUDIO_FILE = (
    Path(__file__).resolve().parent
    / "data"
    / "stt_benchmark"
    / "test_001.wav"
)


def main() -> None:
    print()
    print("Assistant STT - Parakeet Test")
    print("-----------------------------")
    print(f"Model : {MODEL_NAME}")
    print(f"Audio : {AUDIO_FILE}")
    print()

    if not AUDIO_FILE.exists():
        raise FileNotFoundError(f"Audio file not found: {AUDIO_FILE}")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    device = torch.device("cuda")

    print(f"GPU   : {torch.cuda.get_device_name(0)}")
    print()
    print("Loading model...")

    load_start = time.perf_counter()

    model = nemo_asr.models.ASRModel.from_pretrained(
        model_name=MODEL_NAME,
        map_location=device,
    )

    model.eval()

    load_seconds = time.perf_counter() - load_start

    print(f"Model loaded in {load_seconds:.2f} s")
    print(
        "VRAM after load: "
        f"{torch.cuda.memory_allocated(0) / 1024**3:.2f} GB"
    )

    print()
    print("Transcribing...")

    torch.cuda.reset_peak_memory_stats(0)
    torch.cuda.synchronize()

    inference_start = time.perf_counter()

    with torch.inference_mode():
        result = model.transcribe(
            [str(AUDIO_FILE)],
            batch_size=1,
        )

    torch.cuda.synchronize()

    inference_seconds = time.perf_counter() - inference_start

    peak_vram_gb = torch.cuda.max_memory_allocated(0) / 1024**3

    print()
    print("========== RESULT ==========")
    print()

    if isinstance(result, tuple):
        result = result[0]

    first_result = result[0]

    if hasattr(first_result, "text"):
        transcript = first_result.text
    else:
        transcript = str(first_result)

    print(f"Transcript : {transcript}")
    print(f"Inference  : {inference_seconds:.3f} s")
    print(f"Peak VRAM  : {peak_vram_gb:.2f} GB")
    print()
    print("============================")
    print()


if __name__ == "__main__":
    main()