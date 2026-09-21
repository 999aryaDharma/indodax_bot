"""Operator manual approval CLI for semi-automated execution mode."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from indodax_lab.control.approval import (
    ManualApprovalStore,
    ProposalStatus,
    generate_approval_token,
)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage human operator order approval proposals.")
    parser.add_argument(
        "--store-path",
        type=Path,
        default=Path("var/approval_store.json"),
        help="Path to the persistent JSON approval store (default: var/approval_store.json)",
    )
    parser.add_argument(
        "--signing-secret",
        default=None,
        help="Optional HMAC signing secret for cryptographic operator verification",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: list
    list_parser = subparsers.add_parser("list", help="List order proposals")
    list_parser.add_argument(
        "--status",
        choices=["PENDING", "APPROVED", "REJECTED", "EXPIRED", "ALL"],
        default="PENDING",
        help="Filter proposals by status (default: PENDING)",
    )

    # Subcommand: approve
    approve_parser = subparsers.add_parser("approve", help="Approve an order proposal")
    approve_parser.add_argument("proposal_id", help="Proposal ID to approve")
    approve_parser.add_argument(
        "--operator-id",
        required=True,
        help="Operator ID confirming approval",
    )
    approve_parser.add_argument(
        "--token",
        default=None,
        help="Cryptographic HMAC authorization token",
    )
    approve_parser.add_argument(
        "--reason",
        default="OPERATOR_MANUAL_APPROVED",
        help="Optional justification for audit log",
    )

    # Subcommand: sign
    sign_parser = subparsers.add_parser("sign", help="Generate authorization token for a proposal")
    sign_parser.add_argument("proposal_id", help="Proposal ID to sign")
    sign_parser.add_argument(
        "--operator-id",
        required=True,
        help="Operator ID",
    )
    sign_parser.add_argument(
        "--secret-key",
        required=True,
        help="HMAC signing secret key",
    )

    # Subcommand: reject
    reject_parser = subparsers.add_parser("reject", help="Reject an order proposal")
    reject_parser.add_argument("proposal_id", help="Proposal ID to reject")
    reject_parser.add_argument(
        "--operator-id",
        required=True,
        help="Operator ID confirming rejection",
    )
    reject_parser.add_argument(
        "--reason",
        default="OPERATOR_MANUAL_REJECTED",
        help="Optional justification for audit log",
    )

    # Subcommand: clean
    subparsers.add_parser("clean", help="Mark expired proposals as EXPIRED")

    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    parser = _argument_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 3

    store = ManualApprovalStore(
        persistence_path=args.store_path,
        signing_secret=args.signing_secret,
    )
    now = datetime.now(UTC)

    if args.subcommand == "sign":
        prop = store.get(args.proposal_id)
        if prop is None:
            output = {
                "ok": False,
                "error": f"PROPOSAL_NOT_FOUND:{args.proposal_id}",
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 1
        token = generate_approval_token(
            proposal_id=prop.proposal_id,
            operator_id=args.operator_id,
            expires_at=prop.expires_at,
            secret_key=args.secret_key,
        )
        output = {
            "ok": True,
            "action": "SIGNED",
            "proposal_id": prop.proposal_id,
            "operator_id": args.operator_id,
            "token": token,
            "expires_at": prop.expires_at.isoformat(),
        }
        stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
        return 0

    if args.subcommand == "list":
        if args.status == "ALL":
            proposals = store.get_all()
        elif args.status == "PENDING":
            proposals = store.get_pending(now=now)
        else:
            status_filter = ProposalStatus(args.status)
            proposals = tuple(p for p in store.get_all() if p.status == status_filter)

        output = {
            "ok": True,
            "status_filter": args.status,
            "count": len(proposals),
            "proposals": [p.model_dump(mode="json") for p in proposals],
        }
        stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
        return 0

    if args.subcommand == "approve":
        try:
            approved = store.approve(
                args.proposal_id,
                operator_id=args.operator_id,
                at=now,
                reason=args.reason,
                token=args.token,
            )
            output = {
                "ok": True,
                "action": "APPROVED",
                "proposal": approved.model_dump(mode="json"),
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 0
        except KeyError:
            output = {
                "ok": False,
                "error": f"PROPOSAL_NOT_FOUND:{args.proposal_id}",
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 1
        except TimeoutError:
            output = {
                "ok": False,
                "error": f"PROPOSAL_EXPIRED:{args.proposal_id}",
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 2
        except PermissionError as exc:
            output = {
                "ok": False,
                "error": str(exc),
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 1
        except ValueError as exc:
            output = {
                "ok": False,
                "error": str(exc),
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 1

    if args.subcommand == "reject":
        try:
            rejected = store.reject(
                args.proposal_id,
                operator_id=args.operator_id,
                at=now,
                reason=args.reason,
            )
            output = {
                "ok": True,
                "action": "REJECTED",
                "proposal": rejected.model_dump(mode="json"),
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 0
        except KeyError:
            output = {
                "ok": False,
                "error": f"PROPOSAL_NOT_FOUND:{args.proposal_id}",
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 1
        except ValueError as exc:
            output = {
                "ok": False,
                "error": str(exc),
            }
            stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
            return 1

    if args.subcommand == "clean":
        expired = store.clean_expired(at=now)
        output = {
            "ok": True,
            "expired_count": len(expired),
            "expired": [p.model_dump(mode="json") for p in expired],
        }
        stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
        return 0

    return 3


if __name__ == "__main__":
    sys.exit(main())
