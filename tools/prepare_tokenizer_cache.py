"""Verify public tokenizer assets; optionally download them without credentials."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

ASSETS = {
    'cl100k_base': '223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7',
    'o200k_base': '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Fetch missing public assets; no provider inference')
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / 'outputs/token-cache'
    for name, expected in ASSETS.items():
        url = f'https://openaipublic.blob.core.windows.net/encodings/{name}.tiktoken'
        target = directory / hashlib.sha1(url.encode()).hexdigest()
        if target.exists():
            data = target.read_bytes()
        elif args.download:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=30) as response:
                data = response.read()
        else:
            raise SystemExit(f'Missing public tokenizer {name}; rerun with --download during setup')
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit(f'Checksum mismatch for {name}; existing bytes left unchanged')
        if not target.exists():
            directory.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        print(f'PASS {name} SHA256 {expected}')


if __name__ == '__main__':
    main()
