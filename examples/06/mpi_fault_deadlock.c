/* MPI deadlock fixture. Usage: mpi_fault_deadlock [work_s] [skip_rank]
 * Print "rank N deadlock" then skip_rank omits MPI_Barrier; others wait.
 * Demo MUST pass a short --time so SLURM eventually TIMEOUTs; rollup keeps mpi_deadlock.
 */
#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);
    int rank = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);

    int work_s = 5;
    int skip_rank = 0;
    if (argc > 1 && argv[1][0] != '\0') {
        work_s = atoi(argv[1]);
        if (work_s < 1) {
            work_s = 1;
        }
    }
    if (argc > 2 && argv[2][0] != '\0') {
        skip_rank = atoi(argv[2]);
    }

    time_t t0 = time(NULL);
    volatile unsigned long busy = 0;
    while ((time(NULL) - t0) < work_s) {
        for (int i = 0; i < 100000; i++) {
            busy += (unsigned long)i;
        }
        if (rank == 0) {
            fprintf(stderr, "mpi_fault_deadlock rank0 working elapsed=%ld busy=%lu\n",
                    (long)(time(NULL) - t0), (unsigned long)busy);
            fflush(stderr);
        }
        usleep(200000);
    }

    fprintf(stderr, "rank %d deadlock (skip barrier)\n", rank);
    fflush(stderr);
    if (rank != skip_rank) {
        MPI_Barrier(MPI_COMM_WORLD);
    }
    sleep(3600);
    MPI_Finalize();
    return 0;
}
