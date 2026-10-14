"""Restore or verify the original bytes described by dataset_manifest.json."""
import argparse
import hashlib
import json
from pathlib import Path


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Manifest path leaves the selected directory')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('restored'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'dataset_manifest.json').read_text(encoding='utf-8'))
    total = 0
    for entry in manifest['files']:
        pieces = entry['parts'] if entry['storage'] == 'ordered_parts' else [entry]
        destination = within(args.output.resolve(), entry['original_path'])
        if not args.verify_only and destination.exists():
            raise FileExistsError(f'Output already exists: {destination}')
        output = None
        complete_hash = hashlib.sha256()
        complete_size = 0
        try:
            if not args.verify_only:
                destination.parent.mkdir(parents=True, exist_ok=True)
                output = destination.open('xb')
            for piece in pieces:
                piece_hash = hashlib.sha256()
                piece_size = 0
                with within(root, piece['path']).open('rb') as stream:
                    for data in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        piece_hash.update(data)
                        complete_hash.update(data)
                        piece_size += len(data)
                        complete_size += len(data)
                        if output is not None:
                            output.write(data)
                if piece_size != piece['bytes'] or piece_hash.hexdigest() != piece['sha256']:
                    raise ValueError(f'Part verification failed: {piece["path"]}')
            if complete_size != entry['bytes'] or complete_hash.hexdigest() != entry['sha256']:
                raise ValueError(f'Original verification failed: {entry["original_path"]}')
        finally:
            if output is not None:
                output.close()
        total += complete_size
    print(json.dumps({'verified_original_files': len(manifest['files']), 'verified_bytes': total, 'mode': 'verify-only' if args.verify_only else 'restore'}))


if __name__ == '__main__':
    main()
