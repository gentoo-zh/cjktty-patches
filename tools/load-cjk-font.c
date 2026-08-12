// SPDX-License-Identifier: GPL-2.0
/* Load the cjktty two-cell BMP layout through the console font ioctl. */

#include <errno.h>
#include <fcntl.h>
#include <linux/kd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#define PSF2_MAGIC 0x864ab572U
#define PSF2_HEADER_SIZE 32U
#define CJK_FONT_GLYPHS (65536U * 2U)

static uint32_t get_le32(const unsigned char *value)
{
	return (uint32_t)value[0] | (uint32_t)value[1] << 8 |
	       (uint32_t)value[2] << 16 | (uint32_t)value[3] << 24;
}

static void fail(const char *name)
{
	fprintf(stderr, "load-cjk-font: %s: %s\n", name, strerror(errno));
	exit(EXIT_FAILURE);
}

static void invalid(const char *path, const char *reason)
{
	fprintf(stderr, "load-cjk-font: %s: %s\n", path, reason);
	exit(EXIT_FAILURE);
}

int main(int argc, char **argv)
{
	const char *console = argc == 3 ? argv[2] : "/dev/tty0";
	const unsigned char *header;
	const unsigned char *glyphs;
	struct console_font_op op = { .op = KD_FONT_OP_SET_TALL };
	uint32_t headersize, flags, length, charsize, height, width;
	size_t payload_size;
	struct stat status;
	void *mapping;
	int font_fd, console_fd;

	if (argc < 2 || argc > 3) {
		fprintf(stderr, "usage: %s FONT.psf [CONSOLE]\n", argv[0]);
		return EXIT_FAILURE;
	}

	font_fd = open(argv[1], O_RDONLY | O_CLOEXEC);
	if (font_fd < 0)
		fail(argv[1]);
	if (fstat(font_fd, &status) < 0)
		fail(argv[1]);
	if (status.st_size < (off_t)PSF2_HEADER_SIZE)
		invalid(argv[1], "file is shorter than a PSF2 header");

	mapping = mmap(NULL, status.st_size, PROT_READ, MAP_PRIVATE, font_fd, 0);
	if (mapping == MAP_FAILED)
		fail(argv[1]);
	header = mapping;

	if (get_le32(header) != PSF2_MAGIC)
		invalid(argv[1], "not a PSF2 font");
	if (get_le32(header + 4) != 0)
		invalid(argv[1], "unsupported PSF2 version");
	headersize = get_le32(header + 8);
	flags = get_le32(header + 12);
	length = get_le32(header + 16);
	charsize = get_le32(header + 20);
	height = get_le32(header + 24);
	width = get_le32(header + 28);

	if (headersize < PSF2_HEADER_SIZE || headersize > (uint64_t)status.st_size)
		invalid(argv[1], "invalid PSF2 header size");
	if (flags != 0)
		invalid(argv[1], "PSF2 Unicode tables are not accepted");
	if (length != CJK_FONT_GLYPHS)
		invalid(argv[1], "font does not contain the two-cell BMP layout");
	if (!((width == 8 && height == 16) ||
	      (width == 16 && height == 32)))
		invalid(argv[1], "font is not 8x16 or 16x32");
	if (charsize != ((width + 7) / 8) * height)
		invalid(argv[1], "invalid PSF2 character size");
	payload_size = (size_t)length * charsize;
	if (payload_size > (uint64_t)status.st_size - headersize)
		invalid(argv[1], "truncated PSF2 glyph data");

	glyphs = (const unsigned char *)mapping + headersize;
	op.width = width;
	op.height = height;
	op.charcount = length;
	op.data = (unsigned char *)glyphs;

	console_fd = open(console, O_RDWR | O_CLOEXEC);
	if (console_fd < 0)
		fail(console);
	if (ioctl(console_fd, KDFONTOP, &op) < 0)
		fail(console);

	printf("loaded %u glyphs (%ux%u) from %s on %s\n",
	       length, width, height, argv[1], console);
	return EXIT_SUCCESS;
}
