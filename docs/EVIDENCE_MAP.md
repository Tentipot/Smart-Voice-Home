# Smart voice home — EVIDENCE MAP
Updated: 2026-09-22

## Primary historical source
`VoiceAssistant_ChatLOG.txt`
- 101,106 lines.
- Begins 2026-08-29 with offline Bulgarian speech-recognition discussion.
- Continues through Android MVP, Spotify, platform architecture, Windows AssistantServer development and 2026-09-22 reconstruction.
- Treat as the primary conversation-history source until compared with the official ChatGPT export.

Important regions:
- early Android/offline STT: beginning through ~L20500;
- platform/client-server transition: ~L20914 onward;
- Home Assistant and multi-home: ~L21300 onward;
- multi-user/wake/device/permissions architecture: ~L21600–L23600;
- TTS/network/platform portability: ~L24300 onward;
- Windows STT/resource implementation: later large development sections through the end.

## Full-log reconstruction
`Smart_voice_home_FULL_LOG_RECONSTRUCTION.md`
- Derived architectural/history reconstruction from the full chat log.
- Use as a navigational summary, not as a replacement for primary evidence.

## Forensic source snapshot
`AssistantServer_FORENSIC.zip` and forensic retrospective/inventory, when present.
Use for actual file existence, timestamps, source contents and diagnostic artifacts.

## Historical architecture PDF
`Assistant_Platform_Project_Architecture_BG_v2(1).pdf`
Use as a historical architecture snapshot only.
It must not override later explicit conversation decisions or implementation evidence.

## Current implementation evidence classes
Strong:
- actual source/config/test code;
- saved CSV/manifest;
- saved stdout/result artifact.

Medium:
- diagnostic source that proves intended test configuration but has no saved output.

Weak:
- assistant prose saying a test/result existed without independent artifact.

## Evidence rules
- File existence ≠ production integration.
- Diagnostic script ≠ successful measured result unless output/result is preserved.
- Calibration set ≠ independent validation.
- Assistant proposal ≠ accepted user decision.
- Newer explicit user correction overrides older assumptions.
