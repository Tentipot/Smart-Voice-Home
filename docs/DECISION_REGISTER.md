# Smart voice home — DECISION REGISTER
Updated: 2026-09-26

| ID | Decision | Status |
|---|---|---|
| D001 | Project is `Smart voice home`; `Аурора` is a wake word, not project name | CURRENT |
| D002 | Platform is local/offline-first | CURRENT |
| D003 | Central client/server architecture with Android as one client | CURRENT |
| D004 | Android client remains Kotlin | CURRENT |
| D005 | Initial server is Windows PC; architecture must remain Linux-migratable | CURRENT |
| D006 | Modular monolith first; no premature microservices | CURRENT |
| D007 | Multiple users/accounts are fundamental | CURRENT |
| D008 | Wake word is context selection, not authentication | CURRENT |
| D009 | Users may select personal wake words | CURRENT |
| D010 | Authenticated account/device and policy determine permissions | CURRENT |
| D011 | Origin device and execution/playback target are separate concepts | CURRENT |
| D012 | Explicit media target wins over default/origin routing | CURRENT |
| D013 | Media provider and playback target are separate abstractions | CURRENT |
| D014 | Media queries are open vocabulary; do not hardcode artists/songs | CURRENT |
| D015 | Spotify ultimately uses per-user service connections | CURRENT |
| D016 | Home Assistant is smart-home authority; initial one home, later multi-home | CURRENT |
| D017 | Security-critical capabilities may be VOICE_FORBIDDEN even for admins | CURRENT |
| D018 | Preferences never grant permissions or silently become routines | CURRENT |
| D019 | Bulgarian and English speech/response support required | CURRENT |
| D020 | User profile has default language with per-request/dynamic override | CURRENT |
| D021 | PC-oriented admin GUI is planned; maximum roughly two admins | CURRENT |
| D022 | External cloud/search/AI is not a silent fallback; explicit intent/consent required | CURRENT |
| D023 | Resource-aware behavior must yield to gaming/workload | CURRENT |
| D024 | Final local-AI CPU/RAM/GPU placement will be benchmark-driven | CURRENT / OPEN IMPLEMENTATION |
| D025 | Current STT route: CTC evidence → resolver → Buzz/Whisper | IMPLEMENTED DIRECTION |
| D026 | Later investigated STT residency: Buzz+Whisper GPU, CTC CPU/RAM | IMPLEMENTATION EVIDENCE |
| D027 | Current resolver thresholds 0.003 / 0.043 are calibration-derived, not independently validated | CURRENT EVIDENCE |
| D028 | Speaker recognition is not the primary identity mechanism | CURRENT |
| D029 | Local wake detection should not require continuous room audio upload | CURRENT |
| D030 | Exact multi-device same-command arbitration remains unresolved/requires recovery/design | OPEN |
| D031 | User-authorized bounded post-STT review: preserve evidence, exact single-command grammar, clarify unresolved/conflicting candidates, no execution authorization | IMPLEMENTED LIMITED V1 — 2026-09-26; see SEMANTIC_REVIEW_V1.md |
| D032 | Project memory is maintained in files, not in chat length: after each completed stage or new explicit user decision, update DECISION_REGISTER / PROJECT_STATE / OPEN_QUESTIONS (and CHATLOG_FULL_READ_2026-09-26.md for log-derived findings) | CURRENT — user decision 2026-09-26 |
| D033 | Wake word and command are spoken as one phrase without pause; two-step "Аурора" → "Да?" → command was considered and rejected (log L77723–77751) | CURRENT — recovered from ChatLOG |
| D034 | ~~No additional model only for the wake word; use the existing models (log L74303–74307)~~ | SUPERSEDED — user decision 2026-09-26: no longer valid; a dedicated or different wake mechanism/model is allowed, and larger rework of the program is acceptable if needed |
| D035 | Typical mixed speech = Bulgarian command + foreign brand/artist/song/film names, not full clause switching (log L43413–43506, newer than L29290) | CURRENT — recovered from ChatLOG |
| D036 | Wake detection default: CTC keyword spotting with the BG CTC model on CPU; Whisper wake kept as switchable fallback (SMART_VOICE_WAKE_DETECTOR) | IMPLEMENTED — user approval 2026-09-26; offline replay only, live validation pending |

## Superseded / rejected assumptions
Implementation clarification (2026-09-26, user-authorized continuation):
the service adds `SttTranscription` through `transcribe_with_evidence()`
while preserving the simple SttResult API. This is routing provenance and
aggregate evidence, not the deferred SttCandidate design or a new MIXED policy.

- One global Spotify account for all users — prototype only.
- Wake word as proof of identity — rejected.
- `Аурора` as project/assistant name — incorrect.
- CTC necessarily resident on GPU — superseded by later CPU/RAM diagnostic composition.
- Local conversational AI fixed to CPU-only — not final; benchmark-driven.
- Android `base.en-q5_1` as sufficient universal open-vocabulary STT — superseded by server-STT direction.
- "No additional model only for the wake word" (D034, log L74303) — declared invalid by the user on 2026-09-26.
