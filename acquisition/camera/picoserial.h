#pragma once

// USB-CDC link to the Pico that runs the lamp-relay firmware (acquisition/pico_firmware/main.py).

#include <sys/ioctl.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>

// Address the board by its stable by-id symlink: /dev/ttyACM* numbering follows
// enumeration order, so the Pico lands on ttyACM1 whenever an ODrive is up on ttyACM0.
// Override with PICO_SERIAL_PORT.
inline const char* picoSerialPort() {
    const char* env = std::getenv("PICO_SERIAL_PORT");
    return (env && *env) ? env : "/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_e6614104034a962a-if00";
}

class PicoLink {
    int fd = -1;

public:
    PicoLink() = default;
    PicoLink(const PicoLink&) = delete;
    PicoLink& operator=(const PicoLink&) = delete;
    ~PicoLink() { close(); }

    // Opening a CDC-ACM port in the usual way raises DTR, and MicroPython answers a
    // rising DTR with a soft reset: main.py restarts, and a command written right
    // after open is swallowed by the REPL
    // boot window instead of reaching main.py's command loop. Keep DTR and RTS low
    // across open, and leave HUPCL cleared so closing does not toggle them either.
    bool open() {
        const char* port = picoSerialPort();
        fd = ::open(port, O_RDWR | O_NOCTTY | O_NONBLOCK);
        if (fd < 0) {
            std::cerr << "[ERROR] Cannot open " << port << ": " << std::strerror(errno) << "\n";
            return false;
        }
        ::ioctl(fd, TIOCEXCL);
        int low = TIOCM_DTR | TIOCM_RTS;
        ::ioctl(fd, TIOCMBIC, &low);

        struct termios tty {};
        if (::tcgetattr(fd, &tty) != 0) {
            std::cerr << "[ERROR] tcgetattr: " << std::strerror(errno) << "\n";
            close();
            return false;
        }
        cfsetospeed(&tty, B115200);
        cfsetispeed(&tty, B115200);
        tty.c_iflag = 0;
        tty.c_oflag = 0;
        tty.c_lflag = 0;
        tty.c_cflag = CLOCAL | CREAD | CS8;  // HUPCL clear: close() must not drop DTR
        tty.c_cc[VMIN] = 0;
        tty.c_cc[VTIME] = 0;  // reads are polled against our own deadline
        ::tcflush(fd, TCIOFLUSH);
        if (::tcsetattr(fd, TCSANOW, &tty) != 0) {
            std::cerr << "[ERROR] tcsetattr: " << std::strerror(errno) << "\n";
            close();
            return false;
        }
        ::fcntl(fd, F_SETFL, ::fcntl(fd, F_GETFL) & ~O_NONBLOCK);

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        ::tcflush(fd, TCIFLUSH);  // drop any boot chatter already queued
        return true;
    }

    void close() {
        if (fd >= 0) ::close(fd);
        fd = -1;
    }

    // The firmware prints an [INFO] line, performs the action (relay on for the
    // heating duration), and only then replies "pong" (or "error" if it rejected
    // the command). send() + poll() let the caller keep working - e.g. grabbing
    // frames - while that happens, instead of blocking until the reply.
    enum class Reply { Pending, Pong, Error };

    // Writes one command line without waiting for the reply.
    bool send(const std::string& command) {
        if (fd < 0) return false;
        received_.clear();
        const std::string line = command + "\n";
        if (::write(fd, line.data(), line.size()) < 0) {
            std::cerr << "[ERROR] Write to serial failed: " << std::strerror(errno) << "\n";
            return false;
        }
        return true;
    }

    // Collects whatever has arrived since send() and reports whether the reply is
    // complete. Never blocks: the port is opened with VMIN = VTIME = 0.
    Reply poll() {
        if (fd < 0) return Reply::Error;
        char buf[256];
        ssize_t n;
        while ((n = ::read(fd, buf, sizeof(buf))) > 0) {
            received_.append(buf, static_cast<size_t>(n));
        }
        if (received_.find("pong") != std::string::npos) return Reply::Pong;
        if (received_.find("error") != std::string::npos) return Reply::Error;
        return Reply::Pending;
    }

    // Everything the Pico sent since the last send(), for error messages.
    const std::string& received() const { return received_; }

private:
    std::string received_;
};
