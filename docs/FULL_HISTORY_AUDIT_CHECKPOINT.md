# Smart Voice Home --- Full History Audit Checkpoint

**Checkpoint date:** 2026-09-26\
**Repository:** `D:\AssistantServer`\
**Historical primary source:** `VoiceAssistant_ChatLOG.txt`\
**Purpose:** Forensic reconstruction checkpoint created during the full
project-history audit.

------------------------------------------------------------------------

## 1. Status and purpose of this document

This is an **INTERMEDIATE FORENSIC CHECKPOINT**, not the final project
reconstruction.

Its purpose is to preserve findings recovered so far from:

-   the primary historical ChatGPT conversation log;
-   the current repository snapshot;
-   current project-memory documents;
-   historical benchmark and diagnostic evidence already inspected.

The audit is intentionally broader than STT. It covers the complete
Smart Voice Home platform, including:

-   Android client;
-   server/API;
-   STT;
-   wake word;
-   identity;
-   authentication and authorization;
-   users/devices/homes;
-   Home Assistant;
-   media/providers/playback targets;
-   security/privacy;
-   Resource Manager;
-   Model Manager;
-   TTS;
-   local conversational AI;
-   fallback behavior;
-   remote access;
-   future administration/deployment architecture.

This checkpoint MUST NOT be interpreted as proof that every historical
statement has already been verified.

The primary historical log contains approximately 101,106 lines and the
repository snapshot contains 131 tracked files. The forensic audit is
still in progress.

No architecture change is authorized by this document.

No STT route, threshold, model, resource policy, API contract,
permission model, or fallback behavior should be changed solely because
it appears in this checkpoint.

------------------------------------------------------------------------

## 2. Evidence classification

Every recovered item should be interpreted using these categories.

### IMPLEMENTED

Confirmed to exist in current or historical code.

This does NOT automatically mean the implementation is currently used in
the production path.

### EXECUTED / VERIFIED

There is evidence that code/test/diagnostic was actually executed and
produced a result.

This does NOT automatically imply production readiness or independent
validation.

### ACCEPTED DESIGN

The historical conversation contains sufficiently strong evidence that
the user accepted or explicitly defined the architectural behavior.

Implementation may still be absent.

### HISTORICAL PROPOSAL

Discussed or proposed, but acceptance and/or implementation has not yet
been established.

Assistant proposals alone MUST NOT be promoted to project decisions.

### SUPERSEDED / REJECTED

An older mechanism or proposal was later replaced, rejected, or
constrained by a later decision/evidence.

### UNRESOLVED

Evidence is incomplete, contradictory, or still under forensic review.

------------------------------------------------------------------------

# 3. Fundamental platform architecture

## 3.1 Local/offline-first platform

**Status: ACCEPTED DESIGN**

Smart Voice Home is fundamentally a local/offline-first assistant
platform.

Cloud/search/online AI must NOT silently become fallback merely because
a local component fails.

External processing requires explicit user intent/consent according to
the project's privacy policy.

This remains a fundamental architectural boundary.

------------------------------------------------------------------------

## 3.2 Client/server architecture

**Status: ACCEPTED DESIGN**

The project evolved from an Android-local prototype into a client/server
assistant platform.

Target conceptual structure:

\`\`\`text Clients \| \| HTTPS / WebSocket v Assistant Server \| +--
Authentication +-- Session/User Context +-- Speech +-- Assistant/Intent
Core +-- Security/Policy +-- Integrations +-- TTS +-- Resource
Management Android must communicate through our own Assistant
API/protocol rather than depend directly on Whisper, Spotify, Home
Assistant, or another backend implementation. This allows server
internals to change without redesigning every client. 3.3 Android
remains Kotlin Status: ACCEPTED DESIGN Android remains a Kotlin client.
The move toward centralized server processing does NOT mean discarding
the Android implementation. Android is intended to retain
responsibilities such as: - UI; - microphone/capture; - local wake
detection; - device-local capabilities; - manual microphone
interaction; - local/offline fallback; - communication with Assistant
Server.

## 4. Android historical evolution 4.1 Original Android-local
STT Status: IMPLEMENTED / HISTORICAL An earlier Android implementation
used local whisper.cpp/JNI speech recognition. Historical tests included
quantized English Whisper models. Evidence recovered so far indicates
that small.en-q5_1 produced roughly similar command accuracy to
base.en-q5_1 in one specific test, while being significantly slower.
Approximate historical observation: base.en-q5_1 \~0.9--1.0 s
small.en-q5_1 \~3.5--3.7 s

with approximately 6/8 recognized examples in that particular
comparison. These values are historical test evidence and MUST NOT be
generalized beyond that test. 4.2 Reason for moving STT toward the
server Status: EXECUTED EVIDENCE + ACCEPTED ARCHITECTURAL DIRECTION The
Android-local model was adequate for a limited command vocabulary but
was not sufficient for robust open-vocabulary recognition such as
arbitrary: - artist names; - song titles; - media queries. This was an
important reason for testing stronger server-side STT on the RTX 3070.
Therefore the server architecture was not chosen arbitrarily; it evolved
from observed limitations of the Android-local speech path. 4.3 Android
local fallback remains part of the design Status: ACCEPTED DESIGN The
target behavior is conceptually: Home Wi-Fi -\> Assistant Server

Internet / 4G / 5G -\> secure remote Assistant Server

Server unavailable / no connection -\> Android local fallback

The client should not require separate "home" and "remote" applications.
The same Assistant API concept should remain usable across transport
environments. Exact fallback models/policies remain subject to future
validation.

## 5. Historical Android CommandParser safety lessons 5.1
Exact before fuzzy Status: HISTORICAL IMPLEMENTATION / ACCEPTED SAFETY
LESSON The historical Android CommandParser evolved toward processing
exact command matches before fuzzy matches. This is important evidence
for future semantic/intent design. 5.2 Opposite actions must not be
aggressively fuzzy-matched Status: ACCEPTED SAFETY PRINCIPLE Historical
parser work explicitly identified the danger of fuzzy matching opposite
commands such as: по-силно \<-\> по-тихо increase \<-\> decrease stop
\<-\> continue

The safer behavior is to reject/clarify an uncertain command rather than
execute the opposite action. The historical Android parser itself may be
superseded architecturally, but this safety principle remains relevant
to future Intent/Entity resolution. This principle directly relates to
later STT findings where a low-WER transcript can still invert command
semantics.

## 6. Identity model A major historical finding is that
several concepts MUST remain separate. 6.1 Personal context Status:
ACCEPTED DESIGN Personal context answers approximately: Whose
personalization/context is being requested?

A personal wake word can contribute to this context. 6.2 Authenticated
identity / authorization context Status: ACCEPTED DESIGN Permissions do
NOT come from the spoken wake word. Authorization comes from the
authenticated account/device/session context. A physical person saying
another user's wake word must NOT inherit that user's security
permissions. 6.3 Origin device Status: ACCEPTED DESIGN Origin device
means: Which device heard/initiated the request?

This is independent of who the system believes the request concerns. 6.4
Execution/playback target Status: ACCEPTED DESIGN Target means: Where
should the requested action occur?

Origin and target may be different. Example: origin = phone target =
LivingRoomTV

6.5 Critical separation Status: ACCEPTED DESIGN The architecture
therefore distinguishes at least: PERSONAL CONTEXT AUTHORIZATION CONTEXT
ORIGIN DEVICE EXECUTION TARGET

These MUST NOT be collapsed into a single user or device field in future
architecture.

## 7. Wake words and identity 7.1 Wake word is not
authentication Status: ACCEPTED DESIGN Wake words provide
context/activation. They are NOT security credentials. 7.2 General and
personal wake-word concepts Status: ACCEPTED DESIGN, DETAILS STILL UNDER
AUDIT Historical design includes both shared/general wake behavior and
personal wake-word concepts. Personal wake words may select
personalization. They must never elevate authorization. Exact final
rules concerning common vs personal wake words are still being
reconstructed and should not be simplified prematurely. 7.3
User-selected personal wake word Status: ACCEPTED DESIGN The user should
choose their personal wake word when the account/device relationship is
configured. It should not simply be program-generated. 7.4 Wake-word
onboarding quality check Status: ACCEPTED DESIGN / NOT IMPLEMENTED
Historical design includes an onboarding process in which the user says
the candidate wake word multiple times and the system evaluates
characteristics such as: - detection quality; - false activation risk; -
conflict with existing wake words. A poor candidate should cause the
system to recommend another word. Within an acoustically shared group,
personal wake words should avoid conflicts/duplication. 7.5
Open-vocabulary wake-word technology Status: HISTORICAL PROPOSAL /
FUTURE BENCHMARK sherpa-onnx open-vocabulary KWS was identified as a
possible technology for dynamic personal wake words. It was NOT
established as the final production wake-word engine. No future
documentation should state: Wake engine = sherpa-onnx

as an accepted implementation decision without additional evidence.

##
8. Multi-device wake arbitration Status: HISTORICAL DESIGN /
IMPLEMENTATION NOT ESTABLISHED A future mechanism was discussed for
situations where multiple devices hear the same wake word. Conceptually:
multiple clients hear wake \| v send WakeEvent \| v server arbitration
\| +-\> winner continues \| +-\> other clients CANCEL LISTENING

Possible arbitration evidence discussed included: - wake confidence; -
SNR/audio level; - approximate distance; - device priority; - device
state; - user interaction/context. This MUST NOT currently be documented
as implemented behavior. Exact final arbitration policy remains
unresolved.

## 9. Multi-user / multi-device / multi-home 9.1 Multi-user
is fundamental Status: ACCEPTED DESIGN The system must not be structured
around one hard-coded user. Conceptually: User +-- Devices +-- Sessions
+-- Preferences +-- Provider accounts +-- Permissions +-- Home
memberships +-- Assistant context

9.2 One user may own/use multiple devices Status: ACCEPTED DESIGN
Authorization is tied to authenticated account/device/session
relationships rather than physical voice identity alone. 9.3 Home
membership is per-home Status: ACCEPTED DESIGN The same user may have
different rights in different homes. Conceptually: Home A Stan -\> OWNER
Peter -\> MEMBER

Home B Stan -\> MEMBER ...

Global user identity does not imply identical permissions across every
home. 9.4 Explicit home overrides inferred/default home Status: ACCEPTED
DESIGN Home resolution precedence recovered so far includes: explicitly
specified home \> inferred/default home

Context/location may choose a default home, but it must not override an
explicitly named home.

## 10. Authorization and security policy 10.1
Effective permissions are contextual Status: ACCEPTED DESIGN Historical
design reached a model conceptually equivalent to: Effective permission
= User permissions INTERSECT Device restrictions INTERSECT Home
permissions INTERSECT Voice policy

A role such as OWNER/ADMIN does not automatically make every capability
voice-accessible. 10.2 Security-critical actions Status: ACCEPTED DESIGN
A later, stricter security decision superseded the weaker idea that all
sensitive voice actions could simply require confirmation. For selected
security-critical capabilities, the target policy is: VOICE_ACCESS =
NEVER

Examples discussed include security-sensitive actions such as locks.
Such capabilities should remain available through appropriately
authenticated non-voice mechanisms such as Home Assistant/app/physical
control, according to their own security policy. This is stronger than:
voice action -\> ask for confirmation

and future reconstruction must preserve the later stricter decision.

##
11. Home Assistant architecture 11.1 Home Assistant remains hardware
authority Status: ACCEPTED DESIGN Smart Voice Home should not
independently reinvent low-level smart-home device control where Home
Assistant already owns that responsibility. Conceptual path: User
command -\> Smart Voice Home -\> Home Assistant -\> actual entity/device

Example: Turn off bedroom lights -\> Assistant -\> Home Assistant -\>
light.bedroom

11.2 Home Assistant Conversation API Status: ACCEPTED DESIGN /
IMPLEMENTATION NOT YET ESTABLISHED A principal integration direction is:
Our STT -\> Assistant Core -\> Home Assistant Conversation API -\> Home
Assistant

The exact production adapter/API implementation remains to be audited.
11.3 Home Assistant custom sentences / aliases Status: HISTORICAL DESIGN
DIRECTION Home Assistant custom sentences, aliases and automations were
considered useful so the Android CommandParser.kt would not become a
giant catalog of smart-home grammar. The old Android parser is therefore
historical implementation/evidence, not necessarily the target central
smart-home parser. 11.4 Wyoming integration Status: ACCEPTED FUTURE
ARCHITECTURAL DIRECTION / NOT CURRENT IMPLEMENTATION A second direction
was discussed: HA Voice Satellite -\> Home Assistant Assist -\> our
STT/TTS service

using a Wyoming adapter. The intended principle is to avoid maintaining
a completely separate heavy speech stack only for Home Assistant.
Conceptually the same speech services could expose multiple adapters:
Speech Engine +-- Our REST/WebSocket API +-- Wyoming Adapter

Current implementation status still requires full repository
verification.

## 12. Media architecture 12.1 Assistant Core must not
contain Spotify-specific logic Status: ACCEPTED DESIGN Media
functionality was generalized conceptually around something like:
PlayMedia( query, mediaType, provider, target )

Provider-specific behavior belongs behind adapters/services. Potential
providers discussed include: - Spotify; - YouTube; - future
Plex/Jellyfin/etc. 12.2 Provider capabilities Status: HISTORICAL DESIGN
Providers may expose capabilities such as: search play pause next seek

Exact interface is not yet confirmed as current code. 12.3 Provider
account and playback target are separate Status: ACCEPTED DESIGN A
critical architectural distinction is: service/provider account !=
playback target

Example: Spotify account = Stan Playback target = LivingRoomTV

Personal context may determine which provider account is used.
Origin/explicit target determines where playback occurs. 12.4 Default
playback target Status: ACCEPTED DESIGN DIRECTION Where no explicit
target is provided, origin device was established as a natural default
candidate: target = origin device

Context-specific exceptions may still exist and require later
implementation design.

## 13. Credentials and secrets 13.1 Server
integration credentials stay server-side Status: ACCEPTED DESIGN Android
should authenticate to our platform. It should not receive server
integration secrets unnecessarily. Examples of credentials that should
remain server-side include Home Assistant/provider secrets where the
server owns the integration. 13.2 Secrets must not be committed Status:
ACCEPTED DESIGN Sensitive material such as: client_secret HA_TOKEN
JWT_SECRET

must not be stored in Git. Repository/configuration handling will be
audited separately.

## 14. Remote access 14.1 Remote use is a
first-class requirement Status: ACCEPTED DESIGN The Assistant should
eventually remain usable outside the home network. This includes access
over mobile Internet. 14.2 Do not expose internal service ports directly
Status: ACCEPTED DESIGN Remote access must not mean directly exposing
arbitrary internal services such as: FastAPI development port Home
Assistant port Whisper service database

to the Internet. Target conceptual ingress: HTTPS/WSS -\> gateway -\>
rate limiting -\> authentication -\> device/session validation -\>
authorization -\> Assistant API

Exact production gateway/VPN/reverse-proxy technology remains open
unless separately confirmed.

## 15. Privacy 15.1 Raw audio retention
Status: ACCEPTED DESIGN Default desired behavior: audio -\>
processing/STT -\> delete raw recording

Raw recordings should only be retained when diagnostic recording is
explicitly enabled. 15.2 Wake processing should be local Status:
ACCEPTED DESIGN Continuous room audio should not normally be streamed to
the server merely for wake detection. Wake-word detection is intended to
run locally on the client/endpoint. 15.3 Online services are not silent
fallback Status: ACCEPTED DESIGN Cloud speech/search/AI must not
automatically receive user data because a local component failed.
Explicit intent/consent is required according to the eventual policy
implementation.

## 16. Assistant ON/OFF semantics Status: ACCEPTED
DESIGN Historical discussion distinguishes at least: Assistant ON
Mic/Wake paused Assistant OFF

Assistant OFF is intended to mean a real shutdown of background
assistant behavior, conceptually including: wake detector OFF microphone
OFF background voice processing OFF server heartbeat/assistant
communication OFF

The manual microphone interaction should remain available according to
the eventual UI behavior. Exact implementation still requires future
Android work.

## 17. STT --- current implemented route 17.1 Current
high-level route Status: IMPLEMENTED Current server STT architecture is:
WAV -\> BG/EN CTC evidence -\> LanguageResolver -\> SttRouter -\> final
transcription

Current route policies: BG -\> BuzzASR -\> forced Bulgarian

EN -\> Whisper -\> forced English

MIXED -\> Whisper -\> language AUTO / None

AUTO must be resolved before SttRouter. 17.2 Current thresholds Status:
IMPLEMENTED / CALIBRATION-DERIVED / NOT INDEPENDENTLY VALIDATED Current
LanguageResolver thresholds: entropy delta \<= 0.003 -\> BG entropy
delta \>= 0.043 -\> EN between -\> MIXED

These thresholds came from calibration evidence. They must NOT be
described as independently validated production thresholds. No threshold
changes are authorized by this checkpoint.

## 18. CTC historical role
is broader than current routing This is one of the most important
findings of the historical audit. 18.1 CTC as pre-STT language-routing
evidence Status: IMPLEMENTED DIRECTION Current code uses paired BG/EN
CTC evidence before final transcription to select the language route.
Conceptually: CTC evidence -\> LanguageResolver -\> BG / EN / MIXED -\>
STT model

18.2 CTC as post-STT acoustic evidence Status: HISTORICALLY RECOVERED
DESIGN / NOT CURRENTLY IMPLEMENTED The historical design also proposed
retaining CTC acoustic evidence AFTER final STT so that a future
Intent/Entity Resolver could compare competing evidence. Example
recovered from historical reasoning: Buzz hypothesis + CTC acoustic
evidence + grammar/context/entities -\> semantic decision

Important example: true command: Спри музиката Buzz: Спи музиката CTC:
спри музихта

Here CTC preserved the critical intent verb while Buzz did not.
Therefore CTC was historically considered useful not only for language
classification but also as supplementary acoustic evidence. 18.3 Current
SttService preserves evidence Status: IMPLEMENTED API PREPARATION
Current SttService.analyze_language() returns both: LanguageEvidence
LanguageResolution

The code/docstring anticipates possible future higher-level use of
evidence. However current transcribe_file() does not implement a
semantic post-STT resolver. Therefore: evidence preservation =
implemented semantic evidence fusion = not implemented

## 19. CTC confidence lesson

Status: EXECUTED / VERIFIED HISTORICAL FINDING Historical experiments
found that: mean(max softmax per CTC frame)

cannot be treated as semantic confidence. A poor decoded transcript
could still show extremely high mean frame confidence because
blank/acoustic frame predictions may be individually confident. This
metric MUST NOT be reintroduced as semantic confidence without new
justification.

## 20. CTC + language model / beam decoding Status:
HISTORICAL PROPOSAL / EXECUTION STILL UNDER AUDIT Historical discussion
identified a possible experiment: same CTC acoustic model +-- greedy
decoding +-- CTC + LM beam decoding

and a richer future comparison: Raw CTC hypothesis + CTC+LM hypothesis +
Buzz hypothesis -\> Intent/Entity Resolver

The audit has NOT YET established that the CTC+LM/pyctcdecode experiment
was actually executed. Do not document it as executed until the
remainder of ChatLOG and repository scripts/results have been checked.
## 21. Temporal CTC language analysis Status: HISTORICALLY INVESTIGATED
/ FULL RECONSTRUCTION STILL IN PROGRESS Historical evidence shows
investigation of temporal BG/EN CTC behavior rather than only whole-file
classification. Recovered mechanisms include: - temporal BG/EN
evidence; - speech-region analysis; - smoothing; - minimum-duration
filtering; - speech-only masking; - handling false English evidence
during silence; - local baseline concepts; - language-region analysis. A
recovered conceptual direction is: audio -\> speech regions -\> temporal
BG/EN CTC evidence -\> smoothing/filtering -\> presumed language spans
-\> primary STT candidates -\> command/entity evaluation

The exact final historical mechanism is NOT yet fully reconstructed.
This is a priority continuation item.

## 22. MIXED speech 22.1 MIXED is
an uncertainty zone Status: CURRENT INTERPRETATION A MIXED route does
not automatically mean that the audio is perfectly balanced bilingual
speech. It represents an uncertainty region in current language
evidence. Likewise, a mixed phrase routing BG is not automatically a
routing error. 22.2 Historical MIXED strategy was richer than current
route Status: HISTORICAL DESIGN / NOT CURRENT IMPLEMENTATION Historical
discussion explicitly noted that: MIXED != necessarily Whisper AUTO

For Bulgarian command grammar containing foreign names/entities,
historical proposals included: Buzz + Whisper forced BG

as candidate hypotheses, with a selective English pass for problematic
entity regions. This is materially different from the current simple:
MIXED -\> Whisper AUTO

No route change is authorized yet. 22.3 Current MIXED comparisons
Status: EXECUTED / VERIFIED ON CURRENT PILOT On the current 8 MIXED
pilot WAVs: current route: 45.00% WER direct Whisper AUTO: 43.33% forced
BG: 43.33% forced EN: 60.00% multilingual AUTO: 43.33%

Forced BG and multilingual AUTO produced the same text as AUTO for all
eight examples in that experiment. The set is too small for a production
conclusion. Critically, one result inverted intended music action
semantics. Therefore lower aggregate WER is not sufficient to select a
production route.

## 23. Related-language fallback Status: IMPLEMENTED
CODE PATH / CURRENT USE REQUIRES CAREFUL INTERPRETATION Historical
discussion explicitly considered Whisper confusing Bulgarian with
related languages. Current LanguageResolver contains a Bulgarian-family
fallback set including languages such as: ru uk be mk sr hr bs sl cs sk
pl

The historical intent was approximately: if evidence says Bulgarian, do
not let an incidental related-language detection redirect the command
incorrectly.

However the current paired-CTC SttService path primarily uses
resolve_evidence(). Therefore the existence of
resolve_detected_language() must NOT be confused with proof that
related-language fallback is active in the current production-like
paired-CTC route. All call sites still need full audit.

## 24. Future
Intent/Entity Resolver Status: HISTORICAL DESIGN / NOT IMPLEMENTED A
richer semantic layer was repeatedly discussed. Possible evidence inputs
include: STT hypotheses CTC evidence command grammar known Home
Assistant entities media candidates current context user context device
state

Example reasoning: Buzz -\> "спи музиката" CTC -\> evidence for
"спри..." grammar -\> STOP MUSIC is valid context -\> music currently
playing

The future resolver could prefer the semantically coherent action or ask
for clarification. This is more principled than fuzzy matching a single
transcript. However the audit has not yet established one final
mandatory accepted algorithm. No IntentEntityResolver equivalent is
currently established as production implementation.

## 25. Selective
second passes / cascade Status: HISTORICAL PROPOSAL / ACCEPTANCE AND
FINAL FORM STILL UNDER AUDIT Historical strategies included avoiding
multiple expensive STT passes on every command. Conceptually: primary
STT -\> result plausible? \| +-- yes -\> continue \| +-- suspicious -\>
additional evidence / second STT / selective language pass

Signals discussed included: - grammar validity; - entities; - acoustic
evidence; - profile/context; - suspicious semantic mismatch. Exact final
policy remains unresolved.

## 26. SttCandidate Status: DISCUSSED /
DEFERRED A formal candidate type was discussed for representing multiple
STT hypotheses. It was deliberately not introduced prematurely into the
current SttService. This should be recorded as deferred design, not
missing implementation.

## 27. STT validation evidence 27.1 Current
24-file pilot Status: EXECUTED The current local pilot contains: 24 / 24
successful processings

Expanded diagnostics report corpus WER: 55 / 173 = 31.79%

This is the same pilot corpus, not an independent validation set. 27.2
Semantic validation remains incomplete Status: UNRESOLVED / OPEN Raw WER
does not adequately measure command safety. Known problematic categories
include: - lost target; - damaged stop/pause semantics; - damaged
English names/entities; - transliteration; - time/value loss; - possible
action inversion. A full semantic checklist should evaluate at least:
action negation value target names/entities

This remains unfinished.

## 28. AuroraCapture 28.1 Functional capture
evidence Status: IMPLEMENTED + EXECUTED DIAGNOSTIC Current AuroraCapture
includes: - 16 kHz capture; - WebRTC VAD; - pre-roll; - wake checking; -
phrase start/end detection; - maximum/minimum phrase controls; -
CapturedPhrase delivery. Historical live microphone diagnostics
demonstrated functional capture in limited cases. 28.2 Important
limitation Status: NOT VERIFIED END-TO-END The following is NOT yet
proven as a complete same-process production path: AuroraCapture -\>
SttService -\> resource-managed transcription -\> semantic intent -\>
real action

Existing separate-process WAV diagnostics must not be described as
equivalent to this full live path. No real actions should be executed
during initial integration diagnostics.

## 29. Resource Manager 29.1
Resource Manager is a high-level policy component Status: ACCEPTED
DESIGN / NOT FULLY IMPLEMENTED Historical Resource Manager/Scheduler
design monitors or may monitor: CPU utilization RAM availability GPU
utilization VRAM used/free GPU temperature foreground process active
Assistant requests

and uses system load to influence assistant behavior. 29.2 Resource
modes Status: HISTORICAL DESIGN / EXACT FINAL ENUM STILL REQUIRES
RECONCILIATION Modes discussed across project history include concepts
such as: IDLE NORMAL BUSY GAMING CRITICAL

and manual policy concepts such as: AUTO PERFORMANCE GAMING ECO

Later STT model residency discussions also used concepts such as:
PERFORMANCE NORMAL GAMING CRITICAL

These sets must not be merged blindly. The final Resource Manager state
model remains to be reconstructed. 29.3 Resource policy behavior Status:
ACCEPTED DESIGN DIRECTION Conceptually: NORMAL -\> full server
processing allowed

BUSY -\> lighter processing

GAMING -\> yield GPU resources / prefer lighter or client processing

CRITICAL -\> strong fallback / deny or defer expensive work

Exact policy thresholds remain open.

## 30. ModelManager is NOT the
full Resource Manager Status: IMPORTANT CURRENT ARCHITECTURAL
DISTINCTION Current ModelManager is a lower-level lifecycle/ownership
component. It does NOT currently implement: - gaming detection; - GPU
scheduling; - VRAM budget policy; - LRU; - automatic eviction; - request
priority; - automatic client fallback; - CPU/GPU policy selection. Those
belong to the future Resource Manager/Scheduler layer.

## 31.
ModelHandle / lease semantics Status: IMPLEMENTED + EXECUTED TESTS
ModelHandle provides temporary model leases. Conceptually: acquire -\>
active_leases + 1

use model

release -\> active_leases - 1

The handle does not decide residency policy. Important verified
properties include: - context-manager release; - double-release
safety; - release after exception; - resource access rejected after
release. Historical test output confirms these checks passed.

## 32.
ModelManager behavior Status: IMPLEMENTED + EXECUTED TESTS The initial
ModelManager was deliberately limited to responsibilities such as:
register acquire unload unload_all is_loaded active_leases

Features deliberately NOT included in the first version: - LRU; - VRAM
budgeting; - Gaming Mode; - automatic eviction; - inference
scheduling; - full Resource Manager policy. This was intentional scope
control, not an accidental omission. 32.1 Release is not unload Status:
ACCEPTED + IMPLEMENTED BEHAVIOR A lease reaching zero does NOT
automatically unload the model. Conceptually: release lease != unload
model

This allows warm/resident reuse and avoids paying model-load latency for
every voice command. Unload remains explicit until a higher-level policy
manager decides otherwise.

## 33. ModelManager tests Status: EXECUTED /
VERIFIED Historical execution confirms at least nine ModelManager tests
passed, including: LAZY LOADING RESIDENT REUSE MULTIPLE LEASES ACTIVE
LEASE UNLOAD REJECTION EXPLICIT UNLOAD RELOAD AFTER UNLOAD BACKEND
MISMATCH RESOURCE RELEASED BEFORE CLEANUP HANDLE DROPS REFERENCE

Concurrency behavior was also tested historically. Exact current test
files will be independently reviewed during the repository audit.

##
34. Backend-specific model lifecycle 34.1 PyTorch Status: IMPLEMENTED A
PyTorch-specific lifecycle exists because releasing Python references
alone does not necessarily release cached CUDA allocator memory. Cleanup
historically involved: gc.collect() torch.cuda.empty_cache()

as appropriate after ownership references are removed. 34.2 CTranslate2
Status: IMPLEMENTED CTranslate2/faster-whisper uses a separate lifecycle
path. It intentionally does not rely on PyTorch CUDA cache cleanup. This
backend separation reflects observed runtime differences rather than
merely stylistic abstraction.

## 35. Ownership correctness Status:
IMPLEMENTED + TESTED An important Python ownership rule was explicitly
addressed. Lifecycle cleanup cannot destroy an object while the manager
still owns a strong reference. The intended sequence became
conceptually: manager owns resource -\> manager removes owning reference
-\> backend cleanup -\> temporary reference disappears

Concurrency handling was added so that a replacement instance does not
overlap incorrectly with cleanup of the old instance.

## 36. Resource
measurements Status: EXECUTED HISTORICAL EVIDENCE / FULL RESULT
INVENTORY PENDING Historical diagnostics include real measurements of: -
model load time; - inference time; - VRAM before/after; - unload
behavior; - sequential model use; - warm/resident reuse. One recovered
Buzz lifecycle result showed approximately 3.2 GB of VRAM released after
unload in that specific diagnostic. This must be treated as evidence
from that test, not a universal guarantee. All corresponding diagnostic
scripts and retained outputs still need to be cross-checked.

## 37. TTS
37.1 No final production TTS engine established yet Status: UNRESOLVED
Piper and other TTS approaches were researched. The current forensic
evidence does NOT justify writing: Production TTS = Piper

as a final decision. 37.2 Bulgarian + English voice identity Status:
OPEN DESIGN QUESTION An important unresolved TTS requirement is whether
the Assistant should use: one multilingual voice/model

or: BG model + EN model

while preserving a consistent Assistant voice identity. A future
benchmark is required. 37.3 Android TTS fallback Status: HISTORICAL
DESIGN DIRECTION Local Android TTS fallback when the server is
unavailable was discussed. Implementation status remains unconfirmed.
## 38. Local conversational AI 38.1 Local AI comes after core voice
functionality Status: ACCEPTED PROJECT DIRECTION The
conversational/local-AI layer is not intended to block completion of the
core voice assistant. 38.2 GPU contention is an architectural concern
Status: ACCEPTED CONSTRAINT Local conversational AI must not casually
consume the same limited RTX 3070 VRAM required by speech components.
Later historical discussion favored investigating local AI using system
RAM + CPU to avoid competing with speech models for VRAM. However final
placement remains subject to benchmarking. Therefore current status
should be interpreted as: preferred architectural direction: avoid
speech-GPU contention

final CPU/RAM/GPU placement: requires benchmark

This point must be reconciled against current Decision Register D024
during the final audit.

## 39. Server API target Status: ACCEPTED
HISTORICAL DESIGN / PARTIALLY IMPLEMENTED Historical target API concepts
included endpoints similar to: POST /api/v1/stt POST /api/v1/command
POST /api/v1/tts

GET /api/v1/server/status GET /api/v1/server/capabilities

WS /api/v1/audio/stream

The exact production API contract was not frozen. 39.1 Current server
reality Status: IMPLEMENTED CURRENT CODE Current app/main.py is only a
skeleton exposing: /health /status

There is currently no established production: - /stt; - /command; -
/tts; - streaming audio WebSocket. Therefore historical API diagrams
must not be described as implemented endpoints.

## 40. Deployment
direction Status: ACCEPTED DESIGN DIRECTION The current Windows PC is a
development/shared host. Architecture should remain portable so future
migration to a dedicated Linux host does not require rewriting Assistant
Core. OS-specific behavior should be isolated behind platform-specific
adapters where necessary. Containers/WSL/other deployment mechanisms are
tools/options rather than fundamental architecture dependencies unless
later evidence says otherwise.

## 41. Important distinctions that MUST
survive reconstruction The following pairs/concepts must not be
conflated: wake identity != authentication

personal context != authorization context

origin device != execution target

provider account != playback target

wake ASR transcript != final command STT

CTC acoustic evidence != semantic confidence

CTC language routing != future semantic CTC use

SttRouter != Intent/Entity Resolver

ModelManager != Resource Manager

lease release != model unload

calibration != independent validation

separate-process WAV test != live same-process pipeline

historical proposal != accepted decision

accepted design != implemented feature

implemented feature != validated production feature

low WER != semantically safe command

These distinctions are central to avoiding another incorrect
reconstruction.

## 42. Known documentation inconsistencies / stale
areas The audit has already identified areas requiring reconciliation.
42.1 Decision Register date DECISION_REGISTER.md appears stale relative
to later 2026-09-25 work. Do not update it until the full forensic audit
establishes the final decision set. 42.2 OPEN_QUESTIONS metadata The
file contains later additions while its header date appears older. Some
MIXED questions may also be stale because later forced-language
comparisons were subsequently executed. 42.3 PromptingWhisper
contradiction One current document says PromptingWhisper was not tested.
Historical audit material indicates an older prompting experiment may
have produced a negative result. Status: UNRESOLVED Primary ChatLOG and
repository scripts/results must determine exactly what was tested, with
which model/settings, and what result occurred. 42.4 Local AI placement
Current Decision Register says final CPU/RAM/GPU placement is
benchmark-driven. Later historical conversation contains a stronger
preference/decision toward CPU + RAM to avoid GPU contention. Status:
UNRESOLVED / REQUIRES CHRONOLOGICAL RECONCILIATION Do not overwrite
either interpretation until the later history is fully read.

## 43.
High-priority unresolved historical questions The continuing forensic
audit must answer at least: 1. Was CTC + LM / pyctcdecode actually
executed, or only proposed? 2. What exactly happened in the historical
Whisper prompting experiment? 3. What was the complete temporal CTC
mechanism? 4. Which smoothing, speech masking, minimum-duration and
local-baseline mechanisms were actually tested? 5. Which
grammar/context/semantic-resolver mechanisms were explicitly accepted by
the user versus only proposed? 6. What was the complete historical MIXED
strategy and how did it evolve? 7. What exact related-language fallback
path was intended and which code paths currently invoke it? 8. What old
Android CommandParser, Spotify, media and playback mechanisms were
actually implemented and tested? 9. What exact wake arbitration policy
was accepted versus proposed? 10. What is the final relationship between
general and personal wake words? 11. Which TTS engines were merely
researched, and was any TTS engine actually benchmarked? 12. What is the
final chronological decision concerning CPU/RAM/GPU placement of local
conversational AI? 13. What Resource Manager state/mode model should be
considered current? 14. Which resource measurements have retained raw
execution evidence? 15. What server/API/admin/database components
existed historically versus only in architecture diagrams? 16. Which
Home Assistant/Wyoming components were actually implemented? 17. Which
security rules are final and which were earlier superseded proposals?
18. Which historical mechanisms are missing entirely from current
project-memory documents?

## 44. Repository audit still required The
checkpoint does NOT replace the repository audit. The continuing audit
must inspect all tracked files, including old benchmark and diagnostic
scripts. Priority groups include: Project memory
README_PROJECT_MEMORY.md PROJECT_MASTER.md ARCHITECTURE.md
PROJECT_STATE.md DECISION_REGISTER.md OPEN_QUESTIONS.md
PROJECT_HISTORY.md EVIDENCE_MAP.md AUDIO_DATASETS.md BACKUP_INDEX.md

Historical STT reconstruction STT_HISTORY_CHECKPOINT.md
STT_HISTORY_MECHANISMS_AUDIT.md STT_SCHEMES_AUDIT.md
HISTORY_SCHEMES_INDEX.md Smart_voice_home_FULL_LOG_RECONSTRUCTION.md

Validation evidence STT_VALIDATION_PLAN.md STT_VALIDATION_PILOT_01*
MIXED_WHISPER*

including JSONL/stdout/stderr where available. Current implementation
Full review required for: BuzzASR Whisper CTC evidence LanguageResolver
SttRouter SttService AuroraCapture ModelManager ModelHandle
ModelLifecycle system monitoring CUDA helpers FastAPI composition

Historical benchmark/diagnostic scripts All benchmark and diagnostic
scripts must be inspected. Their existence alone is NOT evidence that
they were executed. Where possible, scripts must be correlated with
retained stdout/results and historical ChatLOG execution.

## 45.
Backup/reproducibility boundary Tracked Git files are not the complete
operational project. Important local assets may exist outside Git,
especially: data/ models/

A clean Git status does not prove those assets are backed up. Model
revisions, datasets, dependency state and local paths must be handled
separately in the reproducibility audit.

## 46. Audit methodology going
forward For each recovered mechanism or project decision, reconstruct:
IDEA -\> USER ACCEPTANCE / REJECTION -\> IMPLEMENTATION -\> TEST -\>
RESULT -\> LATER CHANGE / SUPERSESSION -\> CURRENT STATUS

Every important claim should ultimately be classifiable as one of:
IMPLEMENTED EXECUTED / VERIFIED ACCEPTED DESIGN HISTORICAL PROPOSAL
SUPERSEDED / REJECTED UNRESOLVED

No assistant-generated historical proposal should silently become a
project decision. No documentation statement should silently become
execution evidence. No old benchmark should silently become
representative of the current model/configuration.

## 47. Current audit
stopping point At the time this checkpoint was created, the deep audit
had already substantially covered: - Android STT evolution; - Android
fallback concept; - historical CommandParser safety lessons; -
client/server architecture; - multi-user foundation; - multi-device
concepts; - multi-home model; - identity vs authorization; - origin vs
target; - personal/general wake concepts; - wake arbitration proposal; -
security-critical voice policy; - Home Assistant architectural
boundary; - Conversation API direction; - Wyoming direction; - media
provider abstraction; - provider account vs playback target; -
credential boundary; - remote access/security boundary; - privacy/audio
retention; - Assistant ON/OFF semantics; - major STT history; - CTC
dual-role history; - temporal CTC direction; - semantic resolver
direction; - MIXED strategy history; - related-language fallback; -
current STT pilot evidence; - Resource Manager concept; - ModelManager
scope; - ModelHandle leases; - backend lifecycle; - ModelManager
tests/concurrency; - selected historical resource measurements; - TTS
research direction; - local conversational-AI placement question. The
audit is NOT complete.

## 48. Next audit continuation point Continue
with: 1. Server/API evolution 2. Web/Admin GUI 3.
persistence/database/user/device/home models 4.
authentication/session/device registration 5. complete Resource Manager
history 6. complete TTS history 7. complete local-AI history 8.
remaining Home Assistant history 9. Android/Spotify/media implementation
timeline 10. full temporal CTC reconstruction 11. CTC+LM execution
question 12. PromptingWhisper contradiction 13. every historical
benchmark/diagnostic script 14. all current project-memory documents 15.
all remaining tracked repository files 16. final cross-check: historical
source vs current code vs execution evidence vs current documentation

Only after those steps should the project memory be comprehensively
rewritten/reconciled.

## 49. Safety rule for continuation Until the
forensic reconstruction is sufficiently complete: - do not change STT
thresholds; - do not change STT model routing; - do not remove Buzz; -
do not introduce a new MIXED policy; - do not promote historical
proposals to current architecture; - do not implement Resource Manager
policy based only on partial history; - do not execute real assistant
actions during speech diagnostics; - do not rewrite major project-memory
documents from partial evidence; - do not commit or push without
explicit user approval.

## 50. Checkpoint conclusion The recovered
history shows that Smart Voice Home is not merely: microphone -\> STT
-\> command -\> Home Assistant

The intended platform is substantially broader: Client -\> Wake /
Capture -\> Identity + Device + Session -\> Secure Assistant API -\>
Speech processing -\> Context / Intent / Policy -\> Authorization -\>
Provider / Home integration -\> Execution target -\> Audit / response

with resource-aware local execution underneath and client-side fallback
where appropriate. The current repository implements only part of this
architecture. The purpose of the continuing forensic audit is to
determine exactly which parts are: historically intended, explicitly
accepted, implemented, actually tested, superseded, or still unresolved.

END OF INTERMEDIATE CHECKPOINT

------------------------------------------------------------------------

## 51. Forensic addendum --- server/API, identity, persistence, TTS, local AI and resources

**Status:** INTERMEDIATE / AUDIT STILL IN PROGRESS

This addendum records findings recovered after the original checkpoint
was created. It does not authorize implementation changes.

### 51.1 Server/API evolution

**ACCEPTED DESIGN**

The Assistant Server is intended to expose one platform-owned API in
front of replaceable backend components. Android, Web Admin and future
clients should not be coupled directly to a particular STT engine.

The historical target API included concepts equivalent to:

    /api/v1/stt
    /api/v1/command
    /api/v1/tts
    /api/v1/server/status
    /api/v1/server/capabilities
    WebSocket /api/v1/audio/stream

These are historical target endpoints/contracts, not proof of current
implementation.

**CURRENT IMPLEMENTATION**

The current `app/main.py` exposes only:

    /health
    /status

Therefore even the historical first server/STT phase is not complete: a
production `/stt` API is still absent.

The history also shows deliberate implementation phasing.
Authentication, persistent multi-user storage, Home Assistant, TTS, Web
Admin and remote access were intentionally deferred until the basic
server/STT path was proven. Their absence from current code must not
automatically be classified as forgotten architecture.

### 51.2 Authentication, sessions and device registration

**ACCEPTED DESIGN**

The historical conceptual chain is:

    User account
      -> Login
      -> authenticated session/access
      -> device registration
      -> Assistant API

Devices are intended to have their own registered identity. Device
identity is part of the security model, not merely UI metadata.

A registered device can conceptually be revoked. Device
credentials/secrets are sensitive material and must not be exposed in
plaintext through Web Admin.

**UNRESOLVED**

The historical audit has not established a final concrete protocol for:

-   JWT versus another token format;
-   exact access-token lifetime;
-   refresh-token rotation;
-   device enrollment/challenge flow;
-   exact device-secret/key format;
-   final token claims/schema.

No such details should be invented or promoted to accepted architecture
without later evidence.

**CURRENT IMPLEMENTATION**

No production authentication/device-registration API has been
established in the current server snapshot.

### 51.3 Personal devices versus shared devices

**ACCEPTED DESIGN**

A personal device can supply authorization identity through its
authenticated account/session.

A shared home endpoint is conceptually different. Low-risk shared-home
actions may be allowed by the shared endpoint/home policy without
proving the physical speaker's identity.

Personal operations such as "my Spotify" require personal
context/account selection.

Therefore:

    personal device -> account-bound context

and

    shared device -> home/shared-endpoint context

must not be collapsed into a simplistic assumption that every device has
exactly one permanent `user_id`.

Speaker recognition, if ever added, is only a possible future confidence
signal. It is not an authentication authority.

Personal wake words may select personal context, but they do not elevate
permissions.

### 51.4 Identity/context separation

The historical architecture distinguishes at least:

-   PERSONAL CONTEXT --- whose preferences/services/context are
    intended;
-   AUTHORIZATION CONTEXT --- which authenticated account/device/home
    permissions govern the action;
-   ORIGIN --- which device heard/originated the request;
-   TARGET --- where the requested action/playback should occur.

These concepts must remain separate.

Audit records must represent the source of identity/context honestly. A
personal wake word must not be logged as proof of physical-speaker
identity.

### 51.5 Web Admin

**ACCEPTED DESIGN**

Web Admin is a separate administrative interface for the platform and is
primarily desktop-oriented, while remaining responsive.

Its historical scope includes management/visibility for:

-   users;
-   devices;
-   homes;
-   integrations;
-   permissions;
-   preferences;
-   wake words;
-   audit events;
-   server CPU/RAM/GPU/VRAM/STT state;
-   connected clients;
-   network/access administration.

Web Admin should use the same authenticated/authorized Assistant API
rather than bypassing policy by directly manipulating the database.

Administrative authority does not imply permission to reveal stored
secrets.

**HISTORICAL PROPOSAL --- NOT SELECTED**

`React` / `TypeScript` appeared as proposed implementation technology
for Web Admin. It has not been established as the selected frontend
stack.

### 51.6 Network & Access administration

A historical Web Admin proposal includes a `Network & Access` area
covering server interfaces/IP/gateway/DNS/hostname, registered devices,
online/last-seen information, revoke/block operations, access
restrictions, rate limits, TLS/VPN/tunnel status and connectivity
diagnostics.

Router/DHCP reservation management is only feasible when the router
exposes a suitable supported integration/API. The platform must not
pretend to control infrastructure it cannot actually manage.

Network changes should eventually have validation, auditability and safe
rollback because incorrect IP/firewall/access changes can lock an
administrator out.

This area remains design/proposal work, not current implementation.

### 51.7 Persistence/database status

**ACCEPTED DESIGN**

The platform needs a persistent data layer for the permanent
multi-user/multi-device/multi-home version.

The historical domain model contains concepts such as:

-   User;
-   Device;
-   Home;
-   HomeMembership;
-   ServiceConnection;
-   UserPreferences / UserProfile;
-   Session;
-   Permission;
-   AuditEvent.

These are domain concepts. They are not a finalized physical database
schema.

**HISTORICAL PROPOSAL --- NOT SELECTED**

PostgreSQL was proposed as a suitable future database. The user has
explicitly clarified during the current forensic audit that the database
technology was only proposed and was not selected.

Therefore:

    PostgreSQL != accepted technology decision

No project-memory document should describe PostgreSQL as final/current
unless a later explicit decision is found.

**CURRENT IMPLEMENTATION**

No permanent multi-user database implementation has been established in
the audited current server snapshot.

### 51.8 UserProfile and language preferences

Historical design separates several language-related concepts rather
than treating them as one immutable user language:

-   primary/profile language;
-   STT language or allowed-language preference;
-   response language;
-   search/preferred content language;
-   per-request language override;
-   multilingual-query allowance.

This evolved alongside the later acoustic language-routing work.

The old profile-level `stt_language` concept must not automatically be
treated as a hard route for the current CTC `LanguageResolver`. The
exact integration between user-language preferences and acoustic routing
remains to be designed/verified.

### 51.9 Permission Engine, Context Engine and Preference Engine

The history distinguishes:

    Permission Engine -> Can this action be performed?
    Context Engine    -> What is happening / who / where / target?
    Preference Engine -> How should the assistant behave for this user?

A learned preference is not automatically an executable routine.

A historical example explicitly distinguishes:

-   Preference --- influences response/suggestion;
-   Routine --- may perform an action;
-   Permission --- determines whether that action is allowed.

Observed user behavior must not silently become an automation.

### 51.10 AuditEvents and superseded security examples

Audit events are intended to capture more than transcript text.
Conceptually relevant fields include command/action, personal context,
origin device, authenticated account/session, home, authorization
result/reason and executor/target.

An older historical example treated a lock/unlock action as denied
because confirmation was required.

That example is **SUPERSEDED** by the later stricter accepted security
rule:

    security-critical voice capability = NEVER

Locks and equivalent security-critical capabilities are not
voice-controlled even for an administrator. They remain accessible only
through the appropriate non-voice Home Assistant interface/policy.

### 51.11 TTS status

**USER-CONFIRMED DURING CURRENT AUDIT**

No TTS benchmark was performed.

No TTS engine/model has been selected.

Historical work only researched/design-discussed candidates and
architecture.

The desired architectural property is that `voice identity` and
`language` are separate concepts: where technically feasible, Bulgarian
and English output should preserve a consistent Assistant voice
identity.

Historical TTS research included candidates such as Piper,
Sherpa-ONNX/Kokoro/VITS-related possibilities and Android fallback
concepts. These are research/proposals, not selected production
technologies.

A future benchmark was planned around:

-   Bulgarian naturalness/pronunciation;
-   English naturalness/pronunciation;
-   voice-identity consistency;
-   latency;
-   CPU/GPU/resource usage;
-   long text;
-   names/titles;
-   mixed BG/EN;
-   streaming behavior.

Current classification:

    TTS engine/model       -> UNRESOLVED
    TTS benchmark          -> NOT EXECUTED
    TTS production code    -> NOT ESTABLISHED
    concrete TTS selection -> NONE

### 51.12 Local conversational AI

**ACCEPTED DESIGN**

After the core voice assistant is completed, the project is intended to
gain a local/offline conversational AI component.

The later user-confirmed resource direction is:

    Local conversational AI -> CPU + system RAM
    Speech models            -> use their separately validated CPU/GPU placement

The intent is to avoid competing with the speech pipeline for VRAM.

**NOT YET BENCHMARKED**

No final local conversational model/runtime has been selected and no
accepted CPU performance benchmark has been established.

`Ollama`, `LM Studio` and related runtimes appeared as possible isolated
benchmark tools/technical options. They are not selected production
technologies.

Earlier CPU_ONLY/HYBRID/GPU mode discussions are historical
possibilities. The later explicit project direction favors CPU + RAM
without GPU for the local conversational AI.

### 51.13 Local AI security boundary

**ACCEPTED SECURITY REQUIREMENT**

Conversational AI is not the Command Engine and must not receive
unrestricted direct access to Home Assistant, devices, provider
credentials or private platform data.

The intended security direction is conceptually:

    conversational AI
      -> structured/controlled request
      -> Assistant Core
      -> authorization/policy
      -> integration/executor

Ordinary commands must not silently be sent to external AI.

External/cloud AI, if ever used, requires explicit user intent/consent.
Silent cloud fallback is not allowed.

Security-critical voice prohibitions remain in force even when AI is
involved.

### 51.14 Resource Manager --- historical policy model

The original `Resource Manager / Scheduler` proposal observes at least:

-   CPU utilization;
-   available RAM;
-   GPU utilization;
-   VRAM used/free;
-   GPU temperature;
-   foreground workload/process;
-   active Assistant requests.

Historical automatic runtime states were proposed as:

    IDLE
    NORMAL
    BUSY
    GAMING
    CRITICAL

A separate manual-policy/override proposal used:

    AUTO
    PERFORMANCE
    GAMING
    ECO

These are two different concepts and must not be merged into one
historical enum:

    observed runtime state
      +
    user-selected/manual policy
      ->
    effective resource policy

The exact future names and policy semantics remain unimplemented.

### 51.15 Resource-aware client/server fallback

The historical target routing includes:

    server unavailable
      -> client/local fallback

    server available + resources normal
      -> full server STT

    server available + resource-constrained/gaming
      -> reduced/lightweight server path or client fallback

A powered-off PC/server is intended to be a normal operational state,
not an exceptional failure.

This is target architecture. End-to-end Android/server resource-aware
fallback has not been verified in the current project state.

### 51.16 Resource Monitor --- implemented versus Resource Manager --- not implemented

**IMPLEMENTED / EXECUTED**

`app/resources/system_monitor.py` exists and historical execution
evidence confirms collection of real:

-   CPU utilization/core counts;
-   RAM total/used/available;
-   NVIDIA GPU presence/utilization;
-   VRAM used/free/total;
-   GPU temperature.

The `/status` endpoint was executed historically and returned real
machine telemetry.

**NOT IMPLEMENTED**

The following remain future Resource Manager policy:

-   automatic NORMAL/BUSY/GAMING/CRITICAL classification;
-   manual AUTO/PERFORMANCE/GAMING/ECO policy;
-   automatic workload scheduling;
-   automatic client fallback based on resource state;
-   general CPU/RAM/GPU/VRAM arbitration;
-   Local AI scheduling/throttling.

### 51.17 ModelManager is deliberately narrower than Resource Manager

The current `ModelManager` originated from the concrete
model-ownership/lifecycle problem, not from an attempt to implement the
whole Resource Manager.

Its deliberately limited responsibilities include:

-   lazy model creation;
-   single manager ownership;
-   acquire/release leases;
-   resident reuse;
-   explicit safe unload;
-   backend-specific lifecycle cleanup;
-   concurrency protection around unload/reload.

The first ModelManager design explicitly deferred:

-   LRU;
-   VRAM budgeting;
-   Gaming Mode;
-   automatic eviction;
-   scheduler/queue policy;
-   background preloading.

Those omissions are intentional scope boundaries, not evidence that the
historical Resource Manager requirement was forgotten.

### 51.18 `release != unload`

A `ModelHandle.release()` means that a caller/request no longer uses the
resource.

It does not mean that the model must be destroyed.

Resident reuse is intentional. A separate policy/explicit unload
decision determines when the model leaves memory.

This distinction is a core lifecycle invariant and must survive future
Resource Manager integration.

### 51.19 Backend-specific lifecycle --- executed evidence

Historical diagnostics established materially different cleanup
behavior.

For PyTorch-backed CTC/Buzz resources, releasing Python references alone
did not necessarily return cached CUDA memory to the driver; PyTorch
CUDA cache cleanup was required in the tested lifecycle.

For CTranslate2/Whisper, releasing the final owning `WhisperModel`
reference plus garbage collection returned most of the observed model
VRAM; a later `torch.cuda.empty_cache()` control did not materially
change that result.

Therefore separate lifecycle adapters are evidence-based architecture,
not speculative abstraction.

### 51.20 Historical GPU residency measurements

Historical diagnostics measured approximate resident deltas around:

    CTC BG+EN pair     ~1.31 GB
    BuzzASR            ~3.32 GB
    Whisper large-v3   ~3.91 GB

The old sum of all three on GPU was therefore above the practical budget
of an RTX 3070 8 GB before allowing for baseline/runtime/inference
workspace.

These are observed historical diagnostic values, not universal hardcoded
budgets.

Later validation composition moved CTC toward CPU/RAM while Buzz and
Whisper remained GPU-backed. Therefore older GPU-residency schemes
involving all three components are partially superseded by later
placement.

### 51.21 Correct Resource Manager / ModelManager layering

The recovered history now supports the following responsibility
boundary:

    ResourceMonitor
      -> observes real CPU/RAM/GPU/VRAM state

    ResourceManager / Scheduler
      -> future policy: decides what may run, when and where

    ModelManager
      -> safe model ownership, leases, residency and explicit unload

    ModelLifecycle
      -> backend-specific cleanup mechanism

    SttService
      -> speech orchestration; does not own global resource policy

This distinction should be preserved in the final project
reconstruction.

### 51.22 Current audit status after this addendum

The following areas are now materially better reconstructed than at the
original checkpoint:

-   server/API target versus current implementation;
-   authentication/device identity boundaries;
-   personal versus shared device context;
-   Web Admin role and security boundary;
-   persistence/domain-model status;
-   PostgreSQL non-selection;
-   React/TypeScript non-selection;
-   language/profile separation;
-   Preference versus Routine versus Permission;
-   AuditEvent security evolution;
-   TTS non-test/non-selection;
-   local conversational AI CPU/RAM direction;
-   Resource Manager state/mode history;
-   Resource Monitor versus Resource Manager;
-   ModelManager scope and lifecycle evidence.

The audit remains incomplete.

The next major historical branch to inspect is:

    Android -> CommandParser -> AndroidMediaController
      -> Spotify implementation/tests
      -> Web API / App Remote
      -> previous-track behavior
      -> open-vocabulary artist/title
      -> MediaService / Provider abstraction
      -> PlaybackTarget abstraction

After that, continue the remaining unresolved STT-history and full
repository cross-check work.

------------------------------------------------------------------------

## 52. Updated safety/decision guardrails

Until the full forensic reconstruction is complete:

-   PostgreSQL must not be recorded as the selected database.

-   React/TypeScript must not be recorded as the selected Web Admin
    framework.

-   No TTS engine/model must be recorded as selected or benchmarked.

-   Ollama/LM Studio must not be recorded as selected Local AI runtime.

-   ModelManager must not be described as the complete Resource Manager.

-   Historical Resource Manager state/mode names must not be treated as
    implemented enums.

-   Speaker recognition or personal wake word must not be treated as
    authentication.

-   Shared devices must not be forced into a simplistic
    one-device/one-user model without later design work.

-   Old lock/door confirmation examples must not override the later
    `VOICE_ACCESS = NEVER` security rule.

-   No STT route/threshold/model/resource-policy change is authorized by
    this addendum.

- No commit or push is authorized by this addendum.

## 53. Media / Spotify forensic reconstruction

### 53.1 Historical Android media proof of concept

The old Android branch contained a real media-control and Spotify proof
of concept. It must not be described as merely conceptual.

Historically verified behavior includes:

-   Android media volume control worked on the real device;
-   Pause/Resume/Next/Previous media actions reached the Android/Spotify
    media layer;
-   Spotify search/deep-link integration existed;
-   Spotify Developer configuration was actually performed;
-   Spotify authorization/search/playback code was developed;
-   the user explicitly verified a real end-to-end playback case in
    which the assistant redirected to Spotify and a Metallica song
    started.

This is historical implementation evidence. It is not evidence that the
old Android Spotify architecture is the current production architecture.

### 53.2 Main Android media bottleneck

The decisive failure was not basic Spotify playback. It was reliable
open-vocabulary speech recognition for arbitrary artist names and song
titles.

Examples in the historical tests include:

    Spoken:
      Play Metallica Enter Sandman

    Small Android Whisper result:
      Play Metallica in Jersey and Men

The user then tested several other artists/titles and reported that the
small local model failed to recognize them reliably and Spotify
therefore played unrelated content.

Forensic classification:

-   Spotify authorization/playback infrastructure: IMPLEMENTED +
    USER-VERIFIED HISTORICALLY
-   PlayMusic free-text command structure: IMPLEMENTED HISTORICALLY
-   reliable arbitrary artist/title recognition on the old Android
    model: FAILED / INSUFFICIENT
-   hardcoded artist/song catalog: EXPLICITLY REJECTED

This failure is one concrete causal driver for moving heavy STT to the
central local server.

### 53.3 Generic media-provider architecture

The later architecture deliberately separates Assistant Core from
provider-specific Spotify/YouTube logic.

Conceptual structure:

    PlayMedia
      -> MediaService
      -> MediaProvider
           -> SpotifyProvider
           -> YouTubeProvider
           -> future providers

The extensible provider architecture is an accepted design direction.
Exact class names, method signatures and physical persistence schema are
not final.

Capability-aware provider behavior was proposed, but the exact interface
must not be treated as an implemented production API.

### 53.4 Per-user service connections

The platform design requires provider accounts to belong to user
context, not to one global application account.

Conceptually:

    User
      -> ServiceConnection
           -> Spotify account
           -> YouTube account
           -> future provider account

This supports different household members using their own media
accounts.

The exact database representation is unresolved.

### 53.5 Provider, content owner, origin and playback target are separate

A central invariant recovered from the history is:

    provider != content account != origin device != playback target

Examples:

    Play Metallica on Spotify
      provider = Spotify
      target = origin/default target

    Play Metallica on the living room TV
      provider = resolved/default provider
      target = LivingRoomTV

    Play this video on YouTube on the bedroom TV
      provider = YouTube
      target = BedroomTV

Explicit target takes precedence over an inferred/default target.

When no stronger target context exists, origin device is the historical
default target.

Home Assistant may expose or execute some playback targets, but the
PlaybackTarget abstraction belongs to Smart Voice Home because a target
may also be an Android device, PC, speaker or another endpoint that is
not an HA entity.

### 53.6 YouTube and other future providers

YouTube support was explicitly requested as a future capability and the
provider architecture was intended to allow it.

Classification:

-   YouTube support: ACCEPTED FUTURE CAPABILITY
-   YouTube provider implementation: NOT ESTABLISHED / NOT VERIFIED
-   Plex, Jellyfin, YouTube Music examples: EXTENSIBILITY EXAMPLES, NOT
    ESTABLISHED REQUIREMENTS

### 53.7 Media preferences

User-specific default music/video providers and preferred playback
devices were discussed as preferences.

The general preference direction is accepted, but exact fields and
resolution precedence are not final.

A stronger invariant is:

    explicit command choice > default preference

------------------------------------------------------------------------

## 54. Wake word, identity and multi-device arbitration

### 54.1 Origin device

The device that receives the activation/command is the origin device.

Origin device does not prove which physical person spoke.

Origin, personal context, authenticated authorization identity and
target must remain separate concepts.

### 54.2 General and personal wake phrases

The design supports:

    GENERAL wake
      -> general/shared context

    PERSONAL wake
      -> mapped personal context

Users should be able to choose a personal wake phrase during account
setup/enrollment.

A personal wake phrase selects context. It is not a password and does
not grant authorization.

### 54.3 Authorization boundary

The historical security model evolved toward:

    authenticated account/device
      INTERSECT
    device permissions
      INTERSECT
    home permissions
      INTERSECT
    voice capability policy

Personal wake words and optional speaker recognition must not increase
privileges.

### 54.4 Shared endpoints

A shared endpoint must not be forced into a one-device/one-user model.

A shared tablet may execute allowed low-risk household actions under its
shared endpoint/home policy without proving the physical speaker.

A request requiring personal context, such as a personal media account,
requires a resolved personal context or explicit clarification.

### 54.5 Speaker recognition

Speaker recognition was deliberately not selected as authentication.

Classification:

-   speaker recognition as security authority: REJECTED
-   speaker recognition as optional future contextual hint: DEFERRED /
    ALLOWED
-   first-version dependency on speaker recognition: NOT REQUIRED

### 54.6 Wake enrollment and KWS technology

Wake enrollment/testing should evaluate whether a selected phrase is
reliably detectable and sufficiently distinct from confusers.

This does not necessarily mean training a separate neural model for
every user.

Open-vocabulary KWS and sherpa-onnx KWS were candidates for evaluation,
not selected production technologies.

Wake phrase language and command STT language are independent.

### 54.7 Multi-device arbitration

The requirement is established: multiple endpoints may hear the same
wake event and the platform must avoid multiple devices executing the
same command.

A server-mediated WakeEvent/arbitration concept was discussed using
signals such as timestamp, confidence, signal quality and device state.

The exact algorithm remains unresolved, including:

-   grouping/arbitration time window;
-   timestamp tolerance and synchronization;
-   score normalization across devices/KWS engines;
-   SNR weighting;
-   device priority;
-   proximity estimation;
-   tie handling;
-   command-capture latency;
-   loser-device buffering/cancellation;
-   offline behavior;
-   interaction between general and personal wake phrases.

Therefore the correct status is:

    arbitration requirement:
      ACCEPTED / REQUIRED

    exact arbitration algorithm:
      UNRESOLVED

------------------------------------------------------------------------

## 55. Android client lifecycle and hybrid server/local operation

### 55.1 Assistant ON/OFF

A real Android Assistant ON/OFF control is an accepted requirement.

OFF must mean more than a UI state. The historical requirement is that
unneeded voice/background activity is stopped, including microphone/wake
processing and unnecessary server communication.

### 55.2 Local wake detection

Wake detection is intended to run locally on the endpoint.

Continuous room-audio streaming to the central server while waiting for
a wake phrase is not the target design.

This preserves privacy, bandwidth and operation when the central server
is unavailable.

### 55.3 Manual microphone activation

Manual push-to-talk remains useful alongside wake-word activation for
diagnostics, noisy environments and explicit user activation.

It should not automatically be removed when wake-word support is added.

A separate "mic muted / wake paused" state was proposed historically but
is not established as a final UI requirement.

### 55.4 Hybrid server/local fallback

The old Android local Whisper capability was intentionally retained as a
fallback concept when the architecture moved toward a central server.

Target behavior:

    server available
      -> use appropriate server path

    server unavailable / PC off
      -> degraded local fallback

PC OFF is a normal supported operating condition, not a fatal platform
error.

The same client architecture is intended to work over home LAN and
remote connectivity, subject to the later security design.

### 55.5 Resource-aware routing

The Android/server architecture is intended eventually to account for
server resource availability so that a gaming/work PC is not monopolized
by the assistant.

The exact Resource Manager states, Gaming Mode protocol, heartbeat
protocol and capability/status API are not finalized or implemented
end-to-end.

Current `/status` must not be presented as proof of the complete future
resource-aware client/server protocol.

### 55.6 Server STT internals are behind the Assistant API

Android should communicate with the Smart Voice Home API rather than
selecting Buzz, Whisper or CTC engines directly.

Server STT model selection/routing is a server implementation detail.

------------------------------------------------------------------------

## 56. Historical Android whisper.cpp prompting experiment

### 56.1 Prompting was actually implemented and executed

The old Android whisper.cpp pipeline did test `initial_prompt`.

A Bulgarian command-vocabulary prompt was inserted into native C++ and
assigned through:

    params.initial_prompt = COMMAND_PROMPT

This was not merely a proposal.

### 56.2 Negative result

The tested configuration produced undesirable behavior including:

-   command hallucination;
-   repeated prompted phrases;
-   strong vocabulary bias;
-   pathological latency/fallback behavior.

One historical case took roughly 27 seconds.

The prompt was subsequently removed:

    params.initial_prompt = nullptr

Temperature fallback was disabled and command-length decoding was
bounded.

### 56.3 Correct scope of the conclusion

The evidence proves only:

    Android whisper.cpp + the tested small/base command configuration
    + that historical prompt
      -> unsuccessful and removed

It does NOT prove that all prompting with all Whisper implementations is
bad.

Therefore:

-   Android whisper.cpp command prompting: IMPLEMENTED + EXECUTED +
    REJECTED FOR TESTED CONFIGURATION
-   current server-side Whisper prompting: NOT ESTABLISHED AS TESTED
-   universal rejection of prompting: NOT SUPPORTED

Any project document saying simply "prompting was not tested" must be
qualified to distinguish current server prompting from the old Android
experiment.

### 56.4 Other surviving Android decoder settings

The historical Android branch retained or introduced independently:

-   dynamic `audio_ctx`;
-   bounded `max_tokens`;
-   greedy/single-segment command decoding;
-   `no_context`;
-   temperature fallback disabled;
-   no `initial_prompt`.

These settings belong to the old Android whisper.cpp configuration and
must not automatically be copied into the current server backend.

------------------------------------------------------------------------

## 57. CTC+LM / pyctcdecode branch

### 57.1 LM support was discovered but deliberately not executed

During the Bulgarian CTC work, the checkpoint/processor path exposed
`Wav2Vec2ProcessorWithLM` and a dependency on `pyctcdecode`.

The historical decision at that point was explicitly not to install
`pyctcdecode`; the experiment first needed clean acoustic CTC evidence.

The code path was changed to load the feature extractor, tokenizer and
CTC acoustic model directly.

### 57.2 Executed CTC evidence

Greedy/raw CTC was actually benchmarked.

Historical measured result:

    80.000 s audio
    0.535 s total inference
    ~0.053 s average
    RTF ~0.007
    peak CUDA allocated ~0.695 GB

This supports the existence and speed of the raw CTC acoustic probe.

### 57.3 Naive CTC confidence was disproved

A poor CTC transcript was observed with approximately:

    MEAN CONF = 0.9909

This demonstrated that mean per-frame maximum softmax probability is not
a valid semantic/transcript confidence score for this use.

Blank-heavy CTC frames can be locally confident while the decoded
transcript is poor.

This is an executed negative finding and should remain a guardrail.

### 57.4 CTC+LM status

A future design was proposed in which the same acoustic logits feed:

    greedy decoder
      +
    LM beam decoder

and potentially combine with Buzz/main-STT evidence in a later
Intent/Entity Resolver.

However:

-   `pyctcdecode` was not installed at that stage;
-   no CTC+LM benchmark was executed;
-   no measured improvement over greedy CTC exists in the recovered
    evidence.

Classification:

    CTC+LM / beam-search mechanism:
      HISTORICAL PROPOSAL

    executed production/benchmark mechanism:
      NO

The current paired-CTC language routing did not originate from a proven
CTC+LM implementation.

------------------------------------------------------------------------

## 58. Temporal CTC / MIXED-language diagnostics

### 58.1 Temporal paired-CTC experiment was executed

A diagnostic mixed-language experiment compared BG and EN CTC evidence
over normalized temporal windows of an utterance.

It demonstrated that some real language transitions and foreign-language
regions appear in paired acoustic evidence.

This was diagnostic evidence, not a production segment classifier.

### 58.2 Simple B/E window classification was insufficient

The temporal timelines also contained noisy rapid B/E transitions and
false EN evidence during silence/trailing padding.

Therefore:

    every B<->E window transition == language boundary

was not supported.

### 58.3 Follow-up mechanisms proposed

The history then proposed:

-   speech/VAD masking;
-   temporal smoothing;
-   minimum-duration language regions;
-   local-baseline comparison;
-   stable BG/EN region extraction.

The audit has not established that these follow-up mechanisms were
actually implemented and benchmarked.

They must therefore remain:

    PROPOSED FOLLOW-UP MECHANISMS

rather than implemented current behavior.

### 58.4 Foreign entity islands

Later temporal diagnostics showed useful EN regions around some longer
foreign phrases/entities, while short entities such as Bosch and some
Lenovo/ThinkPad cases were less stable.

The evidence supports temporal CTC as a possible hint that a foreign
acoustic region exists.

It does not support requiring temporal CTC to identify every artist,
device name or foreign entity by itself.

### 58.5 Android/server boundary

These paired-CTC and temporal-CTC experiments belong to the later
PC/server STT development.

They must not be retroactively attributed to the old Android fallback,
which used much smaller local whisper.cpp models and did not have this
independent paired-CTC evidence layer.

------------------------------------------------------------------------

## 59. Old Android small-model capability boundary

### 59.1 Bulgarian local pipeline

The original Bulgarian small-model Android tests showed substantial STT
errors in short control commands and numbers.

A particularly important failure was an absolute volume request in which
40 percent was recognized as 4 percent.

This confirms that the old Android local STT cannot be assumed to have
server-level reliability.

### 59.2 Clean English base/small comparison

The Android pipeline later compared:

    ggml-base.en-q5_1
    ggml-small.en-q5_1

under substantially the same native decoding configuration.

Historical result:

    base.en-q5_1:
      6/8 control commands
      ~0.9-1.0 s

    small.en-q5_1:
      6/8 control commands
      ~3.5-3.7 s

The larger small.en model therefore did not provide sufficient accuracy
benefit for its latency cost in this specific tablet/control workload.

The practical historical Android choice remained `base.en-q5_1`.

### 59.3 Command vocabulary adaptation

Both English models struggled particularly with very short phrases such
as `pause` and `volume up`.

The command vocabulary was therefore moved toward more acoustically
distinct phrases such as:

    stop
    more volume
    less volume

This is different from blindly fuzzy-correcting a badly recognized
opposite command.

### 59.4 Safety-oriented parser behavior

The Android parser evolved toward:

    exact match first
      -> safe limited recovery where appropriate
      -> reject uncertain/opposite-action cases

Aggressive fuzzy matching between opposite actions such as volume-up and
volume-down was deliberately rejected.

A failed command is preferable to executing the opposite action.

This historical principle remains relevant to future semantic resolver
safety, even though the old Android parser itself is not the current
server resolver.

### 59.5 Constrained commands versus open vocabulary

The historical Android evidence supports an important distinction:

    constrained control vocabulary
      -> workable with carefully selected phrases

    arbitrary artist/title/entity dictation
      -> unreliable with the small local model

`Play Metallica` could work, and the Spotify playback path was
user-verified.

Arbitrary artist/song-title requests were not reliable.

Therefore Android local fallback must be treated as degraded capability,
not as a full-quality copy of central server STT.

The exact future fallback feature policy remains unresolved and should
be decided from later requirements/testing rather than inferred from the
old POC.

### 59.6 Android audit coverage decision

The old Android branch is now sufficiently covered for the architecture
audit.

Further exhaustive reconstruction of every historical Kotlin edit,
Gradle issue and minor media-key behavior is not required unless a later
repository/history finding points back to an Android mechanism that
materially affects current architecture.

This preserves the important Android evidence without allowing obsolete
POC implementation details to dominate the current Smart Voice Home
design.

------------------------------------------------------------------------

## 60. Additional guardrails from sections 53-59

Until the remaining server/STT/repository audit is complete:

-   do not treat old Android small-model results as evidence for current
    server STT quality;
-   do not treat current server CTC/Buzz/large-Whisper capabilities as
    if they existed in the old Android fallback;
-   do not describe CTC+LM as benchmarked or implemented;
-   do not use naive CTC mean-frame confidence as semantic confidence;
-   do not describe temporal smoothing/VAD/min-duration segmentation as
    implemented without new evidence;
-   do not describe old Android prompting as "never tested";
-   do not generalize the failed Android prompt experiment into a
    universal rejection of all Whisper prompting;
-   do not hardcode artists or song titles into the assistant;
-   keep provider/account/origin/target as separate media concepts;
-   personal wake word and speaker recognition must not become
    authorization;
-   do not assume one device equals one user;
-   Android local fallback must be described as potentially degraded;
-   no code, STT route, threshold, model or architecture change is
    authorized by these findings;
-   no commit or push is authorized by this checkpoint update.

The next high-value audit work should return to the current server/STT
history and repository cross-check rather than continuing low-value
reconstruction of obsolete Android implementation details.

END OF UPDATED INTERMEDIATE CHECKPOINT
------------------------------------------------------------------------

## 61. Current STT production-composition and validation addendum

**Status:** CURRENT EXECUTION EVIDENCE / STT STILL IN PROGRESS

This section records work performed after the preceding forensic
checkpoint.

It does not replace or invalidate the earlier STT history.

In particular, the historical richer MIXED, temporal CTC, post-STT
acoustic-evidence, selective-second-pass, SttCandidate and semantic
resolver directions remain relevant historical design evidence.

No new production routing policy is authorized merely by this section.

### 61.1 Production STT composition

The current STT implementation has now been wired through a common
production composition layer.

New current components include:

    app/speech/stt/managed.py
    app/speech/stt/composition.py

`composition.py` registers the current STT resources with ModelManager:

    BUZZ_BG
      -> BuzzAsrSttEngine
      -> PyTorch lifecycle

    WHISPER_LARGE_V3
      -> WhisperSttEngine
      -> CTranslate2 lifecycle

    CTC_LANGUAGE
      -> CtcLanguageEvidenceProvider
      -> PyTorch lifecycle
      -> CPU / float32 in the current composition

The resulting service graph remains:

    CTC language evidence
      -> LanguageResolver
      -> SttRouter
      -> final STT engine

The currently implemented routing policy remains:

    BG
      -> BuzzASR / Bulgarian

    EN
      -> Whisper / forced English

    MIXED
      -> Whisper / AUTO

No routing or LanguageResolver threshold change was made during this
integration work.

### 61.2 Managed STT adapters

`ManagedLanguageEvidenceProvider` and `ManagedSttEngine` now acquire
their underlying resources through ModelManager.

The important lifecycle behavior was verified:

    acquire
      -> temporary lease

    context exit / release
      -> lease returns to zero

    release
      != unload

A resource may therefore remain resident after its temporary lease has
ended.

Explicit unload remains a ModelManager responsibility.

An early adapter defect was identified during integration:

    ModelHandle.__enter__()
      -> returns the underlying resource

rather than the ModelHandle itself.

The managed adapters were corrected to use the returned resource
directly.

### 61.3 Lazy construction

Creating the current STT runtime does not itself preload all registered
models.

A static/runtime check established that immediately after
`create_stt_runtime()`:

    CTC_LANGUAGE       unloaded
    BUZZ_BG            unloaded
    WHISPER_LARGE_V3   unloaded

This preserves lazy model creation.

### 61.4 Windows CTranslate2 CUDA DLL failure and correction

The first real production-composition Whisper inference exposed a
Windows CUDA runtime-loading failure.

The failure occurred at the first Whisper CUDA operation because:

    cublas64_12.dll

was not discoverable/loadable by the CTranslate2 execution path despite
the NVIDIA package DLL being present in the Python environment.

Diagnostics established that:

- the required DLL existed;
- explicit `ctypes.WinDLL()` loading worked;
- CTranslate2 detected the CUDA device;
- explicit cuBLAS/cuDNN preload allowed Whisper inference to succeed.

`app/resources/cuda_dll.py` was consequently extended so that the
relevant NVIDIA DLL directories are registered and the required
cuBLAS/cuDNN libraries are explicitly loaded on Windows.

After this correction, the production Whisper path executed without a
manual external ctypes preload.

Classification:

    CUDA DLL problem:
      EXECUTED / DIAGNOSED

    cuda_dll.py correction:
      IMPLEMENTED / EXECUTED SUCCESSFULLY

### 61.5 Real production-route execution

Real audio inference through the current production composition has now
been exercised for all three current route classes.

Verified paths include:

    BG
      -> BuzzASR

    EN
      -> Whisper forced EN

    MIXED
      -> Whisper AUTO

These tests establish that the current route graph is executable.

They do NOT establish that the current routing policy is sufficiently
accurate or semantically safe.

### 61.6 ModelManager lifecycle execution evidence

The following lifecycle behavior has now been exercised with real
resources:

- temporary acquire/release;
- resident reuse after release;
- leases returning to zero;
- explicit unload;
- exception-path lease cleanup.

An intentional inference exception left the resource resident while its
active lease count correctly returned to zero.

Explicit unload of real Whisper and CTC resources was also exercised
successfully.

This supports the current distinction:

    ModelManager
      -> model ownership and lifecycle

    future Resource Manager / Scheduler
      -> policy, budgets, gaming behavior, eviction decisions, etc.

No LRU, VRAM-budget policy, Gaming Mode, automatic eviction or general
Resource Manager policy was implemented by this work.

### 61.7 Validation runner now uses production composition

`run_stt_validation.py` was adapted so that validation no longer builds
a separate eager STT/model graph.

It now uses the current production composition.

The accepted-case manifest validation remains responsible for checking
the accepted pilot recordings, including identifiers, reference text,
attempt information, file existence and SHA256 evidence.

The runner records production language evidence, route, transcription,
WER and resource state.

This change is important because later validation results now exercise
the same current STT composition rather than a parallel validation-only
model graph.

### 61.8 Production-composition smoke test

A production-composition smoke test was executed on BG01.

Result:

    completed: 1
    failed:    0

Observed route:

    BG01
      -> BG
      -> BuzzASR

Observed WER:

    0.125

After inference:

    CTC_LANGUAGE
      resident
      leases = 0

    BUZZ_BG
      resident
      leases = 0

    WHISPER_LARGE_V3
      not loaded

Cleanup completed without recorded cleanup errors.

### 61.9 Production 24-file regression

The complete accepted `pilot_01` corpus was subsequently executed
through the current production composition.

Corpus:

    BG01-BG08
    EN01-EN08
    MX01-MX08

Result:

    planned:   24
    completed: 24
    failed:    0

Therefore the current production composition completed all 24 accepted
pilot files without runtime failure.

This remains the SAME known pilot corpus.

It is NOT an independent final validation corpus.

### 61.10 Production routing observations

The production 24-file run exposed several important routing behaviors.

Clean Bulgarian:

    7 / 8
      -> BG

    BG04
      -> MIXED

Clean English:

    6 / 8
      -> EN

    EN05
      -> MIXED

    EN07
      -> MIXED

Accepted MIXED recordings:

    MX01 -> MIXED
    MX02 -> MIXED
    MX03 -> BG
    MX04 -> BG
    MX05 -> MIXED
    MX06 -> BG
    MX07 -> BG
    MX08 -> BG

These labels must not be interpreted naively as routing correctness.

A recording containing mixed-language speech does not necessarily obtain
its best final transcription from the current MIXED route.

MX04 is a concrete counterexample: its BG/Buzz production path produced
an exact WER result even though the reference itself contains mixed
Bulgarian and English speech.

### 61.11 Aggregate CTC feature analysis

Existing production JSONL evidence was used to inspect multiple
whole-utterance CTC features without rerunning the acoustic models.

Examined evidence included:

- entropy delta;
- BG and EN entropy;
- BG and EN uncertainty;
- BG and EN non-blank confidence;
- non-blank rate.

The accepted BG, EN and MIXED recordings overlap substantially in these
aggregate measurements.

The evidence therefore does NOT currently justify treating the problem
as merely incorrect values for the existing:

    0.003
    0.043

entropy-delta thresholds.

Classification:

    simple threshold retuning:
      NOT JUSTIFIED BY CURRENT EVIDENCE

This does not prove that the thresholds are optimal.

It means that the observed errors cannot currently be reduced to a
demonstrated two-number calibration problem.

### 61.12 Candidate-comparison diagnostic

A new diagnostic script was introduced:

    diagnose_stt_candidates_24.py

Its purpose is diagnostic comparison only.

It does not change production routing.

For every accepted pilot recording it compares:

    existing saved production result

    Buzz BG

    Whisper AUTO

    Whisper forced BG

    Whisper forced EN

The saved production result is reused rather than rerunning the
production route.

The diagnostic uses the public STT engine interfaces rather than direct
private Whisper-model access.

### 61.13 Production-like simultaneous model residency

The candidate diagnostic deliberately retained Buzz and Whisper
simultaneously after their first load.

This was done because the current ModelManager semantics are:

    release != unload

and simultaneous residency can occur in the intended running system.

A one-file smoke diagnostic verified:

    after Buzz:
      Buzz loaded
      Whisper unloaded
      leases = 0

    after first Whisper inference:
      Buzz loaded
      Whisper loaded
      leases = 0

Both models then remained resident through the remaining candidate
passes.

Final explicit cleanup unloaded both models successfully.

### 61.14 VRAM evidence

On the current NVIDIA GeForce RTX 3070 8 GB system, the one-file
candidate smoke run observed approximately:

    initial:
      1842 MB used

    after Buzz:
      5516 MB used

    Buzz + Whisper resident:
      7480 MB used
      ~91.3 percent

    free while both resident:
      ~712 MB

    after cleanup:
      2052 MB used

The full 24-file diagnostic similarly operated around approximately
7.3-7.6 GB VRAM while both models were resident.

The full candidate experiment completed without CUDA OOM or runtime
failure.

This establishes that simultaneous residency worked in this diagnostic
on the current machine.

It does NOT establish a future general VRAM policy or sufficient margin
for all other GPU workloads.

### 61.15 Full candidate experiment

The full accepted pilot corpus was processed through all four diagnostic
candidate modes.

Result:

    24 recordings
      x
    4 candidate transcriptions
      =
    96 candidate transcriptions

Execution result:

    completed: 24
    failed:    0

Final cleanup:

    Buzz loaded:     false
    Whisper loaded:  false

    Buzz leases:     0
    Whisper leases:  0

    cleanup_errors:  []

This is current execution evidence that Buzz and Whisper can coexist
resident during this diagnostic workload on the current RTX 3070 8 GB
system.

### 61.16 Candidate comparison demonstrates that routing and ASR quality
are separate problems

The candidate experiment demonstrates that:

    correct language-category routing
      != guaranteed good transcription

and:

    speech language label
      != automatically the best STT engine/mode

Examples include:

- BG04 improved from the production MIXED/Whisper result to an exact
  Buzz result;
- EN07 failed badly under production MIXED/Whisper AUTO but was recovered
  by Whisper forced EN;
- MX04 was handled extremely well by Buzz despite containing mixed
  language;
- MX06 and MX07 were substantially better with Whisper AUTO/BG than with
  the current production BG/Buzz path.

Therefore neither:

    MIXED -> always Whisper AUTO

nor:

    MIXED -> always Buzz

is supported as a general solution by this pilot.

### 61.17 Semantic review of current candidate evidence

Raw WER remains insufficient for command safety.

The current candidate transcripts exposed concrete semantic failure
classes.

#### BG06

Reference target:

    bedroom / спалнята

was damaged to a phrase equivalent to:

    с памет

The target was therefore lost.

This is a semantic failure that is not repaired merely by choosing the
currently tested alternative candidates.

#### EN05

The critical command verb:

    pause

was not reliably preserved.

Candidate outputs contained forms such as:

    Paul's / Pol's playback

or phonetic approximations.

This is an ASR-level command-semantic problem rather than merely a route
label problem.

#### EN07

Whisper AUTO produced a badly language-switched result and lost the
intended English weather/time semantics.

Whisper forced EN recovered:

    Aurora, what will the temperature be tomorrow morning?

with WER 0.000 in the candidate diagnostic.

This is strong evidence that explicit language information can remain
valuable even though the current aggregate classifier is imperfect.

#### MX04

Reference:

    Аурора, включи лампата, but keep the music playing.

Buzz preserved the command essentially exactly.

Whisper AUTO/BG changed the English clause toward turning the music off.

This is a critical example of possible action-semantic inversion.

It reinforces the existing project safety principle:

    low aggregate text error
      != safe command semantics

and:

    an uncertain command is preferable to executing an opposite action.

#### MX06

The current production BG/Buzz path damaged the mixed-language request.

Whisper AUTO/BG produced an essentially exact transcription.

#### MX07

The current production BG/Buzz path damaged the mixed-language request.

Whisper AUTO/BG produced an essentially exact transcription.

#### MX08

Whisper AUTO/BG better preserved the mixed-language request and its
critical negative instruction:

    не променяй звука

than the current production result.

These findings strengthen the requirement that future evaluation include
at least:

    action
    negation
    value
    target
    names/entities
    time

### 61.18 Historical richer STT architecture is directly relevant

The current evidence must NOT be interpreted as discovery of an entirely
new architecture.

Earlier project history already contained a richer STT direction than
the current simple router.

Recovered historical mechanisms include:

    paired BG/EN CTC acoustic evidence

    temporal CTC evidence

    foreign-language region hints

    multiple STT hypotheses

    selective second passes

    post-STT retention of CTC acoustic evidence

    grammar/context/entity comparison

    future semantic / Intent-Entity Resolver

    deferred SttCandidate representation

Historical MIXED reasoning explicitly did NOT equate:

    MIXED
      ==
    Whisper AUTO

For Bulgarian command grammar containing foreign names/entities,
historical proposals included combinations such as:

    Buzz
      +
    Whisper forced BG

with selective English processing for problematic foreign regions.

The current candidate experiment provides new evidence that this richer
historical direction deserves renewed evaluation.

It does NOT prove one exact historical proposal to be the final
production algorithm.

### 61.19 Post-STT CTC evidence remains a relevant historical direction

Earlier project reasoning proposed retaining CTC evidence after primary
STT rather than using CTC only as a pre-STT language classifier.

Conceptually:

    acoustic evidence
      +
    STT hypothesis/hypotheses
      +
    grammar
      +
    context
      +
    entities
      ->
    semantic decision

This was motivated by cases where one recognizer could damage a
command-critical word while another acoustic evidence stream retained
useful information.

Current `SttService` already preserves language evidence in its analysis
API, but no current production semantic evidence-fusion resolver has
been established.

Classification:

    evidence preservation:
      CURRENT API SUPPORT EXISTS

    semantic evidence fusion:
      NOT IMPLEMENTED

### 61.20 Temporal CTC status remains unchanged

Historical temporal paired-CTC diagnostics demonstrated that some
language transitions and longer foreign regions can appear in temporal
BG/EN evidence.

They also demonstrated that naive per-window B/E classification is too
noisy.

Historically proposed follow-up mechanisms included:

    speech/VAD masking
    smoothing
    minimum-duration regions
    local-baseline comparison
    stable language-span extraction

The current work has NOT newly established those mechanisms as
implemented.

They therefore remain historical/proposed mechanisms requiring evidence
before production use.

### 61.21 Selective candidate strategy remains unresolved

The current evidence makes a richer candidate strategy plausible.

A conceptual direction remains:

    CTC / acoustic evidence
             |
             v
      candidate strategy
             |
       +-----+-----+
       |     |     |
       v     v     v
     Buzz  Whisper Whisper
      BG      BG    EN/AUTO
       |      |      |
       +------+------+
             |
             v
       semantic evaluation
             |
             v
      selected hypothesis
        or safe rejection

However this diagram is a DESIGN DIRECTION, not current production
behavior.

The present 24-file pilot is too small and too familiar to justify
hardcoding a candidate-selection algorithm around its individual cases.

The project must avoid overfitting the production architecture to these
24 recordings.

### 61.22 Relationship of historical design and current evidence

The correct chronology is:

    HISTORICAL DESIGN
      ->
    CURRENT SIMPLE IMPLEMENTATION
      ->
    CURRENT PRODUCTION EXECUTION
      ->
    CURRENT 24-FILE CANDIDATE EXPERIMENT
      ->
    NEW SEMANTIC EVIDENCE
      ->
    CURRENT INTERPRETATION
      ->
    FINAL POLICY STILL UNRESOLVED

Historical ideas must not be promoted to implemented status merely
because new evidence makes them attractive again.

Likewise, new evidence must not be forced to preserve an older design if
future experiments support a better mechanism.

### 61.23 Current STT completion boundary

STT is NOT frozen and must NOT yet be described as complete.

Before final STT completion, independent real-microphone validation is
still required.

That validation should include at least:

- clean Bulgarian;
- clean English;
- mixed Bulgarian/English;
- short commands;
- longer commands;
- different speaking speeds;
- natural pauses;
- names/entities;
- numbers and values;
- acoustically confusable command words;
- quieter/louder speech;
- reasonable background noise.

Evaluation must cover separately:

    routing / language evidence
    transcription quality
    semantic preservation
    command safety

The current accepted 24-file pilot remains valuable regression evidence,
but it is not an independent final validation set.

### 61.24 Current resource-policy boundary

The candidate diagnostic established a useful measured fact:

    Buzz + Whisper simultaneous residency
      works on the current RTX 3070 8 GB diagnostic workload

with little remaining VRAM margin.

This must be retained as evidence for future resource-policy work.

It does NOT authorize implementation of:

    LRU
    automatic eviction
    VRAM budget policy
    Gaming Mode
    scheduler policy
    client fallback policy

Those remain separate Resource Manager / Scheduler concerns.

### 61.25 Current change-control boundary

At this checkpoint:

- no new production STT routing policy has been selected;
- no LanguageResolver threshold change has been justified;
- no semantic candidate selector has been implemented;
- no temporal CTC production segmentation has been implemented;
- no Resource Manager policy has been implemented;
- independent final real-microphone validation remains open;
- STT remains in active validation/design;
- no commit or push is authorized by this checkpoint update.

The last previously established Git checkpoint remains:

    f71ab11
    Checkpoint STT evidence and semantic review

Current uncommitted work must remain distinguishable from that Git
checkpoint until explicit approval is given.

------------------------------------------------------------------------

## 62. Next STT continuation point

The next high-value STT task is NOT blind threshold adjustment.

The next analysis should correlate:

    existing CTC evidence
      <->
    candidate transcription behavior
      <->
    semantic preservation

with special attention to cases where the candidate behavior diverges,
including:

    BG04
    EN05
    EN07
    MX01
    MX03
    MX04
    MX06
    MX07
    MX08

The purpose is to determine whether existing or richer acoustic/language
evidence can support a selective candidate strategy.

If the available pre-STT evidence cannot reliably make that distinction,
the project should evaluate post-STT semantic candidate selection rather
than forcing all decisions into the current whole-utterance language
classifier.

No production implementation should be chosen until that analysis is
completed and reconciled with the historical richer STT design.

END OF CURRENT STT VALIDATION ADDENDUM

## 63. STT production wiring, candidate diagnostics and live-microphone validation — 2026-09-26

### 63.1 Scope and status

**Status: EXECUTED DIAGNOSTICS / STT NOT FROZEN**

This section records work performed after the previous canonical checkpoint update.
It is evidence and current-state documentation, not authorization to change routing,
thresholds, models, Resource Manager policy, APIs, or assistant actions merely to
make validation pass.

No commit or push is authorized by this section.

### 63.2 Production STT composition and managed model lifecycle

The production-like STT composition path now uses `create_stt_runtime()` and
managed model adapters around `ModelManager`.

Confirmed registrations and roles:

- `BUZZ_BG`: Bulgarian BuzzASR model, PyTorch backend, estimated 3323 MB.
- `WHISPER_LARGE_V3`: faster-whisper/CTranslate2 large-v3, estimated 3913 MB,
  `int8_float16`.
- `CTC_LANGUAGE`: paired CTC language evidence on CPU/float32, estimated 0 MB GPU.

The managed adapters acquire temporary `ModelManager` leases for inference and
release those leases afterward. Release is still deliberately distinct from unload:
a resource may remain resident with zero active leases for warm reuse.

A bug discovered during this work was that `ModelHandle.__enter__()` returns the
resource itself, not the handle. The managed adapter was corrected accordingly.

Verified lifecycle behavior includes:

- `create_stt_runtime()` itself does not preload the three production STT resources;
- normal managed inference returns leases to zero;
- an intentionally raised engine exception also returned the lease count to zero;
- resources can remain resident after release;
- explicit unload was verified separately;
- no permanent model handle is required by the STT service.

The exception-cleanup target passed. Two defects in the temporary fake diagnostic
harness (a missing `.backend` member and a wrong cleanup signature) were unrelated
to the production lease behavior and are not production failures.

### 63.3 Windows CUDA DLL registration fix

The first real managed Whisper production inference failed at the first CUDA
operation because `cublas64_12.dll` was not loadable through the process DLL search
path.

Diagnostics established that the DLL existed and could be loaded explicitly.
`app/resources/cuda_dll.py` was changed so Windows registers the NVIDIA
cublas/cuda_nvrtc/cudnn `bin` directories with `os.add_dll_directory`, explicitly
loads `cublas64_12.dll` and `cudnn64_9.dll` with `ctypes.WinDLL`, and retains the
handles.

After this change, production MIXED -> Whisper inference worked without a manual
one-off `ctypes` preload.

A remaining implementation caveat is that the current helper's retry semantics
after a partial DLL-registration success followed by explicit-load failure have not
been hardened. The successful path is verified; this caveat is not evidence of a
current observed failure.

### 63.4 Production route execution checks

Real production-path checks succeeded for:

- BG -> Buzz;
- EN -> Whisper with the production EN route;
- MIXED -> Whisper;
- explicit model unload after use.

These checks establish that the composed route can execute. They do not establish
that the current routing policy or transcription quality is sufficient for final
STT freeze.

### 63.5 Production 24-case regression

`run_stt_validation.py` was changed to use `create_stt_runtime()` and the managed
production wiring while retaining manifest/SHA validation, WER calculation,
semantic parser review, local/offline preflight, JSONL output and explicit cleanup.

The full accepted 24-file pilot completed:

- planned: 24;
- completed: 24;
- failed: 0;
- cleanup errors: none;
- observed active model leases after cases: 0.

Observed routing:

- clean BG: 7/8 routed BG; BG04 routed MIXED;
- clean EN: 6/8 routed EN; EN05 and EN07 routed MIXED;
- MIXED: MX01, MX02 and MX05 routed MIXED; the remaining five routed BG.

This routing distribution must not be interpreted as a correctness score by itself.
A MIXED-labelled reference routed BG can still transcribe correctly, and a
nominally correct route can still lose command semantics.

When Buzz and Whisper were both resident, measured GPU memory was approximately
7.55–7.58 GB on the 8 GB RTX 3070 in this diagnostic. This is important evidence
for later residency/resource policy, but it does not itself define that policy.

### 63.6 Aggregate CTC evidence

The existing CTC evidence from the 24 cases was analysed without rerunning the
models.

MIXED cases overlap substantially with clean BG and EN cases in aggregate
`entropy_delta` and related scalar features. No obvious one-dimensional separator
was established.

Therefore the evidence does **not** justify changing the current 0.003/0.043
boundaries merely to make this pilot classify more MIXED examples as desired.
The observed limitation appears more fundamental than a simple threshold mistake.

This remains consistent with the older temporal-CTC history: useful temporal
language evidence has been observed, while a simple global scalar classifier is
insufficient for all code-switching cases.

### 63.7 Candidate diagnostic across the 24 accepted cases

`diagnose_stt_candidates_24.py` was used to compare, per accepted WAV:

- current production result;
- Buzz BG;
- Whisper AUTO;
- Whisper forced BG;
- Whisper forced EN.

The full diagnostic completed 24/24 with no case failures or cleanup errors.
Buzz and Whisper were intentionally kept resident after first load for the
diagnostic; active leases returned to zero. Peak observed after-case GPU memory was
approximately 7.624 GB and no OOM occurred. Explicit cleanup unloaded the models.

The result does not support one universal candidate for MIXED speech:

- MX04: Buzz/current production was exact; Whisper AUTO/BG inverted the meaning of
  keeping music playing into turning it off, which is unsafe.
- MX06: Whisper AUTO/BG was essentially exact.
- MX07: Whisper AUTO/BG was exact; forced EN changed sequencing/agency.
- MX08: Whisper AUTO/BG was exact and preserved the critical negation.
- MX01, MX03 and MX05 did not produce a universally safe obvious candidate.
- EN07: production/AUTO was severely wrong while forced EN was exact.

Additional manual semantic findings:

- BG06: all compared candidates lost the bedroom target.
- EN05: all compared candidates lost the pause action.
- EN07: forced EN was exact; Buzz was semantically near-exact; AUTO was severely
  corrupted.
- MX04 demonstrated that lower WER or a plausible multilingual candidate is not
  enough when action semantics can invert.
- MX03 forced EN changed "reduce" toward "normalize", which is not semantically safe.

Consequently, neither `MIXED -> always Whisper AUTO` nor `MIXED -> always Buzz` is
supported as a final policy, and WER alone must not select a production candidate.

### 63.8 Semantic validation remains open

`SemanticReviewer().review(result.text)` reviews the parsed hypothesis. It is not a
reference-versus-hypothesis correctness oracle.

Final STT validation still requires explicit semantic comparison covering at least:

- action;
- negation;
- value;
- target;
- names/entities;
- time;
- sequencing where relevant.

Low WER is insufficient if one of these safety-critical fields is changed.

### 63.9 Real-microphone validation collector was not the requested final-use test

A new real-microphone BG01 capture was made with
`collect_stt_validation.py --start BG01 --count 1 --speaker stan
--environment "real-mic-final"`.

The accepted attempt was 5.30 s with RMS 0.0414 and the spoken/reference text
"Аурора, намали силата на звука до двадесет процента."

The collector required manual acceptance plus manual entry of the actually spoken
text and speech language. That workflow is appropriate for building a labelled
validation corpus, but it is not equivalent to testing the assistant as if it were
ready for normal use.

The user therefore redirected validation toward a true live path:
wake/capture -> production STT -> visible result, with no manual reference entry.

### 63.10 Live production STT diagnostic runner

`diagnose_live_production_stt.py` was introduced as a diagnostic-only live runner.

Its intended path is:

    microphone
      -> AuroraCapture
      -> CapturedPhrase
      -> temporary WAV required by the current Path-based STT interface
      -> runtime.service.transcribe_with_evidence(...)
      -> diagnostic output
      -> delete temporary WAV
      -> resume capture

The temporary WAV is an implementation bridge for the current file-path STT API;
it is not a validation corpus item and is deleted after processing.

The runner does **not** execute Home Assistant or other assistant actions.

The first version exposed a live integration defect: `AuroraCapture` deliberately
calls `pause()` before handing a completed phrase to its consumer, but the runner
did not resume capture. The result was one successful phrase followed by an
apparently stuck listener.

Repository inspection confirmed the public methods:

- `AuroraCapture.pause()` sets `pause_event`;
- `AuroraCapture.resume()` clears queued audio/state and clears `pause_event`.

The runner was corrected to call `capture.resume()` after each processed phrase.
The subsequent live test confirmed `[CAPTURE] Resumed.` and accepted later phrases.

### 63.11 Live production test results after resume fix

A multi-command real-microphone session was executed through the production STT
service.

First accepted production phrase:

- capture duration: 8.60 s;
- RMS: 0.0474;
- wake ASR: `Aurora`, detected as `ru` by the wake Whisper pass;
- production route: BG;
- resolution: `CTC_BULGARIAN_EVIDENCE`;
- engine: BuzzASR Bulgarian;
- transcript: `Аурора пуси музиката Аурора колко е часът`;
- production STT measured time: 13.20 s.

This capture appears to contain two command utterances in one 8.60 s phrase. It is
therefore evidence of a capture/segmentation issue in addition to transcription
errors.

Second accepted production phrase:

- capture duration: 4.00 s;
- RMS: 0.0351;
- wake candidates included `id`, `ru`, `hr` and later `sl`;
- wake was eventually confirmed;
- production route: BG;
- resolution: `CTC_BULGARIAN_EVIDENCE`;
- engine: BuzzASR Bulgarian;
- transcript: `Алрура колко е часът`;
- production STT measured time: 9.19 s.

Third accepted production phrase:

- capture duration: 4.50 s;
- RMS: 0.0485;
- wake ASR included `ru`;
- production route: BG;
- resolution: `CTC_BULGARIAN_EVIDENCE`;
- engine: BuzzASR Bulgarian;
- transcript: `Аурора намали музиката в кухнята`;
- production STT measured time: 10.72 s.

The third transcript was substantially better than the first two for command
content. The second preserved the command but damaged the wake name.

### 63.12 Live latency finding: not only cold model loading

The first production command showed visible model weight loading and took 13.20 s.
However the next two production STT calls still took 9.19 s and 10.72 s after the
relevant production resources were already resident.

Therefore the observed live latency cannot be attributed solely to first-command
model loading.

The live log also showed AuroraCapture wake-ASR work continuing while production
STT was processing, including wake Whisper calls measured at multiple seconds.
This is evidence of concurrent/overlapping wake-ASR activity during the production
STT interval and a plausible source of GPU contention. It is **not yet proof** that
this is the sole cause of the 9–11 s warm latency.

This is a blocking performance issue for normal assistant use and requires focused
measurement before STT can be frozen.

### 63.13 Preload/warm-up requirement and VRAM caveat

For the intended real assistant experience, the user should not speak the first
command and then wait for core STT models to load.

The desired runtime behavior is:

    process/service start
      -> initialize required CUDA/model resources
      -> perform required preload/warm-up
      -> report STT READY
      -> begin normal wake/microphone interaction

This is now an accepted operational requirement/direction for the real-use path.

It is **not yet a completed implementation**.

Before blindly preloading every speech model, the project must determine whether
AuroraCapture's wake Whisper large-v3 duplicates or otherwise competes with the
ModelManager-managed Whisper resource. Existing measurements already show the
production Buzz + Whisper residency near the 8 GB GPU limit. A preload strategy
must therefore be measured rather than assumed.

### 63.14 Related-language detection and Bulgarian fallback: historical status clarified

The historical STT checkpoint confirms that the user previously proposed treating
misdetected `ru`/related-language speech as Bulgarian in the relevant Bulgarian
context.

The canonical history also records a Bulgarian-family fallback set in
`LanguageResolver`, including related language codes such as:

    ru uk be mk sr hr bs sl cs sk pl

However, the current paired-CTC production-like path primarily uses
`resolve_evidence()`. The existence of a related-language fallback helper/path is
not proof that it is active for the current production route.

The new live test again demonstrated wake Whisper producing related-language
labels (`ru`, `hr`, `sl`) for Bulgarian-sounding speech. At the same time, all
three accepted production examples above were routed BG by paired CTC evidence.

Therefore:

- the historical related-language requirement/problem is real;
- related-language misdetection remains observable in the live wake path;
- it has **not** been established that a final `all related languages -> BG`
  production rule was previously completed;
- no new production route, threshold or language-family mapping was changed during
  this live test;
- the correct call sites and interaction between wake language detection, paired
  CTC evidence and final STT routing still require explicit audit before changing
  production behavior.

### 63.15 Current STT completion state after live test

STT is **not complete and must not be frozen yet**.

Confirmed working pieces now include:

- production composition can execute BG/EN/MIXED routes;
- managed leases return to zero;
- explicit unload works;
- Windows CUDA DLL loading issue is resolved on the verified success path;
- the 24-case production regression completes without case failures;
- the 24-case multi-candidate diagnostic completes without OOM;
- live AuroraCapture can hand phrases to production STT repeatedly after the
  explicit `resume()` integration fix.

Blocking/open items include:

- warm live latency of approximately 9–11 s in the observed session;
- determining the contribution of concurrent wake Whisper work/GPU contention;
- defining and implementing measured startup preload/warm-up before `READY`;
- checking whether wake Whisper and production Whisper duplicate residency/work;
- capture segmentation that allowed an apparent two-command 8.60 s phrase;
- final treatment of related-language detections in the correct production layer;
- semantic-safe candidate/routing behavior for difficult MIXED and ambiguous cases;
- independent real-use validation after the performance/integration fixes.

No threshold, model or production route should be changed merely to make the
current validation look better. Measure the blocking live behavior first.

