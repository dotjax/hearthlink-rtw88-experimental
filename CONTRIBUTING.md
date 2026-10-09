# Contributing

This repository contains experimental patches. Keep changes small and explain
the concrete failure they address. Attribute adaptations to their original
authors and link the exact upstream version. Keep existing copyright notices.
Local scripts and documentation use GPL-2.0-only; see LICENSES/NOTICE.md for
original driver terms.

For code changes, record the pristine source version, apply with zero fuzz,
run kernel checkpatch, and build against matching headers. Separate build-only
checks from hardware results. Include rollback instructions for a proposed
runtime change and sanitized evidence for any claimed improvement.

Do not add another person's Signed-off-by, Reviewed-by, Tested-by, or Acked-by
to a modified patch without their authorization for that version. Upstream
trailers can be documented as historical provenance, clearly labeled as such.
Any DCO sign-off you supply must be your own truthful certification; see the
[Developer Certificate of Origin](https://developercertificate.org/).
