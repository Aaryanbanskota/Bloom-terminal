import ptyprocess, os, termios
env = os.environ.copy()
env['PS1'] = ''
env['PROMPT_COMMAND'] = ''
pty = ptyprocess.PtyProcessUnicode.spawn(['/bin/bash', '--norc', '--noprofile'], env=env)
attrs = termios.tcgetattr(pty.fd)
attrs[3] = attrs[3] & ~termios.ECHO
termios.tcsetattr(pty.fd, termios.TCSANOW, attrs)
pty.write("ls\n")
import time; time.sleep(0.5)
print("Reading:", repr(pty.read(1024)))
