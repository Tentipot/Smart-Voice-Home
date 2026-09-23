# Smart voice home — OPEN QUESTIONS
Updated: 2026-09-23

These are intentionally unresolved. Do not silently invent answers.

1. Exact arbitration when multiple devices hear the same wake phrase/command.
2. Final authentication/token/device-registration protocol.
3. Final user/device/home/permission database schema.
4. Final production remote-access/gateway technology.
5. Final general/shared wake-word policy.
6. Final TTS model(s), voice(s), streaming strategy and resource placement.
7. Final local conversational-AI model and CPU/RAM/GPU placement.
8. Final Web Admin technology stack and deployment.
9. Exact Home Assistant permission/capability mapping.
10. Final MediaProvider / PlaybackTarget API and default-routing rules for every action type.
11. Production server composition root.
12. Production `/stt` endpoint and streaming protocol.
13. Independent validation dataset for CTC resolver thresholds.
14. MIXED fallback quality, especially Bulgarian/mixed speech.
15. Production Resource Manager policy, budgets and gaming behavior.
16. Exact split of Android-local vs server-side functionality after integration.
17. Profile/preferences synchronization across multiple devices.
18. Ownership/trust model for shared room endpoints.
19. Detailed explicit-consent UX/policy for each type of external online provider.
20. Backup/restore/versioning strategy for server configuration, users and integrations.
21. Full re-audit of Android source and Spotify implementation against current platform design.
22. Reconciliation of this reconstruction with the official ChatGPT export when received.

23. Permanent CUDA DLL discovery for CTranslate2/Whisper on Windows.
    Current verified workaround: prepend the installed NVIDIA DLL
    directories to PATH before starting Python.

24. End-to-end integration of AuroraCapture with SttService:
    full captured phrase → language evidence → resolver → STT router
    → final command transcript. No real assistant actions during
    initial integration diagnostics.

25. Command-only audio extraction and precise wake-word boundary,
    if required by the final command-processing design.

26. Wake-detection reliability validation across speakers, noise
    conditions and a larger BG/EN command dataset. The two accepted
    live recordings establish functional operation only.

27. Separation of preliminary wake-detection ASR text/language labels
    from final command transcription and language routing.

28. Preservation and backup of local audio datasets under data/,
    which is excluded from Git. See docs/AUDIO_DATASETS.md.
