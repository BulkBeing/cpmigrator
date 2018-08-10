from filesystemutils import unit_converter
from logger import Logger
import socket

class bgcolors:
	PINK = '\033[95m'
	BLUE = '\033[94m'
	GREEN = '\033[92m'
	YELLOW = '\033[93m'
	RED = '\033[91m'
	END = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'


class Templates(object):
	def __init__(self, log, user_to_move='', dest_server='', homes=dict()):
		self.log = log
		self.user_to_move = user_to_move
		self.dest_server = dest_server
		self.homes = homes


	def prompt_home_selection(self):
		"""Prompt the list of /home* filesystems to chose from and return the selected filesystem"""
		if self.user_to_move != '':
			# The user to be migrated is specified.
			return self.user_to_move, None

		print bgcolors.BLUE + "Select a home partition:" + bgcolors.END
		i = 1
		selection = {}
		print(bgcolors.GREEN + "{0:>2s}  {1:<6s}\t{2:<9s}\t{3:<8s}\t{4:<4s}%".format("Id", "HOME", "Total(GB)", "Used(GB)", "Used") + bgcolors.END)
		for home in self.homes:
			print(bgcolors.YELLOW + "{0:>2d}) {1:<6s}\t{2:<9.2f}\t{3:<8.2f}\t{4:<4.2f}%".format(i, home, unit_converter(self.homes[home][1],'m','g'), unit_converter(self.homes[home][2], 'm','g'), self.homes[home][3]) + bgcolors.END)
			#print bgcolors.YELLOW + str(i) + ". " + home + "\t" + str(self.homes[home][1]) + "MB\t" + str(self.homes[home][2]) + "MB\t" + str(self.homes[home][3]) + "%" + bgcolors.END
			selection[str(i)] = home
			i = i + 1
		inp = raw_input('Enter a choice[default is "1": ')
		if inp not in selection:
			inp = '1'
			#choice = raw_input(bgcolors.BOLD + "Continue with selecting user for migration from " + selection[inp] + " [y|n|default=y]? ")
			#if choice.lower() == 'n':
			#	self.prompt_home_selection()
		return None, selection[inp]

	def prompt_user_selection(self, users_list, reseller_list):
		"""Displays a list of users with their account details to chose from"""
		print bgcolors.BLUE + "Select an account for migration:" + bgcolors.END
		print(bgcolors.GREEN + "Id  {0:<15s}\t{1:<7s}\t{2:<11s}\t{3:<4s}".format("User", "Quota", "External DNS", "Resold") + bgcolors.END)
		for i,u in enumerate(users_list):
			is_resold = "Yes" if u.is_resold else "No"
			print(bgcolors.YELLOW + "{0:>2d}) {1:<15s}\t{2:<7.2f}\t{3:<11d}\t{4:<4s}".format(i+1, u.user_name, unit_converter(float(u.quota),'k','g'), u.ext_dns, is_resold) + bgcolors.END)
			#print bgcolors.YELLOW + str(i+1) + ") " + u.user_name + "\t" + u.quota + "\t" + str(u.ext_dns) + "\t" + is_resold + bgcolors.END
		selection = raw_input("Enter selection[default=1]>> ")
		try:
			if selection == "":
				selection = 1
			else:
				selection = int(selection)
				if selection > len(users_list):
					raise Exception
		except:
			print bgcolors.RED + "Invalid selection" + bgcolors.END
			migrate_user = self.prompt_user_selection(users_list, reseller_list)
			return migrate_user
		migrate_user = users_list[selection - 1]

		# If the selected account comes under a reseller...
		if migrate_user.is_resold or migrate_user.user_name in reseller_list:
			print bgcolors.PINK + "The user(" + migrate_user.user_name + ") is either a resold or a reseller account. As of now, this script doesn't support migrating a reseller/resold account. Please choose another account." + bgcolors.END
			migrate_user = self.prompt_user_selection(users_list, reseller_list)
			print bgcolors.GREEN + "Selected account for migration: " + migrate_user.user_name + bgcolors.END
			return migrate_user

		print bgcolors.GREEN + "Selected account for migration: " + migrate_user.user_name + bgcolors.END
		cont = raw_input("Continue? [y|n default=y] >> ").strip()
		if cont.upper() == 'N':
			migrate_user = self.prompt_user_selection(users_list, reseller_list)

		return migrate_user

	def prompt_dest_selection(self):
		"""Get the destination server name from user"""
		prompt = bgcolors.GREEN + "Enter destination server name: " + bgcolors.END
		dest = raw_input(prompt)
		ip_addr = ''
		self.log.debug("User entered destination server: " + dest.strip())
		try:
			ip_addr = socket.gethostbyname(dest.strip())
		except:
			print bgcolors.YELLOW + "Couldn't resolve destination hostname : " + bgcolors.END + bgcolors.BLUE + dest + bgcolors.END
			self.log.debug("Couldn't resolve destination hostname : " + dest.strip())
			s = raw_input(bgcolors.RED + "Are you sure you want to continue? [y|n default=n] >> " + bgcolors.END)
			if s.strip().upper != 'Y':
				dest = self.prompt_dest_selection()
		self.dest_server = dest
		return dest, ip_addr
	

def display_command(server_name='', command='', help_text='', title=False, prompt=False):
	if title:
		print(bgcolors.BLUE + "\nRun the below commands on destination server(" + server_name + ")" + bgcolors.END)
	if command != '':
		print(bgcolors.GREEN + command + bgcolors.END)
	if help_text != '':
		print(bgcolors.YELLOW + "(" + help_text + ")" + bgcolors.END + "\n")
	if prompt:
		while raw_input(bgcolors.BOLD + "\nProceed [y|n] >> " + bgcolors.END).strip().lower() == 'n':
			continue


