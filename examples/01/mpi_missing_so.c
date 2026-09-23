/* MPI fixture linked against a .so whose rpath is never deployed.
 * Runtime loader fails with "cannot open shared object file" before main.
 */
#include <mpi.h>

void missing_symbol(void);

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);
    missing_symbol();
    MPI_Finalize();
    return 0;
}
