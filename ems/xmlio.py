"""Bounded-memory MARCXML reader; no trimming of MARC text or indicators."""
import hashlib
import json
from pathlib import Path

from defusedxml.ElementTree import iterparse

NS = 'http://www.loc.gov/MARC21/slim'
Q = '{' + NS + '}'


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(dumps(value).encode('utf-8')).hexdigest()


def file_sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def records(path):
    """Yield source ordinal and a canonical, ordered lossless MARC field structure.

    XML comments, prefix spelling, attribute order, and formatting whitespace
    between elements are retained in source.xml rather than in the relational view.
    DTDs/entities and non-MARC shapes are rejected, not silently skipped.
    """
    with Path(path).open('rb') as stream:
        parser = iterparse(stream, events=('start', 'end'), forbid_dtd=True,
                           forbid_entities=True, forbid_external=True)
        depth, root, ordinal = 0, None, 0
        for event, element in parser:
            if event == 'start':
                depth += 1
                if depth == 1:
                    if element.tag != Q + 'collection':
                        raise ValueError('Oodati MARC21 collection-juurt ja MARC21/slim nimeruumi; HTML pole XML-andmestik.')
                    root = element
                elif depth == 2 and element.tag != Q + 'record':
                    raise ValueError(f'Tundmatu collection-alamelement: {element.tag}')
                continue
            if depth == 2:
                ordinal += 1
                fields = []
                for field in element:
                    kind = field.tag.removeprefix(Q)
                    if kind not in ('leader', 'controlfield', 'datafield') or field.tag != Q + kind:
                        raise ValueError(f'Tundmatu MARC-väli kirjes {ordinal}: {field.tag}')
                    if kind != 'datafield' and len(field):
                        raise ValueError(f'Pesastatud kontrollväli kirjes {ordinal}')
                    subs = []
                    for sub in field:
                        if sub.tag != Q + 'subfield' or len(sub):
                            raise ValueError(f'Tundmatu alamvälja struktuur kirjes {ordinal}')
                        subs.append({'code': sub.get('code'), 'value': sub.text or '',
                                     'attributes': dict(sub.attrib)})
                    fields.append({'kind': kind, 'tag': field.get('tag'),
                                   'ind1': field.get('ind1'), 'ind2': field.get('ind2'),
                                   'value': field.text or '' if kind != 'datafield' else None,
                                   'attributes': dict(field.attrib), 'subfields': subs})
                yield ordinal, {'attributes': dict(element.attrib), 'fields': fields}
                # clear() alone leaves one empty record per source row in the root.
                root.remove(element)
                element.clear()
            depth -= 1
        if not ordinal:
            raise ValueError('XML ei sisalda ühtegi MARC-kirjet.')
