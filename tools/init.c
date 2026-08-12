/* Init for the cjktty boot test.
 *
 * Asks the console which font it loaded and reports the answer on the serial
 * port, so the test does not depend on anyone looking at a screenshot. The
 * built-in VGA fonts hold 256 or 512 glyphs; the CJK font holds 65536 * 2, so
 * the count alone says whether the patch took effect. The CJK lines are written
 * to the framebuffer console as well, for the screenshot kept as an artifact.
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <linux/vt.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <unistd.h>

#define KDFONTOP 0x4B72
#define KD_FONT_OP_GET 1

struct console_font_op {
	unsigned int op;
	unsigned int flags;
	unsigned int width;
	unsigned int height;
	unsigned int charcount;
	unsigned char *data;
};

static int tty;
static int serial;

static void say(const char *text)
{
	size_t len = strlen(text);

	if (tty >= 0)
		(void)!write(tty, text, len);
	if (serial >= 0)
		(void)!write(serial, text, len);
}

/* The CJK literals below are the text whose rendering is under test. */
static void show_cjk(void)
{
	say("Simplified:  中文控制台显示测试\n");
	say("Traditional: 中文主控台顯示測試\n");
	say("Japanese:    日本語のコンソール表示テスト\n");
	say("Korean:      한국어 콘솔 표시 시험\n");
	say("ASCII:       abcdefghijklmnopqrstuvwxyz 0123456789\n");
}

int main(void)
{
	/* con_font_get returns ENOSPC unless width and height are at least as large
	 * as the loaded font; 32 is the pitch the GET path uses. */
	struct console_font_op font = { .op = KD_FONT_OP_GET, .width = 32, .height = 32 };
	char line[128];

	/* CONFIG_DEVTMPFS_MOUNT only covers a real root filesystem, so an initramfs
	 * has to mount /dev itself before any device node exists. */
	mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
	mount("proc", "/proc", "proc", 0, NULL);
	mount("sysfs", "/sys", "sysfs", 0, NULL);

	tty = open("/dev/tty0", O_WRONLY);
	serial = open("/dev/ttyS0", O_WRONLY);
	if (tty < 0 && serial < 0)
		serial = STDOUT_FILENO;

	/* Clear and home first: the checker reads fixed rows out of the screenshot,
	 * and the kernel log above would otherwise shift them. */
	say("\033[2J\033[H");
	say("cjktty boot test\n");
	show_cjk();

	/* Diagnostic only. cjktty leaves vc_font at the 256-glyph base font and
	 * renders CJK through its own buffer, so this count says nothing about the
	 * patch; whether the glyphs appear is decided from the screenshot. */
	if (tty >= 0 && ioctl(tty, KDFONTOP, &font) == 0)
		snprintf(line, sizeof(line), "vc-font: %ux%u charcount=%u\n",
			 font.width, font.height, font.charcount);
	else
		snprintf(line, sizeof(line), "vc-font: unavailable (%s)\n", strerror(errno));
	if (serial >= 0)
		(void)!write(serial, line, strlen(line));

	/* The serial port is an emulated UART and fbcon draws pixel by pixel, so
	 * under TCG the marker outruns the glyphs the screenshot is taken for.
	 * VT_WAITACTIVE returns once the console has finished switching, and the
	 * sleep covers the drawing that follows it. */
	if (tty >= 0)
		(void)ioctl(tty, VT_WAITACTIVE, 1);
	sleep(3);

	if (serial >= 0)
		(void)!write(serial, "CJKTTY-BOOTED\n", 14);

	say("=== end ===\n");
	sync();

	for (;;)
		pause();
}
