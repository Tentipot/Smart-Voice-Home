# Smart voice home — Architecture reference



Updated: 2026-09-24

Command review (2026-09-26): `CommandReviewService` composes SttService and
`SemanticReviewer` after transcription, preserving the original evidence.
The reviewer is a bounded single-command grammar with candidate conflict
checks, not a complete Intent/Entity Resolver. It never authorizes or executes
actions, never treats CTC scores as semantic confidence, and leaves unresolved
targets/queries to future integration. See SEMANTIC_REVIEW_V1.md.

STT evidence contract (2026-09-26): `transcribe_with_evidence(path)` returns
`SttTranscription` with audio_path, result, evidence and resolution from one
CTC/routing/STT invocation. `transcribe_file()` still returns SttResult.
This supports downstream review without a second CTC pass. It provides
aggregate metrics, not CTC text, word alignment, semantic confidence or
authorization. Candidate fusion and Intent/Entity Resolver remain unimplemented.



## Purpose and authority



This document collects the architecture diagrams used as a reference during development. It distinguishes current implementation evidence from target architecture and unresolved design choices.



Authoritative requirements and decisions: `PROJECT_MASTER.md` and `DECISION_REGISTER.md`.



Implementation status: `PROJECT_STATE.md`.



Unresolved work: `OPEN_QUESTIONS.md`.



"Aurora / Аурора" is a development wake word, not the project name.



## 1. Microphone to command transcript



Current components and intended connection:



```text

Microphone

&#x20;   |

&#x20;   v

AuroraCapture

&#x20;   |

&#x20;   v

Wake detection ("Аурора")

&#x20;   |

&#x20;   +-- Not detected --> Continue listening

&#x20;   |

&#x20;   +-- Detected

&#x20;           |

&#x20;           v

&#x20;      Phrase capture / WebRTC VAD

&#x20;           |

&#x20;           v

&#x20;      Captured audio

&#x20;           |

&#x20;           v

&#x20;       SttService

&#x20;           |

&#x20;           v

&#x20;      BG + EN CTC evidence (CPU/RAM)

&#x20;           |

&#x20;           v

&#x20;      LanguageResolver

&#x20;           |

&#x20;           v

&#x20;        SttRouter

&#x20;           |

&#x20;           +-- BULGARIAN --> BuzzASR (GPU, forced bg)

&#x20;           |

&#x20;           +-- ENGLISH ----> Whisper large-v3 (GPU, forced en)

&#x20;           |

&#x20;           +-- MIXED ------> Whisper large-v3 (GPU, auto-language)

&#x20;           |

&#x20;           v

&#x20;      Final STT transcript

&#x20;           |

&#x20;           v

&#x20;      Command processing (target integration)

```



**Status:** AuroraCapture has been functionally tested with live microphone recordings. Captured WAV audio has also been processed through SttService in a separate diagnostic process. The live callback-to-SttService connection within one process remains unverified. Preliminary wake ASR text is not the final command transcript. No real assistant actions were executed during these diagnostics.



## 2. STT routing and model roles



```text

Audio

&#x20; |

&#x20; v

BG + EN CTC language evidence

&#x20; |

&#x20; v

LanguageResolver

&#x20; |

&#x20; v

SttRouter

&#x20; |

&#x20; +-- BULGARIAN

&#x20; |      |

&#x20; |      v

&#x20; |   BuzzASR Bulgarian

&#x20; |   language="bg"

&#x20; |

&#x20; +-- ENGLISH

&#x20; |      |

&#x20; |      v

&#x20; |   Whisper large-v3

&#x20; |   language="en"

&#x20; |

&#x20; +-- MIXED

&#x20;        |

&#x20;        v

&#x20;     Whisper large-v3

&#x20;     language=None

&#x20;        |

&#x20;        v

&#x20;     STT result

```



CTC provides language evidence; it is not the final speech-to-text engine.



The current resolver boundaries are BG `<= 0.003` and EN `>= 0.043`. They were derived from calibration recordings and have not been independently validated.



The MIXED route is the current implementation direction, not a guarantee of correct transcription for every Bulgarian or mixed-language command. Consult `PROJECT_HISTORY.md` and `OPEN_QUESTIONS.md` for diagnostic results and remaining validation work.



## 3. Android and server processing



**Target architecture; current end-to-end integration is not verified.**



```text

Android client

&#x20;    |

&#x20;    v

Server reachable?

&#x20;    |

&#x20;    +-- YES --> Assistant Server STT

&#x20;    |

&#x20;    +-- NO  --> Android local fallback

&#x20;                      |

&#x20;                      v

&#x20;               Available local handling

```



Historical Android MVP evidence includes local Whisper fallback. The current Android source and its integration with the newer Assistant Server still require re-audit.



Local fallback is not permission to silently invoke external cloud STT, search or AI services. External services remain subject to the project's explicit intent/consent policy.



## 4. Resource-aware operation



**Target behavior.** The conditions below illustrate possible operating states; `NORMAL`, `GAMING` and `BUSY` are not confirmed implemented software modes.



```text

Assistant workload

&#x20;      |

&#x20;      v

Resource Manager (planned)

&#x20;      |

&#x20;      v

Observe CPU / RAM / GPU / VRAM

and competing PC workload

&#x20;      |

&#x20;      +-- Normal workload

&#x20;      |        |

&#x20;      |        v

&#x20;      |   Standard model allocation

&#x20;      |

&#x20;      +-- Gaming / work

&#x20;      |        |

&#x20;      |        v

&#x20;      |   Yield or reduce GPU pressure

&#x20;      |

&#x20;      +-- Resource pressure

&#x20;               |

&#x20;               v

&#x20;         Bounded fallback / queue policy

```



ModelHandle and ModelManager exist, and model resource residency has been investigated. Final budgets, eviction rules, priorities and gaming behavior remain open.



The placement of local conversational AI across CPU, system RAM, GPU and VRAM is benchmark-driven and has not been finalized.



## 5. Overall platform architecture



**Target modular-monolith architecture; not all modules are implemented.**



```text

Clients

(Android and future endpoints)

&#x20;              |

&#x20;              v

&#x20;       Assistant Server

&#x20;              |

&#x20;              +-- Speech

&#x20;              |   capture / STT / language / TTS

&#x20;              |

&#x20;              +-- Command processing

&#x20;              |

&#x20;              +-- Local conversational AI

&#x20;              |

&#x20;              +-- Explicit-consent external providers

&#x20;              |

&#x20;              +-- Home Assistant integration

&#x20;              |

&#x20;              +-- Media / playback

&#x20;              |

&#x20;              +-- Users / devices / homes / permissions

&#x20;              |

&#x20;              +-- Resource Manager

&#x20;              |

&#x20;              +-- API / transport

&#x20;              |

&#x20;              v

&#x20;    Administration GUI / Web Admin

&#x20;                (planned)

```



The initial server platform is a Windows PC. The architecture must remain Linux-migratable. Android remains a Kotlin client.



Remote access to the user's own Assistant Server is a normal platform capability. External online services require the applicable explicit intent/consent policy.



## Maintenance rule



When architecture changes, update this reference together with the corresponding decision, implementation evidence, open question and project state.



**A diagram alone is not proof that a component or integration has been implemented and tested.**
