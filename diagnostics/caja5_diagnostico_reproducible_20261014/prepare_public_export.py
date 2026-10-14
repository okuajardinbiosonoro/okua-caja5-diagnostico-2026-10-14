"""Prepare a byte-preserving public snapshot; never send commands to devices."""
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
EXPORT = Path('C:/Users/jogoa/AppData/Local/OKUA/exports/okua-caja5-diagnostico-2026-10-14')
ASSET = EXPORT.parent / 'OKUA_Caja5_datos_crudos_2026-10-14.zip'
SHARD_BYTES = 32 * 1024 * 1024
NOW = datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


if EXPORT.exists():
    raise RuntimeError('Export already exists; inspect before a retry')

observation = {
    'recorded_at_utc': NOW,
    'source': 'Direct user message after the coordinated tests ended',
    'operator_statement': 'En las pruebas que hice mientras tú cargabas o hacías demás procesos aparte de las pruebas que registraste, el mejor funcionamiento obtenido fue con EB5 negro enterrado',
    'planned_operating_condition': {
        'black_EB5': 'Enterrado en sustrato de maceta EB5',
        'firmware_requirement': 'Diseñar y evaluar la próxima versión para funcionar con esta configuración física',
    },
    'classification': 'Observación del operador en pruebas adicionales sin marcas temporales coordinadas',
    'use': 'Requisito de funcionamiento y evidencia cualitativa. Las grabaciones pueden contener eventos de esas pruebas, pero sus modalidades e instantes exactos no están etiquetados',
    'preserve': 'No sustituye ni borra la confirmación y las observaciones de la corrida coordinada en tierra',
}
save(ROOT / 'operator_addendum_grounded_EB5.json', observation)
handoff_path = ROOT / 'firmware_remote_handoff.json'
shutil.copy2(handoff_path, ROOT / 'firmware_remote_handoff_before_ground_preference.json')
handoff = json.loads(handoff_path.read_text(encoding='utf-8'))
handoff['planned_operating_condition'] = observation['planned_operating_condition']
handoff['latest_operator_observation'] = observation
handoff['next_remote_session'][0]['work'] += '. Tomar negro EB5 enterrado como configuración prevista; el usuario reporta que fue la de mejor funcionamiento en pruebas adicionales'
save(handoff_path, handoff)

# Read existing credentials only to detect an accidental occurrence in export data.
# Neither values nor matched text are printed or written to the export.
sys.path.insert(0, str(ROOT.parent))
from caja5_ota_probe import get_secrets
secret_bytes, api_token = get_secrets()
known_secrets = [s for s in [secret_bytes, api_token.encode('utf-8')] if len(s) >= 8]
patterns = [
    re.compile(rb'gh[opusr]_[A-Za-z0-9_]{30,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'(?i)["\'](?:password|passwd|api_key|access_token|refresh_token|authorization)["\']\s*:\s*["\'][^"\'\r\n]{8,}["\']'),
]

sources = []
excluded = []
for file in sorted(ROOT.rglob('*')):
    if not file.is_file():
        continue
    if '__pycache__' in file.parts:
        excluded.append({'path': str(file.relative_to(WORKSPACE)), 'reason': 'Caché de bytecode Python; no contiene registros de medición'})
        continue
    sources.append((file, file.relative_to(WORKSPACE)))
hardware = ROOT.parent / 'hardware_actual_20261014'
for file in sorted(hardware.rglob('*')):
    if file.is_file() and '__pycache__' not in file.parts:
        sources.append((file, file.relative_to(WORKSPACE)))
for name in ['caja5_signal_check_20261010.py', 'caja5_ota_probe.py']:
    file = ROOT.parent / name
    sources.append((file, file.relative_to(WORKSPACE)))
hardware_zip = Path('C:/Users/jogoa/Downloads/OKUA_HARDWARE_ACTUAL_PARA_AGENTE.zip')
if hardware_zip.exists():
    sources.append((hardware_zip, Path('hardware_original/OKUA_HARDWARE_ACTUAL_PARA_AGENTE.zip')))

findings = []
for file, logical in sources:
    # Small context files may be binary; the same checks are performed on bytes.
    with file.open('rb') as stream:
        previous = b''
        while True:
            chunk = stream.read(4 * 1024 * 1024)
            if not chunk:
                break
            checked = previous + chunk
            if any(s in checked for s in known_secrets) or any(p.search(checked) for p in patterns):
                findings.append(str(logical))
                break
            previous = checked[-4096:]
if findings:
    print(json.dumps({'credential_scan': 'blocked', 'files': findings}, ensure_ascii=True))
    raise RuntimeError('A possible credential was found; no repository payload has been created')

EXPORT.mkdir(parents=True)
manifest = {
    'created_at_utc': NOW,
    'scope': 'Todos los registros de captura de la sesión 2026-10-14, incluidos arranque inicial, periodos fuera de ensayos, ensayos anulados y marcas originales; más metodología, observaciones, análisis y hardware de referencia',
    'record_policy': 'Sin eliminar registros, modificar valores, normalizar finales de línea, reordenar ni volver a serializar los archivos crudos',
    'storage': 'signals.jsonl grande se divide por límites de línea en partes ordenadas menores de 32 MiB. Su concatenación reproduce exactamente el archivo original',
    'excluded_files': excluded,
    'credential_check': 'Sin coincidencias con credenciales operativas conocidas ni con patrones comprobados; no se publican archivos de configuración de credenciales externos a la sesión',
    'files': [],
}

for source, logical in sources:
    target = EXPORT / logical
    target.parent.mkdir(parents=True, exist_ok=True)
    source_size = source.stat().st_size
    is_raw_signal = source.name == 'signals.jsonl'
    if source_size >= SHARD_BYTES:
        parts_dir = target.parent / (target.name + '.parts')
        parts_dir.mkdir()
        original_hash = hashlib.sha256()
        parts = []
        out = None
        part_size = 0
        part_hash = None
        part_path = None
        line_count = 0

        def finish_part():
            if out is not None:
                out.close()
                parts.append({'path': part_path.relative_to(EXPORT).as_posix(), 'bytes': part_size, 'sha256': part_hash.hexdigest()})

        with source.open('rb') as stream:
            for line in stream:
                if len(line) > SHARD_BYTES:
                    raise RuntimeError('A single record is larger than the shard limit')
                if out is None or part_size + len(line) > SHARD_BYTES:
                    finish_part()
                    part_path = parts_dir / f'part-{len(parts) + 1:05d}.jsonl'
                    out = part_path.open('wb')
                    part_size = 0
                    part_hash = hashlib.sha256()
                out.write(line)
                part_hash.update(line)
                original_hash.update(line)
                part_size += len(line)
                line_count += 1
        finish_part()
        entry = {'original_path': logical.as_posix(), 'bytes': source_size, 'sha256': original_hash.hexdigest(), 'storage': 'ordered_parts', 'parts': parts, 'lines': line_count}
        print(json.dumps({'prepared': logical.as_posix(), 'parts': len(parts), 'bytes': source_size}, ensure_ascii=True), flush=True)
    else:
        shutil.copy2(source, target)
        entry = {'original_path': logical.as_posix(), 'bytes': source_size, 'sha256': digest(target), 'storage': 'exact_file', 'path': logical.as_posix()}
    entry['raw_capture'] = is_raw_signal or source.name == 'markers.jsonl'
    manifest['files'].append(entry)

save(EXPORT / 'dataset_manifest.json', manifest)
(EXPORT / '.gitattributes').write_text('* -text\n', encoding='utf-8')
(EXPORT / '.gitignore').write_text('/restored/\n__pycache__/\n*.pyc\n', encoding='utf-8')

print(json.dumps({'stage': 'building_complete_original_zip'}, ensure_ascii=True), flush=True)
with zipfile.ZipFile(ASSET, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
    for source, logical in sources:
        archive.write(source, logical.as_posix())
    archive.write(EXPORT / 'dataset_manifest.json', 'dataset_manifest.json')

publication = {
    'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
    'local_repository': str(EXPORT),
    'release_asset': str(ASSET),
    'release_asset_bytes': ASSET.stat().st_size,
    'release_asset_sha256': digest(ASSET),
    'original_file_count': len(sources),
    'original_total_bytes': sum(x['bytes'] for x in manifest['files']),
    'status': 'Prepared locally; not yet published',
}
save(ROOT / 'public_export_preparation.json', publication)
save(EXPORT / 'release_asset_integrity.json', {
    'filename': ASSET.name,
    'bytes': publication['release_asset_bytes'],
    'sha256': publication['release_asset_sha256'],
    'contains': 'Archivos originales completos con las mismas rutas lógicas y SHA256 del manifiesto; incluido signals.jsonl sin dividir',
})
print(json.dumps(publication, ensure_ascii=True), flush=True)
