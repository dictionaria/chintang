from collections import ChainMap
import pathlib

from cldfbench import CLDFSpec, Dataset as BaseDataset

from pydictionaria.sfm_lib import Database as SFM
from pydictionaria import sfm2cldf


def reorganize(sfm):
    """Use this function if you need to manually add or remove entrys from the
    SFM data.

    Takes an SFM database as an argument and returns a modified SFM database.
    """
    return sfm


def _swap_lx_and_stem(marker, value, lx, stem):
    if marker == 'lx':
        return 'lx', stem
    elif marker == 'lc':
        return 'stem', lx
    else:
        return marker, value


def swap_stem_and_citation_form(entry):
    ps = entry.get('ps')
    reg = entry.get('reg')
    lc = entry.get('lc')
    if not lc or reg == 'ritual' or ps not in {'v', 'vi', 'vt', 'v2'}:
        return entry
    lx = entry.get('lx')
    return entry.__class__(
        _swap_lx_and_stem(marker, value, lx, lc)
        for marker, value in entry)


def _remove_none(marker, value, lx):
    if marker == 'ps' and value == 'none':
        if lx == 'adi':
            return 'ps', 'gm'
        elif lx in {'urra',  'ghoʔle'}:
            return 'ps', 'interj'
        else:
            print(lx)
            raise AssertionError('UNREACHABLE')
    else:
        return marker, value


def remove_none(entry):
    lx = entry.get('lx')
    return entry.__class__(
        _remove_none(marker, value, lx)
        for marker, value in entry)


POS_ERRATA = {
    'noun': 'n',
    'intj': 'interj',
    'vt; n': 'n',
    'v; n': 'n',
}


def normalise_pos(pair):
    if pair[0] == 'ps':
        return 'ps', POS_ERRATA.get(pair[1], pair[1])
    else:
        return pair


def preprocess(entry):
    """Use this function if you need to change the contents of an entry before
    any other processing.

    This is run on every entry in the SFM database.
    """
    if entry.get('ps') == 'v' or entry.get('lx') == 'SELF':
        return False
    entry = swap_stem_and_citation_form(entry)
    entry = remove_none(entry)
    entry = entry.__class__(map(normalise_pos, entry))
    if entry.get('lx') == 'samet' and not entry.get('ps'):
        entry.append(('ps', 'n'))
    return entry


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "chintang"

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return CLDFSpec(
            dir=self.cldf_dir,
            module='Dictionary',
            metadata_fname='cldf-metadata.json')

    def cmd_download(self, args):
        """
        Download files to the raw/ directory. You can use helpers methods of `self.raw_dir`, e.g.

        >>> self.raw_dir.download(url, fname)
        """

    def cmd_makecldf(self, args):
        """
        Convert the raw data to a CLDF dataset.

        >>> args.writer.objects['LanguageTable'].append(...)
        """

        # read data

        md = self.etc_dir.read_json('md.json')
        properties = md.get('properties') or {}
        language_name = md['language']['name']
        isocode = md['language']['isocode']
        language_id = md['language']['isocode']
        glottocode = md['language']['glottocode']

        marker_map = ChainMap(
            properties.get('marker_map') or {},
            sfm2cldf.DEFAULT_MARKER_MAP)
        entry_sep = properties.get('entry_sep') or sfm2cldf.DEFAULT_ENTRY_SEP
        sfm = SFM(
            self.raw_dir / 'db.sfm',
            marker_map=marker_map,
            entry_sep=entry_sep)

        examples = sfm2cldf.load_examples(self.raw_dir / 'examples.sfm')

        if (self.etc_dir / 'cdstar.json').exists():
            media_catalog = self.etc_dir.read_json('cdstar.json')
        else:
            media_catalog = {}

        # preprocessing

        sfm = reorganize(sfm)
        sfm.visit(preprocess)

        # processing

        with open(self.dir / 'cldf.log', 'w', encoding='utf-8') as log_file:
            log_name = f'{language_id}.cldf'
            cldf_log = sfm2cldf.make_log(log_name, log_file)

            entries, senses, examples, media = sfm2cldf.process_dataset(
                self.id, language_id, properties,
                sfm, examples, media_catalog=media_catalog,
                glosses_path=self.raw_dir / 'glosses.flextext',
                examples_log_path=self.dir / 'examples.log',
                glosses_log_path=self.dir / 'glosses.log',
                cldf_log=cldf_log)

            # Note: If you want to manipulate the generated CLDF tables before
            # writing them to disk, this would be a good place to do it.

            # cldf schema

            sfm2cldf.make_cldf_schema(
                args.writer.cldf, properties,
                entries, senses, examples, media)

            sfm2cldf.attach_column_titles(args.writer.cldf, properties)

            print(file=log_file)

            entries = sfm2cldf.ensure_required_columns(
                args.writer.cldf, 'EntryTable', entries, cldf_log)
            senses = sfm2cldf.ensure_required_columns(
                args.writer.cldf, 'SenseTable', senses, cldf_log)
            examples = sfm2cldf.ensure_required_columns(
                args.writer.cldf, 'ExampleTable', examples, cldf_log)
            media = sfm2cldf.ensure_required_columns(
                args.writer.cldf, 'MediaTable', media, cldf_log)

            entries = sfm2cldf.remove_senseless_entries(
                senses, entries, cldf_log)

        # output

        args.writer.cldf.properties['dc:creator'] = sfm2cldf.format_authors(
            md.get('authors') or ())

        language = {
            'ID': language_id,
            'Name': language_name,
            'ISO639P3code': isocode,
            'Glottocode': glottocode,
        }
        args.writer.objects['LanguageTable'] = [language]

        args.writer.objects['EntryTable'] = entries
        args.writer.objects['SenseTable'] = senses
        args.writer.objects['ExampleTable'] = examples
        args.writer.objects['MediaTable'] = media
