/* Application I/O failure: open a path that does not exist (ENOENT). */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
    const char *path = "/no/such/agent-sidecar/missing-input.bin";
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        fprintf(stderr, "open %s: %s\n", path, strerror(errno));
        fflush(stderr);
        return 1;
    }
    close(fd);
    return 0;
}
