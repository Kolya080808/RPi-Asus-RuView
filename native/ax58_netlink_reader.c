/* Bounded raw Netlink-to-stdout bridge. No monitor control, packets sent,
 * decoding, files, daemonization or persistent configuration. See docs.
 * Linux only; build static ARM EABI for the repeater. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/netlink.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define MAX_PAYLOAD 65536
#define MAX_RECORDS 64
static volatile sig_atomic_t stopped;
static uint64_t deadline;

static uint64_t now_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        perror("clock_gettime");
        _exit(2);
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static void stop_signal(int sig) { (void)sig; stopped = 1; }
static void alarm_signal(int sig) { (void)sig; _exit(124); }

/* Never let a stalled SSH stdout pipe keep the reader alive indefinitely. */
static int output(const void *bytes, size_t length) {
    const unsigned char *cursor = bytes;
    uint64_t write_deadline = now_ns() + UINT64_C(1000000000);
    if (write_deadline > deadline) write_deadline = deadline;
    while (length) {
        if (stopped || now_ns() >= write_deadline) { errno = ETIMEDOUT; return -1; }
        ssize_t n = write(STDOUT_FILENO, cursor, length);
        if (n > 0) { cursor += n; length -= (size_t)n; continue; }
        if (n < 0 && errno == EINTR) continue;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            struct pollfd fd = {STDOUT_FILENO, POLLOUT, 0};
            if (poll(&fd, 1, 20) < 0 && errno != EINTR) return -1;
            continue;
        }
        if (n == 0) errno = EIO;
        return -1;
    }
    return 0;
}

static void little32(unsigned char *out, uint32_t n) {
    for (unsigned i = 0; i < 4; ++i) out[i] = (unsigned char)(n >> (8 * i));
}

static int frame(const void *payload, size_t length, uint64_t seq,
                 uint64_t stamp, int truncated, const char *error) {
    char header[256];
    unsigned char sizes[8];
    int n = snprintf(header, sizeof(header),
        "{\"source_sequence\":%" PRIu64 ",\"source_monotonic_ns\":%" PRIu64
        ",\"truncated\":%s,\"receive_error\":%s}",
        seq, stamp, truncated ? "true" : "false", error ? error : "null");
    if (n < 0 || (size_t)n >= sizeof(header) || length > MAX_PAYLOAD) {
        errno = EOVERFLOW; return -1;
    }
    little32(sizes, (uint32_t)n); little32(sizes + 4, (uint32_t)length);
    if (output(sizes, sizeof(sizes)) || output(header, (size_t)n)) return -1;
    return output(payload, length);
}

int main(int argc, char **argv) {
    int protocol, seconds, flags, fd = -1, result = 2;
    uint64_t count = 0;
    unsigned char payload[MAX_PAYLOAD];
    struct sigaction action;
    /* No implicit protocol or run. The self-test opens no socket. */
    int self_test = argc == 2 && strcmp(argv[1], "--self-test") == 0;
    if (!self_test && (argc != 3 ||
        (strcmp(argv[1], "22") != 0 && strcmp(argv[1], "23") != 0) ||
        strlen(argv[2]) != 1 || argv[2][0] < '1' || argv[2][0] > '8')) {
        fprintf(stderr, "usage: ax58-netlink-reader {22|23} {1..8}\n"
                        "       ax58-netlink-reader --self-test (no socket)\n");
        return 2;
    }
    protocol = self_test ? 0 : atoi(argv[1]);
    seconds = self_test ? 2 : atoi(argv[2]);
    memset(&action, 0, sizeof(action));
    sigemptyset(&action.sa_mask);
    action.sa_handler = stop_signal;
    if (sigaction(SIGINT, &action, NULL) || sigaction(SIGTERM, &action, NULL)) return 2;
    action.sa_handler = alarm_signal;
    if (sigaction(SIGALRM, &action, NULL)) return 2;
    action.sa_handler = SIG_IGN;
    if (sigaction(SIGPIPE, &action, NULL)) return 2;
    alarm((unsigned)seconds + 2);
    deadline = now_ns() + (uint64_t)seconds * UINT64_C(1000000000);
    flags = fcntl(STDOUT_FILENO, F_GETFL);
    if (flags < 0 || fcntl(STDOUT_FILENO, F_SETFL, flags | O_NONBLOCK) < 0) {
        perror("stdout nonblocking"); return 2;
    }
    if (output("RUVRAW1\n", 8)) goto write_error;
    if (self_test) {
        for (size_t i = 0; i < 2064; ++i) payload[i] = (unsigned char)i;
        if (frame(payload, 2064, 0, 123456789, 0, NULL) ||
            frame(payload, 17, 1, 123456790, 1, "\"MSG_TRUNC\"")) goto write_error;
        fprintf(stderr, "self-test complete records=2; synthetic data only\n");
        return 0;
    }
    fd = socket(AF_NETLINK, SOCK_RAW | SOCK_NONBLOCK | SOCK_CLOEXEC, protocol);
    if (fd < 0) { perror("netlink socket"); goto done; }
    struct sockaddr_nl address;
    memset(&address, 0, sizeof(address));
    address.nl_family = AF_NETLINK;
    address.nl_pid = (uint32_t)getpid();
    address.nl_groups = 2; /* Inspected exporter broadcasts to group 2. */
    if (bind(fd, (struct sockaddr *)&address, sizeof(address))) {
        perror("netlink bind"); goto done;
    }
    while (!stopped && now_ns() < deadline && count < MAX_RECORDS) {
        struct pollfd ready = {fd, POLLIN, 0};
        int rc = poll(&ready, 1, 20);
        if (rc < 0 && errno == EINTR) continue;
        if (rc < 0) { perror("netlink poll"); goto done; }
        if (!rc) continue;
        struct sockaddr_nl sender;
        struct iovec iov = {payload, sizeof(payload)};
        struct msghdr message;
        memset(&sender, 0, sizeof(sender));
        memset(&message, 0, sizeof(message));
        message.msg_name = &sender; message.msg_namelen = sizeof(sender);
        message.msg_iov = &iov; message.msg_iovlen = 1;
        ssize_t n = recvmsg(fd, &message, MSG_TRUNC);
        uint64_t stamp = now_ns();
        if (n < 0 && (errno == EAGAIN || errno == EINTR)) continue;
        if (n < 0) {
            int saved = errno;
            const char *error = saved == ENOBUFS ? "\"ENOBUFS\"" : "\"recvmsg\"";
            if (frame(payload, 0, count, stamp, 0, error)) goto write_error;
            errno = saved; perror("netlink receive"); goto done;
        }
        int truncated = (message.msg_flags & MSG_TRUNC) != 0 || (size_t)n > sizeof(payload);
        int kernel = message.msg_namelen == sizeof(sender) &&
                     sender.nl_family == AF_NETLINK && sender.nl_pid == 0;
        const char *error = !kernel ? "\"unexpected_sender\"" : truncated ? "\"MSG_TRUNC\"" : NULL;
        size_t kept = (size_t)n > sizeof(payload) ? sizeof(payload) : (size_t)n;
        if (frame(payload, kept, count, stamp, truncated, error)) goto write_error;
        ++count;
        if (error) { fprintf(stderr, "receive rejected: %s\n", error); goto done; }
    }
    /* A limit or signal is not a normal end-of-source marker. */
    result = stopped ? 130 : count == MAX_RECORDS ? 4 : count == 0 ? 3 : 0;
    fprintf(stderr, "bounded reader exit=%d records=%" PRIu64 "; driver loss unknown\n", result, count);
    goto done;
write_error:
    perror("stdout frame write");
done:
    if (fd >= 0) close(fd);
    return result;
}
