import urllib2, json, sys, os, time, subprocess

#to get a token, use:
#curl -u username:password -d '{"scopes":["repo"],"note":"Git Autobuilder"}' \
#    https://api.github.com/authorizations

#holds all info needed regarding a repository that needs to be autobuilt
class Repo:
	def __init__(self):
		self.user = None
		self.repo = None
		self.branch = "master"
		self.localpath = None
		self.authtoken = None
		self.etag = None

	def GetUrl(self):
		url = "https://api.github.com/repos/%s/%s/events" % (self.user, self.repo)
		if self.authtoken:
			url += "?access_token=" + self.authtoken
		return url 

	def __str__(self):
		return "%s/%s:%s" % (self.user, self.repo, self.branch)

def LoadConfig(configFile):
	repos = []
	for obj in json.loads(open(configFile).read()):
		print obj
		repo = Repo()
		repo.__dict__.update(obj)
		repos.append(repo)
	return repos

def Main(configFile):

	repos = LoadConfig(configFile)
	print repos

	#poll once per minute
	delaySeconds = 60

	# poll forever
	while True:
		for repo in repos:
			print "requesting events for repo", repo
			# don't fail on an exception.  If there is a problem, then just
			# continue on (should probably log it).
			try:
				eventMessage = RequestEvents(repo)
				if eventMessage:
					print "got message:"
					print eventMessage
					if not "AUTOBUILT" in eventMessage:
						BuildAndCommit(repo)
			except urllib2.HTTPError, e:
				print e
				raise e
		time.sleep(delaySeconds)

def BuildAndCommit(repo):
	#TODO - this assumes all tools are on the path
	#TODO - need to add checking and dealing with errors
	os.chdir(repo.localpath)
	cmd = "git reset --hard && git pull"
	print cmd
	if os.system(cmd):
		print >> sys.stderr, "couldn't sync"
		return
	cmd = "(%s) &> autobuild.log" % repo.command
	print "executing:", cmd
	if os.system(cmd):
		print >> sys.stderr, "error executing command, log in autobuild.log"
	cmd = "git add autobuild.log && git commit -am \"AUTOBUILT\" && git push"
	print cmd
	if os.system(cmd):
		print >> sys.stderr, "error committing and pushing results to git"


def RequestEvents(repo):
	print repo.GetUrl()
	req = urllib2.Request(repo.GetUrl())
	# use the etag if we have one... this lets the server know what the latest
	# event that we have seen is
	if repo.etag:
		req.add_header("If-None-Match", repo.etag)

	#try to get a response, if no new events are available, then
	#the response will be 304 which will trigger an HTTPError
	try:
		resp = urllib2.urlopen(req)
	except urllib2.HTTPError, e:
		print e.code
		if e.code == 304:
			#there are no new events
			print "no new events"
			return None
		raise e

	repo.etag = resp.info().getheader("etag")
	
	# get first push Event
	jsonData = json.loads(resp.read())
	pushEvent = None
	for event in jsonData:
		# get only push events for the branch that we care about
		if event["type"] == "PushEvent" and event["payload"]["ref"] == "refs/heads/" + repo.branch:
			pushEvent = event
			break
	else:
		return None
	#return the commit message for the most recent commit
	return pushEvent["payload"]["commits"][0]["message"]
		
if __name__ == "__main__":
	Main(sys.argv[1])
