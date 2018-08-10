from collections import OrderedDict
from subprocess import Popen, PIPE
import os, sys
from logger import Logger

REPQUOTA = "/usr/sbin/repquota"


class FilesystemUtils(object):
	def __init__(self, log):
		self.homes = {}
		self.quotas = {}
		self.log = log

	def get_homes(self):
		"""Return a dictionary containing home mounts - {home1:[/dev/sda1, total_size, free_size, free_percent]}"""
		with open("/etc/mtab") as f:
			for line in f.readlines():
				if "usrjquota=" in line and ("/home" in line.split()[1] or line.split()[1] == '/'):
					# {"/home1":"/dev/sda1"}
					self.homes[line.split()[1]] = [line.split()[0]]

		# There is a separate home partition.
		if len(self.homes) > 1:
			self.homes.pop('/', None)
			self.log.debug("Detected seperate home partitions:" + ' '.join(self.homes.keys()))

		# Replace "/" with "/home" if there is only single filesystem.
		if "/" in self.homes and "/home" not in self.homes:
			self.log.debug("No seperate home partitions detected:")
			self.homes["/home"] = self.homes.pop("/")
			self.log.debug("/home is on partition " + self.homes["/home"][0])

		for home in self.homes.keys():
			total_size, used_size, percent_used = get_fs_size(home)
			if percent_used is not None:
				self.homes[home].extend([total_size, used_size, percent_used])
			else:
				self.log.error("Couldn't determine free size of the filesystem", home)

		# Order by free percentage (ascending)
		self.homes = OrderedDict(sorted(self.homes.items(), key=lambda x: x[1][3], reverse=True))

		return self.homes

	def get_quota(self, fs="/home"):
		"""Return an ordered dictionary with {username:quota} in descending order"""
		self.log.debug("Running: " + ' '.join([REPQUOTA, self.homes[fs][0]]))
		rep = Popen([REPQUOTA, self.homes[fs][0]], stdout = PIPE, stderr=PIPE)
		res, err = rep.communicate()
		if err != '':
			self.log.critical("Error in repquota: " + err)
		# Actual repquota results starts from line 5
		res = res.splitlines()
		res = res[5:]
		for line in res:
			# To avoid the blank lines at the end of result.
			if len(line) > 5:
				self.quotas[line.split()[0]] = line.split()[2]
		self.quotas = OrderedDict(sorted(self.quotas.items(), key=lambda x: int(x[1]), reverse=True))
		self.log.debug("QUOTA RESULTS:\n" + '\n'.join(["%s - %s" % (a, b) for a,b in self.quotas.items()]))
		return self.quotas


def get_fs_size(fs):
	"""Return filesystem size (MB), used size (MB), usage percentage"""
	try:
		fs_stats = os.statvfs(fs)
	except Exception, e:
		return None, None, None
	total_size = (fs_stats.f_frsize * fs_stats.f_blocks)/float(1024 * 1024)
	used_size = total_size - ((fs_stats.f_frsize * fs_stats.f_bfree)/float(1024 * 1024))
	percent_used = (used_size * 100)/total_size
	return total_size, used_size, percent_used


def unit_converter(val, from_u, to_u):
	"""convert value from one unit to another"""
	converter = {'b':0, 'k':1, 'm':2, 'g':3, 't':4}
	if converter[from_u] < converter[to_u]:
		val = float(val)
		for _ in range(converter[to_u] - converter[from_u]):
			val = val/1024
	else:
		for _ in range(converter[from_u] - converter[to_u]):
			val = val * 1024
			
	return val 


def show_progress(message, progress):
    sys.stdout.write("%s: %s\r" % (message, str(progress)))
    sys.stdout.flush()