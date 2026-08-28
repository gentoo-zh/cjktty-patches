# Supported kernels

| Kernel.org series | Version tested | Combined patch | Split code patch (with `cjktty-font-unifont-15.1.04.patch`) | Stage 1 (apply, build, render) | Stage 2 (full system) | Notes |
|---|---|---|---|---|---|---|
| 7.2 (stable) | 7.2.2 | `v7.x/cjktty-7.2.patch` | `v7.x/cjktty-code-7.2.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 7.1 (stable) | 7.1.12 | `v7.x/cjktty-7.1.9.patch` | `v7.x/cjktty-code-7.1.9.patch` | Combined ✓<br>Split ✓ | Combined ✓ | KASAN, kmemleak and lockdep clean on 7.1.7 |
| 6.18 (longterm) | 6.18.48 | `v6.x/cjktty-6.18.45.patch` | `v6.x/cjktty-code-6.18.45.patch` | Combined ✓<br>Split ✓ | Combined ✓ | GRUB, installkernel and dracut initramfs on 6.18.44 |
| 6.12 (longterm) | 6.12.107 | `v6.x/cjktty-6.12.104.patch` | `v6.x/cjktty-code-6.12.104.patch` | Combined ✓<br>Split ✓ | Combined ✓ | KASAN, kmemleak and lockdep clean on 6.12.102 |
| 6.6 (longterm) | 6.6.155 | `v6.x/cjktty-6.6.152.patch` | `v6.x/cjktty-code-6.6.152.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 6.1 (longterm) | 6.1.186 | `v6.x/cjktty-6.1.184.patch` | `v6.x/cjktty-code-6.1.184.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 5.15 (longterm) | 5.15.219 | `v5.x/cjktty-5.15.217.patch` | `v5.x/cjktty-code-5.15.217.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 5.10 (longterm) | 5.10.268 | `v5.x/cjktty-5.10.265.patch` | `v5.x/cjktty-code-5.10.265.patch` | Combined ✓<br>Split ✓ | Combined ✓ | stage 2 runs on a pinned OpenRC image: the current systemd cannot boot this kernel, with or without the patch |

Verification dates: 2026-08-12, 2026-08-17, 2026-08-20, 2026-08-24, 2026-08-28, 2026-08-29.

Everything else in `v3.x/` through `v7.x/` is kept for the `SRC_URI` of released ebuilds and is not maintained.
