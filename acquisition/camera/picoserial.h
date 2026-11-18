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

    // Sends one command line and waits for "pong". The firmware prints an
    // [INFO] line first, then performs the action (relay on for the heating
    // duration), then replies - so the timeout has to cover the action, not just
    // the wire.
    bool sendCommand(const std::string& command, std::chrono::milliseconds timeout) {
        if (fd < 0) return false;

        const std::string line = command + "\n";
        if (::write(fd, line.data(), line.size()) < 0) {
            std::cerr << "[ERROR] Write to serial failed\n";
            return false;
        }

        const auto start = std::chrono::steady_clock::now();
        std::string response;
        char buf[256];
        while (true) {
            const ssize_t n = ::read(fd, buf, sizeof(buf));
            if (n > 0) {
                response.append(buf, static_cast<size_t>(n));
                if (response.find("pong") != std::string::npos) {
                    std::cout << "[INFO] Pico confirmed: " << command << "\n";
                    return true;
                }
                if (response.find("error") != std::string::npos) {
                    std::cerr << "[ERROR] Pico rejected \"" << command << "\": " << response << "\n";
                    return false;
                }
            }
            if (std::chrono::steady_clock::now() - start > timeout) {
                std::cerr << "[ERROR] Timeout waiting for pong after \"" << command << "\". Got: "
                          << response << "\n";
                return false;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
    }
};
