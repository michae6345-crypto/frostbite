"""UF2 parsing."""
from __future__ import annotations

import struct

UF2_MAGIC0, UF2_MAGIC1, UF2_MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
UF2_FLAG_FAMILY = 0x00002000
RP2040_FAMILY = 0xE48BFF56


def parse_uf2(data: bytes) -> dict:
    """Return {ok, errors[], blocks, family_ids, payload_bytes, size}."""
    errs = []
    if len(data) == 0:
        errs.append("file is empty")
    if len(data) % 512:
        errs.append(f"size {len(data)} is not a multiple of 512 (truncated or padded)")
    nblk = len(data) // 512
    fams, payload, declared = set(), 0, set()
    addrs = []
    for i in range(nblk):
        b = data[i * 512:(i + 1) * 512]
        m0, m1, flags, addr, size, bno, ntot, fam = struct.unpack_from("<8I", b, 0)
        (mend,) = struct.unpack_from("<I", b, 508)
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or mend != UF2_MAGIC_END:
            errs.append(f"block {i}: bad magic ({m0:#x},{m1:#x},{mend:#x})")
            continue
        if bno != i:
            errs.append(f"block {i}: block number field is {bno}")
        declared.add(ntot)
        if size > 476:
            errs.append(f"block {i}: payload size {size} > 476")
        payload += size
        addrs.append(addr)
        if flags & UF2_FLAG_FAMILY:
            fams.add(fam)
        else:
            errs.append(f"block {i}: familyID flag not set")
    if len(declared) > 1:
        errs.append(f"inconsistent numBlocks fields {sorted(declared)}")
    elif declared and next(iter(declared)) != nblk:
        errs.append(f"numBlocks field says {next(iter(declared))}, file has {nblk} blocks (truncated?)")
    if fams and fams != {RP2040_FAMILY}:
        errs.append("family IDs " + ", ".join(f"{f:#010x}" for f in sorted(fams)) + f" != {RP2040_FAMILY:#010x} (RP2040)")
    if len(data) >= 2 * 1024 * 1024:
        errs.append(f"size {len(data)} >= 2 MB")
    return {"ok": not errs, "errors": errs[:20], "n_errors": len(errs), "blocks": nblk,
            "declared_blocks": sorted(declared), "family_ids": [f"{f:#010x}" for f in sorted(fams)],
            "payload_bytes": payload, "size": len(data),
            "flash_range": [f"{min(addrs):#x}", f"{max(addrs):#x}"] if addrs else None}
