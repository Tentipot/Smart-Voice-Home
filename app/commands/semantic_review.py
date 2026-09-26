"""Conservative single-command grammar. No fuzzy correction or execution."""
from dataclasses import dataclass, field
import re
import unicodedata


@dataclass(frozen=True, slots=True)
class CommandProposal:
    intent: str
    target: str | None = None
    value: int | None = None
    query: str | None = None
    steps: tuple['CommandProposal', ...] = ()
    constraints: tuple['CommandProposal', ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateReview:
    text: str
    command: CommandProposal | None
    reason: str


@dataclass(frozen=True, slots=True)
class SemanticReview:
    status: str
    reason: str
    command: CommandProposal | None
    candidates: tuple[CandidateReview, ...]
    can_execute: bool = field(default=False, init=False)


def normalize(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', text).casefold()
                    .replace('’', "'").split()).strip(' .,!')


def percent_value(text: str) -> int | None:
    """Exact integer forms only: no rounding, clamping or fuzzy repair."""
    if re.fullmatch(r'[0-9]{1,3}', text):
        return int(text) if int(text) <= 100 else None
    for units, teens, tens, hundred, connector in (
        ('нула едно две три четири пет шест седем осем девет'.split(),
         'десет единадесет дванадесет тринадесет четиринадесет петнадесет шестнадесет седемнадесет осемнадесет деветнадесет'.split(),
         'двадесет тридесет четиридесет петдесет шестдесет седемдесет осемдесет деветдесет'.split(), 'сто', ' и '),
        ('zero one two three four five six seven eight nine'.split(),
         'ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),
         'twenty thirty forty fifty sixty seventy eighty ninety'.split(), 'one hundred', ' '),
    ):
        forms = {word: i for i, word in enumerate(units + teens)}
        forms[hundred] = 100
        for i, word in enumerate(tens, 2):
            forms[word] = i * 10
            for j in range(1, 10):
                forms[word + connector + units[j]] = i * 10 + j
        value = forms.get(text.replace('-', ' '))
        if value is not None:
            return value
    return None


class SemanticReviewer:
    """Parsed means supported syntax, NOT acoustic truth or authorization.

    Caller-supplied alternatives must refer to the same audio. Contradictory
    proposals or an unparsed candidate require clarification. CTC language
    scores never become semantic confidence. Targets remain unresolved text.
    """

    def review(self, text: str, *, alternatives: tuple[str, ...] = ()) -> SemanticReview:
        candidates = tuple(self._parse(t) for t in (text, *alternatives))
        commands = {c.command for c in candidates if c.command is not None}
        if len(commands) > 1:
            return SemanticReview('needs_clarification', 'conflicting_candidates', None, candidates)
        if any(c.command is None or c.reason != 'supported' for c in candidates):
            reason = candidates[0].reason if len(candidates) == 1 else 'unresolved_candidate'
            return SemanticReview('needs_clarification', reason, None, candidates)
        return SemanticReview('parsed', 'supported_single_command', candidates[0].command, candidates)

    def _parse(self, raw: str, depth: int = 0) -> CandidateReview:
        text = normalize(raw)
        text = re.sub(r'^(?:аурора|aurora)(?:\s*[,!:]\s*|\s+|$)', '', text)

        def result(command=None, reason='unsupported_or_incomplete'):
            return CandidateReview(raw, command, reason)

        if not text:
            return result(reason='empty_text')
        if depth > 2:
            return result(reason='compound_depth_requires_review')

        # Keep an explicit preservation clause separate from positive actions.
        # In particular, "keep playing" must never become "resume" or "stop".
        preservation = re.fullmatch(
            r'(.+?)(?:,?\s+)(?:but keep the music playing|но не променяй звука)', text)
        if preservation:
            action = self._parse(preservation.group(1), depth + 1)
            if action.command is None or action.reason != 'supported':
                return result(reason='unresolved_compound_action')
            constraint = (CommandProposal('keep_playing', target='music')
                          if text.endswith('but keep the music playing')
                          else CommandProposal('preserve_volume'))
            return result(CommandProposal('constrained', steps=(action.command,),
                                          constraints=(constraint,)),
                          'state_constraint_requires_context')

        # Explicit order only; no inferred order from "and", "after" or context.
        clauses = re.split(r',?\s+(?:then|после)\s+', text)
        if len(clauses) > 1:
            if len(clauses) > 2:
                return result(reason='too_many_actions')
            parsed = tuple(self._parse(clause, depth + 1) for clause in clauses)
            if any(c.command is None or c.reason != 'supported' for c in parsed):
                return result(reason='unresolved_compound_action')
            return result(CommandProposal('sequence', steps=tuple(c.command for c in parsed)),
                          'supported')
        if re.search(r"\b(?:не|недей|без|not|never|without|don't|dont|cannot|can't)\b", text):
            return result(reason='negation_requires_review')
        if re.search(r'\b(?:ако|когато|освен|после|преди|след|но|if|when|unless|then|before|after|but|keep)\b|[;?]', text):
            return result(reason='condition_or_sequence_requires_review')

        exact = {
            'спри музиката': 'stop_media', 'stop the music': 'stop_media',
            'пауза': 'pause_media', 'pause the music': 'pause_media',
            'продължи музиката': 'resume_media', 'resume the music': 'resume_media',
            'следваща песен': 'next_track', 'next song': 'next_track',
            'предишна песен': 'previous_track', 'previous song': 'previous_track',
            'рестартирай песента': 'restart_track', 'restart the song': 'restart_track',
            'намали звука': 'volume_down', 'turn down the volume': 'volume_down',
            'увеличи звука': 'volume_up', 'turn up the volume': 'volume_up',
        }
        if text in exact:
            return result(CommandProposal(exact[text]), 'supported')
        volume = re.fullmatch(
            r'(?:задай|настрой|намали|увеличи) (?:силата на )?звука (?:на|до) (.+?)(?:\s*%| процента)|'
            r'set (?:the )?volume to (.+?)(?:\s*%| percent)', text)
        if volume:
            value = percent_value(volume.group(1) or volume.group(2))
            if value is None:
                return result(reason='invalid_or_unsupported_number')
            if text.startswith(('намали ', 'увеличи ')):
                return result(reason='directional_value_requires_context')
            return result(CommandProposal('set_volume', value=value), 'supported')
        if re.search(r'\b(?:и|and)\b', text):
            return result(reason='multiple_actions_or_unparsed_text')
        device = re.fullmatch(r'(включи|изключи|turn on|turn off|switch on|switch off) (.+)', text)
        if device:
            verb, target = device.groups()
            if re.search(r'[.!,:]|\b(?:включи|изключи|спри|пусни|turn|switch|stop|play|pause)\b', target):
                return result(reason='multiple_actions_or_unparsed_text')
            return result(CommandProposal('turn_on' if verb in ('включи', 'turn on', 'switch on')
                                           else 'turn_off', target=target), 'supported')
        media = re.fullmatch(r'(?:пусни|play)\s+(.+)', text)
        if media:
            return result(CommandProposal('play_media', query=media.group(1)),
                          'media_query_requires_resolution')
        return result()
