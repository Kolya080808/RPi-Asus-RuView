/* One reviewed short trial. No daemon, persistent settings or broad PID kills.
 * Time bounds do not recover an uninterruptible kernel/driver. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef WL_PROGRAM
#define WL_PROGRAM "/usr/sbin/wl"
#endif
static volatile sig_atomic_t interrupted;
static void stop(int sig) { (void)sig; interrupted = 1; }
static double now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) _exit(90);
    return t.tv_sec + t.tv_nsec / 1e9;
}
static void nap(void) { struct timespec t = {0, 10000000}; nanosleep(&t, NULL); }
static int wait_child(pid_t pid, double seconds) {
    double end = now() + seconds;
    int status;
    do {
        pid_t done = waitpid(pid, &status, WNOHANG);
        if (done == pid) return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
        if (done < 0 && errno != EINTR) return 91;
        nap();
    } while (now() < end);
    /* Signal only our still-unreaped child, whose PID cannot have been reused. */
    kill(pid, SIGKILL);
    end = now() + .3;
    do { if (waitpid(pid, &status, WNOHANG) == pid) return 124; nap(); } while (now() < end);
    return 125; /* May be stuck in kernel; never claim process cleanup. */
}
static int command(const char *iface, const char *operation, const char *peer) {
    pid_t child = fork();
    if (child < 0) return 92;
    if (!child) {
        /* wl output is diagnostic; stdout contains reader envelopes only. */
        dup2(STDERR_FILENO, STDOUT_FILENO);
        if (!strcmp(operation, "add"))
            execl(WL_PROGRAM, WL_PROGRAM, "-i", iface, "csimon", operation, peer, "500", (char *)NULL);
        else if (!strcmp(operation, "del"))
            execl(WL_PROGRAM, WL_PROGRAM, "-i", iface, "csimon", operation, peer, (char *)NULL);
        else execl(WL_PROGRAM, WL_PROGRAM, "-i", iface, "csimon", operation, (char *)NULL);
        _exit(127);
    }
    int result = wait_child(child, 1.0);
    fprintf(stderr, "supervisor command=%s pid=%ld exit=%d\n", operation, (long)child, result);
    return result;
}
int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--self-test")) {
        fprintf(stderr, "supervisor socket-free self-test; no commands\n"); return 0;
    }
    /* Current authorization covers this exact interface/protocol/known Pi peer. */
    if (argc != 3 || strcmp(argv[1], "--one-active-trial") ||
        strncmp(argv[2], "/tmp/ruview-active-", 19) || strlen(argv[2]) != 38 ||
        strcmp(argv[2] + 31, "-reader")) return 2;
    for (int i = 19; i < 31; ++i)
        if (!((argv[2][i] >= '0' && argv[2][i] <= '9') ||
              (argv[2][i] >= 'a' && argv[2][i] <= 'f'))) return 2;
    struct sigaction action;
    memset(&action, 0, sizeof(action)); sigemptyset(&action.sa_mask);
    action.sa_handler = stop;
    sigaction(SIGINT, &action, NULL); sigaction(SIGTERM, &action, NULL); sigaction(SIGHUP, &action, NULL);
    action.sa_handler = SIG_IGN; sigaction(SIGPIPE, &action, NULL);
    int pipefd[2];
    if (pipe(pipefd)) return 93;
    pid_t reader = fork();
    if (reader < 0) { close(pipefd[0]); close(pipefd[1]); return 94; }
    if (!reader) {
        close(pipefd[0]);
        if (pipefd[1] != 3) { if (dup2(pipefd[1], 3) < 0) _exit(95); close(pipefd[1]); }
        execl(argv[2], argv[2], "23", "8", "--ready-fd=3", (char *)NULL);
        _exit(127);
    }
    close(pipefd[1]);
    fprintf(stderr, "supervisor pid=%ld reader_pid=%ld\n", (long)getpid(), (long)reader);
    struct pollfd ready = {pipefd[0], POLLIN, 0};
    char marker = 0;
    int ready_ok = poll(&ready, 1, 1500) > 0 && read(pipefd[0], &marker, 1) == 1 && marker == 'R';
    close(pipefd[0]);
    int added = 0, enabled = 0, result = 2, cleanup = 0;
    const char *iface = "wl0.1", *peer = "88:A2:9E:94:7D:80";
    if (!ready_ok || interrupted) goto finish;
    added = 1; /* An ioctl may take effect even when its caller times out. */
    if (command(iface, "add", peer) || interrupted) goto finish;
    enabled = 1;
    if (command(iface, "enable", peer) || interrupted) goto finish;
    double end = now() + 5.0;
    while (!interrupted && now() < end) nap();
    result = interrupted ? 130 : 0;
finish:
    if (enabled && command(iface, "disable", peer)) cleanup = 1;
    if (added && command(iface, "del", peer)) cleanup = 1;
    /* Normal helper completion retains its exit/count diagnostic. */
    int reader_result = wait_child(reader, 3.0);
    fprintf(stderr, "supervisor reader_exit=%d cleanup=%s interrupted=%d\n",
            reader_result, cleanup ? "failed" : "commands-completed", (int)interrupted);
    if (cleanup) return 5;
    if (result) return result;
    return reader_result;
}
