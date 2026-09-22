# Smart voice home — DECISION REGISTER
Updated: 2026-09-22

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

## Superseded / rejected assumptions
- One global Spotify account for all users — prototype only.
- Wake word as proof of identity — rejected.
- `Аурора` as project/assistant name — incorrect.
- CTC necessarily resident on GPU — superseded by later CPU/RAM diagnostic composition.
- Local conversational AI fixed to CPU-only — not final; benchmark-driven.
- Android `base.en-q5_1` as sufficient universal open-vocabulary STT — superseded by server-STT direction.
