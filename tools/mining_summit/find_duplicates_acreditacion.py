'''
    Finds CIs that appear more than once across the accreditation Excel files and
    writes every occurrence to a CSV so the operator can review real duplicates
    vs data-entry errors. Read-only (no DB access).
'''
import csv
import os
import warnings
from collections import defaultdict

import bulk_load_acreditacion as loader

warnings.filterwarnings('ignore')

OUT_CSV = '/Users/rafael/Work/projects/back/SmartBear/data/duplicados_ci_acreditacion.csv'
HEADERS = ['ci', 'n_ocurrencias', 'source_file', 'first_name', 'last_name',
           'institution', 'email', 'phone', 'department', 'eje']


def main():
    occurrences = defaultdict(list)
    files = sorted(f for f in os.listdir(loader.FOLDER)
                   if f.lower().endswith(('.xlsx', '.xls')))
    for name in files:
        try:
            rows = list(loader.read_rows(os.path.join(loader.FOLDER, name)))
        except Exception:
            continue
        for _row_no, values in rows:
            ci = loader.cell(values.get('ci'))
            if not ci:
                continue
            occurrences[ci].append({
                'source_file': name,
                'first_name': loader.cell(values.get('first_name')),
                'last_name': loader.cell(values.get('last_name')),
                'institution': loader.cell(values.get('institution'))
                or loader.institution_from_filename(name),
                'email': loader.cell(values.get('email')),
                'phone': loader.cell(values.get('phone')),
                'department': loader.cell(values.get('department')),
                'eje': loader.cell(values.get('axis')),
            })

    dups = {ci: occ for ci, occ in occurrences.items() if len(occ) > 1}
    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, extrasaction='ignore')
        writer.writeheader()
        for ci in sorted(dups):
            for occ in dups[ci]:
                writer.writerow({'ci': ci, 'n_ocurrencias': len(dups[ci]), **occ})

    total_rows = sum(len(occ) for occ in dups.values())
    print(f'CIs duplicados: {len(dups)}  (ocurrencias totales: {total_rows})')
    print(f'CSV -> {OUT_CSV}')


if __name__ == '__main__':
    main()
