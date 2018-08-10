#!/usr/bin/python2

from targetselector import Target
from templates import bgcolors, display_command
from logger import Logger
import os
from subprocess import Popen, PIPE, call
import re
import sys
import datetime

# Destination server's SSH port.
SSH_PORT = "22"
log = Logger()

def run_command(cmd, shell=False):
	"""
	Runs the commands passed as array and displays the ouput in realtime
	Returns output, error and exit status
	"""
	log.debug("Running command: " + ' '.join(cmd))
	process = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=shell)
	cmd_out = ''
	cmd_err = ''
	while True:
		out = process.stdout.readline()
		if out == '' and process.poll() != None:
			cmd_err = process.stderr.read()
			break
		if out != '':
			sys.stdout.write(out)
			sys.stdout.flush()
			cmd_out += out
			
	if cmd_err != '':
		log.warning("Error running command: " + cmd_err)
	return cmd_out, cmd_err, process.returncode

def ssh_command(dest, command, s_user="root", s_key=''):
	if s_key != '':
		ssh = Popen(["ssh", "-i", s_key, "-p", SSH_PORT,"-o", "PasswordAuthentication=no", "-o", "StrictHostKeyChecking=no", s_user + "@" + dest, command], shell=False, stdout=PIPE, stderr=PIPE)
		log.debug("Running: " + ' '.join(["ssh", "-i", s_key, "-p", SSH_PORT,"-o", "PasswordAuthentication=no", "-o", "StrictHostKeyChecking=no", s_user + "@" + dest, command]))
	else:
		ssh = Popen(["ssh", "-p", SSH_PORT, "-o", "PasswordAuthentication=no", "-o", "StrictHostKeyChecking=no", s_user + "@" + dest, command], shell=False, stdout=PIPE, stderr=PIPE)
		log.debug("Running: " + ' '.join(["ssh", "-p", SSH_PORT, "-o", "PasswordAuthentication=no", "-o", "StrictHostKeyChecking=no", s_user + "@" + dest, command]))
	return ssh.stdout.read(), ssh.stderr.read(), ssh.returncode

def restore_on_dest(dest, s_key, filename):
	"""Run restoration command on destination server"""
	restore_cmd = [
                "ssh",
                "-p", SSH_PORT,
                "-o", "PasswordAuthentication=no",
                "-o", "StrictHostKeyChecking=no",
                "-i", s_key,
                "root@" + dest,
                "/scripts/restorepkg " + filename
            	]	
	return run_command(restore_cmd)

def final_sync(target, s_key, migrate_user):
	"""Do a final sync of home directories"""
	log.debug("Starting final sync of home directories")
	rsync = 'rsync -avP --bwlimit=3200 -e "ssh -o StrictHostKeyChecking=no -i ' + s_key + ' -p ' + SSH_PORT + '" ' + migrate_user.home_dir + '/ ' + target.destserver_ip + ':' + migrate_user.dest_home_dir + '/'

	# rsync = [
	# 			'rsync',
	# 			'-avP',
	# 			'--bwlimit=3200',
	# 			'-e', '"ssh -o StrictHostKeyChecking=no -i ' + s_key + ' -p ' + SSH_PORT + '"',
	# 			migrate_user.home_dir + '/',
	# 			target.destserver_ip + ':' + migrate_user.dest_home_dir + '/'
	# 		]
	# r = Popen([rsync], shell=True, stdout=PIPE, stderr=PIPE)
	# return r.stdout.read(), r.stderr.read()
	return run_command([rsync], True)

def final_reply(dest_server):
	"""Print final reply for customer"""
	reply = """
I'm happy to inform you that we have finished migrating your website content. So far, we have copied your site files and databases, and we've also made the necessary changes so everything is connected. Now you will need to check your sites to ensure everything has been moved correctly.

If you are making use of our mail server then make sure that the mail client settings is as follows:

Incoming Server :    {0}
Incoming Ports  :    IMAP - 143/POP - 110
Outgoing Server :    {1}
SMTP (Outgoing) Port:      25

If everything is working correctly then nothing else needs to be done, however if you do find any issues please update this ticket accordingly.
           """.format(dest_server, dest_server)
	print(bgcolors.GREEN + "-" * 10 + bgcolors.END)
	print(bgcolors.YELLOW + reply + bgcolors.END)
	print(bgcolors.GREEN + "-" * 10 + bgcolors.END)


def main():
	ticket_id = ''
	while ticket_id == '':
		ticket_id = raw_input(bgcolors.BLUE + "Enter the ticket ID >> " + bgcolors.END)
	target = Target(log)
	migrate_user = target.select_user()  # Returns a targetselector.User() object

	#Ask destination server details
	target.get_dest_server()

	#Create a channel between source and destination
	display_command(server_name = target.dest_server, command = "ipset add ssh_in " + target.source_ip, title=True)
	display_command(command="nano /etc/security/access.conf && chattr +i /etc/security/access.conf")
	display_command(help_text="add " + target.source_ip + "to the list of ip's at the end", prompt=True)

	#Select the home partition with maximum space for saving the pkgaccount files
	home_dir = sorted(target.homes.items(), key=lambda val: val[1][1] - val[1][2], reverse=True)[0][0]
	backup_dir = home_dir + "/accttransfer"
	log.debug("/scripts/pkgacct files will be stored in " + backup_dir)
	if not os.path.isdir(backup_dir):
		os.mkdir(backup_dir)
	if os.path.isfile(backup_dir + '/mig_key'):
		os.rename(backup_dir + '/mig_key', backup_dir + '/mig_key-backup')
	if os.path.isfile(backup_dir + '/mig_key.pub'):
		os.rename(backup_dir + '/mig_key.pub', backup_dir + '/mig_key.pub-backup')
	log.debug("Generating ssh keys: " + ' '.join(["/usr/bin/ssh-keygen", "-f", backup_dir + "/mig_key", "-q", "-N", ""]))
	keygen = Popen(["/usr/bin/ssh-keygen", "-f", backup_dir + "/mig_key", "-q", "-N", ""], stderr=PIPE, stdout=PIPE)

	if keygen.stderr.read() != '':
		print(bgcolors.RED + "Error in generating ssh key" + bgcolors.END)
		print(bgcolors.BLUE + "Please generate SSH key manually" + bgcolors.END)
		display_command(command="mkdir -pv /home/accttransfer && cd /home/accttransfer && ssh-keygen", title=False)
		display_command(help_text="Enter key name as 'mig_key'")

	while not (os.path.isfile(backup_dir + "/mig_key") and os.path.isfile(backup_dir + "/mig_key.pub")):
		print(bgcolors.RED + "Couldn't find SSH key files " + backup_dir + "/mig_key or " + backup_dir + "/mig_key.pub. Proceed only after generating SSH key" + bgcolors.END)
		display_command(prompt=True)

	# Display the SSH public key
	print(bgcolors.GREEN + "Append below SSH public key in destination servers' /root/.ssh/authorized_keys:\n" + bgcolors.END)
	with open(backup_dir + "/mig_key.pub") as f:
		print(bgcolors.YELLOW + f.read() + bgcolors.END)
	print("\n" + bgcolors.BLUE + "NOTE: The SSH key may not be displayed properly in a screen session. If adding above SSH key didn't work, please manually copy the contents of " + bgcolors.END + bgcolors.RED + backup_dir + "/mig_key.pub" + bgcolors.END)
	display_command(prompt=True)

	# Check SSH connection
	print(bgcolors.GREEN + "Checking SSH connection..." + bgcolors.END)
	out = ""
	ssh_key = backup_dir + "/mig_key"
	while out == "":
		out, err, ret_code = ssh_command(target.destserver_ip, "hostname", s_key= ssh_key)
		if out != "":
			break
		print(bgcolors.RED + "SSH connection failed: " + err + "\nPlease proceed only after adding proper firewall rules and SSH keys" + bgcolors.END)
		display_command(prompt=True)
	print(bgcolors.GREEN + "SSH connection succeeded." + bgcolors.END)

	# Run pkgacct
	print(bgcolors.GREEN  + "Running /scripts/pkgacct for " + migrate_user.user_name + bgcolors.END)
	log.debug("Running /scripts/pkgacct for " + migrate_user.user_name)
	if os.path.isdir(backup_dir + "/" + ticket_id):
		now = datetime.datetime.now()
		os.rename(backup_dir + "/" + ticket_id, backup_dir + "/" + ticket_id + "-" + str(now.isoformat()))
	os.mkdir(backup_dir + "/" + ticket_id)
	log.debug(' '.join(["/scripts/pkgacct", migrate_user.user_name, "--skiphomedir", backup_dir + "/" + ticket_id]))
	p = call(["/scripts/pkgacct", migrate_user.user_name, "--skiphomedir", backup_dir + "/" + ticket_id])
	if p != 0:
		print(bgcolors.RED + "pkgaccount failed. Please proceed only after taking backup. Run below command manually on a seperate window to create backups" + bgcolors.END)
		display_command(command="/scripts/pkgacct " + migrate_user.user_name + " --skiphomedir " + backup_dir + "/" + ticket_id)
		display_command(prompt=True)
	print(bgcolors.GREEN + "Package account completed." + bgcolors.END)
	log.debug("Package account completed.")

	# First rsync
	# mkdir /home_dir/accttransfer in destination
	cmd = ["ssh", "-i", ssh_key, "-p", SSH_PORT,"-o", "PasswordAuthentication=no", "-o", "StrictHostKeyChecking=no", target.destserver_ip, 'mkdir -p ' + backup_dir]
	out, err, exit_status = run_command(cmd)
	if err:
		for line in err.split('\n'):
			print(bgcolors.RED + line + bgcolors.END)

	print(bgcolors.GREEN + "Starting pre-sync..." + bgcolors.END)
	pre_sync = 'rsync -avP --bwlimit=3200 -e "ssh -o StrictHostKeyChecking=no -i ' + ssh_key + ' -p ' + SSH_PORT + '" ' + backup_dir + '/' + ticket_id + ' ' + target.destserver_ip + ':' + backup_dir + '/'
	log.debug("Running pre-sync: " + pre_sync)

	ret = call([pre_sync], shell=True)
	if ret != 0:
		print(bgcolors.RED + "Error in pre-sync. Please run below command in a seperate window before proceeding." + bgcolors.END)
		log.warning("Error in presync. Asking for manual presync.")
		display_command(command=pre_sync)
		display_command(prompt=True)
	else:
		print(bgcolors.GREEN + "Pre-sync finished." + bgcolors.END)
		log.debug("Pre-sync finished successfully")


	# Running restorepkg on destination
	log.debug("Running /scripts/restorepkg on destination server...")
	for pkg in os.listdir(backup_dir + '/' + ticket_id + '/'):
		if pkg.endswith(".tar.gz"):
			print(bgcolors.GREEN + "Restoring account " + pkg[7:-7] + bgcolors.END)
			log.debug("Restoring account " + pkg[7:-7])
			out, err, exit_status = restore_on_dest(target.destserver_ip, ssh_key, backup_dir + '/' + ticket_id + '/' + pkg)

			if re.search(r'HomeRoot:\s+(\S+)', out):
				migrate_user.dest_home_dir = re.search(r'HomeRoot:\s+(\S+)', out).group(1)
				migrate_user.dest_home_dir += "/" + migrate_user.user_name
				log.debug("Home directory on destination server is: " + migrate_user.dest_home_dir)

			for line in err.split('\n'):
				print(bgcolors.RED + line + bgcolors.END)

			if exit_status == 0:
				print (bgcolors.GREEN + "\nPackage restoration successful!" + bgcolors.END)
			else:
				print (bgcolors.RED + "\nPackage restoration FAILED!\nRun below command on destination server before proceeding:" + bgcolors.END)
				log.warning("/scripts/restorepkg resulted in error. Asking user to manaully run: " + "/scripts/restorepkg " + backup_dir + '/' + ticket_id + '/' + pkg)
				display_command(command="/scripts/restorepkg " + backup_dir + '/' + ticket_id + '/' + pkg)
				display_command(prompt=True)
				#sys.exit()

	if not migrate_user.dest_home_dir:
		print(bgcolors.YELLOW + "Couldn't find user home directory in destination server: " + target.dest_server + " from restorepkg output" + bgcolors.END)
		proceed = ''
		while migrate_user.dest_home_dir  == '' or proceed.lower() != 'y':
			migrate_user.dest_home_dir = raw_input('Enter user home directory in destination server: ')
			print("Home directory will be synced to " + migrate_user.dest_home_dir)
			proceed = raw_input('Proceed? [y/n]: ')

	# Run final sync of home directories
	print(bgcolors.YELLOW + "\nPlease ensure that destination directory is correct" + bgcolors.END)
	print(bgcolors.GREEN + "Syncing home directory : " + migrate_user.home_dir + " (source) to " + target.dest_server + ':' + migrate_user.dest_home_dir + " (destination)" + bgcolors.END)
	proceed = raw_input('Proceed? [y/n]: ')
	while proceed.lower() != 'y':
		migrate_user.dest_home_dir = raw_input('Enter user home directory in destination server: ').strip()
		proceed = raw_input('Proceed? [y/n]: ')

	out, err, exit_status = final_sync(target, ssh_key, migrate_user)

	if exit_status == 0:
		print(bgcolors.GREEN + "Completed syncing home directory : " + migrate_user.home_dir + bgcolors.END)
	else:
		print (bgcolors.RED + "Final sync FAILED!" + bgcolors.END)
		print(bgcolors.RED + err + bgcolors.END)
		log.warning("Final sync failed with error:\n" + str(err) + "\n Asking user for manual sync.")
		print(bgcolors.BLUE + "Run below command from source server to finish syncing of home directory:" + bgcolors.END)
		print(bgcolors.GREEN + 'rsync -avP --bwlimit=3200 -e "ssh -o StrictHostKeyChecking=no -i ' + ssh_key + ' -p ' + SSH_PORT + '" ' + migrate_user.home_dir + '/ ' + target.destserver_ip + ':' + migrate_user.dest_home_dir + '/' + bgcolors.END)
		print('\n')
		exit(1)
	
	# Print final reply for customer
	final_reply(target.dest_server)


if __name__ == '__main__':
	# Ensure that script is executed from screen session
	if not os.getenv('STY'):
		print(bgcolors.RED + "\nThe script must be executed from a screen session\n" + bgcolors.END)
		sys.exit(0)

	main()

