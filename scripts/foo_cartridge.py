#!/usr/bin/env python3
"""
foo_cartridge.py — stdlib-only core of the canonical context cartridge.

foo-cartridge-replay-v1, step one: the constants, writer, and verifier for
the three-member foo.zip (payload.md, prompt.md, manifest.json), extracted
from prompt_foo.py into a module with ZERO third-party imports. A clean-room
consumer can fetch this single file and verify or rebuild a cartridge with
nothing but the Python standard library.

Schema: foo-cartridge-integrity-v1 — unchanged. This extraction is a
refactor, not a schema bump; byte-identical archive output with the
pre-extraction code is the flip's TRUE condition.

Deliberate deltas from the in-prompt_foo original:
  * write_context_cartridge requires output_path — the stdlib core has no
    repo to default into. Repo-lane defaulting (REPO_ROOT/foo.zip) lives in
    prompt_foo's thin wrapper.
  * A log=print callable replaces the captured logger, so this module never
    imports anything from the compiler it serves.
"""
import io
import os
import json
import hashlib
import tempfile
import zipfile
from pathlib import Path

FOO_CARTRIDGE_MEMBERS = ("payload.md", "prompt.md", "manifest.json")
FOO_CARTRIDGE_SOURCE_EPOCH = 1767225600
FOO_CARTRIDGE_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
FOO_CARTRIDGE_FILE_MODE = 0o100644 << 16


def _sha256_hex(data: bytes) -> str:
    """Return a lowercase SHA-256 digest for exact member bytes."""
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: dict) -> bytes:
    """Serialize canonical manifest JSON: UTF-8, sorted, compact, one final LF."""
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (text + "\n").encode("utf-8")


def _extract_prompt_member(final_output: str) -> bytes:
    """Extract the final outer Prompt section from the scrubbed payload.

    The last markers are intentionally selected because compiled source and
    historical transcripts may contain earlier Prompt markers. Deriving this
    member from final_output prevents an unsanitized secondary input path.
    """
    start_marker = "\n--- START: Prompt ---\n"
    end_marker = "\n--- END: Prompt ---"
    if start_marker not in final_output:
        raise ValueError("Compiled payload has no final Prompt start marker.")

    prompt_tail = final_output.rsplit(start_marker, 1)[1]
    if end_marker not in prompt_tail:
        raise ValueError("Compiled payload has no final Prompt end marker.")

    prompt_text = prompt_tail.rsplit(end_marker, 1)[0]
    return (prompt_text.rstrip("\n") + "\n").encode("utf-8")


def _build_cartridge_manifest(
    payload_bytes: bytes,
    prompt_bytes: bytes,
) -> dict:
    """Build the complete reproducible manifest from exact member bytes."""
    return {
        "canonicalization": {
            "json": "utf-8-sorted-compact-lf-v1",
            "zip": "stored-fixed-metadata-v1",
            "zip_file_mode": "0100644",
            "zip_member_order": list(FOO_CARTRIDGE_MEMBERS),
            "zip_source_epoch": FOO_CARTRIDGE_SOURCE_EPOCH,
        },
        "schema": "foo-cartridge-integrity-v1",
        "sha256": {
            "payload.md": _sha256_hex(payload_bytes),
            "prompt.md": _sha256_hex(prompt_bytes),
        },
    }


def _canonical_zip_info(member_name: str) -> zipfile.ZipInfo:
    """Return fixed ZIP metadata for one canonical cartridge member."""
    info = zipfile.ZipInfo(
        member_name,
        date_time=FOO_CARTRIDGE_ZIP_TIME,
    )
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.internal_attr = 0
    info.external_attr = FOO_CARTRIDGE_FILE_MODE
    info.extra = b""
    info.comment = b""
    return info


def _reject_duplicate_json_keys(pairs):
    """Fail closed when manifest JSON repeats an object key."""
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate manifest key: {key!r}")
        value[key] = item
    return value


def verify_context_cartridge(path) -> dict:
    """Verify exact membership, metadata, canonical JSON, CRCs, and hashes.

    Missing, modified, duplicated, reordered, or unexpected members fail.
    The verifier deliberately accepts no archive comments, extra fields,
    alternate compression, timestamps, permissions, or JSON representation.
    """
    cartridge_path = Path(path)

    with zipfile.ZipFile(cartridge_path, "r") as archive:
        if archive.comment:
            raise ValueError("Archive comment must be empty.")

        names = archive.namelist()
        duplicates = sorted({
            name for name in names
            if names.count(name) > 1
        })
        missing = sorted(set(FOO_CARTRIDGE_MEMBERS) - set(names))
        unexpected = sorted(set(names) - set(FOO_CARTRIDGE_MEMBERS))

        if duplicates or missing or unexpected:
            raise ValueError(
                f"Invalid cartridge members: missing={missing}, "
                f"unexpected={unexpected}, duplicates={duplicates}"
            )

        if tuple(names) != FOO_CARTRIDGE_MEMBERS:
            raise ValueError(f"Invalid member order: {names!r}")

        member_bytes = {}
        for member_name in FOO_CARTRIDGE_MEMBERS:
            info = archive.getinfo(member_name)

            if info.date_time != FOO_CARTRIDGE_ZIP_TIME:
                raise ValueError(
                    f"Noncanonical timestamp for {member_name!r}."
                )
            if info.compress_type != zipfile.ZIP_STORED:
                raise ValueError(
                    f"Noncanonical compression for {member_name!r}."
                )
            if (
                info.create_system != 3
                or info.create_version != 20
                or info.extract_version != 20
            ):
                raise ValueError(
                    f"Noncanonical ZIP version metadata for {member_name!r}."
                )
            if info.flag_bits != 0 or info.internal_attr != 0:
                raise ValueError(
                    f"Noncanonical ZIP flags for {member_name!r}."
                )
            if info.external_attr != FOO_CARTRIDGE_FILE_MODE:
                raise ValueError(
                    f"Noncanonical file mode for {member_name!r}."
                )
            if info.extra or info.comment or info.is_dir():
                raise ValueError(
                    f"Noncanonical member metadata for {member_name!r}."
                )

            member_bytes[member_name] = archive.read(info)

        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise ValueError(f"CRC failure in {corrupt_member!r}.")

    try:
        manifest = json.loads(
            member_bytes["manifest.json"].decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid manifest.json: {exc}") from exc

    try:
        payload_text = member_bytes["payload.md"].decode("utf-8")
        expected_prompt_bytes = _extract_prompt_member(payload_text)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(
            f"payload.md cannot yield canonical prompt.md: {exc}"
        ) from exc

    if member_bytes["prompt.md"] != expected_prompt_bytes:
        raise ValueError(
            "prompt.md does not match the final Prompt section in payload.md."
        )

    expected_manifest = _build_cartridge_manifest(
        member_bytes["payload.md"],
        member_bytes["prompt.md"],
    )

    if manifest != expected_manifest:
        raise ValueError(
            "Manifest content or member hashes do not match the cartridge."
        )

    if (
        member_bytes["manifest.json"]
        != _canonical_json_bytes(expected_manifest)
    ):
        raise ValueError("manifest.json is not canonical JSON.")

    canonical_buffer = io.BytesIO()
    with zipfile.ZipFile(
        canonical_buffer,
        "w",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
    ) as canonical_archive:
        canonical_archive.comment = b""
        for member_name in FOO_CARTRIDGE_MEMBERS:
            canonical_archive.writestr(
                _canonical_zip_info(member_name),
                member_bytes[member_name],
            )

    archive_bytes = cartridge_path.read_bytes()
    if archive_bytes != canonical_buffer.getvalue():
        raise ValueError("Archive bytes are not canonical.")

    return {
        "archive_sha256": _sha256_hex(archive_bytes),
        "member_sha256": expected_manifest["sha256"],
    }


def write_context_cartridge(final_output, output_path, log=print):
    """Atomically emit and self-verify the canonical three-member foo.zip.

    Canonical reproducibility means identical scrubbed final_output bytes
    produce identical archive bytes. No wall-clock value enters the archive.
    ZIP_STORED avoids compressor-version variability, while every writable
    metadata field and the JSON representation are fixed explicitly.

    output_path is REQUIRED here: the stdlib core has no repo to default
    into. Repo-lane defaulting lives in prompt_foo's thin wrapper.
    """
    cartridge_path = Path(output_path)

    payload_bytes = final_output.encode("utf-8")
    prompt_bytes = _extract_prompt_member(final_output)
    manifest_bytes = _canonical_json_bytes(
        _build_cartridge_manifest(payload_bytes, prompt_bytes)
    )

    members = (
        ("payload.md", payload_bytes),
        ("prompt.md", prompt_bytes),
        ("manifest.json", manifest_bytes),
    )

    with tempfile.NamedTemporaryFile(
        dir=cartridge_path.parent,
        prefix=f".{cartridge_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        with zipfile.ZipFile(
            temp_path,
            "w",
            compression=zipfile.ZIP_STORED,
            allowZip64=False,
        ) as archive:
            archive.comment = b""
            for member_name, data in members:
                archive.writestr(
                    _canonical_zip_info(member_name),
                    data,
                )

        verification = verify_context_cartridge(temp_path)
        os.replace(temp_path, cartridge_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    log(
        f"📦 Canonical context cartridge written to {cartridge_path} "
        f"(sha256={verification['archive_sha256'][:12]}…, "
        f"members={len(FOO_CARTRIDGE_MEMBERS)})"
    )
    return cartridge_path
