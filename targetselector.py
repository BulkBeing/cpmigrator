from filesystemutils import FilesystemUtils, show_progress
from templates import Templates, bgcolors
from subprocess import Popen, PIPE
from collections import OrderedDict
import dns.resolver
import socket
import re, os

IFCONFIG = "/sbin/ifconfig"
GREP = "/bin/grep"

class User(object):
	"""To store user details for later sorting based on quota and number of domains using external dns"""
	def __init__(self, username="", quota=0, ext_dns=0, is_resold = False):
		self.user_name = username
		self.quota = quota
		self.ext_dns = ext_dns
		self.is_resold = is_resold
		self.source_server = socket.gethostname()
		self.dest_server = ''
		self.home_dir = ''
		self.dest_home_dir = ''


class Target(object):

	def __init__(self, log):
		self.log = log
		self.fs_utils = FilesystemUtils(self.log)
		self.homes = self.fs_utils.get_homes() # {home1:[/dev/sda1, total_size, free_size, free_percent]}
		self.ignore_users = ["root", "bin", "mysql", "daemon", "adm", "lp", "ntp", "sync", "shutdown", "halt", "mail", "uucp", "ftp", "nobody", "dbus", "vcsa", "saslauth", "sshd", "tcpdump", "named", "nscd", "mailnull", "mailman", "cpanelroundcube", "cpanelphpmyadmin", "cpanelphppgadmin", "cpanelcabcache", "cpanelrrdtool", "cpanellogin", "cpaneleximfilter", "cpaneleximscanner", "cpanelconnecttrack", "cpanelanalytics", "nginx", "cpanel", "zabbix", "postfix", "puppet", "dovecot"]
		self.server_ips = []
		#Main IP
		self.source_ip = ''
		self.source_name = ''
		self.destserver_name = ''
		self.destserver_ip = ''
		self.ext_dns = ['ns1.example.com.']
		# List of User objects.
		self.users = []
		self.migrate_user = ''
		#List of all reseller accounts
		self.reseller_list = self._get_resellers()

	def select_user(self, user_to_move='', dest_server='', ignore_users=[]):
		"""Return a candidate for migration"""
		self.user_to_move = user_to_move
		self.dest_server = dest_server
		if len(ignore_users) > 0:
			self.ignore_users.extend(ignore_users)
		self.template = Templates(self.log, self.user_to_move, self.dest_server, self.homes)
		if self.user_to_move == '':
			self.source_home = self.template.prompt_home_selection()[1]
			self.log.debug("User selected: " + self.source_home)
			self.quotas = self.fs_utils.get_quota(self.source_home) # OrderedDict({username:quota})
			self.log.debug("Quota results:\n" + '\n'.join([str(user) + " : " + str(quota) for user, quota in self.quotas.items()]))

			for u in self.ignore_users:
				self.quotas.pop(u, None)

			# For now, we only consider the top 10
			if len(self.quotas) > 10:
				self.quotas = OrderedDict(self.quotas.items()[0:10])

			# create a list of User objects
			for u in self.quotas.items():
				self.users.append(User(u[0], u[1], self.check_dns(self.get_list_of_domains(u[0])), self.is_resold(u[0])))
			print ""
			self.migrate_user = self.template.prompt_user_selection(self.users, self.reseller_list) # User object is returned.
			#Get users homedir
			self.migrate_user.home_dir = os.path.expanduser('~' + self.migrate_user.user_name)
			while not (os.path.isdir(self.migrate_user.home_dir) and self.migrate_user.home_dir.startswith('/home')):
				print(bgcolors.RED + "Couldn't determine " + self.migrate_user.user_name + "'s home directory." + bgcolors.END)
				self.log.debug("Couldn't determine " + self.migrate_user.user_name + "'s home directory.")
				self.migrate_user.home_dir = raw_input("Enter home directory of " + self.migrate_user.user_name + " >> ")
			return self.migrate_user



	def _get_server_ips(self):
		"""Get the list of IPs on the server"""
		p = Popen([IFCONFIG], stdout=PIPE)
		output = Popen([GREP, "inet addr"], stdin=p.stdout, stdout=PIPE)
		for line in output.stdout.readlines():
			self.server_ips.append(line.split()[1].split(':')[1])
		try:
			self.server_ips.remove('127.0.0.1')
		except:
			pass
		self.source_name = socket.gethostname()
		try:
			self.source_ip = socket.gethostbyname(self.source_name)
			if self.source_ip not in self.server_ips:
				raise Exception
		except:
			print(bgcolors.RED + "Couldn't determine this(source) server's IP address. Please specify it manually" + bgcolors.END)
			while self.source_ip not in self.server_ips:
				self.source_ip = raw_input("Enter this server's IP address >> ")
				if self.source_ip not in self.server_ips:
					print(bgcolors.RED + "The IP address you entered is not present on this server. Please enter a valid IP address." + bgcolors.END)


	def get_list_of_domains(self, username):
		"""Get the list of domains owned by that user"""
		domain_list = []
		with open("/etc/userdomains") as f:
			for line in f.readlines():
				if line.split()[1] == username:
					domain_list.append(line.split()[0].rstrip(':'))
		self.log.debug("Domains found under " + username + '\n' + '\n'.join(domain_list))
		return domain_list
	
	def _get_resellers(self):
		"""Get list of all resller accounts"""
		resellers = []
		with open("/etc/trueuserowners") as f:
			for line in f.readlines():
				u = line.split()[1]
				if u not in resellers and u != "root":
					resellers.append(u)	
		return resellers

	def is_resold(self, username):
		"""Return True if the user is under any reseller"""
		with open("/etc/trueuserowners") as f:
			for line in f.readlines():
				if username == line.split(":")[0]:
					if line.split()[1] == "root":
						self.log.debug(username + " is not under any reseller.")
						return False
					else:
						self.log.debug(username + " is under resller " + line.split()[1])
						return True
		return False

	def check_dns(self, domainlist):
		"""Check if all domains are using our DNS. Return the number of domains that are not using our DNS"""
		ext_dns = 0
		for dom in domainlist:
			show_progress("Checking nameservers of", dom)
			skip_loop = False
			try:
				self.log.debug("Checking DNS of: " + dom)
				dns_res = dns.resolver.query(dom, "NS")
			except:
				continue
			for x in dns_res:
				"""If at least one DNS server is ours or not resolving or pointing to server, the domain is
				considered to be using our DNS"""
				if str(x) in self.ext_dns:
					skip_loop = True
					break
				else:
					try:
						dns_ip = socket.gethostbyname(str(x))
						if dns_ip in self.server_ips:
							#print "dns server ip is present in server:", socket.gethostbyname(x)
							self.log.debug("DNS server " + str(x) + " IP points to this server. Resolved IP: " + dns_ip)
							skip_loop = True
							break
					except Exception, e:
						#print "Exception in getting ip of dns server", str(x), "ERROR:", str(e), 
						self.log.debug("Exception in getting IP of dns server " + str(x) + "ERROR: " + str(e))
						skip_loop = True
						break
			if skip_loop:
				continue
			else:
				ext_dns = ext_dns + 1
				self.log.debug("Name servers of " + dom + " is pointing to external IPs.")
		return ext_dns

	def get_dest_server(self):
		"""Get destination servers name, IP address"""
		self.dest_server, self.destserver_ip = self.template.prompt_dest_selection()
		self._get_server_ips()
		while self.destserver_ip == '' or not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",self.destserver_ip):

				print bgcolors.RED + "Couldn't determine destination server's public IP address" + bgcolors.END
				self.log.warning(self.destserver_ip + " is not a valid IP address.")
				self.destserver_ip = raw_input(bgcolors.GREEN + "Enter destination server's public IP address>> " + bgcolors.END)



