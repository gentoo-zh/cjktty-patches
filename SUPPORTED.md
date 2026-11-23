# Supported kernels

| Kernel.org series | Version tested | Combined patch | Split code patch (with `cjktty-font-unifont-18.0.01.patch`) | Stage 1 (apply, build, render) | Stage 2 (full system) | Notes |
|---|---|---|---|---|---|---|
| 7.4 (mainline) | 7.4-rc4 |  | `v7.x/cjktty-code-7.4-rc3.patch` | Split ✓ | Split ✓ |  |
| 7.3 (stable) | 7.3.6 |  | `v7.x/cjktty-code-7.3.4.patch` | Split ✓ | Split ✓ |  |
| 6.18 (longterm) | 6.18.65 | `v6.x/cjktty-6.18.63.patch` | `v6.x/cjktty-code-6.18.63.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ | GRUB, installkernel and dracut initramfs on 6.18.44 |
| 6.12 (longterm) | 6.12.119 | `v6.x/cjktty-6.12.117.patch` | `v6.x/cjktty-code-6.12.117.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ | KASAN, kmemleak and lockdep clean on 6.12.102 |
| 6.6 (longterm) | 6.6.163 | `v6.x/cjktty-6.6.163.patch` | `v6.x/cjktty-code-6.6.163.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ |  |
| 6.1 (longterm) | 6.1.193 | `v6.x/cjktty-6.1.193.patch` | `v6.x/cjktty-code-6.1.193.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ |  |
| 5.15 (longterm) | 5.15.226 | `v5.x/cjktty-5.15.226.patch` | `v5.x/cjktty-code-5.15.226.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ |  |
| 5.10 (longterm) | 5.10.275 | `v5.x/cjktty-5.10.275.patch` | `v5.x/cjktty-code-5.10.275.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ | stage 2 runs on a pinned OpenRC image: the current systemd cannot boot this kernel, with or without the patch<br>keeps the private side plane: its struct fbcon_ops renderer is too far from struct fbcon_par for the vc_uni_lines port |

Verification dates: 2026-08-12, 2026-08-20, 2026-08-24, 2026-08-28, 2026-08-29, 2026-09-03, 2026-09-09, 2026-09-15, 2026-09-22, 2026-09-26, 2026-10-03, 2026-10-12, 2026-10-17, 2026-10-22, 2026-11-11, 2026-11-15, 2026-11-16, 2026-11-17, 2026-11-23.

Everything else in `v3.x/` through `v7.x/` is kept for the `SRC_URI` of released ebuilds and is not maintained.
