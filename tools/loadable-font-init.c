// SPDX-License-Identifier: GPL-2.0
/* Initramfs init for the loadable-font proof. */

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/wait.h>
#include <unistd.h>

static int tty;
static int serial;

static void say(int fd, const char *text)
{
	if (fd >= 0)
		(void)!write(fd, text, strlen(text));
}

static void show_console(void)
{
	say(tty, "\033[2J\033[H");
	say(tty, "cjktty loadable font test\n");
	/* The CJK literals below are the text whose rendering is under test. */
	say(tty, "Simplified:  中文控制台显示测试\n");
	say(tty, "Traditional: 中文主控台顯示測試\n");
	say(tty, "Japanese:    日本語のコンソール表示テスト\n");
	say(tty, "Korean:      한국어 콘솔 표시 시험\n");
	say(tty, "ASCII:       abcdefghijklmnopqrstuvwxyz 0123456789\n");
}

int main(void)
{
	int status;
	pid_t child;

	mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
	mount("proc", "/proc", "proc", 0, NULL);
	mount("sysfs", "/sys", "sysfs", 0, NULL);

	tty = open("/dev/tty0", O_WRONLY);
	serial = open("/dev/ttyS0", O_WRONLY);
	show_console();
	say(serial, "CJKTTY-BEFORE-LOAD\n");
	sleep(8);

	child = fork();
	if (child == 0) {
		execl("/load-cjk-font", "load-cjk-font", "/cjk-16.psf",
		      "/dev/tty0", NULL);
		_exit(127);
	}
	if (child < 0 || waitpid(child, &status, 0) < 0 ||
	    !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
		say(serial, "CJKTTY-LOAD-FAILED\n");
		for (;;)
			pause();
	}

	/*
	 * The font ioctl redraws the existing screen. Do not rewrite the CJK text:
	 * the post-load image must come from cells stored before the font arrived.
	 */
	say(serial, "CJKTTY-IOCTL-SUCCESS\n");
	say(serial, "CJKTTY-AFTER-LOAD\n");
	for (;;)
		pause();
}
