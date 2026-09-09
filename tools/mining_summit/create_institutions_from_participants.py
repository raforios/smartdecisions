'''
    Registers the catalog institutions referenced by the bulk-loaded participants
    so their name resolves in the app (the participant->institution_name join is
    by institution id). One catalog entry per distinct participant.institution_id.

    The category is a best-effort heuristic (cosmetic: the role lives on each
    person now). cupos defaults to the number of participants of the institution.

    Usage:
      python create_institutions_from_participants.py            # DRY-RUN
      python create_institutions_from_participants.py --commit     # writes catalog
'''
import re
import sys
import unicodedata
from collections import Counter

import boto3

REGION = 'us-east-1'
PARTICIPANTS_TABLE = 'mining_summit_participants'
INSTITUTIONS_TABLE = 'mining_summit_institutions'


def norm(text):
    ascii_text = ''.join(ch for ch in unicodedata.normalize('NFKD', str(text))
                         if not unicodedata.combining(ch)).lower()
    return re.sub(r'\s+', ' ', ascii_text).strip()


def guess_category(name):
    '''Best-effort mapping of a free-text institution to a valid category enum.'''
    key = norm(name)
    if 'ministerio' in key and 'mineria' in key:
        return 'ORGANIZADOR / ENTE RECTOR'
    if 'ministerio' in key or 'viceministerio' in key:
        return 'INSTITUCIONES PÚBLICAS - NIVEL CENTRAL'
    if any(w in key for w in ('gobernacion', 'gobierno autonomo', 'gad ',
                              'secretaria departamental', 'secretario departamental')):
        return 'GOBIERNOS AUTÓNOMOS DEPARTAMENTALES'
    if any(w in key for w in ('senador', 'diputad', 'camara de senadores',
                              'camara de diputados', 'asamblea legislativa',
                              'organo legislativo')):
        return 'ÓRGANO LEGISLATIVO'
    if any(w in key for w in ('universidad', 'academ', 'investigacion')):
        return 'SECTOR ACADÉMICO Y DE INVESTIGACIÓN'
    if any(w in key for w in ('embajada', 'consulado', 'cooperacion', 'jica',
                              'onudi', 'banco mundial', 'agencia', 'union europea',
                              'planetgold', 'pnud', 'finning')):
        return 'COOPERACIÓN Y APOYO LOGÍSTICO'
    if any(w in key for w in ('camara', 'federacion', 'confederacion',
                              'asociacion', 'sociedad', 'colegio')):
        return 'CÁMARAS INDUSTRIALES Y EMPRESARIALES'
    return 'ACTORES PRODUCTIVOS MINEROS'


def scan_all(table):
    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get('Items', []))
        if 'LastEvaluatedKey' not in resp:
            return items
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']


def main():
    commit = '--commit' in sys.argv[1:]
    dynamodb = boto3.resource('dynamodb', region_name=REGION)

    counts = Counter()
    for person in scan_all(dynamodb.Table(PARTICIPANTS_TABLE)):
        inst = (person.get('institution_id') or '').strip()
        if inst:
            counts[inst] += 1

    existing = {inst['id'] for inst in scan_all(dynamodb.Table(INSTITUTIONS_TABLE))}
    to_create = {name: n for name, n in counts.items() if name not in existing}

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==')
    print(f'Instituciones distintas en participantes: {len(counts)}')
    print(f'Ya en el catálogo: {len(counts) - len(to_create)}  |  a crear: {len(to_create)}')
    by_cat = Counter(guess_category(n) for n in to_create)
    for cat, n in by_cat.most_common():
        print(f'   {cat}: {n}')
    print('Muestras:')
    for name in list(to_create)[:8]:
        print(f'   [{guess_category(name)}] {name!r} (cupos={to_create[name]})')

    if not commit:
        print('\nDRY-RUN: no se creó nada. Re-ejecuta con --commit.')
        return

    table = dynamodb.Table(INSTITUTIONS_TABLE)
    with table.batch_writer(overwrite_by_pkeys=['id']) as batch:
        for name, cupos in to_create.items():
            batch.put_item(Item={
                'id': name,
                'name': name,
                'abbreviation': None,
                'category': guess_category(name),
                'cupos': int(cupos),
            })
    print(f'\nCreadas {len(to_create)} instituciones en el catálogo.')


if __name__ == '__main__':
    main()
