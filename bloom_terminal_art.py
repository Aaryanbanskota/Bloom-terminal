#!/usr/bin/env python3
"""
Bloom Terminal — ASCII welcome art
Run: python3 bloom_terminal_art.py
"""

# ANSI colors
RESET   = "\033[0m"
BOLD    = "\033[1m"
WHITE   = "\033[97m"
RED     = "\033[91m"
ORANGE  = "\033[38;5;208m"
DEEPRED = "\033[38;5;196m"
BLUE    = "\033[94m"
CYAN    = "\033[96m"
DARK    = "\033[38;5;236m"

art = f"""
{BLUE}         _(\\    {CYAN}/)_
        {BLUE}(  \\  {CYAN}/  )
         {BLUE}\\_\\||//_/{RESET}
{ORANGE}          .-"``"-.
{ORANGE}         /  {DEEPRED}.::.{ORANGE}  \\
{ORANGE}        |  {DEEPRED}::::::{ORANGE}  |
{ORANGE}         \\  {DEEPRED}"::"{ORANGE}  /
{ORANGE}          `-.__.-'
{DARK}            ||
{DARK}            ||
{DARK}           /||\\
"""

banner = f"""
{BOLD}{WHITE}   __        __   _                            _
{BOLD}{WHITE}   \\ \\      / /__| | ___ ___  _ __ ___   ___    | |_ ___
{BOLD}{WHITE}    \\ \\ /\\ / / _ \\ |/ __/ _ \\| '_ ` _ \\ / _ \\   | __/ _ \\
{BOLD}{WHITE}     \\ V  V /  __/ | (_| (_) | | | | | |  __/   | || (_) |
{BOLD}{WHITE}      \\_/\\_/ \\___|_|\\___\\___/|_| |_| |_|\\___|    \\__\\___/
{RESET}
{BOLD}{DEEPRED}   ____  _        ___   ___  __  __       {BOLD}{WHITE}____  _____ ____  __  __ ___ _   _    _    _
{BOLD}{DEEPRED}  | __ )| |      / _ \\ / _ \\|  \\/  |     {BOLD}{WHITE}|_   _| ____|  _ \\|  \\/  |_ _| \\ | |  / \\  | |
{BOLD}{DEEPRED}  |  _ \\| |     | | | | | | | |\\/| |       {BOLD}{WHITE}| | |  _| | |_) | |\\/| || ||  \\| | / _ \\ | |
{BOLD}{DEEPRED}  | |_) | |___  | |_| | |_| | |  | |       {BOLD}{WHITE}| | | |___|  _ <| |  | || || |\\  |/ ___ \\| |___
{BOLD}{DEEPRED}  |____/|_____|  \\___/ \\___/|_|  |_|       {BOLD}{WHITE}|_| |_____|_| \\_\\_|  |_|___|_| \\_/_/   \\_\\_____|
{RESET}
"""

if __name__ == "__main__":
    print(art)
    print(banner)
