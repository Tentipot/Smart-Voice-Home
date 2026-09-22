# Smart voice home — PROJECT MASTER
Updated: 2026-09-22

## Purpose
Smart voice home is a local/offline-first, multi-user, multi-device and multi-home-ready voice-assistant platform. It grew from an Android offline voice assistant into a client/server system.

"Aurora / Аурора" is a wake word used in development; it is not the project name.

## Core interaction model
Wake word or push-to-talk
→ origin device/context
→ authenticated account/device
→ audio capture
→ language evidence / STT routing
→ transcript
→ intent or conversational routing
→ permission policy
→ user preferences/context
→ integration/provider
→ playback/action target resolution
→ action
→ response/TTS
→ audit.

## Platform
- Central Assistant Server: initially Windows 11 PC, later Linux-capable/dedicated host.
- Android client: Kotlin; microphone, wake/UI, local fallback and device-side actions.
- Common API/protocol: HTTPS/WebSocket direction; server internals remain replaceable.
- Future clients can include Windows, Linux, Web, room endpoints and later iOS.

## Users and identity
- Multiple users/accounts.
- Maximum approximately two administrators.
- Each user may have multiple devices, preferences, permissions, default language, service connections and personal wake word.
- Wake word selects context but is not authentication.
- Permissions derive from authenticated account/device and policy.
- General/shared wake context is possible but must not pretend to identify a person.
- Exact multi-device wake arbitration remains open.

## Languages
- Bulgarian and English are required.
- Per-user default language.
- Per-request/dynamic language switching.
- Input/STT language, response language and search language are distinct concerns.

## Media
- Open-vocabulary media queries; no hardcoded artist/song catalog.
- Media provider and playback target are separate abstractions.
- Providers include Spotify and planned YouTube.
- Targets can include phone, TV, PC, speaker or Home Assistant media target.
- Explicit target wins over default/origin routing.
- Spotify connection must ultimately be per-user.

## Home Assistant
- Home Assistant is the smart-home authority/integration layer.
- Initially one home; later at least two homes.
- Admins control exposed capabilities and permissions.
- Security-critical capabilities can be VOICE_FORBIDDEN even for admins; door/access unlocking is the canonical example.

## Preferences vs permissions
Preferences can change tone, verbosity, language and proactive follow-up suggestions.
They cannot grant permissions or silently create routines/actions.
Example: after "Спри телевизора в спалнята", a user's preferences may allow the assistant to ask "Да спра ли и лампата?", but the extra action still requires its own authorization/confirmation logic.

## Online boundary
Local/offline-first.
Remote access to the user's own Assistant Server is a normal platform capability.
External online search, cloud STT or external AI providers must not become an invisible fallback; they require explicit intent/consent according to policy.

## Administration
A PC-oriented GUI/Web Admin is planned for users, devices, homes, permissions, wake words, integrations, preferences, speech settings, network/server settings, audit and resource status.
Secrets/passwords are not shown as plaintext.

## Resource awareness
The server shares the PC with gaming/work.
A Resource Manager is planned to observe CPU/RAM/GPU/VRAM and degrade/yield appropriately.
The exact local conversational-AI CPU/RAM/GPU placement remains benchmark-driven and open.

## Architectural style
Start as a modular monolith. Do not prematurely split into microservices.
Keep platform-specific Windows/Linux operations behind adapters.
Do not equate source-file existence with production integration.

## Authority rules
Newer explicit user decisions override older proposals.
Assistant proposal is not a requirement unless accepted.
Implementation/test evidence describes what exists, not necessarily what is desired.
The old architecture PDF is historical evidence, not final authority.
