from __future__ import annotations

import argparse
import json
from pathlib import Path

from castdub.doctor import inspect_environment
from castdub.jianying import import_draft
from castdub.jianying_export import export_localized_draft
from castdub.pilot import run_pilot
from castdub.project import create_project, load_rights


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="castdub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Inspect local capabilities without installing or downloading"
    )
    doctor_parser.add_argument("--model-path", type=Path)

    init_parser = subparsers.add_parser(
        "init-project", help="Create a private, rights-gated localisation job"
    )
    init_parser.add_argument("--workspace", type=Path, required=True)
    init_parser.add_argument("--slug", required=True)
    init_parser.add_argument("--rights", type=Path, required=True)
    init_parser.add_argument("--target-language", default="en-US")

    import_parser = subparsers.add_parser(
        "import-jianying", help="Import a Jianying draft into editable manifests"
    )
    import_parser.add_argument("--draft-root", type=Path, required=True)
    import_parser.add_argument("--output-dir", type=Path, required=True)
    import_parser.add_argument("--source-video", type=Path)

    pilot_parser = subparsers.add_parser(
        "run-pilot", help="Render a configured Jianying localisation pilot"
    )
    pilot_parser.add_argument("--project-root", type=Path, required=True)
    pilot_parser.add_argument("--config", type=Path, required=True)
    pilot_parser.add_argument("--work-dir", type=Path, required=True)

    export_parser = subparsers.add_parser(
        "export-jianying", help="Create a localized Jianying draft copy"
    )
    export_parser.add_argument("--source-draft", type=Path, required=True)
    export_parser.add_argument("--output-draft", type=Path, required=True)
    export_parser.add_argument("--dialogue-wav", type=Path, required=True)
    export_parser.add_argument("--qc-report", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        print(
            json.dumps(
                inspect_environment(model_path=args.model_path),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    elif args.command == "init-project":
        rights = load_rights(args.rights)
        project_dir = create_project(
            workspace=args.workspace,
            slug=args.slug,
            target_language=args.target_language,
            rights=rights,
        )
        print(project_dir)
    elif args.command == "import-jianying":
        report = import_draft(
            draft_root=args.draft_root,
            output_dir=args.output_dir,
            source_video=args.source_video,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "run-pilot":
        outputs = run_pilot(
            project_root=args.project_root,
            config_path=args.config,
            work_dir=args.work_dir,
        )
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
    elif args.command == "export-jianying":
        report = export_localized_draft(
            source_draft_root=args.source_draft,
            output_draft_root=args.output_draft,
            dialogue_wav=args.dialogue_wav,
            qc_report=args.qc_report,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
