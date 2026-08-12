# Supported kernels

| Kernel.org series | Version tested | Combined patch | Split code patch (with `cjktty-font-unifont-15.1.04.patch`) | Stage 1 (apply, build, render) | Stage 2 (full system) | Notes |
|---|---|---|---|---|---|---|
| 7.2 (mainline) | 7.2-rc7 | `v7.x/cjktty-7.2-rc7.patch` | `v7.x/cjktty-code-7.2-rc7.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 7.1 (stable) | 7.1.8 | `v7.x/cjktty-7.1.7.patch` | `v7.x/cjktty-code-7.1.7.patch` | Combined ✓<br>Split ✓ | Combined ✓ | KASAN, kmemleak and lockdep clean on 7.1.7 |
| 6.18 (longterm) | 6.18.44 | `v6.x/cjktty-6.18.patch` | `v6.x/cjktty-code-6.18.patch` | Combined ✓<br>Split ✓ | Combined ✓<br>Split ✓ | GRUB, installkernel and dracut initramfs |
| 6.12 (longterm) | 6.12.103 | `v6.x/cjktty-6.12.102.patch` | `v6.x/cjktty-code-6.12.102.patch` | Combined ✓<br>Split ✓ | Combined ✓ | KASAN, kmemleak and lockdep clean on 6.12.102 |
| 6.6 (longterm) | 6.6.151 | `v6.x/cjktty-6.6.151.patch` | `v6.x/cjktty-code-6.6.151.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 6.1 (longterm) | 6.1.182 | `v6.x/cjktty-6.1.182.patch` | `v6.x/cjktty-code-6.1.182.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 5.15 (longterm) | 5.15.215 | `v5.x/cjktty-5.15.215.patch` | `v5.x/cjktty-code-5.15.215.patch` | Combined ✓<br>Split ✓ | Combined ✓ |  |
| 5.10 (longterm) | 5.10.264 | `v5.x/cjktty-5.10.264.patch` | `v5.x/cjktty-code-5.10.264.patch` | Combined ✓<br>Split ✓ | Combined ✓ | stage 2 runs on a pinned OpenRC image: the current systemd cannot boot this kernel, with or without the patch |

Verification date: 2026-08-12.

Everything else in `v3.x/` through `v7.x/` is kept for the `SRC_URI` of released ebuilds and is not maintained.
