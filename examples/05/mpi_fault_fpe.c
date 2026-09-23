/* MPI SIGFPE fault fixture. Usage: mpi_fault_fpe [work_s] [fault_rank]
 * Busy-wait then raise(SIGFPE) after printing "rank N fpe".
 */
#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <mpi.h>
#include <signal.h>
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
    int fault_rank = 0;
    if (argc > 1 && argv[1][0] != '\0') {
        work_s = atoi(argv[1]);
        if (work_s < 1) {
            work_s = 1;
        }
    }
    if (argc > 2 && argv[2][0] != '\0') {
        fault_rank = atoi(argv[2]);
    }

    time_t t0 = time(NULL);
    volatile unsigned long busy = 0;
    while ((time(NULL) - t0) < work_s) {
        for (int i = 0; i < 100000; i++) {
            busy += (unsigned long)i;
        }
        if (rank == 0) {
            fprintf(stderr, "mpi_fault_fpe rank0 working elapsed=%ld busy=%lu\n",
                    (long)(time(NULL) - t0), (unsigned long)busy);
            fflush(stderr);
        }
        usleep(200000);
    }

    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == fault_rank) {
        fprintf(stderr, "rank %d fpe (SIGFPE)\n", rank);
        fflush(stderr);
        raise(SIGFPE);
    }
    sleep(3);
    _exit(0);
    return 0;
}
