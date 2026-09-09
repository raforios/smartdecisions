'''
    Resolves a free-text institution name to the canonical catalog slug, reusing
    the same acronym/name/heuristic matching used for the first consolidation.
    Returns the official slug when matched, else None (caller keeps the raw text
    and create_institutions_from_participants will register it).
'''
import re
import unicodedata


def norm(text):
    t = ''.join(c for c in unicodedata.normalize('NFKD', str(text))
                if not unicodedata.combining(c)).upper()
    return re.sub(r'[^A-Z0-9]+', ' ', t).strip()


GOB = {'LA PAZ': 'gobernacion-de-la-paz', 'COCHABAMBA': 'gobernacion-de-cochabamba',
       'POTOSI': 'gobernacion-de-potosi', 'TARIJA': 'gobernacion-de-tarija',
       'ORURO': 'gobernacion-de-oruro', 'SANTA CRUZ': 'gobernacion-de-santa-cruz',
       'BENI': 'gobernacion-de-beni', 'PANDO': 'gobernacion-de-pando',
       'CHUQUISACA': 'gobernacion-de-chuquisaca'}

MANUAL = {
    'ONUDI BOLIVIA': 'organizacion-de-las-naciones-unidas-para-el-desarrollo-industrial-onudi',
    'ONUDI PLANET GOLD': 'organizacion-de-las-naciones-unidas-para-el-desarrollo-industrial-onudi',
    'PLANETGOLD BOLIVIA': 'organizacion-de-las-naciones-unidas-para-el-desarrollo-industrial-onudi',
    'PLANET GOLD': 'organizacion-de-las-naciones-unidas-para-el-desarrollo-industrial-onudi',
    'COMITE IMPULSOR DE LAS EMPRESAS MINERAS PRIVADAS DE BOLIVIA':
        'comite-impulsor-de-actores-mineros-privados-de-bolivia',
    'COMITE IMPULSOR DE EMPRESAS MINERAS PRIVADAS':
        'comite-impulsor-de-actores-mineros-privados-de-bolivia',
    'SINCHI WAYRA': 'Minera Sinchi Wayra',
}


class Resolver:
    '''Builds acronym/name indexes from the official catalog for fast matching.'''

    def __init__(self, official_items):
        self.acr, self.namekey = {}, {}
        for item in official_items:
            name = item.get('name') or ''
            match = re.search(r'\(([^)]+)\)\s*$', name)
            if match:
                self.acr[norm(match.group(1))] = item['id']
            self.namekey[norm(re.sub(r'\([^)]*\)', '', name))] = item['id']

    def resolve(self, raw):
        '''Returns the official slug for a raw institution text, or None.'''
        key = norm(raw)
        if not key:
            return None
        if key in MANUAL:
            return MANUAL[key]
        if key in self.acr:
            return self.acr[key]
        if key in self.namekey:
            return self.namekey[key]
        if 'SENADOR' in key:
            return 'camara-de-senadores'
        if 'GOBIERNO AUTONOMO DEPARTAMENTAL DE' in key or 'GOBERNACION DE' in key:
            for dep, slug in GOB.items():
                if dep in key:
                    return slug
        if 'MINISTERIO DE ECONOMIA' in key:
            return 'ministerio-de-economia-y-finanzas-publicas'
        if 'MINISTERIO DE MINERIA' in key:
            return 'ministerio-de-mineria-y-metalurgia-equipo-tecnico-y-legal'
        if 'MINISTERIO DE TURISMO' in key:
            return 'ministerio-de-turismo-sostenible-culturas-folklore-y-gastronomia'
        if 'EMPRESARIOS PRIVADOS' in key and 'ORURO' in key:
            return 'federacion-de-empresarios-privados-de-oruro-fepo'
        if 'ALCHEMY' in key:
            return 'empresa-minera-alchemy-s-r-l'
        for acronym, slug in self.acr.items():
            if acronym and (f' {acronym} ' in f' {key} ' or key == acronym):
                return slug
        return None
