#Author - Austin Marcus
#Tarrlab @ Carnegie Mellon University
#October 2018
#aimarcus@andrew.cmu.edu

import os
import subprocess
import pip

#install package
def pip_install(modname):
	if hasattr(pip, 'main'):
		pip.main(['install', modname])
	else:
		pip._internal.main(['install', modname])

print('\n')
print('-----------------------')
print('------physio2bids------')
print('-----------------------')
print('(c) 2018 Austin Marcus')
print('Tarrlab @ Carnegie Mellon University')
print('-----------------------')
print("Installing...\n")

#check if pydicom present, get it if not
try:
	import pydicom
except ImportError, e:
	print('Did not find package pydicom - installing it now')
	pip_install('pydicom')

#make physio2bids executable
ex = 'chmod +x physio2bids'
proc = subprocess.Popen(ex.split(), stdin=subprocess.PIPE)
proc.communicate()

#put physio2bids in /usr/local/bin
cwd = os.getcwd()
install_dest = '/usr/local/bin/'
cmd = "sudo -S cp %s %s" % (os.path.join(cwd, 'physio2bids'), install_dest)
proc = subprocess.Popen(cmd, shell=True)
while proc.returncode == None:
	proc.wait()

print('Installed as /usr/local/bin/physio2bids')
print('Installation complete.')
print('-----------------------\n')
