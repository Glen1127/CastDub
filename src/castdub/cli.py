from __future__ import annotations

import argparse
import json
from pathlib import Path

from castdub.demo import render_synthetic_demo
from castdub.doctor import inspect_environment
from castdub.jianying import import_draft
from castdub.jianying_export import export_localized_draft
from castdub.jobs import create_episode_job, get_episode_job
from castdub.pilot import run_pilot
from castdub.preflight import preflight_registered_job
from castdub.project import create_project, load_rights
from castdub.runner import import_registered_draft
from castdub.roles import approve_role_mapping
from castdub.reverse import run_reverse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="castdub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Inspect local capabilities without installing or downloading"
    )
    doctor_parser.add_argument("--model-path", type=Path)

    demo_parser = subparsers.add_parser(
        "demo", help="Render a synthetic three-character delivery without models"
    )
    demo_parser.add_argument("--output-dir", type=Path, required=True)

    start_parser = subparsers.add_parser(
        "start-episode", help="Register an authorised episode as a resumable job"
    )
    start_parser.add_argument("--store", type=Path, required=True)
    start_parser.add_argument("--series-id", required=True)
    start_parser.add_argument("--episode-id", required=True)
    start_parser.add_argument("--target-language", required=True)
    start_parser.add_argument(
        "--output-mode", choices=("editor", "final"), default="final"
    )
    start_parser.add_argument("--rights", type=Path, required=True)
    start_parser.add_argument("--draft-root", type=Path, required=True)
    start_parser.add_argument("--source-video", type=Path)

    status_parser = subparsers.add_parser(
        "job-status", help="Read compact persisted state for one episode job"
    )
    status_parser.add_argument("--store", type=Path, required=True)
    status_parser.add_argument("--job-id", required=True)

    preflight_parser = subparsers.add_parser(
        "preflight", help="Validate registered episode inputs and advance the job"
    )
    preflight_parser.add_argument("--store", type=Path, required=True)
    preflight_parser.add_argument("--job-id", required=True)
    preflight_parser.add_argument("--duration-tolerance-ms", type=int, default=1000)

    job_import_parser = subparsers.add_parser(
        "import-episode", help="Import a verified draft and stop for role approval"
    )
    job_import_parser.add_argument("--store", type=Path, required=True)
    job_import_parser.add_argument("--job-id", required=True)

    role_parser = subparsers.add_parser(
        "approve-roles", help="Validate role assignments and create translation work"
    )
    role_parser.add_argument("--store", type=Path, required=True)
    role_parser.add_argument("--job-id", required=True)
    role_parser.add_argument("--mapping", type=Path, required=True)

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

    reverse_parser = subparsers.add_parser(
        "reverse", help="Reverse a finished video into an editable multimodal blueprint"
    )
    reverse_parser.add_argument("video", type=Path)
    reverse_parser.add_argument("--output", type=Path, required=True)
    reverse_parser.add_argument("--scene-threshold", type=float, default=27.0)
    reverse_parser.add_argument("--vision-base-url")
    reverse_parser.add_argument("--vision-model")
    reverse_parser.add_argument("--demucs-model-repository", type=Path)
    reverse_parser.add_argument("--whisper-model-path", type=Path)
    reverse_parser.add_argument("--jianying-template", type=Path)
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
    elif args.command == "demo":
        print(
            json.dumps(
                render_synthetic_demo(args.output_dir),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    elif args.command == "start-episode":
        print(
            json.dumps(
                create_episode_job(
                    store_path=args.store,
                    series_id=args.series_id,
                    episode_id=args.episode_id,
                    target_language=args.target_language,
                    output_mode=args.output_mode,
                    rights_path=args.rights,
                    draft_root=args.draft_root,
                    source_video=args.source_video,
                ),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    elif args.command == "job-status":
        print(
            json.dumps(
                get_episode_job(args.store, args.job_id),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    elif args.command == "preflight":
        report = preflight_registered_job(
            args.store, args.job_id, args.duration_tolerance_ms
        )
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
        if not report["ok"]:
            raise SystemExit(2)
    elif args.command == "import-episode":
        print(
            json.dumps(
                import_registered_draft(args.store, args.job_id),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    elif args.command == "approve-roles":
        print(
            json.dumps(
                approve_role_mapping(args.store, args.job_id, args.mapping),
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
    elif args.command == "reverse":
        report = run_reverse(
            args.video,
            args.output,
            scene_threshold=args.scene_threshold,
            vision_base_url=args.vision_base_url,
            vision_model=args.vision_model,
            demucs_model_repository=args.demucs_model_repository,
            whisper_model_path=args.whisper_model_path,
            jianying_template=args.jianying_template,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
