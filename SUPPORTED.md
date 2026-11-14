# Supported kernels

| Kernel.org series | Version tested | Combined patch | Split code patch (with `cjktty-font-unifont-18.0.01.patch`) | Stage 1 (apply, build, render) | Stage 2 (full system) | Notes |
|---|---|---|---|---|---|---|
| 7.3 (mainline) | 7.3 |  | `v7.x/cjktty-code-7.3.patch` | Split ✓ | Split ✓ |  |
| 7.2 (stable) | 7.2.12 | `v7.x/cjktty-7.2.patch` | `v7.x/cjktty-code-7.2.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ |  |
| 6.18 (longterm) | 6.18.58 | `v6.x/cjktty-6.18.45.patch` | `v6.x/cjktty-code-6.18.45.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ | GRUB, installkernel and dracut initramfs on 6.18.44 |
| 6.12 (longterm) | 6.12.114 | `v6.x/cjktty-6.12.104.patch` | `v6.x/cjktty-code-6.12.104.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ | KASAN, kmemleak and lockdep clean on 6.12.102 |
| 6.6 (longterm) | 6.6.160 | `v6.x/cjktty-6.6.152.patch` | `v6.x/cjktty-code-6.6.152.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ |  |
| 6.1 (longterm) | 6.1.190 | `v6.x/cjktty-6.1.184.patch` | `v6.x/cjktty-code-6.1.184.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ |  |
| 5.15 (longterm) | 5.15.223 | `v5.x/cjktty-5.15.217.patch` | `v5.x/cjktty-code-5.15.217.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ |  |
| 5.10 (longterm) | 5.10.272 | `v5.x/cjktty-5.10.265.patch` | `v5.x/cjktty-code-5.10.265.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ | stage 2 runs on a pinned OpenRC image: the current systemd cannot boot this kernel, with or without the patch<br>keeps the private side plane: its struct fbcon_ops renderer is too far from struct fbcon_par for the vc_uni_lines port |

Verification dates: 2026-08-12, 2026-08-20, 2026-08-24, 2026-08-28, 2026-08-29, 2026-09-03, 2026-09-09, 2026-09-15, 2026-09-22, 2026-09-26, 2026-10-03, 2026-10-12, 2026-10-17, 2026-10-22, 2026-11-11, 2026-11-15.

Everything else in `v3.x/` through `v7.x/` is kept for the `SRC_URI` of released ebuilds and is not maintained.
