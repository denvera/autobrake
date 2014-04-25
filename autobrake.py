#!/usb/bin/python
import argparse
import os
import re
import subprocess
from threading import Thread
from Queue import Queue

HANDBRAKE="""C:\Program Files\Handbrake\HandBrakeCLI.exe"""
HB_TITLE_REGEX="\+ title (\d+):"
DVD_DIR_REGEX=".*S(\d+)D(\d)" # Should match a season and disk number, group 0 = season, group 1 = disk

io_q = Queue()

def stream_watcher(identifier, stream):

    for line in stream:
        io_q.put((identifier, line))

    if not stream.closed:
        stream.close()

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='RIP a Series DVD')
	parser.add_argument('-s', '--sourcedir', required=True)
	parser.add_argument('-d', '--destdir', required=True)
	parser.add_argument('-b', '--basename', required=True, help='Prefix to use when naming episodes. Output filenames will be <basename>.SnnEnn.mkv')
	parser.add_argument('-n', '--epsperdisk', type=int, help='Number of episodes expected per disk')
	parser.add_argument('-m', '--minlength', type=int, help='Min title length in minutes to use when scanning (default is 15 minutes)', default=15)
	parser.add_argument('-f', '--scanfullpath', help='Scan the full path to the VIDEO_TS directory when looking for something resembling the given regex', action='store_true')
	parser.add_argument('-r', '--regex', help='DVD directory regex to use when trying to figure out Season numbers', default=DVD_DIR_REGEX)
	parser.add_argument('-v', '--verbose', help='Be verbose', action='store_true')
	
	args = parser.parse_args()
	
	regex = re.compile(args.regex)
	diskmap = {}
	
	if args.scanfullpath:
		for root, dirs, files in os.walk(args.sourcedir):
			if 'VIDEO_TS' in dirs:
				if regex.search(root) is not None:
					match = regex.search(root)
					if len(match.groups()) == 2:
						path = os.path.join(root, 'VIDEO_TS')
						groups = match.groups()
						print "Season %s Disk %s: %s" % (groups[0], groups[1], path)
						if 'Season%s' % groups[0] not in diskmap:
							diskmap['Season%s' % groups[0]] = {}
						#diskmap["S%sD%s" % (groups[0], groups[1])] = { 'path': path }
						diskmap["Season%s" % groups[0]][int(groups[1])] = { 'path': path }
			pass
	else:
		for entry in os.listdir(args.sourcedir):
			pass
	for season, sdict in diskmap.items():
		for disknum, diskdict in sdict.items():
			hb = subprocess.Popen([HANDBRAKE, '-i', diskdict['path'], '-t0', '--min-duration', str(args.minlength*60)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			stdout = Thread(target=stream_watcher, name='stdout-watcher', args=('stdout', hb.stdout))
			stdin = Thread(target=stream_watcher, name='stderr-watcher', args=('stderr', hb.stderr))
			stdout.start()
			stdin.start()
			
			stdout.join()
			stdin.join()
			
			hbtitlere = re.compile(HB_TITLE_REGEX)
			diskdict['titles'] = []
			while not io_q.empty():			
					id, line = io_q.get()								
					match = hbtitlere.search(line)
					if match:						
						if args.verbose:
							print "[%s Disk %d] Title: %s" % (season, disknum, match.groups()[0])
						if args.epsperdisk is None or len(diskdict['titles']) < args.epsperdisk:
							diskdict['titles'].append(int(match.groups()[0]))
		
	
	seasons = sorted(diskmap.keys())
	for season in seasons:
		disknums = sorted(diskmap[season].keys())
		epcount = 1
		for d in disknums:
			diskdict = diskmap[season][d]
			for t in diskdict['titles']:
				epname = "%s.S%02dE%02d.mkv" % (args.basename, seasons.index(season)+1, epcount)
				print "Ripping %s Episode %d\t[D%dT%d] -> %s" % (season, epcount, d, t, epname)
				epcount += 1
		
	print diskmap
		
	
	