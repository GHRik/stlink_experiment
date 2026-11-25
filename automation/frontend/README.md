# HIL frontend prototype

Open [index.html](index.html) in a browser by double-clicking the local file. No installation or server is required.

The wiring diagram provides sample COM port selectors for STLINK, the relay controller and three DUTs. Duplicate assignments are flagged. The Run button beside the PC validates port assignments and displays a prototype message. Hardware access and configuration persistence are not implemented.

Each DUT has a local `.ino` file picker showing the selected filename. Files stay in the browser; they are not uploaded or flashed.
