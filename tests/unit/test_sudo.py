import sys
from PyQt5.QtCore import QCoreApplication, QProcess

app = QCoreApplication(sys.argv)
proc = QProcess()
proc.start("sudo", ["echo", "hi"])
proc.waitForFinished()
print("STDOUT:", proc.readAllStandardOutput().data().decode())
print("STDERR:", proc.readAllStandardError().data().decode())
