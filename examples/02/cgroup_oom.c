/* cgroup malloc fixture for 总表 2b / 13 (slurm_oom).
 * Usage: cgroup_oom [bytes]
 * Default 268435456 (256 MiB): larger than a tiny --mem demo (AGENT_CASE_MEM).
 * Do NOT size this to fill the node.
 * 2a kernel OOM (dmesg "Killed process" → node_local) is unittest-only;
 * never run this binary as an srun demo intended to trigger the kernel OOM killer.
 */
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    size_t bytes = 256UL * 1024UL * 1024UL;
    if (argc > 1 && argv[1][0] != '\0') {
        bytes = (size_t)strtoull(argv[1], NULL, 10);
        if (bytes < 4096UL) {
            bytes = 4096UL;
        }
    }
    fprintf(stderr, "cgroup_oom malloc bytes=%zu\n", bytes);
    fflush(stderr);
    char *p = (char *)malloc(bytes);
    if (p == NULL) {
        perror("malloc");
        return 1;
    }
    for (size_t i = 0; i < bytes; i += 4096UL) {
        p[i] = (char)(i & 0xff);
    }
    p[bytes - 1] = 1;
    sleep(30);
    free(p);
    return 0;
}
