import time

import torch
from speechbrain.inference.classifiers import EncoderClassifier


MODEL_NAME = "speechbrain/lang-id-voxlingua107-ecapa"


def main() -> None:
    print("Loading LID model...")

    start = time.perf_counter()

    classifier = EncoderClassifier.from_hparams(
        source=MODEL_NAME,
        savedir="models/lid-voxlingua107-ecapa",
        run_opts={
            "device": "cuda",
        },
    )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    load_seconds = time.perf_counter() - start

    print()
    print("LID MODEL LOADED")
    print(f"Model : {MODEL_NAME}")
    print(f"Device: {classifier.device}")
    print(f"Load  : {load_seconds:.3f} s")


if __name__ == "__main__":
    main()