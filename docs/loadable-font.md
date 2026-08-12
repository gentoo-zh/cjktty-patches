# Runtime-loadable CJK console font

## Recommendation

Extend `KDFONTOP` with CJK-specific set, query, and clear operations, keep the
loaded bitmap in an immutable system-wide object separate from `vc_font`, and
load a PSF2 file from early userspace when early CJK output matters. A console
ioctl keeps filesystem policy out of fbcon, reuses the existing permission
and serialization path, permits replacement at runtime, and removes the font
data from the kernel image.

An initramfs can deliver the file and loader early but does not define another
kernel loading API. `request_firmware()` is not recommended because a firmware
request must be deferred past fbcon setup, needs a retry when the initramfs
lacks the file, and provides no runtime replacement interface.

## Required semantics

Three reset categories affect the design. An ANSI terminal reset such as
`ESC c`, `reset_vc()`, and a Secure Attention Key reset do not currently
replace `vc_font`. `setfont -R`, `PIO_FONTRESET`, and
`KD_FONT_OP_SET_DEFAULT` explicitly replace the ordinary console font. An
fbcon unbind and rebind destroys fbcon-private state but not VT-global state.

The recommended CJK object survives all three. Ordinary `setfont` and
`setfont -R` continue to control the 256- or 512-glyph base font and cell
geometry without silently discarding the much larger CJK extension. A new
CJK clear operation explicitly releases the extension. A CJK slot whose
geometry does not match the current base font remains installed but dormant.
The slot becomes usable again after a base-font change restores the matching geometry.
The object does not survive a reboot.

## Mechanism comparison

| Mechanism | When the CJK font becomes available | Before availability | Reset and replacement | Distribution payload |
| --- | --- | --- | --- | --- |
| `request_firmware()` | Not at `console_init()`, which runs before initcalls or initramfs unpacking. In Linux 7.1, framebuffer core starts at a `subsys_initcall`, also before `rootfs_initcall`; the firmware request therefore requires deferral. A deferred request can find an initramfs file but cannot find an unmounted real root. | The normal built-in font renders ASCII. CJK cells use the missing-glyph fallback. A failed request needs an explicit later retry. | The firmware API only returns bytes. Survival depends on the kernel subsystem that copies and owns the bytes. The firmware API supplies neither replacement nor clear semantics. | A file under `/lib/firmware`, `CONFIG_FW_LOADER=y`, initramfs inclusion for an early request, and kernel retry policy. `CONFIG_EXTRA_FIRMWARE` would put the bytes back in the kernel and defeat the purpose. |
| Existing `PIO_FONTX` / `KD_FONT_OP_SET` path | When a privileged process invokes the ioctl from an initramfs `/init` hook or a normal boot service. | The normal built-in font and missing CJK glyphs remain visible until the call succeeds. | Existing userspace-loaded fonts survive ANSI reset, but another `setfont` or a font reset replaces the loaded font. The proposed separate CJK object fixes the conflict and adds explicit replacement and clear operations. | A PSF2 font, a loader or updated `setfont`, and a service. Initramfs inclusion is needed only for CJK before the real root starts. |
| Initramfs-supplied file | The file exists after initramfs unpacking. An ioctl loader activates the font when `/init` runs. A deferred firmware request can activate the font before `/init`, but still after early console and fbcon setup. | The same base-font window exists from kernel start through the load. | File location defines no lifetime. The consuming API determines whether reset, rebind, and replacement preserve the font. | The font, loader, and an initramfs hook, plus an initramfs rebuild after a font or loader change. The archive must remain a separate boot artifact; `CONFIG_INITRAMFS_SOURCE` would put the bytes back in `vmlinux`. |

`PIO_FONTX` cannot carry the cjktty layout: `PIO_FONTX.charcount` is an unsigned short and
is documented for 256 or 512 glyphs. `struct console_font_op` used by
`KDFONTOP` has 32-bit fields, but `con_font_set()` caps `charcount` at 512 and
fbcon independently accepts only 256 or 512. The cjktty layout is 131,072
half-cell glyphs: two slots for each BMP code point. The UAPI shape can carry
131,072 glyphs, but the operation needs new semantics rather than globally
weakening limits which protect other console drivers.

## Early boot

The first visible console necessarily uses a small built-in mainline font.
Kernel messages are ASCII, so the built-in mainline font covers diagnostics. If CJK text
is written before the external font is loaded, the console shows the base font's
missing-glyph shapes. The proposed CJK set operation must redraw the already-stored
cells from the new bitmap object; cjktty's second screen plane retains the BMP code
point required for that redraw.

No built-in CJK subset is required. The minimum additional subset for the
normal boot path is therefore zero glyphs. An initramfs that emits CJK before
running the loader could compile exactly the code points used by the initramfs
messages, at 32 bytes per 16x16 code point or 128 bytes per 32x32 code
point, plus lookup metadata. There is no useful generic small CJK subset:
selecting thousands of common characters would recreate the static-data
objection while still producing missing glyphs.

The practical timing choices are:

1. No initramfs hook: CJK appears when the normal boot service runs. Earlier
   kernel and initramfs messages use the base font.
2. Initramfs hook: CJK appears when `/init` invokes the loader, before pivoting
   to the real root. Kernel messages before `/init` still use the base font.
3. Deferred `request_firmware()`: CJK can appear after initramfs population but
   requires kernel deferral and retry logic. The firmware path cannot improve the interval
   before `console_init()` and fbcon setup.

## Kernel design

### UAPI and file format

Add provisional operations such as `KD_FONT_OP_SET_CJK`,
`KD_FONT_OP_GET_CJK`, and `KD_FONT_OP_CLEAR_CJK` to `KDFONTOP`. Reuse
`struct console_font_op` so the existing compat ioctl and
`CAP_SYS_TTY_CONFIG` checks remain applicable. The set operation accepts only
the two layouts cjktty draws:

| Cell width and height | Slot count | Bytes per slot | Payload |
| --- | ---: | ---: | ---: |
| 8x16 | 131,072 | 16 | 2,097,152 bytes |
| 16x32 | 131,072 | 64 | 8,388,608 bytes |

The operation is system-wide even when issued on a VT. Duplicating the
same payload per VT is not acceptable. Two slots, one per geometry, allow both
sizes to be installed at once. `GET_CJK` reports which slots exist; data copyout
can be optional. `CLEAR_CJK` names one geometry or both.

Use PSF2 as the userspace file container. The 32-bit `length`, `charsize`,
`height`, and `width` fields express both layouts. The generated file has no
Unicode table because cjktty already addresses slot `codepoint * 2 + half`
directly. Userspace validates PSF2 and passes the bitmap payload to the kernel;
the kernel validates the exact dimensions and derived byte count rather than
parsing a filesystem format. `tools/gen-font.py --format psf2` and
`tools/load-cjk-font.c` implement the PSF2/userspace boundary for the prototype.

### Ownership and lifetime

Do not store the loaded extension in `struct fbcon_par` or replace
`vc_font.data`. Store an immutable object in the VT/console layer, shared by
all VTs and referenced by the 16x16 or 32x32 slot. Allocate the object with
`kvmalloc()` or `vmemdup_user()` and release the object with `kvfree()`; a physically
contiguous multi-megabyte allocation is not a valid requirement.

The object lives from a successful set operation until replacement, explicit
clear, or shutdown. fbcon unbind/rebind must only discard the derived rotated
copies. VT deallocation must not free the shared object. A load failure leaves
the old object installed.

### Locking and replacement

The existing font ioctl enters the console driver under `console_lock()`, and
the fbcon drawing callbacks are expected to run under `console_lock()`. Enforce
the lock invariant with lockdep assertions at publication and at the drawing
entry points; do not rely only on the historical calling convention.

Runtime CJK font replacement follows this order:

1. Validate dimensions and copy the complete candidate outside
   `console_lock()`.
2. Acquire `console_lock()` and atomically replace the matching global slot.
3. Invalidate every matching `fontbuffer_utf` rotated copy and any cursor
   source pointer derived from the old object.
4. Rebuild rotated data either immediately or on the next draw, then redraw
   visible VTs from each VT's saved code-point plane.
5. Release `console_lock()` and `kvfree()` the old object.

Holding the lock from lookup through the renderer's bitmap copy keeps a glyph
pointer valid and makes both halves of a character use one font generation. If
any audited rendering path cannot hold `console_lock()`, the fallback design
is RCU around the complete render batch, not an RCU lookup which returns a
pointer after leaving the read-side critical section.

### Lookup before load

Change `font_bits()` to look up the geometry-specific runtime object instead of
calling `find_font("CJK16x16")` or `find_font("CJK32x32")`. If the slot is
absent, return the already-selected base-font bitmap for marker slot `0xff` or
`0xfe`. Never index a null or partially initialized CJK array. Loading a font
then redraws the saved screen; clearing a slot redraws the screen with missing glyphs.

Ordinary `setfont` continues to change `vc_font`, including ASCII glyphs and
cell geometry. `setfont` does not own or replace the CJK slots. Rotation code consumes
the same published object and tags each derived buffer with the source
generation so a replacement cannot reuse a stale rotated copy.

## Gentoo impact

Current Gentoo configurations that only set `CONFIG_FONT_CJK_16x16=y` will
need the new cjktty rendering option, the generated PSF2 font and loader, and
one privileged load during boot. Until `setfont` supports the new operation,
the runtime package must supply a dedicated OpenRC or systemd helper. After
`setfont` gains support, the normal consolefont or
`systemd-vconsole-setup` configuration can name the font. Gentoo must not
enable either path automatically. CJK output in the initramfs also requires
dracut vconsole integration and an initramfs rebuild. Distribution-kernel
packages should add the runtime package dependency under `USE=cjk`; the
dependency installs the font and loader while activation remains an explicit
configuration choice.

The least duplicated ebuild design is one new runtime package which owns the
versioned PSF2 files and, until `setfont` learns the new operation, the loader
and service/dracut glue. The preferred final integration teaches `setfont` the
new operation so existing OpenRC, systemd, and dracut vconsole configuration can
load the font. The six kernel packages depend on the runtime package when
cjktty support is enabled. Every new or changed distfile still needs a Manifest
update.

| Package | Required ebuild change |
| --- | --- |
| `sys-kernel/gentoo-cjk-sources` | Fetch the code-only patch. Under `USE=cjk`, depend on or clearly recommend the runtime font package; source installation alone cannot make a running kernel load a font. |
| `sys-kernel/gentoo-cjk-kernel` | Replace the `CONFIG_FONT_CJK_16x16=y` fragment with the renderer option, add the runtime package dependency, and let the installkernel/dracut hook include the font when configured. |
| `sys-kernel/gentoo-cjk-kernel-bin` | Keep the source tree used for `modules_prepare` on the same code patch, add the runtime package dependency, and publish the binary kernel without the array. The font should be shared as a normal installed file, not duplicated inside each kernel binary package. |
| `sys-kernel/cachyos-sources` | Fetch the code-only patch and connect `USE=cjk` to the runtime package or an explicit post-install instruction. |
| `sys-kernel/xanmod-sources` | Make the same source-package and runtime dependency change as `cachyos-sources`. |
| `sys-kernel/xanmod-kernel` | Change the package's cjk config fragment, add the runtime dependency, and use the common service/initramfs integration. |

The font distfile must be versioned independently of the kernel patch. A font
update then changes one runtime package and the corresponding Manifest instead of six kernel
ebuilds, while a kernel port changes only the code patch references.

## Prototype and evidence

The prototype tests one claim: whether bitmap data absent from the kernel image
can enter through the existing console font ioctl and then be used by cjktty's
rendering path. The current tree does not pass the rendering part of that test.

`tools/loadable-font-poc.patch` is scoped to Linux 6.18.44 after
`v6.x/cjktty-6.18.patch`. The proof patch raises the two existing 512-glyph gates, changes
the large userspace-font allocations to vmalloc-capable allocation, and otherwise
uses `KD_FONT_OP_SET_TALL`. The retained 4 MiB `max_font_size` admits the 2 MiB
16x16 payload but deliberately still rejects the 8 MiB 32x32 payload. The proof patch does
not implement the separate production CJK object.
`tools/test-loadable-font.sh` performs the following sequence:

1. Apply the cjktty patch and proof patch with fuzz disabled.
2. Build with both `CONFIG_FONT_CJK_16x16` and
   `CONFIG_FONT_CJK_32x32` unset and assert that `vmlinux` has no CJK font
   symbol.
3. Generate `cjk-16.psf` outside the kernel build and place the PSF2 file, loader,
   and test init in a separate initramfs.
4. Boot with QEMU/KVM and capture the cells after CJK text is written but before
   the ioctl. The normal CJK screenshot check must fail.
5. Load the PSF2 payload. The ioctl's existing `update_screen()` attempts to
   redraw the same cells; the init does not write the CJK text a second time.
6. Capture again and compare nine CJK cells with the expected Unifont bitmaps.

The reproducer is:

```sh
CJKTTY_LAB=/home/zakk/code/gentoo-install/cjktty/lab \
JOBS=4 tools/test-loadable-font.sh \
  6.18.44 v6.x/cjktty-6.18.patch
```

Before the bitmap checker compared exact Unifont glyphs, an earlier run recorded:

```text
CJK glyphs differ and carry ink (144 and 135 lit subpixels)
loader ioctl: success
built-in CJK font: absent
before load: CJK rendering check failed as expected
after load: CJK rendering check passed
loadable-font proof: PASS
```

That check established distinct ink in two cells but did not establish the
expected glyph shapes.

On 2026-08-12, the command exited nonzero with this terminal diagnostic:

```text
console check failed: U+4E2D differs from the expected Unifont bitmap at 60 pixels
```

The serial log records `CJKTTY-IOCTL-SUCCESS`, and `vmlinux` contains neither
`font_cjk_16x16` nor `font_cjk_32x32`. The first post-load CJK cell contains the
42-pixel missing-glyph box instead of the 48-pixel U+4E2D bitmap. A capture taken
five seconds after the marker has the same mismatch, so the marker does not race
a delayed correct redraw. The prototype therefore demonstrates acceptance of
the external 2 MiB payload but does not demonstrate cjktty rendering that
payload.

The prototype does not prove the proposed new UAPI or shared-object lifetime; replacement
under concurrent output; 32x32 loading; rotation; another `setfont`; font reset;
VT switching or deallocation; fbcon unbind/rebind; DRM handover; suspend/resume;
full-system initramfs generation; any of the six ebuild changes; a bootloader or
real machine; or upstream acceptance. The proof's reuse of `vc_font` means a
later ordinary `setfont` replaces the CJK payload, so the `vc_font` storage
model is not the recommendation.

## Remaining upstream blockers

Removing the static array eliminates the largest immediate objection, not the
rest of the review burden:

- The VT change still doubles `vc_screenbuf` and stores a parallel 16-bit code
  point plane. Allocation, resize, scroll, selection, redraw, and teardown of the plane
  behavior needs a standalone review and failure-path tests.
- The design is BMP-only. Non-BMP CJK extensions, combining characters,
  variation selectors, and terminal width rules remain outside the cjktty model.
- A new global console-font UAPI needs agreement from VT, console, kbd, and
  fbcon maintainers, including limits, compat behavior, permissions, and how
  userspace discovers support.
- Runtime replacement needs KASAN and lockdep coverage while output, rotation,
  VT switching, base-font loading, and fbcon bind operations run concurrently.
- All rendering paths, including rotation and cursor paths, must use one lookup
  helper and one proved lifetime rule. The current patch has duplicated fbcon
  call-site changes and derived buffers.
- Font provenance and licensing still need correct metadata in the runtime
  package even though the bytes leave the kernel source and image.
- fbcon is a maintenance-mode subsystem in practical review terms. The current
  kernel `MAINTAINERS` file labels `FRAMEBUFFER CONSOLE` as maintained but the
  adjacent framebuffer core as `Odd Fixes`; a large feature still has a high
  acceptance bar and may be rejected in favor of a userspace console design.

The runtime-loading design is therefore necessary for an upstream proposal,
but the design alone does not establish upstream acceptance.
