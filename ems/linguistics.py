"""One local EstNLTK/Vabamorf resolver; original offsets survive NFC changes."""
from dataclasses import dataclass
from functools import lru_cache
import importlib.metadata
from pathlib import Path
import threading
import unicodedata

from .storage import EMSDataError
from .xmlio import digest, dumps, file_sha256

NORMALIZER_VERSION = 'nfc-casefold-token-v1'
MORPH_SETTINGS = dict(disambiguate=True, guess=True, propername=True, phonetic=False,
                      compound=True, stem=False, slang_lex=False, use_reorderer=True,
                      predisambiguate=False, postdisambiguate=False)


def normalize(text):
    return unicodedata.normalize('NFC', text).casefold()


def key(tokens):
    return dumps(list(tokens))


@lru_cache(maxsize=1)
def signature():
    import estnltk
    import nltk
    try:
        punkt = Path(str(nltk.data.find('tokenizers/punkt_tab/estonian')))
    except LookupError as exc:
        raise EMSDataError('Puudub NLTK punkt_tab ressurss. Paigalda enne offline-kasutust: '
                           'python -m nltk.downloader punkt_tab') from exc
    files = {f'punkt_tab/estonian/{p.name}': file_sha256(p) for p in sorted(punkt.glob('*')) if p.is_file()}
    lexicons = Path(estnltk.__file__).parent / 'vabamorf' / 'dct'
    files.update({f'vabamorf/{p.relative_to(lexicons).as_posix()}': file_sha256(p)
                  for p in sorted(lexicons.rglob('*.dct'))})
    if len(files) < 8:
        raise EMSDataError('Puudulikud NLTK/Vabamorfi kohalikud keeleressursid.')
    return {'normalizer': NORMALIZER_VERSION, 'morphology': MORPH_SETTINGS,
            'ambiguity_policy': 'sorted_distinct_normalized_lemmas_first; no Cartesian expansion',
            'pos_scoring': 'aligned_disambiguated_pos; match=+2; conflict=-2; uncertain=0; uncertain_weight=0.5',
            'single_label_pos_policy': 'retain all nondisambiguated POS alternatives',
            'packages': {n: importlib.metadata.version(n) for n in ('estnltk','estnltk-core','nltk','regex')},
            'resources_sha256': files}


@dataclass(frozen=True)
class Token:
    start: int
    end: int
    text: str
    surface: str
    lemma: str
    options: tuple
    pos_options: tuple = ()

    @property
    def lexical(self):
        return any(c.isalnum() for c in self.surface)


@dataclass
class Analysis:
    sentences: list
    ambiguous_tokens: int = 0
    fallback_tokens: int = 0

    @property
    def tokens(self):
        return [token for sentence in self.sentences for token in sentence]


class Analyzer:
    def __init__(self):
        signature()  # Check resources BEFORE EstNLTK can attempt automatic downloads.
        from estnltk.default_resolver import make_resolver
        self.resolver = make_resolver(**MORPH_SETTINGS)
        self.pos_resolver = None
        self.lock = threading.RLock()

    def possible_pos(self, original):
        """Return raw POS alternatives for a short, contextless EMS label."""
        from estnltk import Text
        import regex
        normalized=''.join(unicodedata.normalize('NFC',cluster.group())
                            for cluster in regex.finditer(r'\X',original))
        text=Text(normalized)
        with self.lock:
            if self.pos_resolver is None:
                from estnltk.default_resolver import make_resolver
                self.pos_resolver=make_resolver(**{**MORPH_SETTINGS,'disambiguate':False})
            text.tag_layer('morph_analysis',resolver=self.pos_resolver)
        return tuple(sorted({pos for span in text.morph_analysis for pos in span.partofspeech if pos}))

    def analyze(self, original, morphology=True):
        from estnltk import Text
        import regex
        # Grapheme mapping handles decomposed Estonian letters without shifting snippets.
        normalized, positions = [], []
        for cluster in regex.finditer(r'\X', original):
            nfc = unicodedata.normalize('NFC', cluster.group())
            normalized.append(nfc)
            positions.extend([(cluster.start(), cluster.end())] * len(nfc))
        text = Text(''.join(normalized))
        with self.lock:
            text.tag_layer(['morph_analysis'] if morphology else ['sentences'], resolver=self.resolver)
        analyses = {(span.start, span.end): (list(span.lemma), list(span.partofspeech))
                    for span in text.morph_analysis} if morphology else {}
        result = Analysis([])
        for sentence in text.sentences:
            tokens = []
            for word in sentence.words:
                start, end = positions[word.start][0], positions[word.end-1][1]
                raw = original[start:end]
                surface = normalize(raw)
                lemmas, pos = analyses.get((word.start,word.end), ([], []))
                options = tuple(sorted({normalize(x) for x in lemmas if x}))
                pos_options = tuple(sorted({x for x in pos if x}))
                if morphology and not options:
                    result.fallback_tokens += 1
                if len(options) > 1:
                    result.ambiguous_tokens += 1
                tokens.append(Token(start, end, raw, surface, options[0] if options else surface,
                                    options, pos_options))
            if tokens:
                result.sentences.append(tokens)
        return result


@lru_cache(maxsize=1)
def analyzer():
    return Analyzer()


@lru_cache(maxsize=8192)
def analyze_label(text, language):
    analysis = analyzer().analyze(text, morphology=language == 'et')
    tokens = analysis.tokens
    surfaces = [t.surface for t in tokens]
    lemmas = [t.lemma for t in tokens] if language == 'et' else None
    pos_options=[list(t.pos_options) for t in tokens] if language == 'et' else None
    if language=='et' and len(tokens)==1:
        pos_options=[list(analyzer().possible_pos(text))]
    warnings = []
    if analysis.ambiguous_tokens:
        warnings.append(f'ambiguous_tokens={analysis.ambiguous_tokens}')
    if analysis.fallback_tokens:
        warnings.append(f'fallback_tokens={analysis.fallback_tokens}')
    if len(analysis.sentences) > 1:
        warnings.append('multiple_sentences')
    return dict(normalized=' '.join(surfaces), surface_key=key(surfaces), lemmas=lemmas,
                lemma_key=key(lemmas) if lemmas is not None else None,
                lemma_options=[list(t.options) for t in tokens] if language == 'et' else None,
                pos_options=pos_options,
                token_count=len(tokens), analysis_warnings=warnings)
