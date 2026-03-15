#!/usr/bin/env python3
import sys


def main() -> int:
    if len(sys.argv) != 2:
        return 1

    pdf_path = sys.argv[1]

    try:
        from pypdf import PdfReader
    except Exception:
        return 1

    try:
        reader = PdfReader(pdf_path)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n".join(page for page in pages if page).strip()
        if not text:
            return 1
        sys.stdout.write(text)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
