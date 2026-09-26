"""One STT pass followed by semantic review, without action executors."""
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from app.commands.semantic_review import SemanticReview, SemanticReviewer

if TYPE_CHECKING:
    from app.speech.stt.service import SttService, SttTranscription


@dataclass(frozen=True, slots=True)
class ReviewedTranscription:
    transcription: 'SttTranscription'
    review: SemanticReview


class CommandReviewService:
    def __init__(self, stt_service: 'SttService', reviewer: SemanticReviewer | None = None):
        self._stt = stt_service
        self._reviewer = reviewer or SemanticReviewer()

    def transcribe_and_review(self, audio_path: Path) -> ReviewedTranscription:
        transcription = self._stt.transcribe_with_evidence(audio_path)
        return ReviewedTranscription(transcription, self._reviewer.review(transcription.result.text))
