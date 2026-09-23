'''
    Turns a PDF into Markdown so it can be read in pieces instead of whole.

    Why it exists: reading a PDF directly renders each page as an image, and a
    normative of two hundred pages costs a fortune in tokens before anyone has
    found the article they were looking for. The text of that same PDF is a few
    hundred kilobytes, and once it is a `.md` file it can be grepped, and only
    the twenty lines that matter get read.

    Every page is written under a `## Página N` heading, which is what makes
    the partial read possible: find the page with `grep -n`, then read only
    that range. The file also opens with an index of the headings it detected,
    so the table of contents is visible without scrolling the whole document.

    Usage:
        python tools/pdf_to_markdown.py RND11.pdf
        python tools/pdf_to_markdown.py RND11.pdf --output docs/rnd11.md
        python tools/pdf_to_markdown.py RND11.pdf --pages 1-40

    Then read what you need instead of the whole file:
        grep -n 'Código de Control' rnd11.md
        sed -n '820,880p' rnd11.md
'''
import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import fitz

# A line that looks like a heading in a Bolivian normative: an article, a
# chapter, a numbered section. Used only to build the index at the top.
HEADING = re.compile(
    r'^\s*(ART[ÍI]CULO\s+\d+|CAP[ÍI]TULO\s+[IVXLC]+|SECCI[ÓO]N\s+[IVXLC]+|'
    r'ANEXO\s+\w+|DISPOSICI[ÓO]N\w*\s+\w+|\d+\.\d*\s+[A-ZÁÉÍÓÚÑ][^\n]{4,80})\s*$',
    re.IGNORECASE
)


def parse_pages(value: Optional[str], total: int) -> Tuple[int, int]:
    '''
        The page range to convert, as a half-open pair of indexes.

        Args:
            value (str | None): "12", "1-40", or None for everything.
            total (int): Pages the document has.

        Returns:
            Tuple[int, int]: (first index, last index), zero-based.

        Raises:
            ValueError: The range is not readable or falls outside the document.
    '''
    if not value:
        return 0, total
    parts = value.split('-', 1)
    first = int(parts[0])
    last = int(parts[1]) if len(parts) == 2 else first
    if first < 1 or last < first or last > total:
        raise ValueError(f'Rango fuera del documento: 1-{total}.')
    return first - 1, last


def page_markdown(
    page: fitz.Page,
    number: int
) -> str:
    '''
        One page as Markdown, under its own heading.

        Args:
            page (fitz.Page): The page to read.
            number (int): Page number as the reader counts it, from 1.

        Returns:
            str: The page text under a `## Página N` heading.
    '''
    text = page.get_text('text').strip()
    # Hard-wrapped columns turn into ragged lines; collapsing the blank runs
    # keeps the paragraphs readable without reflowing what the PDF laid out.
    text = re.sub(r'\n{3,}', '\n\n', text)
    return f'## Página {number}\n\n{text}\n'


def build_index(pages: List[str]) -> str:
    '''
        The headings found, with the page each one is on.

        Args:
            pages (List[str]): The already rendered pages.

        Returns:
            str: A Markdown list, or an empty string when nothing looked like
                a heading.
    '''
    entries: List[str] = []
    for block in pages:
        number = block.split('\n', 1)[0].replace('## Página ', '')
        for line in block.splitlines()[1:]:
            if HEADING.match(line):
                entries.append(f'- p. {number} — {line.strip()}')
    if not entries:
        return ''
    return '## Índice detectado\n\n' + '\n'.join(entries) + '\n'


def convert(
    source: Path,
    output: Path,
    pages: Optional[str] = None
) -> int:
    '''
        Writes the Markdown of a PDF.

        Args:
            source (Path): The PDF to read.
            output (Path): The Markdown file to write.
            pages (str | None): Range to convert; everything when absent.

        Returns:
            int: Characters written.
    '''
    with fitz.open(source) as document:
        first, last = parse_pages(pages, document.page_count)
        rendered = [page_markdown(document[index], index + 1)
                    for index in range(first, last)]

    header = (f'# {source.stem}\n\n'
              f'Convertido de `{source.name}` · páginas {first + 1}–{last} '
              f'de {last if not pages else "?"}.\n\n')
    body = header + build_index(rendered) + '\n---\n\n' + '\n'.join(rendered)
    output.write_text(body, encoding = 'utf-8')
    return len(body)


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success, 1 when the source cannot be read.
    '''
    parser = argparse.ArgumentParser(
        description = 'Convierte un PDF a Markdown para leerlo por partes.'
    )
    parser.add_argument('source', type = Path, help = 'Archivo PDF de entrada.')
    parser.add_argument('--output', type = Path, default = None,
                        help = 'Archivo .md de salida; junto al PDF por defecto.')
    parser.add_argument('--pages', default = None,
                        help = 'Rango de páginas, por ejemplo 1-40.')
    args = parser.parse_args()

    if not args.source.is_file():
        print(f'No existe el archivo: {args.source}', file = sys.stderr)
        return 1

    output = args.output or args.source.with_suffix('.md')
    try:
        written = convert(args.source, output, args.pages)
    except (ValueError, RuntimeError) as error:
        print(f'No se pudo convertir: {error}', file = sys.stderr)
        return 1

    print(f'{output} · {written:,} caracteres')
    print('Leelo por partes:  grep -n "<término>" ' + str(output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
