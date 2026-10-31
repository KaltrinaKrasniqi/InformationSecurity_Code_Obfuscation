#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
/* Benign research target. The secret intentionally lives in the program.
 * --benchmark measures the checker inside one process, excluding startup/I/O.
 * Input is supplied on stdin, including benchmark input, never generated from ground truth here.
 */
int check_password(const char *input) {
    return strcmp(input, "K0sova_2026!") == 0;
}

static double now_ns(void) {
#ifdef _WIN32
    return (double)clock() * (1000000000.0 / CLOCKS_PER_SEC);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e9 + ts.tv_nsec;
#endif
}
int main(int argc, char **argv) {
    char input[128], wrong[128];
    unsigned long i, iterations;
    volatile unsigned long accepted = 0;
    double start, elapsed;
    if (!fgets(input, sizeof(input), stdin)) return 1;
    input[strcspn(input, "\r\n")] = 0;
    if (argc == 3 && strcmp(argv[1], "--benchmark") == 0) {
        iterations = strtoul(argv[2], NULL, 10);
        if (iterations < 1 || iterations > 100000000) return 2;
        strcpy(wrong, input);
        if (wrong[0]) wrong[0] = wrong[0] == 'X' ? 'Y' : 'X';
        else strcpy(wrong,"WRONG");
        for (i=0; i<1000; ++i) accepted += check_password((i&1) ? input : wrong);
        start=now_ns();
        for (i=0; i<iterations; ++i) accepted += check_password((i&1) ? input : wrong);
        elapsed=now_ns()-start;
        printf("BENCH_NS %.9f\nCHECKSUM %lu\n", elapsed/iterations, (unsigned long)accepted);
        return 0;
    }
    puts(check_password(input) ? "SUCCESS" : "FAIL");
    return 0;
}
