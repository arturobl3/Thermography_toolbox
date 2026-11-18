# WIC SDK
SDK designed for C++ development of applications that use WIC thermal cameras.

Version: 3.1

## Installation:
- Install provided eBUS Runtime: 
    - for Debian 11 and Ubuntu 20.04 use:
        ```bash
        apt install eBUS_Runtime_Ubuntu-20.04-x86_64-6.4.0-6670.deb
        ```
    - for Debian 12 and Ubuntu 22.04 use:
        ```bash
        apt install eBUS_Runtime_Ubuntu-22.04-x86_64-6.4.0-6670.deb
        ```
- Install WIC SDK package: 
    ```bash
    apt install wic-sdk_3.1_amd64.deb
    ```

## Usage:
WIC SDK provides CMake support. To use WIC SDK in Your own project, you can use:
```CMake
find_package(WIC REQUIRED)

...

target_link_libraries(<your_target> PRIVATE WIC::WIC)
```

For usage examples, please visit examples folder.

## Documentation
For detailed API documentation, please visit <a href="documentation/index.html" target="_blank">Documentation</a>

