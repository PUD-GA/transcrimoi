"""Point d'entrée PyInstaller, sans importer les outils de développement."""
import argparse
from pathlib import Path
import sys

if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        import json
        parser = argparse.ArgumentParser()
        parser.add_argument("--self-test", required=True, type=Path)
        args = parser.parse_args()
        try:
            from transcrimoi.desktop_check import check_desktop
            check_desktop(args.self_test)
        except Exception as error:
            # Pas de dialogue d'erreur PyInstaller bloquant une CI windowed.
            # Le diagnostic normal écrit déjà son rapport, sauf échec d'import Qt.
            if not args.self_test.exists():
                args.self_test.mkdir(parents=True)
                (args.self_test / "report.json").write_text(
                    json.dumps({"status": "failed", "error": str(error)}), encoding="utf-8")
            raise SystemExit(1)
    else:
        from transcrimoi.gui import main
        raise SystemExit(main())
