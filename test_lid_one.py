import time

from speechbrain.inference.classifiers import EncoderClassifier


MODEL_NAME = "speechbrain/lang-id-voxlingua107-ecapa"

AUDIO_PATH = (
    "D:/AssistantServer/data/stt_benchmark/test_003.wav"
)


def main() -> None:
    print("Loading LID model...")

    classifier = EncoderClassifier.from_hparams(
        source=MODEL_NAME,
        savedir="models/lid-voxlingua107-ecapa",
        run_opts={
            "device": "cuda",
        },
    )

    print("Classifying:")
    print(AUDIO_PATH)
    print()

    start = time.perf_counter()

    result = classifier.classify_file(
        AUDIO_PATH
    )

    elapsed = time.perf_counter() - start

    print("RAW RESULT:")
    print(result)
    print()

    print("RESULT TYPES:")
    for index, value in enumerate(result):
        print(
            f"[{index}] "
            f"{type(value).__name__}: "
            f"{value}"
        )

    print()
    print(
        f"Inference: {elapsed:.3f} s"
    )


if __name__ == "__main__":
    main()