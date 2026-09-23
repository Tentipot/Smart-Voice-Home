# Smart voice home — PROJECT HISTORY
Updated: 2026-09-23

## 1. Origin — offline Bulgarian STT
The project begins on 2026-08-29 as a search for a free offline Bulgarian voice-recognition solution for a software project.

## 2. Android offline assistant
The work becomes an Android/Kotlin assistant with microphone capture, whisper.cpp/local Whisper, command parsing and Android media actions. Early manual Start/Stop listening is a development mechanism rather than the intended final interaction.

## 3. Media and Spotify
The assistant evolves from Spotify search/deep-link behavior into Spotify Developer setup, App Remote and Web API search so open-vocabulary artist/title queries can resolve to a real track URI and play.

## 4. Server-platform transition
The decisive architectural expansion occurs when the user requires:
- use outside the home over Internet;
- multiple users;
- future non-Android clients;
- server resource awareness while the PC is gaming/working.

The project becomes a client/server assistant platform rather than a phone app.

## 5. Smart-home expansion
Home Assistant is added as the smart-home authority. The design expands from one home to future multiple homes, with permission controls and voice-forbidden security-critical actions.

## 6. Identity and multi-device design
Personal user-selected wake words, general/shared wake context, authenticated accounts/devices, origin-vs-target separation and per-user services/preferences are developed. Wake word is explicitly not authentication.

## 7. Administration and personalization
The architecture gains a PC-oriented admin GUI, user/device/home/permission management, language profiles, response preferences, TTS planning, network management and audit.

## 8. Windows AssistantServer
The central server work starts on Windows 11 / Ryzen 5 3600 / 32 GB / RTX 3070 with FastAPI/system monitoring and extensive STT benchmarking.

## 9. STT model selection and routing
Multiple engines are compared. The implementation evolves toward:
- BuzzASR for Bulgarian;
- Whisper large-v3 for English/mixed;
- BG+EN CTC as language evidence;
- LanguageResolver + SttRouter + SttService.

## 10. Resource lifecycle
Model lifecycle abstractions, ModelHandle and ModelManager are developed and tested. GPU/RAM residency experiments lead to an investigated composition with Buzz+Whisper on GPU and CTC on CPU/RAM.

## 11. Natural capture / wake work
Live microphone capture, WebRTC VAD and wake-word experiments lead to AuroraCapture. "Аурора" is a wake word used in development, not the project name.

## 12. Language calibration
A dedicated 40-WAV BG/EN dataset is manually reviewed and used to calibrate the production LanguageResolver ambiguity zone.

## 13. Reconstruction checkpoint
On 2026-09-22 development pauses because the long chat no longer provides trustworthy complete historical context. A forensic source snapshot and then the full `VoiceAssistant_ChatLOG.txt` are used to reconstruct project history and architecture.

The official ChatGPT export remains useful as an independent completeness check when it arrives.

## 14. AuroraCapture functional verification — 2026-09-23

A live microphone test verifies the basic Aurora wake-word capture path
with one Bulgarian and one English utterance.

The user speaks the wake word and command continuously, without an
intentional pause. AuroraCapture retains pre-roll audio, uses WebRTC VAD
to detect the phrase boundaries, recognizes the wake word and delivers
the complete captured phrase.

Both recordings are played back and manually accepted:
- `data/language_dataset/bg_001_20260923_212640_017014.wav`
- `data/language_dataset/en_002_20260923_212654_840062.wav`

Two earlier isolated wake-word recordings are also successfully
recognized using Whisper large-v3 on CUDA.

This checkpoint establishes basic functional operation, not production
wake-detection reliability. Final command STT and real assistant actions
are outside the scope of this test.

A CUDA dependency issue is identified: CTranslate2 inference works
when the NVIDIA DLL directories are added to PATH before Python starts.
A permanent startup fix remains open.

The audio dataset inventory and its validation boundaries are recorded
in `docs/AUDIO_DATASETS.md`.
